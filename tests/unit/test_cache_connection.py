"""Regression tests for src.cache.connection.CacheConnection.

get_connection() previously had its real implementation (the third,
non-stub definition) accidentally decorated with @typing.overload. At
runtime, an @overload-decorated function's body is replaced with a dummy
that raises NotImplementedError when actually called - so get_connection()
was completely broken for every call, not just Qdrant/Redis specifically.
"""
from unittest.mock import MagicMock

import pytest

from src.cache import connection as connection_module
from src.cache.connection import CacheConnection
from src.utils.types import CacheType


def test_get_connection_returns_the_exact_redis_connection():
    CacheConnection._redis_conn = "fake-redis-conn"

    assert CacheConnection.get_connection(CacheType.EXACT) == "fake-redis-conn"


def test_get_connection_returns_the_semantic_vector_db_connection():
    CacheConnection._vector_db_conn = "fake-qdrant-conn"

    assert CacheConnection.get_connection(CacheType.SEMANTIC) == "fake-qdrant-conn"


def _redis_qdrant_config(fake_config, redis_overrides=None, qdrant_overrides=None):
    fake_config._data = {
        **fake_config._data,
        "redis": {
            "host": "localhost", "port": "6379", "password": "NOT_CONFIGURED", "tls": "false",
            **(redis_overrides or {}),
        },
        "qdrant": {
            "host": "localhost", "port": "6333", "api_key": "NOT_CONFIGURED", "https": "false",
            **(qdrant_overrides or {}),
        },
    }
    return fake_config


@pytest.fixture(autouse=True)
def reset_connections():
    original_redis, original_qdrant = CacheConnection._redis_conn, CacheConnection._vector_db_conn
    yield
    CacheConnection._redis_conn, CacheConnection._vector_db_conn = original_redis, original_qdrant


def test_initialize_builds_redis_from_configured_host_and_port(fake_config, monkeypatch):
    redis_factory = MagicMock()
    monkeypatch.setattr(connection_module.redis, "Redis", redis_factory)
    monkeypatch.setattr(connection_module, "AsyncQdrantClient", MagicMock())

    _redis_qdrant_config(fake_config, redis_overrides={"host": "my-cluster.cache.amazonaws.com", "port": "6380"})

    CacheConnection.initialize(fake_config)

    _, kwargs = redis_factory.call_args
    assert kwargs["host"] == "my-cluster.cache.amazonaws.com"
    assert kwargs["port"] == 6380


def test_initialize_passes_none_password_when_not_configured(fake_config, monkeypatch):
    redis_factory = MagicMock()
    monkeypatch.setattr(connection_module.redis, "Redis", redis_factory)
    monkeypatch.setattr(connection_module, "AsyncQdrantClient", MagicMock())

    _redis_qdrant_config(fake_config)

    CacheConnection.initialize(fake_config)

    _, kwargs = redis_factory.call_args
    assert kwargs["password"] is None


def test_initialize_passes_the_real_password_when_configured(fake_config, monkeypatch):
    redis_factory = MagicMock()
    monkeypatch.setattr(connection_module.redis, "Redis", redis_factory)
    monkeypatch.setattr(connection_module, "AsyncQdrantClient", MagicMock())

    _redis_qdrant_config(fake_config, redis_overrides={"password": "hunter2", "tls": "true"})

    CacheConnection.initialize(fake_config)

    _, kwargs = redis_factory.call_args
    assert kwargs["password"] == "hunter2"
    assert kwargs["ssl"] is True


def test_initialize_builds_qdrant_from_configured_host_api_key_and_https(fake_config, monkeypatch):
    monkeypatch.setattr(connection_module.redis, "Redis", MagicMock())
    qdrant_factory = MagicMock()
    monkeypatch.setattr(connection_module, "AsyncQdrantClient", qdrant_factory)

    _redis_qdrant_config(fake_config, qdrant_overrides={
        "host": "xyz.cloud.qdrant.io", "port": "6334", "api_key": "real-api-key", "https": "true",
    })

    CacheConnection.initialize(fake_config)

    _, kwargs = qdrant_factory.call_args
    assert kwargs["host"] == "xyz.cloud.qdrant.io"
    assert kwargs["port"] == 6334
    assert kwargs["api_key"] == "real-api-key"
    assert kwargs["https"] is True


def test_initialize_passes_none_api_key_when_qdrant_not_configured(fake_config, monkeypatch):
    monkeypatch.setattr(connection_module.redis, "Redis", MagicMock())
    qdrant_factory = MagicMock()
    monkeypatch.setattr(connection_module, "AsyncQdrantClient", qdrant_factory)

    _redis_qdrant_config(fake_config)

    CacheConnection.initialize(fake_config)

    _, kwargs = qdrant_factory.call_args
    assert kwargs["api_key"] is None
