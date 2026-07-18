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
