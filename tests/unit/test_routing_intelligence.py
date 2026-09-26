import asyncio
from unittest.mock import AsyncMock, MagicMock

from src.app.intelligence.intelligence import RoutingIntelligenceLayer


def make_classify_response(content: str):
    response = MagicMock()
    response.choices = [MagicMock(message=MagicMock(content=content))]
    return response


def make_layer(embedding_repo=None, vector_cache_repo=None, classify_response=None):
    # Bypass __init__ entirely - it spawns a real llama-server subprocess and
    # blocks until it's ready, which has no place in a fast unit test.
    layer = RoutingIntelligenceLayer.__new__(RoutingIntelligenceLayer)
    layer.embedding_model_repo = embedding_repo or AsyncMock()
    layer.vector_cache_repo = vector_cache_repo or AsyncMock()
    layer.client = AsyncMock()
    if classify_response is not None:
        layer.client.chat.completions.create.return_value = make_classify_response(classify_response)
    return layer


async def test_classify_unwraps_a_cache_hit_to_the_plain_category_string():
    """Regression test: QdrantRepository.search() wraps a hit as
    {"response": <value>} - classify() used to return that whole dict
    instead of the category string, crashing every downstream consumer
    (resolve_smart_model) that expects a plain string."""
    embedding_repo = AsyncMock()
    embedding_repo.create_vector_embeddings.return_value = "embedding-vector"
    vector_cache_repo = AsyncMock()
    vector_cache_repo.search.return_value = {"response": "REASONING"}
    layer = make_layer(embedding_repo, vector_cache_repo)

    result = await layer.classify("solve this equation")

    assert result == "REASONING"
    layer.client.chat.completions.create.assert_not_called()


async def test_classify_returns_a_plain_string_on_a_cache_miss_and_caches_it():
    embedding_repo = AsyncMock()
    embedding_repo.create_vector_embeddings.return_value = "embedding-vector"
    vector_cache_repo = AsyncMock()
    vector_cache_repo.search.return_value = {}
    layer = make_layer(embedding_repo, vector_cache_repo, classify_response="CREATIVE")

    result = await layer.classify("write me a poem")

    assert result == "CREATIVE"
    vector_cache_repo.save.assert_awaited_once_with(
        "embedding-vector", "intelligence_classifier_cache", "write me a poem", "CREATIVE"
    )


async def test_classify_sends_the_grammar_as_an_extension_field():
    """llama-server's OpenAI-compatible endpoint accepts `grammar` as a
    non-standard extension field via extra_body - not a typed SDK param."""
    embedding_repo = AsyncMock()
    embedding_repo.create_vector_embeddings.return_value = "embedding-vector"
    vector_cache_repo = AsyncMock()
    vector_cache_repo.search.return_value = {}
    layer = make_layer(embedding_repo, vector_cache_repo, classify_response="SIMPLE")

    await layer.classify("what is the capital of Japan?")

    _, kwargs = layer.client.chat.completions.create.call_args
    assert kwargs["extra_body"] == {"grammar": 'root ::= "SIMPLE" | "CODE" | "REASONING" | "CREATIVE"'}
    assert kwargs["max_tokens"] == 10


async def test_classify_does_not_serialize_concurrent_cache_misses():
    """The old in-process Llama object needed a lock to avoid crashing under
    concurrent calls. That's llama-server's job now (a separate process with
    its own slot-based concurrent request handling) - classify() itself must
    not reintroduce any artificial serialization on this side."""
    embedding_repo = AsyncMock()
    embedding_repo.create_vector_embeddings.return_value = "embedding-vector"
    vector_cache_repo = AsyncMock()
    vector_cache_repo.search.return_value = {}
    layer = make_layer(embedding_repo, vector_cache_repo)

    concurrent_calls = 0
    max_concurrent = 0

    async def fake_create(**kwargs):
        nonlocal concurrent_calls, max_concurrent
        concurrent_calls += 1
        max_concurrent = max(max_concurrent, concurrent_calls)
        await asyncio.sleep(0.05)
        concurrent_calls -= 1
        return make_classify_response("SIMPLE")

    layer.client.chat.completions.create.side_effect = fake_create

    await asyncio.gather(*(layer.classify(f"query {i}") for i in range(5)))

    assert max_concurrent == 5
