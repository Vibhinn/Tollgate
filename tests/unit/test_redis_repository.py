from unittest.mock import AsyncMock

import pytest

from src.cache.connection import CacheConnection
from src.cache.repository.redis_repository import RedisRepository
from src.utils.tokens import hash_token


@pytest.fixture
def redis_conn(monkeypatch):
    conn = AsyncMock()
    monkeypatch.setattr(CacheConnection, "get_connection", classmethod(lambda cls, t: conn))
    return conn


@pytest.fixture
def repo(redis_conn):
    return RedisRepository()


async def test_get_user_id_returns_the_user_id_stored_with_the_token(repo, redis_conn):
    redis_conn.get.return_value = '{"user_id": "u-42", "requirement": "chat", "user_role": "user"}'

    value = await repo.get_user_id("tg_abc")

    # only the hash of a token is stored, never the token itself
    redis_conn.get.assert_awaited_once_with(f"token:{hash_token('tg_abc')}")
    assert value == "u-42"


@pytest.mark.parametrize("stored", [None, "", "not json", '["a list"]', '{"requirement": "chat"}'])
async def test_get_user_id_treats_missing_or_malformed_tokens_as_invalid(repo, redis_conn, stored):
    redis_conn.get.return_value = stored

    assert await repo.get_user_id("tg_abc") is None


async def test_save_sets_key_value_with_expiry(repo, redis_conn):
    await repo.save(key="token:tg_abc", value="payload", timeout=3600)

    redis_conn.set.assert_awaited_once_with("token:tg_abc", "payload", ex=3600)


async def test_save_without_timeout_passes_none_expiry(repo, redis_conn):
    await repo.save(key="k", value="v", timeout=None)

    redis_conn.set.assert_awaited_once_with("k", "v", ex=None)


async def test_search_returns_connection_value(repo, redis_conn):
    redis_conn.get.return_value = "cached response"

    result = await repo.search("some message")

    redis_conn.get.assert_awaited_once_with("some message")
    assert result == "cached response"
