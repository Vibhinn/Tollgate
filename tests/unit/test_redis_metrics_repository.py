"""Against fakeredis, so the real INCR / HINCRBY / MGET / pipeline behaviour is exercised."""
import pytest
from fakeredis import FakeAsyncRedis

from src.cache.connection import CacheConnection
from src.cache.repository.redis_metrics_repository import RedisMetricsRepository
from src.utils.types import RedisAtomicCounters


@pytest.fixture
def repo(monkeypatch):
    redis = FakeAsyncRedis(decode_responses=True)
    monkeypatch.setattr(CacheConnection, "get_connection", classmethod(lambda cls, t: redis))
    return RedisMetricsRepository()


async def test_counters_start_at_zero_and_count_up(repo):
    await repo.increment(RedisAtomicCounters.RESPONSES_2XX)
    await repo.increment(RedisAtomicCounters.RESPONSES_2XX)
    await repo.increment(RedisAtomicCounters.CACHE_MISSES)

    counters = await repo.read_counters()

    assert counters[RedisAtomicCounters.RESPONSES_2XX] == 2
    assert counters[RedisAtomicCounters.CACHE_MISSES] == 1
    assert counters[RedisAtomicCounters.RESPONSES_5XX] == 0
    assert set(counters) == {counter.value for counter in RedisAtomicCounters}


async def test_model_stats_add_up_calls_tokens_and_errors(repo):
    await repo.record_model_call("gpt-4o", input_tokens=100, output_tokens=20)
    await repo.record_model_call("gpt-4o", input_tokens=50, output_tokens=10)
    await repo.record_model_error("gpt-4o")

    stats = await repo.read_model_stats(["gpt-4o", "never-used"])

    assert stats["gpt-4o"] == {"requests": 2, "errors": 1, "input_tokens": 150, "output_tokens": 30}
    assert stats["never-used"] == {"requests": 0, "errors": 0, "input_tokens": 0, "output_tokens": 0}


async def test_reading_stats_for_no_models_returns_nothing(repo):
    assert await repo.read_model_stats([]) == {}


async def test_ping_reports_whether_redis_answers(repo, monkeypatch):
    assert await repo.ping() is True

    async def down():
        raise ConnectionError("redis down")
    monkeypatch.setattr(repo.cache_conn, "ping", down)

    assert await repo.ping() is False
