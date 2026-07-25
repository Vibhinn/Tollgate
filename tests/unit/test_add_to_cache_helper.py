import json
from unittest.mock import AsyncMock

import pytest

from src.jobs.helpers.add_to_cache import AddToCache


@pytest.fixture
def helper():
    exact_cache = AsyncMock()
    embedding_repo = AsyncMock()
    vector_cache = AsyncMock()
    return AddToCache(exact_cache, embedding_repo, vector_cache), exact_cache, embedding_repo, vector_cache


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
    adapter, exact_cache, embedding_repo, vector_cache = helper
    embedding_repo.create_vector_embeddings.return_value = "embedding-vector"

    await adapter.execute(make_payload(cache_type="semantic"))

    embedding_repo.create_vector_embeddings.assert_awaited_once_with("hello")
    vector_cache.save.assert_awaited_once_with(
        embedding="embedding-vector", user_message="hello", model_response="hi there"
    )
    exact_cache.save.assert_not_awaited()


async def test_unrecognized_cache_type_is_a_silent_no_op(helper):
    adapter, exact_cache, embedding_repo, vector_cache = helper

    await adapter.execute(make_payload(cache_type="UNKNOWN"))

    exact_cache.save.assert_not_awaited()
    embedding_repo.create_vector_embeddings.assert_not_awaited()
    vector_cache.save.assert_not_awaited()
