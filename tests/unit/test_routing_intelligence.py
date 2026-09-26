from unittest.mock import AsyncMock, MagicMock

from src.app.intelligence.intelligence import RoutingIntelligenceLayer


def make_layer(embedding_repo=None, vector_cache_repo=None, local_llm_response=None):
    # Bypass __init__ entirely - it loads a real ~400MB GGUF model, which has
    # no place in a fast unit test.
    layer = RoutingIntelligenceLayer.__new__(RoutingIntelligenceLayer)
    layer.embedding_model_repo = embedding_repo or AsyncMock()
    layer.vector_cache_repo = vector_cache_repo or AsyncMock()
    layer.local_llm = MagicMock()
    if local_llm_response is not None:
        layer.local_llm.create_chat_completion.return_value = local_llm_response
    layer.grammar = MagicMock()
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
    layer.local_llm.create_chat_completion.assert_not_called()


async def test_classify_returns_a_plain_string_on_a_cache_miss_and_caches_it():
    embedding_repo = AsyncMock()
    embedding_repo.create_vector_embeddings.return_value = "embedding-vector"
    vector_cache_repo = AsyncMock()
    vector_cache_repo.search.return_value = {}
    layer = make_layer(
        embedding_repo, vector_cache_repo,
        local_llm_response={"choices": [{"message": {"content": "CREATIVE"}}]},
    )

    result = await layer.classify("write me a poem")

    assert result == "CREATIVE"
    vector_cache_repo.save.assert_awaited_once_with(
        "embedding-vector", "intelligence_classifier_cache", "write me a poem", "CREATIVE"
    )


async def test_classify_gives_the_local_model_enough_budget_for_multi_token_labels():
    """Regression test: max_tokens=1 truncated multi-token labels like
    "REASONING"/"CREATIVE" to their first sub-word token (e.g. "CRE"),
    which then got cached and kept being replayed."""
    embedding_repo = AsyncMock()
    embedding_repo.create_vector_embeddings.return_value = "embedding-vector"
    vector_cache_repo = AsyncMock()
    vector_cache_repo.search.return_value = {}
    layer = make_layer(
        embedding_repo, vector_cache_repo,
        local_llm_response={"choices": [{"message": {"content": "CREATIVE"}}]},
    )

    await layer.classify("write me a poem")

    _, kwargs = layer.local_llm.create_chat_completion.call_args
    assert kwargs["max_tokens"] > 1
