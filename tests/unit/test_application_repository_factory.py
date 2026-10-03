from unittest.mock import MagicMock

import pytest

from src.cache.connection import CacheConnection
from src.llm.connection import LLMConnection
from src.app.factory.repository_factory import ApplicationRepositoryFactory
from src.cache.repository.redis_repository import RedisRepository
from src.cache.repository.qdrant_repository import QdrantRepository
from src.cache.repository.redis_ranking_repository import RedisRankingRepository
from src.llm.repository.model2vec_repository import Model2VecRepository


@pytest.fixture
def factory(monkeypatch):
    monkeypatch.setattr(CacheConnection, "get_connection", classmethod(lambda cls, t: MagicMock()))
    monkeypatch.setattr(LLMConnection, "get_connection", classmethod(lambda cls, p: MagicMock()))
    return ApplicationRepositoryFactory(
        embedding_repo=Model2VecRepository(),
        redis_repo=RedisRepository(),
        vector_db_repo=QdrantRepository(),
        ranking_repo=RedisRankingRepository(),
    )


def test_embedding_repo_is_model2vec_repository(factory):
    assert isinstance(factory.get_repo("embedding"), Model2VecRepository)


def test_vector_cache_repo_is_qdrant_repository(factory):
    assert isinstance(factory.get_repo("vector_cache"), QdrantRepository)


def test_exact_cache_repo_is_redis_repository(factory):
    assert isinstance(factory.get_repo("exact_cache"), RedisRepository)


def test_ranking_repo_is_redis_ranking_repository(factory):
    assert isinstance(factory.get_repo("ranking"), RedisRankingRepository)


def test_get_repo_returns_same_instance_on_repeated_calls(factory):
    first = factory.get_repo("exact_cache")
    second = factory.get_repo("exact_cache")
    assert first is second

