import json
from unittest.mock import AsyncMock

import pytest

from src.jobs.helpers.analytics import AnalyticsJobHelper


def make_payload(model_name="gpt-4o", input_tokens=1000, output_tokens=500, latency_ms=42.0):
    payload = {
        "model_name": model_name,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "latency_ms": latency_ms,
        "timestamp": "2026-07-17T00:00:00",
    }
    return {"payload": json.dumps(payload)}


@pytest.fixture
def ranking_repo():
    return AsyncMock()


@pytest.fixture
def helper(ranking_repo):
    return AnalyticsJobHelper(ranking_repo)


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
