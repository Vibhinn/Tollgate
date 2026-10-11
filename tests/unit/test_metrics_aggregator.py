import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.jobs import MetricsAggregator
from src.utils.types import RedisAtomicCounters as Counter

COUNTERS = {
    Counter.RESPONSES_2XX: 90, Counter.RESPONSES_4XX: 8, Counter.RESPONSES_5XX: 2,
    Counter.RATE_LIMITED: 5, Counter.SHED: 1, Counter.IN_FLIGHT: 3,
    Counter.CACHE_EXACT_HITS: 20, Counter.CACHE_SEMANTIC_HITS: 10, Counter.CACHE_MISSES: 70,
    Counter.NO_MODEL_AVAILABLE: 4,
}
GPT_STATS = {"requests": 40, "errors": 2, "input_tokens": 4000, "output_tokens": 900}
HAIKU_STATS = {"requests": 0, "errors": 0, "input_tokens": 0, "output_tokens": 0}
TEAMS = {"payments": {"requests": 3}}
USERS = {"payments:alice": {"requests": 3}}
TOKENS = {"e72bb248c316": {"team": "payments", "name": "alice", "requests": 3}}


@pytest.fixture
def metrics_repo():
    repo = AsyncMock()
    repo.read_counters.return_value = dict(COUNTERS)
    repo.read_model_stats.return_value = {"gpt-4o": GPT_STATS, "claude-haiku-4-5": HAIKU_STATS}
    repo.ping.return_value = True
    repo.read_entity_stats.side_effect = lambda kind: {"team": TEAMS, "user": USERS, "token": TOKENS}[kind]
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
def aggregator(metrics_repo, ranking_repo, vector_db_repo):
    router = MagicMock()
    router.available_models.return_value = {"gpt-4o": "openai", "claude-haiku-4-5": "anthropic"}
    classifier = MagicMock(available=True)
    return MetricsAggregator(metrics_repo, ranking_repo, vector_db_repo, router, classifier)


async def build_snapshot(aggregator):
    await aggregator.refresh()
    return aggregator.snapshot


async def test_the_snapshot_reports_requests_by_status_class(aggregator):
    snapshot = await build_snapshot(aggregator)

    assert snapshot["requests"] == {"total": 100, "2xx": 90, "4xx": 8, "5xx": 2,
                                    "rate_limited": 5, "no_model_available": 4, "rejected_by_backpressure": 1,
                                    "in_flight": 3}


async def test_the_snapshot_reports_cache_hits_and_the_hit_rate(aggregator):
    snapshot = await build_snapshot(aggregator)

    assert snapshot["cache"] == {"exact_hits": 20, "semantic_hits": 10, "misses": 70, "hit_rate": 0.3}


async def test_hit_rate_is_zero_before_any_lookup(aggregator, metrics_repo):
    metrics_repo.read_counters.return_value = {counter.value: 0 for counter in Counter}

    assert (await build_snapshot(aggregator))["cache"]["hit_rate"] == 0.0


async def test_the_snapshot_reports_each_configured_model(aggregator):
    models = (await build_snapshot(aggregator))["models"]

    assert models["gpt-4o"] == {**GPT_STATS, "avg_latency_ms": 812, "available": True}
    # benched, and never measured yet
    assert models["claude-haiku-4-5"] == {**HAIKU_STATS, "avg_latency_ms": None, "available": False}


async def test_the_snapshot_reports_dependency_health(aggregator, vector_db_repo):
    aggregator.routing_intelligence.available = False
    vector_db_repo.ping.return_value = False

    assert (await build_snapshot(aggregator))["dependencies"] == {"redis": "ok", "qdrant": "down", "classifier": "degraded"}


async def test_a_redis_outage_yields_nulls_and_redis_down_instead_of_an_error(aggregator, metrics_repo):
    metrics_repo.read_counters.side_effect = ConnectionError("redis down")
    metrics_repo.read_model_stats.side_effect = ConnectionError("redis down")
    metrics_repo.ping.return_value = False

    snapshot = await build_snapshot(aggregator)

    assert snapshot["requests"] is None
    assert snapshot["cache"] is None
    assert snapshot["models"] is None
    assert snapshot["dependencies"]["redis"] == "down"
    assert snapshot["uptime_seconds"] >= 0
    assert snapshot["process"]["memory_mb"] > 0


async def test_a_hanging_health_check_counts_as_down(aggregator, vector_db_repo):
    async def hang():
        import asyncio
        await asyncio.sleep(10)
    vector_db_repo.ping.side_effect = hang
    aggregator._HEALTH_CHECK_TIMEOUT_SECONDS = 0.05

    assert (await build_snapshot(aggregator))["dependencies"]["qdrant"] == "down"


async def test_the_admin_snapshot_adds_the_breakdown_per_team_user_and_token(aggregator):
    await aggregator.refresh()

    admin = aggregator.admin_snapshot
    assert (admin["teams"], admin["users"], admin["tokens"]) == (TEAMS, USERS, TOKENS)
    # everything a normal token sees is in it too
    assert {key: admin[key] for key in aggregator.snapshot} == aggregator.snapshot
    assert "teams" not in aggregator.snapshot


async def test_there_is_no_snapshot_before_the_first_refresh(aggregator):
    assert aggregator.snapshot is None
    assert aggregator.admin_snapshot is None


async def test_start_builds_a_snapshot_right_away_and_stop_ends_the_loop(aggregator):
    await aggregator.start()
    try:
        assert aggregator.snapshot is not None
    finally:
        aggregator.stop()
    await asyncio.sleep(0)
    assert aggregator._task.cancelled()


async def test_no_model_available_is_false_while_any_configured_model_is_in_rotation(aggregator):
    # gpt-4o is available, claude-haiku-4-5 is benched
    assert (await build_snapshot(aggregator))["no_model_available"] is False


async def test_no_model_available_is_true_when_every_configured_model_is_benched(aggregator, ranking_repo):
    ranking_repo.filter_available.return_value = []

    assert (await build_snapshot(aggregator))["no_model_available"] is True


async def test_no_model_available_is_null_when_the_models_cant_be_read(aggregator, metrics_repo):
    metrics_repo.read_model_stats.side_effect = ConnectionError("redis down")

    assert (await build_snapshot(aggregator))["no_model_available"] is None
