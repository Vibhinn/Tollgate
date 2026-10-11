from unittest.mock import AsyncMock, MagicMock

import pytest

from src.app.adapters.chat_adapter import ChatAdapter
from src.app.exceptions import ModelSemanticNotFound
from src.cache.keys import CacheKeys
from src.utils.types import Message, GenerationParams, ChatRequest, LLMInvocationResult

PARAMS = GenerationParams(max_tokens=4096)
KEYS = CacheKeys(exact_key="cache:exact:abc", context_hash="ctx", prompt="hello")
LLM_RESULT = LLMInvocationResult("fresh answer", 12, 5, finish_reason="stop", model="claude-haiku-4-5")


def chat_request(**overrides) -> ChatRequest:
    fields = {"model": "cheap", "messages": [Message(role="user", content="hello")], "params": PARAMS}
    fields.update(overrides)
    return ChatRequest(**fields)


@pytest.fixture
def response_cache():
    cache = AsyncMock()
    cache.build_keys = MagicMock(return_value=KEYS)
    cache.lookup.return_value = None
    return cache


@pytest.fixture
def router_manager():
    router = AsyncMock()
    router.has_model = MagicMock(side_effect=lambda model_name: model_name == "gpt-4o")
    router.get_best_model.return_value = "claude-haiku-4-5"
    router.invoke_model.return_value = LLM_RESULT
    return router


@pytest.fixture
def adapter(response_cache, router_manager):
    return ChatAdapter(response_cache, router_manager)


async def test_complete_returns_a_cache_hit_without_calling_the_model(adapter, response_cache, router_manager):
    response_cache.lookup.return_value = "cached answer"

    result = await adapter.complete("payments:alice", chat_request(cache_match_score=0.8))

    assert (result.content, result.cached, result.model) == ("cached answer", True, "cheap")
    assert (result.input_tokens, result.output_tokens, result.finish_reason) == (0, 0, "stop")
    response_cache.build_keys.assert_called_once_with("payments:alice", chat_request(cache_match_score=0.8))
    response_cache.lookup.assert_awaited_once_with(KEYS, 0.8)
    router_manager.invoke_model.assert_not_awaited()


async def test_complete_asks_the_model_on_a_miss_and_does_not_cache_without_cache_type(adapter, response_cache):
    result = await adapter.complete("payments:alice", chat_request())

    assert result == LLM_RESULT
    assert result.cached is False
    response_cache.store.assert_not_awaited()


async def test_complete_caches_the_answer_under_the_lookup_keys(adapter, response_cache):
    await adapter.complete("payments:alice", chat_request(cache_type="exact", cache_ttl=120))

    response_cache.store.assert_awaited_once_with(KEYS, "fresh answer", "exact", 120)


@pytest.mark.parametrize("finish_reason", ["length", "content_filter"])
async def test_complete_never_caches_a_cut_off_or_filtered_answer(adapter, response_cache, router_manager, finish_reason):
    router_manager.invoke_model.return_value = LLMInvocationResult("half an answ", 12, 5, finish_reason, "gpt-4o")

    result = await adapter.complete("payments:alice", chat_request(cache_type="exact"))

    assert result.finish_reason == finish_reason
    response_cache.store.assert_not_awaited()


async def test_complete_rejects_an_unknown_model_before_any_cache_work(adapter, response_cache):
    with pytest.raises(ModelSemanticNotFound, match="not-a-model"):
        await adapter.complete("payments:alice", chat_request(model="not-a-model"))

    response_cache.build_keys.assert_not_called()
    response_cache.lookup.assert_not_awaited()


@pytest.mark.parametrize("model", ["fast", "cheap", "smart", "gpt-4o"])
def test_ensure_model_exists_accepts_policies_and_available_models(adapter, model):
    adapter.ensure_model_exists(model)


@pytest.mark.parametrize("policy", ["fast", "cheap", "smart"])
async def test_query_llm_routes_policy_models_through_router(adapter, router_manager, sample_messages, policy):
    result = await adapter.query_llm(policy, sample_messages, PARAMS)

    assert result == LLM_RESULT
    call_args, call_kwargs = router_manager.get_best_model.await_args
    assert call_args[0] == policy
    if policy == "smart":
        assert call_kwargs["user_message"] == sample_messages[-1]
    else:
        assert call_kwargs["user_message"] is None
    router_manager.invoke_model.assert_awaited_once_with(
        model_name="claude-haiku-4-5", messages=sample_messages, params=PARAMS, model_selection_policy=policy
    )


async def test_smart_routing_classifies_the_last_user_message(adapter, router_manager):
    messages = [
        Message(role="system", content="You are a tutor."),
        Message(role="user", content="prove this theorem"),
        Message(role="assistant", content="Sure, the proof"),
    ]
    params = GenerationParams(temperature=0.3)

    await adapter.query_llm("smart", messages, params)

    assert router_manager.get_best_model.await_args.kwargs["user_message"] == messages[1]
    assert router_manager.invoke_model.await_args.kwargs["params"] == params


async def test_query_llm_sends_a_named_model_straight_to_the_router(adapter, router_manager, sample_messages):
    await adapter.query_llm("gpt-4o", sample_messages, PARAMS)

    router_manager.get_best_model.assert_not_awaited()
    router_manager.invoke_model.assert_awaited_once_with(model_name="gpt-4o", messages=sample_messages, params=PARAMS)
