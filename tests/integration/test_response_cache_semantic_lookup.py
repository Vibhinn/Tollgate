"""Regression test for the semantic-cache miss path, wired to the real
QdrantRepository (only the network client mocked) rather than an adapter-level
mock. This used to crash: the cache lookup (then ChatAdapter.check_cache, now ResponseCache.lookup) called
self.vector_db_repo.search(embedding) with a single positional argument,
which silently bound to `collection` instead of `embedding` - see git history
for the original test_semantic_cache_miss_crashes_with_the_real_qdrant_repository,
which documented the crash before this was fixed.
"""
from unittest.mock import AsyncMock

import pytest

from src.cache.connection import CacheConnection
from src.cache.repository.qdrant_repository import QdrantRepository
from src.cache import ResponseCache
from src.cache.keys import CacheKeys, CacheKeyBuilder
from src.utils.types import VectorRepositoryCollection


@pytest.fixture
def qdrant_network_client(monkeypatch):
    client = AsyncMock()
    monkeypatch.setattr(CacheConnection, "get_connection", classmethod(lambda cls, t: client))
    return client


@pytest.fixture
def real_qdrant_repository(qdrant_network_client):
    return QdrantRepository()


async def test_semantic_cache_miss_queries_qdrant_with_the_real_repository(
    real_qdrant_repository, qdrant_network_client, fake_embedding
):
    exact_cache = AsyncMock()
    exact_cache.search.return_value = None
    embedding_repo = AsyncMock()
    embedding_repo.create_vector_embeddings.return_value = fake_embedding
    qdrant_network_client.query_points.return_value.points = []

    response_cache = ResponseCache(exact_cache, embedding_repo, real_qdrant_repository, AsyncMock(), CacheKeyBuilder())

    result = await response_cache.lookup(CacheKeys(exact_key="cache:exact:abc", context_hash="ctx", prompt="hello"), 0.9)

    call_kwargs = qdrant_network_client.query_points.await_args.kwargs
    assert call_kwargs["collection_name"] == VectorRepositoryCollection.SEMANTIC_CACHE
    assert call_kwargs["query"] == fake_embedding[0].tolist()
    assert call_kwargs["query_filter"].must[0].match.value == "ctx"
    assert call_kwargs["score_threshold"] == 0.9
    assert result is None
