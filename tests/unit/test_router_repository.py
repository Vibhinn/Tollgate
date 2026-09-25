from unittest.mock import AsyncMock

import pytest

from src.app.exceptions import (
    ModelSemanticNotFound, CreditExhaustion, RateLimitedFromModelProvider, BadRequestToModel,
)
from src.router.router import RouterRepository
from src.utils.types import LLMInvocationResult, Message


def make_model_response(text="the answer", input_tokens=10, output_tokens=20):
    return LLMInvocationResult(content=text, input_tokens=input_tokens, output_tokens=output_tokens)


@pytest.fixture
def llm_repo_factory():
    factory = AsyncMock()
    llm_repo = AsyncMock()
    llm_repo.invoke.return_value = make_model_response()
    factory.get_repo = lambda repository_name: llm_repo if repository_name == "openai" else None
    return factory, llm_repo


@pytest.fixture
def router_adapter():
    return AsyncMock()


@pytest.fixture
def router_repository(llm_repo_factory, router_adapter, fake_config):
    factory, _ = llm_repo_factory
    return RouterRepository(factory, router_adapter, fake_config)


async def test_invoke_model_returns_llm_text_and_records_analytics(router_repository, router_adapter, llm_repo_factory):
    _, llm_repo = llm_repo_factory
    messages = [Message(role="user", content="hello there")]

    result = await router_repository.invoke_model("gpt-4o", messages, 4096)

    assert result == "the answer"
    llm_repo.invoke.assert_awaited_once_with("hello there", "gpt-4o", 4096)


async def test_invoke_model_sends_the_real_provider_model_id_not_the_routing_alias(
    router_repository, router_adapter, llm_repo_factory
):
    """Regression test: invoke_model used to send model_name (the routing
    table key the client requests by, e.g. "claude-haiku-4-5") straight to
    the provider instead of model_entry["model"] (the real identifier the
    provider expects, e.g. the dated "claude-haiku-4-5-20251001"). This
    matters even more for self-hosted models, where the alias and the real
    model name the local server has loaded are routinely different strings."""
    _, llm_repo = llm_repo_factory
    router_repository.routing_table = {
        **router_repository.routing_table,
        "ollama-llama3": {"provider": "openai", "model": "llama3"},
    }
    messages = [Message(role="user", content="hello there")]

    await router_repository.invoke_model("ollama-llama3", messages, 4096)

    llm_repo.invoke.assert_awaited_once_with("hello there", "llama3", 4096)

    router_adapter.add_job_to_queue.assert_awaited_once()
    call_args, call_kwargs = router_adapter.add_job_to_queue.await_args
    assert call_kwargs["collection_name"] == "analytics"
    analytics_payload = call_kwargs["data"]
    # analytics/blocklisting stay keyed by the routing alias, not the real
    # provider model id - only the actual provider call needs the real one
    assert analytics_payload["model_name"] == "ollama-llama3"
    assert analytics_payload["input_tokens"] == 10
    assert analytics_payload["output_tokens"] == 20
    assert analytics_payload["latency_ms"] >= 0


async def test_invoke_model_returns_empty_string_when_provider_not_configured(router_repository, router_adapter):
    messages = [Message(role="user", content="hello")]

    with pytest.raises(ModelSemanticNotFound):
        await router_repository.invoke_model("claude-sonnet-4-6", messages, 4096)

    router_adapter.add_job_to_queue.assert_not_awaited()


async def test_invoke_model_raises_cleanly_when_model_is_not_in_routing_table(router_repository, router_adapter):
    """Regression test: model_name resolved by get_best_model (e.g. an empty
    ranking sorted set on a cold start, or a classifier label with no routing
    entry) used to crash with AttributeError instead of a handled 404-style
    exception."""
    messages = [Message(role="user", content="hello")]

    with pytest.raises(ModelSemanticNotFound):
        await router_repository.invoke_model("this-model-does-not-exist", messages, 4096)

    router_adapter.add_job_to_queue.assert_not_awaited()


@pytest.mark.parametrize("requirement", ["fast", "cheap"])
async def test_get_best_model_delegates_ranking_requirements_to_adapter(router_repository, router_adapter, requirement):
    router_adapter.get_best_model.return_value = "gemini-2.0-flash"

    result = await router_repository.get_best_model(requirement)

    router_adapter.get_best_model.assert_awaited_once_with(requirement)
    assert result == "gemini-2.0-flash"


async def test_get_best_model_smart_uses_intelligence_layer_with_message_content(router_repository, router_adapter):
    router_adapter.identify_model_intelligently.return_value = "claude-opus-4-6"
    user_message = Message(role="user", content="write me a poem")

    result = await router_repository.get_best_model("smart", user_message=user_message)

    router_adapter.identify_model_intelligently.assert_awaited_once_with("write me a poem")
    assert result == "claude-opus-4-6"


