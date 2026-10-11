import json
from unittest.mock import AsyncMock

import pytest

from src.jobs.helpers.analytics import AnalyticsHelper


def make_payload(model_name="gpt-4o", input_tokens=1000, output_tokens=500, latency_ms=42.0, succeeded=True):
    payload = {
        "model_name": model_name,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "latency_ms": latency_ms,
        "timestamp": "2026-07-17T00:00:00",
        "succeeded": succeeded,
    }
    return {"payload": json.dumps(payload)}


@pytest.fixture
def ranking_repo():
    return AsyncMock()


@pytest.fixture
def metrics_repo():
    return AsyncMock()


@pytest.fixture
def helper(ranking_repo, metrics_repo):
    return AnalyticsHelper(ranking_repo, metrics_repo)


async def test_first_observation_seeds_latency_ema_with_raw_value(helper, ranking_repo):
    ranking_repo.get_score.return_value = None

    await helper.execute(make_payload(model_name="gpt-4o", latency_ms=42.0))

    ranking_repo.update_score.assert_awaited_once_with("model:ranking:latency", "gpt-4o", pytest.approx(42.0))


async def test_subsequent_observation_blends_latency_with_previous_ema(helper, ranking_repo):
    ranking_repo.get_score.return_value = 100.0

    await helper.execute(make_payload(model_name="gpt-4o", latency_ms=50.0))

    expected_latency_ema = 0.1 * 50.0 + 0.9 * 100.0
    ranking_repo.update_score.assert_awaited_once_with(
        "model:ranking:latency", "gpt-4o", pytest.approx(expected_latency_ema)
    )


async def test_execute_only_updates_latency_ranking(helper, ranking_repo):
    ranking_repo.get_score.return_value = None

    await helper.execute(make_payload())

    assert ranking_repo.update_score.await_count == 1
    updated_keys = {call.args[0] for call in ranking_repo.update_score.await_args_list}
    assert updated_keys == {"model:ranking:latency"}


async def test_a_successful_call_adds_to_the_model_request_and_token_totals(helper, ranking_repo, metrics_repo):
    ranking_repo.get_score.return_value = None

    await helper.execute(make_payload(model_name="gpt-4o", input_tokens=1000, output_tokens=500))

    metrics_repo.record_model_call.assert_awaited_once_with("gpt-4o", 1000, 500)
    metrics_repo.record_model_error.assert_not_awaited()


async def test_a_failed_call_only_counts_an_error_and_leaves_latency_alone(helper, ranking_repo, metrics_repo):
    await helper.execute(make_payload(model_name="gpt-4o", succeeded=False))

    metrics_repo.record_model_error.assert_awaited_once_with("gpt-4o")
    metrics_repo.record_model_call.assert_not_awaited()
    ranking_repo.update_score.assert_not_awaited()


async def test_a_job_queued_before_the_succeeded_field_counts_as_a_success(helper, ranking_repo, metrics_repo):
    ranking_repo.get_score.return_value = None
    payload = json.loads(make_payload()["payload"])
    del payload["succeeded"]

    await helper.execute({"payload": json.dumps(payload)})

    metrics_repo.record_model_call.assert_awaited_once()
