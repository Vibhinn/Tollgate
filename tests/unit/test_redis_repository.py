from unittest.mock import AsyncMock

import pytest

from src.cache.connection import CacheConnection
from src.cache.repository.redis_repository import RedisRepository


@pytest.fixture
def redis_conn(monkeypatch):
    conn = AsyncMock()
    monkeypatch.setattr(CacheConnection, "get_connection", classmethod(lambda cls, t: conn))
    return conn


@pytest.fixture
def repo(redis_conn):
    return RedisRepository()


async def test_check_token_validity_true_when_token_present(repo, redis_conn):
    redis_conn.get.return_value = json_value = '{"requirement": "chat", "user_role": "user"}'

    is_valid = await repo.check_token_validity("tg_abc")

    redis_conn.get.assert_awaited_once_with("token:tg_abc")
    assert is_valid is True


async def test_check_token_validity_false_when_token_absent(repo, redis_conn):
    redis_conn.get.return_value = None

    is_valid = await repo.check_token_validity("tg_missing")

    assert is_valid is False


async def test_get_user_id_returns_raw_stored_value(repo, redis_conn):
    redis_conn.get.return_value = '{"requirement": "chat", "user_role": "user"}'

    value = await repo.get_user_id("tg_abc")

    redis_conn.get.assert_awaited_once_with("token:tg_abc")
    assert value == '{"requirement": "chat", "user_role": "user"}'


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
