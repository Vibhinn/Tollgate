"""Regression test for a real, reproducible crash on the semantic-cache miss path.

KNOWN BUG: ChatAdapter.check_cache calls
    self.vector_db_repo.search(embedding)
with a single positional argument. But VectorDBRepositoryInterface.search
(and its only implementation, QdrantRepository.search) is defined as
    search(self, collection, embedding, score_threshold=0.9)
so the lone positional argument binds to `collection`, and the required
`embedding` argument is missing. Today, any request that misses the exact
cache and falls through to the semantic cache crashes with a TypeError
instead of querying Qdrant. This test wires ChatAdapter to the real
QdrantRepository (with only the network client mocked) to prove the crash
is real, not a mocking artifact - see test_check_cache_falls_back_to_semantic_search_on_exact_miss
in test_chat_adapter.py for the adapter's intended contract, which a fix
should satisfy without breaking this file (delete/update this test once fixed).
"""
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.cache.connection import CacheConnection
from src.cache.repository.qdrant_repository import QdrantRepository
from src.app.adapters.chat_adapter import ChatAdapter


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
def real_qdrant_repository(monkeypatch):
    monkeypatch.setattr(CacheConnection, "get_connection", classmethod(lambda cls, t: MagicMock()))
    return QdrantRepository()


async def test_semantic_cache_miss_crashes_with_the_real_qdrant_repository(real_qdrant_repository):
    repo_manager = FakeRepoManager(real_qdrant_repository)
    repo_manager.get_repo("exact_cache").search.return_value = None

    adapter = ChatAdapter(repo_manager, AsyncMock(), AsyncMock())

    with pytest.raises(TypeError, match="embedding"):
        await adapter.check_cache("hello")
