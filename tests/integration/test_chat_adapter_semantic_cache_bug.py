"""Regression test for the semantic-cache miss path, wired to the real
QdrantRepository (only the network client mocked) rather than an adapter-level
mock. This used to crash: ChatAdapter.check_cache called
self.vector_db_repo.search(embedding) with a single positional argument,
which silently bound to `collection` instead of `embedding` - see git history
for the original test_semantic_cache_miss_crashes_with_the_real_qdrant_repository,
which documented the crash before this was fixed.
"""
from unittest.mock import AsyncMock

import pytest

from src.cache.connection import CacheConnection
from src.cache.repository.qdrant_repository import QdrantRepository
from src.app.adapters.chat_adapter import ChatAdapter
from src.utils.types import VectorRepositoryCollection


class FakeRepoManager:
    def __init__(self, vector_cache):
        self._repos = {
            "embedding": AsyncMock(),
            "vector_cache": vector_cache,
            "exact_cache": AsyncMock(),
        }

    def get_repo(self, repo_type):
        return self._repos[repo_type]


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
    repo_manager = FakeRepoManager(real_qdrant_repository)
    repo_manager.get_repo("exact_cache").search.return_value = None
    repo_manager.get_repo("embedding").create_vector_embeddings.return_value = fake_embedding
    qdrant_network_client.query_points.return_value.points = []

    adapter = ChatAdapter(repo_manager, AsyncMock(), AsyncMock())

    result = await adapter.check_cache("hello", 0.9)

    qdrant_network_client.query_points.assert_awaited_once_with(
        collection_name=VectorRepositoryCollection.SEMANTIC_CACHE,
        query=fake_embedding[0].tolist(),
        limit=1,
        score_threshold=0.9,
    )
    assert result == {}
