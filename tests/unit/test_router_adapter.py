from unittest.mock import AsyncMock

import pytest

from src.app.adapters.router_adapter import RouterAdapter


@pytest.fixture
def adapter():
    job_queue_manager = AsyncMock()
    ranking_repo = AsyncMock()
    intelligence = AsyncMock()
    return RouterAdapter(job_queue_manager, ranking_repo, intelligence), job_queue_manager, ranking_repo, intelligence


async def test_get_best_model_maps_cheap_to_cost_ranking(adapter):
    router_adapter, _, ranking_repo, _ = adapter
    ranking_repo.get_top.return_value = "gpt-4o-mini"

    result = await router_adapter.get_best_model("cheap")

    ranking_repo.get_top.assert_awaited_once_with("model:ranking:cost")
    assert result == "gpt-4o-mini"


async def test_get_best_model_maps_fast_to_latency_ranking(adapter):
    router_adapter, _, ranking_repo, _ = adapter
    ranking_repo.get_top.return_value = "gemini-2.0-flash"

    result = await router_adapter.get_best_model("fast")

    ranking_repo.get_top.assert_awaited_once_with("model:ranking:latency")
    assert result == "gemini-2.0-flash"


async def test_get_best_model_returns_none_for_unmapped_requirement(adapter):
    router_adapter, _, ranking_repo, _ = adapter

    result = await router_adapter.get_best_model("smart")

    assert result is None
    ranking_repo.get_top.assert_not_awaited()


async def test_identify_model_intelligently_delegates_to_intelligence_layer(adapter):
    router_adapter, _, _, intelligence = adapter
    intelligence.classify.return_value = "REASONING"

    result = await router_adapter.identify_model_intelligently("solve this equation")

    intelligence.classify.assert_awaited_once_with("solve this equation")
    assert result == "REASONING"


async def test_add_job_to_queue_delegates_to_job_queue_manager(adapter):
    router_adapter, job_queue_manager, _, _ = adapter

    await router_adapter.add_job_to_queue("ANALYTICS", {"model_name": "gpt-4o"})

    job_queue_manager.create_job.assert_awaited_once_with("ANALYTICS", {"model_name": "gpt-4o"})
