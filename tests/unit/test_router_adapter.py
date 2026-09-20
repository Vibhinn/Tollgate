from unittest.mock import AsyncMock, MagicMock

import pytest

from src.app.adapters.router_adapter import RouterAdapter


@pytest.fixture
def adapter():
    job_queue_manager = AsyncMock()
    ranking_repo = AsyncMock()
    intelligence = AsyncMock()
    llm_repo_factory = MagicMock()
    return (
        RouterAdapter(job_queue_manager, ranking_repo, intelligence, llm_repo_factory),
        job_queue_manager,
        ranking_repo,
        intelligence,
        llm_repo_factory,
    )


async def test_get_best_model_maps_cheap_to_cheapest_configured_model_by_pricing(adapter, monkeypatch):
    router_adapter, _, ranking_repo, _, llm_repo_factory = adapter
    # gpt-4o-mini ((0.15+0.60)/2 = 0.375) is cheaper than claude-opus-4-6 ((15+75)/2 = 45)
    llm_repo_factory.get_repo = lambda provider: object() if provider == "openai" else None

    result = await router_adapter.get_best_model("cheap")

    assert result == "gpt-4o-mini"
    ranking_repo.get_top.assert_not_awaited()


async def test_get_best_model_maps_fast_to_latency_ranking(adapter):
    router_adapter, _, ranking_repo, _, _ = adapter
    ranking_repo.get_top.return_value = "gemini-2.0-flash"

    result = await router_adapter.get_best_model("fast")

    ranking_repo.get_top.assert_awaited_once_with("model:ranking:latency")
    assert result == "gemini-2.0-flash"


async def test_get_best_model_returns_none_for_unmapped_requirement(adapter):
    router_adapter, _, ranking_repo, _, _ = adapter

    result = await router_adapter.get_best_model("smart")

    assert result is None
    ranking_repo.get_top.assert_not_awaited()


async def test_identify_model_intelligently_delegates_to_intelligence_layer(adapter):
    router_adapter, _, _, intelligence, _ = adapter
    intelligence.classify.return_value = "REASONING"

    result = await router_adapter.identify_model_intelligently("solve this equation")

    intelligence.classify.assert_awaited_once_with("solve this equation")
    assert result == "REASONING"


async def test_add_job_to_queue_delegates_to_job_queue_manager(adapter):
    router_adapter, job_queue_manager, _, _, _ = adapter

    await router_adapter.add_job_to_queue("analytics", {"model_name": "gpt-4o"})

    job_queue_manager.create_job.assert_awaited_once_with("analytics", {"model_name": "gpt-4o"})
