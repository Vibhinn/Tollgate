from unittest.mock import AsyncMock, MagicMock

import pytest

from src.app.adapters import MetricsAdapter
from src.utils.types import RedisAtomicCounters as Counter

COUNTERS = {
    Counter.RESPONSES_2XX: 90, Counter.RESPONSES_4XX: 8, Counter.RESPONSES_5XX: 2,
    Counter.RATE_LIMITED: 5, Counter.SHED: 1, Counter.IN_FLIGHT: 3,
    Counter.CACHE_EXACT_HITS: 20, Counter.CACHE_SEMANTIC_HITS: 10, Counter.CACHE_MISSES: 70,
}
GPT_STATS = {"requests": 40, "errors": 2, "input_tokens": 4000, "output_tokens": 900}
HAIKU_STATS = {"requests": 0, "errors": 0, "input_tokens": 0, "output_tokens": 0}


@pytest.fixture
def metrics_repo():
    repo = AsyncMock()
    repo.read_counters.return_value = dict(COUNTERS)
    repo.read_model_stats.return_value = {"gpt-4o": GPT_STATS, "claude-haiku-4-5": HAIKU_STATS}
    repo.ping.return_value = True
    return repo


@pytest.fixture
def ranking_repo():
    repo = AsyncMock()
    repo.filter_available.return_value = ["gpt-4o"]           # haiku is benched
    repo.get_score.side_effect = lambda key, name: 812.4 if name == "gpt-4o" else None
    return repo


@pytest.fixture
def vector_db_repo():
    repo = AsyncMock()
    repo.ping.return_value = True
    return repo


@pytest.fixture
def adapter(metrics_repo, ranking_repo, vector_db_repo):
    router = MagicMock()
    router.available_models.return_value = {"gpt-4o": "openai", "claude-haiku-4-5": "anthropic"}
    classifier = MagicMock(available=True)
    return MetricsAdapter(metrics_repo, ranking_repo, vector_db_repo, router, classifier)


async def test_snapshot_reports_requests_by_status_class(adapter):
    snapshot = await adapter.snapshot()

    assert snapshot["requests"] == {"total": 100, "2xx": 90, "4xx": 8, "5xx": 2,
                                    "rate_limited": 5, "shed": 1, "in_flight": 3}


async def test_snapshot_reports_cache_hits_and_the_hit_rate(adapter):
    snapshot = await adapter.snapshot()

    assert snapshot["cache"] == {"exact_hits": 20, "semantic_hits": 10, "misses": 70, "hit_rate": 0.3}


async def test_hit_rate_is_zero_before_any_lookup(adapter, metrics_repo):
    metrics_repo.read_counters.return_value = {counter.value: 0 for counter in Counter}

    assert (await adapter.snapshot())["cache"]["hit_rate"] == 0.0


async def test_snapshot_reports_each_configured_model(adapter):
    models = (await adapter.snapshot())["models"]

    assert models["gpt-4o"] == {**GPT_STATS, "avg_latency_ms": 812, "available": True}
    # benched, and never measured yet
    assert models["claude-haiku-4-5"] == {**HAIKU_STATS, "avg_latency_ms": None, "available": False}


async def test_snapshot_reports_dependency_health(adapter, vector_db_repo):
    adapter.routing_intelligence.available = False
    vector_db_repo.ping.return_value = False

    assert (await adapter.snapshot())["dependencies"] == {"redis": "ok", "qdrant": "down", "classifier": "degraded"}


async def test_a_redis_outage_yields_nulls_and_redis_down_instead_of_an_error(adapter, metrics_repo):
    metrics_repo.read_counters.side_effect = ConnectionError("redis down")
    metrics_repo.read_model_stats.side_effect = ConnectionError("redis down")
    metrics_repo.ping.return_value = False

    snapshot = await adapter.snapshot()

    assert snapshot["requests"] is None
    assert snapshot["cache"] is None
    assert snapshot["models"] is None
    assert snapshot["dependencies"]["redis"] == "down"
    assert snapshot["uptime_seconds"] >= 0
    assert snapshot["process"]["memory_mb"] > 0


async def test_a_hanging_health_check_counts_as_down(adapter, vector_db_repo):
    async def hang():
        import asyncio
        await asyncio.sleep(10)
    vector_db_repo.ping.side_effect = hang
    adapter._HEALTH_CHECK_TIMEOUT_SECONDS = 0.05

    assert (await adapter.snapshot())["dependencies"]["qdrant"] == "down"