async def test_get_best_model_falls_back_to_configured_default(router_repository, router_adapter, fake_config):
    result = await router_repository.get_best_model("unrecognized-policy")

    assert result == fake_config.get_config("gateway", "default_model")
    router_adapter.get_best_model.assert_not_awaited()
    router_adapter.identify_model_intelligently.assert_not_awaited()


async def test_invoke_model_blocklists_and_does_not_retry_an_explicit_model_request(
    router_repository, router_adapter, llm_repo_factory
):
    """A client that names a model directly (requirement=None) gets the real
    error back instead of a silent substitution - but the model still gets
    taken out of rotation for everyone else's auto-routed requests."""
    _, llm_repo = llm_repo_factory
    llm_repo.invoke.side_effect = CreditExhaustion("no credits left")
    messages = [Message(role="user", content="hello")]

    with pytest.raises(CreditExhaustion):
        await router_repository.invoke_model("gpt-4o", messages, 4096)

    router_adapter.mark_model_unavailable.assert_awaited_once_with("gpt-4o", 600)
    router_adapter.get_best_model.assert_not_awaited()
    router_adapter.add_job_to_queue.assert_not_awaited()


async def test_invoke_model_falls_back_to_next_best_model_for_auto_routed_requests(
    router_repository, router_adapter, llm_repo_factory
):
    _, llm_repo = llm_repo_factory
    llm_repo.invoke.side_effect = [CreditExhaustion("no credits left"), make_model_response("fallback answer")]
    router_adapter.get_best_model.return_value = "gpt-4o-mini"
    messages = [Message(role="user", content="hello")]

    result = await router_repository.invoke_model("gpt-4o", messages, 4096, model_selection_policy="cheap")

    assert result == "fallback answer"
    router_adapter.mark_model_unavailable.assert_awaited_once_with("gpt-4o", 600)
    router_adapter.get_best_model.assert_awaited_once_with("cheap")
    router_adapter.add_job_to_queue.assert_awaited_once()


async def test_invoke_model_raises_when_fallback_resolves_to_the_same_dead_model(
    router_repository, router_adapter, llm_repo_factory
):
    _, llm_repo = llm_repo_factory
    llm_repo.invoke.side_effect = CreditExhaustion("no credits left")
    router_adapter.get_best_model.return_value = "gpt-4o"  # nothing else available
    messages = [Message(role="user", content="hello")]

    with pytest.raises(CreditExhaustion):
        await router_repository.invoke_model("gpt-4o", messages, 4096, model_selection_policy="cheap")

    router_adapter.mark_model_unavailable.assert_awaited_once_with("gpt-4o", 600)


async def test_invoke_model_raises_when_no_fallback_is_available(
    router_repository, router_adapter, llm_repo_factory
):
    _, llm_repo = llm_repo_factory
    llm_repo.invoke.side_effect = CreditExhaustion("no credits left")
    router_adapter.get_best_model.return_value = None
    messages = [Message(role="user", content="hello")]

    with pytest.raises(CreditExhaustion):
        await router_repository.invoke_model("gpt-4o", messages, 4096, model_selection_policy="cheap")


@pytest.mark.parametrize("exception_cls, expected_ttl", [
    (CreditExhaustion, 600),
    (RateLimitedFromModelProvider, 30),
])
async def test_invoke_model_uses_a_shorter_ttl_for_transient_failures(
    router_repository, router_adapter, llm_repo_factory, exception_cls, expected_ttl
):
    _, llm_repo = llm_repo_factory
    llm_repo.invoke.side_effect = exception_cls("boom")
    messages = [Message(role="user", content="hello")]

    with pytest.raises(exception_cls):
        await router_repository.invoke_model("gpt-4o", messages, 4096)

    router_adapter.mark_model_unavailable.assert_awaited_once_with("gpt-4o", expected_ttl)


async def test_invoke_model_does_not_blocklist_on_request_specific_errors(
    router_repository, router_adapter, llm_repo_factory
):
    """BadRequestToModel reflects the request content, not provider health -
    it shouldn't take the model out of rotation for other requests."""
    _, llm_repo = llm_repo_factory
    llm_repo.invoke.side_effect = BadRequestToModel("malformed request")
    messages = [Message(role="user", content="hello")]

    with pytest.raises(BadRequestToModel):
        await router_repository.invoke_model("gpt-4o", messages, 4096, model_selection_policy="cheap")

    router_adapter.mark_model_unavailable.assert_not_awaited()
    router_adapter.get_best_model.assert_not_awaited()
