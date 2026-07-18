import json
from unittest.mock import AsyncMock

import pytest

from src.jobs.helpers.analytics import AnalyticsJobHelper
from src.router.core.pricing import PRICING_TABLE


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


def expected_cost(model, input_tokens, output_tokens):
    rates = PRICING_TABLE[model]
    return (input_tokens * rates["input"] + output_tokens * rates["output"]) / 1_000_000


async def test_first_observation_seeds_ema_with_raw_value(helper, ranking_repo):
    ranking_repo.get_score.return_value = None

    await helper.execute(make_payload(model_name="gpt-4o", input_tokens=1000, output_tokens=500, latency_ms=42.0))

    cost = expected_cost("gpt-4o", 1000, 500)
    ranking_repo.update_score.assert_any_call("model:ranking:cost", "gpt-4o", pytest.approx(cost))
    ranking_repo.update_score.assert_any_call("model:ranking:latency", "gpt-4o", pytest.approx(42.0))


async def test_subsequent_observation_blends_with_previous_ema(helper, ranking_repo):
    # get_score is called once for the cost key, once for the latency key -
    # return different priors depending on which key was queried.
    async def get_score(key, member):
        return {"model:ranking:cost": 2.0, "model:ranking:latency": 100.0}[key]

    ranking_repo.get_score.side_effect = get_score

    await helper.execute(make_payload(model_name="gpt-4o", input_tokens=1000, output_tokens=500, latency_ms=50.0))

    new_cost = expected_cost("gpt-4o", 1000, 500)
    expected_cost_ema = 0.1 * new_cost + 0.9 * 2.0
    expected_latency_ema = 0.1 * 50.0 + 0.9 * 100.0

    ranking_repo.update_score.assert_any_call("model:ranking:cost", "gpt-4o", pytest.approx(expected_cost_ema))
    ranking_repo.update_score.assert_any_call("model:ranking:latency", "gpt-4o", pytest.approx(expected_latency_ema))


async def test_unpriced_model_costs_zero(helper, ranking_repo):
    ranking_repo.get_score.return_value = None

    await helper.execute(make_payload(model_name="totally-unknown-model", input_tokens=1000, output_tokens=500))

    ranking_repo.update_score.assert_any_call("model:ranking:cost", "totally-unknown-model", 0.0)


async def test_execute_updates_both_cost_and_latency_rankings(helper, ranking_repo):
    ranking_repo.get_score.return_value = None

    await helper.execute(make_payload())

    assert ranking_repo.update_score.await_count == 2
    updated_keys = {call.args[0] for call in ranking_repo.update_score.await_args_list}
    assert updated_keys == {"model:ranking:cost", "model:ranking:latency"}
