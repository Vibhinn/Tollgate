from unittest.mock import AsyncMock

import pytest

from src.cache.connection import CacheConnection
from src.cache.repository.redis_ranking_repository import RedisRankingRepository


@pytest.fixture
def redis_conn(monkeypatch):
    conn = AsyncMock()
    monkeypatch.setattr(CacheConnection, "get_connection", classmethod(lambda cls, t: conn))
    return conn


@pytest.fixture
def repo(redis_conn):
    return RedisRankingRepository()


async def test_update_score_writes_to_sorted_set(repo, redis_conn):
    await repo.update_score("model:ranking:cost", "gpt-4o", 1.23)

    redis_conn.zadd.assert_awaited_once_with("model:ranking:cost", {"gpt-4o": 1.23})


async def test_get_score_returns_member_score(repo, redis_conn):
    redis_conn.zscore.return_value = 4.56

    result = await repo.get_score("model:ranking:cost", "gpt-4o")

    redis_conn.zscore.assert_awaited_once_with("model:ranking:cost", "gpt-4o")
    assert result == 4.56


async def test_get_score_returns_none_for_unknown_member(repo, redis_conn):
    redis_conn.zscore.return_value = None

    result = await repo.get_score("model:ranking:cost", "unknown-model")

    assert result is None


async def test_get_top_returns_lowest_ranked_member(repo, redis_conn):
    redis_conn.zrange.return_value = ["gpt-4o-mini"]

    result = await repo.get_top("model:ranking:cost")

    redis_conn.zrange.assert_awaited_once_with("model:ranking:cost", 0, 0)
    assert result == "gpt-4o-mini"


async def test_get_top_returns_none_when_ranking_is_empty(repo, redis_conn):
    redis_conn.zrange.return_value = []

    result = await repo.get_top("model:ranking:cost")

    assert result is None


async def test_get_top_available_returns_first_candidate_that_is_not_unavailable(repo, redis_conn):
    redis_conn.zrange.return_value = ["gpt-4o", "gpt-4o-mini", "claude-haiku-4-5"]
    redis_conn.mget.return_value = ["1", None, None]

    result = await repo.get_top_available("model:ranking:latency")

    redis_conn.zrange.assert_awaited_once_with("model:ranking:latency", 0, -1)
    assert result == "gpt-4o-mini"


async def test_get_top_available_skips_ranked_models_that_are_no_longer_candidates(repo, redis_conn):
    """Regression test: the ranking in Redis outlives the routing table, so a renamed model
    (e.g. gemini-3.5-flash) or a removed self-hosted alias kept being picked by "fast" and 404'd."""
    redis_conn.zrange.return_value = ["gemini-3.5-flash", "ollama-removed", "gemini-3.8-flash"]
    redis_conn.mget.return_value = [None]

    result = await repo.get_top_available("model:ranking:latency", ["gemini-3.8-flash", "gemini-3.5-flash-lite"])

    redis_conn.mget.assert_awaited_once_with(["model:unavailable:gemini-3.8-flash"])
    assert result == "gemini-3.8-flash"


async def test_get_top_available_returns_none_when_every_candidate_is_unavailable(repo, redis_conn):
    redis_conn.zrange.return_value = ["gpt-4o", "gpt-4o-mini"]
    redis_conn.mget.return_value = ["1", "1"]

    result = await repo.get_top_available("model:ranking:latency")

    assert result is None


async def test_get_top_available_returns_none_when_ranking_is_empty(repo, redis_conn):
    redis_conn.zrange.return_value = []

    result = await repo.get_top_available("model:ranking:latency")

    assert result is None
    redis_conn.mget.assert_not_awaited()


async def test_mark_unavailable_sets_a_ttl_keyed_flag(repo, redis_conn):
    await repo.mark_unavailable("gpt-4o", 600)

    redis_conn.set.assert_awaited_once_with("model:unavailable:gpt-4o", "1", ex=600)


async def test_filter_available_checks_every_model_in_one_round_trip_and_keeps_order(repo, redis_conn):
    redis_conn.mget.return_value = [None, "1", None]

    result = await repo.filter_available(["gpt-4o", "gpt-4o-mini", "claude-haiku-4-5"])

    redis_conn.mget.assert_awaited_once_with(
        ["model:unavailable:gpt-4o", "model:unavailable:gpt-4o-mini", "model:unavailable:claude-haiku-4-5"]
    )
    assert result == ["gpt-4o", "claude-haiku-4-5"]


async def test_filter_available_skips_redis_for_an_empty_list(repo, redis_conn):
    assert await repo.filter_available([]) == []
    redis_conn.mget.assert_not_awaited()


async def test_seconds_until_available_is_the_soonest_bench_to_expire(monkeypatch):
    from fakeredis import FakeAsyncRedis
    from src.cache.connection import CacheConnection
    from src.cache.repository.redis_ranking_repository import RedisRankingRepository
    redis = FakeAsyncRedis(decode_responses=True)
    monkeypatch.setattr(CacheConnection, "get_connection", classmethod(lambda cls, t: redis))
    repo = RedisRankingRepository()

    assert await repo.seconds_until_available(["gpt-4o", "gemini-3.8-flash"]) is None   # nothing benched

    await repo.mark_unavailable("gpt-4o", 600)
    await repo.mark_unavailable("gemini-3.8-flash", 30)

    assert await repo.seconds_until_available(["gpt-4o", "gemini-3.8-flash"]) == 30
    assert await repo.seconds_until_available(["gpt-4o"]) == 600
    assert await repo.seconds_until_available([]) is None
