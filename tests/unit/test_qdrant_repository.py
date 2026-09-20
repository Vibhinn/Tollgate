from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.cache.connection import CacheConnection
from src.cache.repository.qdrant_repository import QdrantRepository


@pytest.fixture
def qdrant_client(monkeypatch):
    client = AsyncMock()
    monkeypatch.setattr(CacheConnection, "get_connection", classmethod(lambda cls, t: client))
    return client


@pytest.fixture
def repo(qdrant_client):
    return QdrantRepository()


async def test_save_upserts_point_with_embedding_and_payload(repo, qdrant_client, fake_embedding):
    await repo.save(
        embedding=fake_embedding,
        collection="semantic_cache",
        user_message="hi there",
        model_response="hello!",
    )

    qdrant_client.upsert.assert_awaited_once()
    call_kwargs = qdrant_client.upsert.call_args.kwargs
    assert call_kwargs["collection_name"] == "semantic_cache"
    point = call_kwargs["points"][0]
    assert point.vector == fake_embedding[0].tolist()
    assert point.payload == {"user_message": "hi there", "model_response": "hello!"}


async def test_search_returns_top_match_response(repo, qdrant_client, fake_embedding):
    match = SimpleNamespace(payload={"model_response": "the cached answer"})
    qdrant_client.query_points.return_value = SimpleNamespace(points=[match])

    result = await repo.search(collection="semantic_cache", embedding=fake_embedding, score_threshold=0.9)

    qdrant_client.query_points.assert_awaited_once_with(
        collection_name="semantic_cache",
        query=fake_embedding[0].tolist(),
        limit=1,
        score_threshold=0.9,
    )
    assert result == {"response": "the cached answer"}


async def test_search_returns_empty_dict_when_no_points_matched(repo, qdrant_client, fake_embedding):
    qdrant_client.query_points.return_value = SimpleNamespace(points=[])

    result = await repo.search(collection="semantic_cache", embedding=fake_embedding)

    assert result == {}


async def test_search_uses_default_score_threshold(repo, qdrant_client, fake_embedding):
    qdrant_client.query_points.return_value = SimpleNamespace(points=[])

    await repo.search(collection="semantic_cache", embedding=fake_embedding)

    assert qdrant_client.query_points.call_args.kwargs["score_threshold"] == 0.9
