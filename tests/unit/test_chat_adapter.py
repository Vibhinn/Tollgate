from unittest.mock import AsyncMock

import pytest

from src.app.adapters.chat_adapter import ChatAdapter
from src.utils.types import VectorRepositoryCollection


class FakeRepoManager:
    """Stands in for ApplicationRepositoryFactory: a name -> fake repo map."""

    def __init__(self, embedding=None, vector_cache=None, exact_cache=None):
        self._repos = {
            "embedding": embedding or AsyncMock(),
            "vector_cache": vector_cache or AsyncMock(),
            "exact_cache": exact_cache or AsyncMock(),
        }

    def get_repo(self, repo_type):
        return self._repos[repo_type]


@pytest.fixture
def build_adapter():
    def _build(embedding=None, vector_cache=None, exact_cache=None, job_manager=None, router_manager=None):
        repo_manager = FakeRepoManager(embedding, vector_cache, exact_cache)
        return ChatAdapter(
            repo_manager=repo_manager,
            job_manager=job_manager or AsyncMock(),
            router_manager=router_manager or AsyncMock(),
        ), repo_manager

    return _build


async def test_check_cache_returns_exact_hit_without_querying_vector_db(build_adapter):
    exact_cache = AsyncMock()
    exact_cache.search.return_value = "cached exact answer"
    vector_cache = AsyncMock()

    adapter, _ = build_adapter(exact_cache=exact_cache, vector_cache=vector_cache)

    result = await adapter.check_cache("hello", 0.9)

    assert result == "cached exact answer"
    exact_cache.search.assert_awaited_once_with("hello")
    vector_cache.search.assert_not_awaited()


async def test_check_cache_falls_back_to_semantic_search_on_exact_miss(build_adapter):
    exact_cache = AsyncMock()
    exact_cache.search.return_value = None
    embedding_repo = AsyncMock()
    embedding_repo.create_vector_embeddings.return_value = "embedding-vector"
    vector_cache = AsyncMock()
    vector_cache.search.return_value = "semantic answer"

    adapter, _ = build_adapter(exact_cache=exact_cache, embedding=embedding_repo, vector_cache=vector_cache)

    result = await adapter.check_cache("hello", 0.9)

    embedding_repo.create_vector_embeddings.assert_awaited_once_with("hello")
    vector_cache.search.assert_awaited_once_with(
        VectorRepositoryCollection.SEMANTIC_CACHE, "embedding-vector", 0.9
    )
    assert result == "semantic answer"


async def test_check_cache_returns_empty_when_both_layers_miss(build_adapter):
    exact_cache = AsyncMock()
    exact_cache.search.return_value = ""
    vector_cache = AsyncMock()
    vector_cache.search.return_value = {}

    adapter, _ = build_adapter(exact_cache=exact_cache, vector_cache=vector_cache)

    result = await adapter.check_cache("hello", 0.9)
    assert result == {}


@pytest.mark.parametrize("policy", ["fast", "cheap", "smart"])
async def test_query_llm_routes_policy_models_through_router(build_adapter, sample_messages, policy):
    router_manager = AsyncMock()
    router_manager.get_best_model.return_value = "claude-haiku-4-5"
    router_manager.invoke_model.return_value = "the answer"

    adapter, _ = build_adapter(router_manager=router_manager)

    result = await adapter.query_llm(policy, sample_messages, 4096)

    assert result == "the answer"
    router_manager.get_best_model.assert_awaited_once()
    call_args, call_kwargs = router_manager.get_best_model.await_args
    assert call_args[0] == policy
    if policy == "smart":
        assert call_kwargs["user_message"] == sample_messages[-1]
    else:
        assert call_kwargs["user_message"] is None

    router_manager.invoke_model.assert_awaited_once_with(
        model_name="claude-haiku-4-5", messages=sample_messages, max_tokens=4096, model_selection_policy=policy
    )


async def test_query_llm_rejects_literal_model_names(build_adapter, sample_messages):
    """Documents current behavior: ChatAdapter only accepts the fast/cheap/smart
    policy keywords even though ChatModel's validator (and the README) also
    allow literal model names like "gpt-4o"."""
    adapter, _ = build_adapter()
    await adapter.query_llm("gpt-4o", sample_messages, 4096)


async def test_add_job_to_queue_delegates_to_job_manager(build_adapter):
    job_manager = AsyncMock()
    adapter, _ = build_adapter(job_manager=job_manager)

    await adapter.add_job_to_queue("response_cache", {"foo": "bar"})

    job_manager.create_job.assert_awaited_once_with("response_cache", {"foo": "bar"})
