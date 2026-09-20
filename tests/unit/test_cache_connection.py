"""Regression tests for src.cache.connection.CacheConnection.

get_connection() previously had its real implementation (the third,
non-stub definition) accidentally decorated with @typing.overload. At
runtime, an @overload-decorated function's body is replaced with a dummy
that raises NotImplementedError when actually called - so get_connection()
was completely broken for every call, not just Qdrant/Redis specifically.
"""
from src.cache.connection import CacheConnection
from src.utils.types import CacheType


def test_get_connection_returns_the_exact_redis_connection():
    CacheConnection._redis_conn = "fake-redis-conn"

    assert CacheConnection.get_connection(CacheType.EXACT) == "fake-redis-conn"


def test_get_connection_returns_the_semantic_vector_db_connection():
    CacheConnection._vector_db_conn = "fake-qdrant-conn"

    assert CacheConnection.get_connection(CacheType.SEMANTIC) == "fake-qdrant-conn"
