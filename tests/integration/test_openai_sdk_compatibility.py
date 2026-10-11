"""The official OpenAI Python client, pointed at Tollgate, must work by changing only base_url and api_key.

Everything from the auth middleware through the router runs for real. Only the edges are faked:
the token lookup, the caches, the job queue and the provider SDK call."""
from unittest.mock import AsyncMock

import httpx
import openai
import pytest
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError

import build.build
from build.build import Builder
from src.app.adapters import ChatAdapter, ModelsAdapter
from src.app.api.chat import chat_api_router
from src.app.api.models import models_api_router
from src.app.api.middleware import auth as auth_module, AuthenticationMiddleware
from src.app.exceptions import CreditExhaustion
from src.app.exceptions.handlers import status_handler, validation_error_handler, unexpected_error_handler
from src.app.injector.dependency_container import DependencyContainer
from src.app.injector.inject import get_chat_adapter, get_models_adapter
from src.app.ports import LLMRepositoryInterface
from src.cache import RedisRepository, ResponseCache
from src.cache.keys import CacheKeyBuilder
from src.router.router import RouterRepository
from src.utils.types import LLMInvocationResult
from tests.conftest import FakeConfig

VALID_TOKEN = "tg_valid"


class FakeProvider(LLMRepositoryInterface):
    def __init__(self):
        self.calls = []
        self.error: Exception | None = None

    async def invoke(self, messages, model_name, params):
        self.calls.append((messages, model_name, params))
        if self.error:
            raise self.error
        return LLMInvocationResult("Paris.", input_tokens=14, output_tokens=2, finish_reason="stop")


class FakeProviderFactory:
    def __init__(self, provider):
        self.provider = provider

    def get_repo(self, provider_name):
        return self.provider if provider_name == "openai" else None


@pytest.fixture
def provider():
    return FakeProvider()


@pytest.fixture
def exact_cache():
    cache = AsyncMock()
    cache.search.return_value = None
    return cache


@pytest.fixture
def job_queue():
    return AsyncMock()


@pytest.fixture
def app(monkeypatch, provider, exact_cache, job_queue):
    token_store = AsyncMock()
    token_store.get_user_id.side_effect = lambda token: "payments:alice" if token == VALID_TOKEN else None
    middleware_container = DependencyContainer()
    middleware_container.register(RedisRepository, lambda: token_store)
    monkeypatch.setattr(auth_module, "container", middleware_container)

    router_adapter = AsyncMock()
    router_adapter.get_best_model.return_value = "gpt-4o-mini"
    router = RouterRepository(FakeProviderFactory(provider), router_adapter, FakeConfig())
    semantic_cache = AsyncMock()
    semantic_cache.search.return_value = None
    response_cache = ResponseCache(exact_cache, AsyncMock(), semantic_cache, job_queue, CacheKeyBuilder(), AsyncMock())
    chat_adapter = ChatAdapter(response_cache, router)

    app = FastAPI()
    app.include_router(chat_api_router)
    app.include_router(models_api_router)
    app.add_middleware(AuthenticationMiddleware)
    app.dependency_overrides[get_chat_adapter] = lambda: chat_adapter
    app.dependency_overrides[get_models_adapter] = lambda: ModelsAdapter(router)

    # the same error handlers the real Builder installs
    monkeypatch.setattr(build.build, "Config", FakeConfig)
    builder = Builder(app)
    for exception_class, error_spec in builder.exception_map.items():
        app.add_exception_handler(exception_class, status_handler(error_spec))
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.add_exception_handler(Exception, unexpected_error_handler)
    return app


@pytest.fixture
def client_for(app):
    def _client(api_key=VALID_TOKEN):
        return openai.AsyncOpenAI(
            base_url="http://tollgate.test/v1",
            api_key=api_key,
            max_retries=0,
            # raise_app_exceptions=False: get the 500 a real server would send, instead of the re-raised bug
            http_client=httpx.AsyncClient(transport=httpx.ASGITransport(app=app, raise_app_exceptions=False)),
        )
    return _client


async def test_chat_completions_create_works_unchanged(client_for, provider):
    completion = await client_for().chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "system", "content": "Be brief."}, {"role": "user", "content": "Capital of France?"}],
        temperature=0.2,
        max_tokens=50,
        stop=["\n\n"],
    )

    assert completion.object == "chat.completion"
    assert completion.model == "gpt-4o"
    assert completion.choices[0].message.role == "assistant"
    assert completion.choices[0].message.content == "Paris."
    assert completion.choices[0].finish_reason == "stop"
    assert (completion.usage.prompt_tokens, completion.usage.completion_tokens, completion.usage.total_tokens) == (14, 2, 16)

    _, model_name, params = provider.calls[0]
    assert model_name == "gpt-4o"
    assert (params.max_tokens, params.temperature, params.stop) == (50, 0.2, ["\n\n"])


