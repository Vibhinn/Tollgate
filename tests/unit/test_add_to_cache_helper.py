import json
from unittest.mock import AsyncMock

import numpy
import pytest

from src.cache.connection import CacheConnection
from src.cache.repository.qdrant_repository import QdrantRepository
from src.jobs.helpers.add_to_cache import AddToCache
from src.utils.types import VectorRepositoryCollection


@pytest.fixture
def helper(monkeypatch):
    exact_cache = AsyncMock()
    embedding_repo = AsyncMock()
    # Real QdrantRepository, not AsyncMock, for vector_cache - a mock doesn't
    # enforce the real save() signature, which is exactly how a missing
    # required argument (collection) went undetected here before: the old
    # test asserted the mock was called with whatever args the buggy code
    # happened to pass, which is tautological, not a real check.
    qdrant_client = AsyncMock()
    monkeypatch.setattr(CacheConnection, "get_connection", classmethod(lambda cls, t: qdrant_client))
    vector_cache = QdrantRepository()
    return AddToCache(exact_cache, embedding_repo, vector_cache), exact_cache, embedding_repo, qdrant_client


def make_payload(**overrides):
    payload = {
        "cache_type": "exact",
        "user_message": "hello",
        "model_response": "hi there",
        "timeout": 3600,
    }
    payload.update(overrides)
    return {"payload": json.dumps(payload)}


async def test_missing_payload_key_raises_value_error(helper):
    adapter, *_ = helper
    with pytest.raises(ValueError, match="Missing 'payload'"):
        await adapter.execute({})


async def test_exact_cache_type_saves_directly_without_embedding(helper):
    adapter, exact_cache, embedding_repo, vector_cache = helper

    await adapter.execute(make_payload(cache_type="exact"))

    exact_cache.save.assert_awaited_once_with(key="hello", value="hi there", timeout=3600)
    embedding_repo.create_vector_embeddings.assert_not_awaited()
    vector_cache.save.assert_not_awaited()


async def test_semantic_cache_type_embeds_then_saves_to_vector_db(helper):
    adapter, exact_cache, embedding_repo, qdrant_client = helper
    embedding = numpy.array([[0.1, 0.2, 0.3]])
    embedding_repo.create_vector_embeddings.return_value = embedding

    await adapter.execute(make_payload(cache_type="semantic"))

    embedding_repo.create_vector_embeddings.assert_awaited_once_with("hello")
    # Asserting on the real QdrantRepository's underlying client call (not a
    # bare AsyncMock standing in for vector_cache) is what actually enforces
    # the real save() signature - this is the exact check that would have
    # caught the missing 'collection' argument bug, since QdrantRepository
    # would have raised a TypeError before ever reaching this point.
    qdrant_client.upsert.assert_awaited_once()
    _, call_kwargs = qdrant_client.upsert.call_args
    assert call_kwargs["collection_name"] == VectorRepositoryCollection.SEMANTIC_CACHE
    point = call_kwargs["points"][0]
    assert point.payload == {"user_message": "hello", "model_response": "hi there"}
    exact_cache.save.assert_not_awaited()


async def test_unrecognized_cache_type_is_a_silent_no_op(helper):
    adapter, exact_cache, embedding_repo, qdrant_client = helper

    await adapter.execute(make_payload(cache_type="UNKNOWN"))

    exact_cache.save.assert_not_awaited()
    embedding_repo.create_vector_embeddings.assert_not_awaited()
    qdrant_client.upsert.assert_not_awaited()
