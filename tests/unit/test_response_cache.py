from unittest.mock import AsyncMock

import pytest

from src.cache import ResponseCache
from src.cache.keys import CacheKeys, CacheKeyBuilder
from src.utils.types import VectorRepositoryCollection, Message, GenerationParams, ChatRequest, RedisAtomicCounters

KEYS = CacheKeys(exact_key="cache:exact:abc", context_hash="ctx", prompt="hello")


@pytest.fixture
def exact_cache():
    cache = AsyncMock()
    cache.search.return_value = None
    return cache


@pytest.fixture
def embedding_repo():
    repo = AsyncMock()
    repo.create_vector_embeddings.return_value = "embedding-vector"
    return repo


@pytest.fixture
def vector_cache():
    cache = AsyncMock()
    cache.search.return_value = None
    return cache


@pytest.fixture
def job_manager():
    return AsyncMock()


@pytest.fixture
def metrics_repo():
    return AsyncMock()


@pytest.fixture
def response_cache(exact_cache, embedding_repo, vector_cache, job_manager, metrics_repo):
    return ResponseCache(exact_cache, embedding_repo, vector_cache, job_manager, CacheKeyBuilder(), metrics_repo)


def test_build_keys_covers_the_user_model_params_and_conversation(response_cache):
    chat_request = ChatRequest(model="cheap", messages=[Message(role="user", content="hi")],
                               params=GenerationParams(temperature=0.2))

    keys = response_cache.build_keys("payments:alice", chat_request)

    assert keys == CacheKeyBuilder().build_cache_keys("payments:alice", "cheap", GenerationParams(temperature=0.2),
                                                      chat_request.messages)
    assert keys.prompt == "hi"


async def test_lookup_returns_an_exact_hit_without_querying_the_vector_db(response_cache, exact_cache, vector_cache):
    exact_cache.search.return_value = "cached exact answer"

    assert await response_cache.lookup(KEYS, 0.9) == "cached exact answer"
    exact_cache.search.assert_awaited_once_with("cache:exact:abc")
    vector_cache.search.assert_not_awaited()


async def test_lookup_falls_back_to_semantic_search_on_an_exact_miss(response_cache, embedding_repo, vector_cache):
    vector_cache.search.return_value = "semantic answer"

    assert await response_cache.lookup(KEYS, 0.9) == "semantic answer"
    embedding_repo.create_vector_embeddings.assert_awaited_once_with("hello")
    vector_cache.search.assert_awaited_once_with(
        VectorRepositoryCollection.SEMANTIC_CACHE, "embedding-vector", 0.9, context_hash="ctx"
    )


async def test_lookup_returns_none_when_both_layers_miss(response_cache):
    assert await response_cache.lookup(KEYS, 0.9) is None


async def test_lookup_treats_a_cache_outage_as_a_miss(response_cache, exact_cache):
    exact_cache.search.side_effect = ConnectionError("redis down")

    assert await response_cache.lookup(KEYS, 0.9) is None


async def test_store_queues_a_cache_write_with_the_lookup_keys(response_cache, job_manager):
    await response_cache.store(KEYS, "the answer", "semantic", 120)

    job_manager.create_job.assert_awaited_once_with("response_cache", {
        "cache_type": "semantic",
        "exact_key": "cache:exact:abc",
        "context_hash": "ctx",
        "prompt": "hello",
        "model_response": "the answer",
        "timeout": 120,
    })


async def test_store_swallows_a_queue_outage_so_the_answer_still_reaches_the_client(response_cache, job_manager, capsys):
    job_manager.create_job.side_effect = ConnectionError("redis down")

    await response_cache.store(KEYS, "the answer", "exact", 120)  # must not raise

    assert "could not queue the cache write" in capsys.readouterr().err


@pytest.mark.parametrize("exact, semantic, expected_counter", [
    ("exact answer", None, RedisAtomicCounters.CACHE_EXACT_HITS),
    (None, "semantic answer", RedisAtomicCounters.CACHE_SEMANTIC_HITS),
    (None, None, RedisAtomicCounters.CACHE_MISSES),
])
async def test_lookup_counts_exact_hits_semantic_hits_and_misses(
    response_cache, exact_cache, vector_cache, metrics_repo, exact, semantic, expected_counter
):
    exact_cache.search.return_value = exact
    vector_cache.search.return_value = semantic

    await response_cache.lookup(KEYS, 0.9)

    metrics_repo.increment.assert_awaited_once_with(expected_counter)


async def test_a_metrics_outage_does_not_lose_a_cache_hit(response_cache, exact_cache, metrics_repo):
    exact_cache.search.return_value = "cached exact answer"
    metrics_repo.increment.side_effect = ConnectionError("redis down")

    assert await response_cache.lookup(KEYS, 0.9) == "cached exact answer"