async def test_a_policy_reports_the_model_that_actually_answered(client_for):
    completion = await client_for().chat.completions.create(
        model="cheap", messages=[{"role": "user", "content": "hi"}],
    )

    assert completion.model == "gpt-4o-mini"


async def test_tollgate_options_travel_in_extra_body_and_cache_status_in_a_header(client_for, job_queue):
    raw = await client_for().chat.completions.with_raw_response.create(
        model="gpt-4o", messages=[{"role": "user", "content": "hi"}], extra_body={"cache_type": "exact"},
    )

    assert raw.headers["X-Tollgate-Cache"] == "miss"
    assert raw.parse().choices[0].message.content == "Paris."
    job_queue.create_job.assert_awaited_once()


async def test_a_cache_hit_is_still_a_valid_completion(client_for, exact_cache, provider):
    exact_cache.search.return_value = "Paris, from cache."

    raw = await client_for().chat.completions.with_raw_response.create(
        model="gpt-4o", messages=[{"role": "user", "content": "Capital of France?"}],
    )

    assert raw.headers["X-Tollgate-Cache"] == "hit"
    assert raw.parse().choices[0].message.content == "Paris, from cache."
    assert provider.calls == []


async def test_models_list_works(client_for):
    models = await client_for().models.list()

    ids = [model.id for model in models.data]
    assert ids[:3] == ["fast", "cheap", "smart"]
    assert "gpt-4o" in ids
    # only OpenAI is configured in this test, so no Anthropic or Gemini models are offered
    assert not any(model_id.startswith(("claude", "gemini")) for model_id in ids)


async def test_a_bad_tollgate_token_raises_authentication_error(client_for):
    with pytest.raises(openai.AuthenticationError) as exc_info:
        await client_for(api_key="tg_wrong").chat.completions.create(
            model="gpt-4o", messages=[{"role": "user", "content": "hi"}],
        )

    assert exc_info.value.code == "invalid_api_key"


@pytest.mark.parametrize("model", ["gpt-9", "claude-sonnet-4-6"])
async def test_a_model_that_cannot_be_served_raises_not_found_before_any_cache_work(client_for, exact_cache, model):
    """gpt-9 doesn't exist; claude-sonnet-4-6 exists, but only OpenAI is configured in this test."""
    with pytest.raises(openai.NotFoundError) as exc_info:
        await client_for().chat.completions.create(model=model, messages=[{"role": "user", "content": "hi"}])

    assert exc_info.value.code == "model_not_found"
    exact_cache.search.assert_not_awaited()


async def test_an_unsupported_feature_raises_bad_request(client_for):
    with pytest.raises(openai.BadRequestError, match="stream=true is not supported yet"):
        await client_for().chat.completions.create(
            model="gpt-4o", messages=[{"role": "user", "content": "hi"}], stream=True,
        )


async def test_a_dead_provider_key_is_a_gateway_error_not_an_auth_error(client_for, provider):
    """The client's own token is fine, so it must not see AuthenticationError."""
    provider.error = CreditExhaustion("credit balance is too low")

    with pytest.raises(openai.InternalServerError) as exc_info:
        await client_for().chat.completions.create(model="gpt-4o", messages=[{"role": "user", "content": "hi"}])

    assert exc_info.value.status_code == 502
    assert exc_info.value.code == "upstream_credit_exhausted"


async def test_x_cache_ttl_travels_as_an_extra_header(client_for, job_queue):
    await client_for().chat.completions.create(
        model="gpt-4o", messages=[{"role": "user", "content": "hi"}],
        extra_body={"cache_type": "exact"}, extra_headers={"X-Cache-TTL": "120"},
    )

    _, job_data = job_queue.create_job.await_args.args
    assert job_data["timeout"] == 120


async def test_an_invalid_x_cache_ttl_raises_bad_request(client_for):
    with pytest.raises(openai.BadRequestError) as exc_info:
        await client_for().chat.completions.create(
            model="gpt-4o", messages=[{"role": "user", "content": "hi"}], extra_headers={"X-Cache-TTL": "abc"},
        )

    assert exc_info.value.param == "X-Cache-TTL"


async def test_the_answer_is_returned_even_when_the_cache_write_fails(client_for, job_queue):
    job_queue.create_job.side_effect = ConnectionError("redis down")

    completion = await client_for().chat.completions.create(
        model="gpt-4o", messages=[{"role": "user", "content": "Capital of France?"}], extra_body={"cache_type": "exact"},
    )

    assert completion.choices[0].message.content == "Paris."
    job_queue.create_job.assert_awaited_once()


async def test_an_unexpected_bug_raises_internal_server_error_with_an_openai_body(client_for, provider):
    provider.error = KeyError("something internal")

    with pytest.raises(openai.InternalServerError) as exc_info:
        await client_for().chat.completions.create(model="gpt-4o", messages=[{"role": "user", "content": "hi"}])

    assert exc_info.value.status_code == 500
    assert exc_info.value.code == "internal_error"
    assert "something internal" not in str(exc_info.value)
