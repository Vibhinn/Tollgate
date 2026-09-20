from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.app.exceptions import ModelSemanticNotFound
from src.router.router import RouterRepository
from src.utils.types import Message


def make_model_response(text="the answer", input_tokens=10, output_tokens=20):
    return SimpleNamespace(
        usage=SimpleNamespace(input_tokens=input_tokens, output_tokens=output_tokens),
        content=[SimpleNamespace(text=text)],
    )


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

    result = await router_repository.invoke_model("gpt-4o", messages)

    assert result == "the answer"
    llm_repo.invoke.assert_awaited_once_with("hello there", "gpt-4o")

    router_adapter.add_job_to_queue.assert_awaited_once()
    call_args, call_kwargs = router_adapter.add_job_to_queue.await_args
    assert call_kwargs["collection_name"] == "analytics"
    analytics_payload = call_kwargs["data"]
    assert analytics_payload["model_name"] == "gpt-4o"
    assert analytics_payload["input_tokens"] == 10
    assert analytics_payload["output_tokens"] == 20
    assert analytics_payload["latency_ms"] >= 0


async def test_invoke_model_returns_empty_string_when_provider_not_configured(router_repository, router_adapter):
    messages = [Message(role="user", content="hello")]

    with pytest.raises(ModelSemanticNotFound):
        await router_repository.invoke_model("claude-sonnet-4-6", messages)

    router_adapter.add_job_to_queue.assert_not_awaited()


async def test_invoke_model_raises_cleanly_when_model_is_not_in_routing_table(router_repository, router_adapter):
    """Regression test: model_name resolved by get_best_model (e.g. an empty
    ranking sorted set on a cold start, or a classifier label with no routing
    entry) used to crash with AttributeError instead of a handled 404-style
    exception."""
    messages = [Message(role="user", content="hello")]

    with pytest.raises(ModelSemanticNotFound):
        await router_repository.invoke_model("this-model-does-not-exist", messages)

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
