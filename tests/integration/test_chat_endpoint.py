"""The controller only translates HTTP to an adapter call and back. What happens in between
(cache, routing) is covered by the adapter and ResponseCache tests."""
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.testclient import TestClient

from src.app.api.chat import chat_api_router
from src.app.exceptions import ModelSemanticNotFound
from src.app.exceptions.handlers import ErrorSpec, status_handler, validation_error_handler
from src.app.injector.inject import get_chat_adapter
from src.utils.types import LLMInvocationResult, GenerationParams, ChatRequest, Message

LLM_RESULT = LLMInvocationResult("fresh llm reply", input_tokens=12, output_tokens=5, finish_reason="stop",
                                 model="claude-haiku-4-5")


@pytest.fixture
def chat_adapter():
    adapter = AsyncMock()
    adapter.complete.return_value = LLM_RESULT
    return adapter


def build_app(chat_adapter) -> FastAPI:
    app = FastAPI()
    app.include_router(chat_api_router)
    app.add_exception_handler(ModelSemanticNotFound,
                              status_handler(ErrorSpec(404, "invalid_request_error", "model_not_found")))
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.dependency_overrides[get_chat_adapter] = lambda: chat_adapter
    return app


@pytest.fixture
def client(chat_adapter):
    return TestClient(build_app(chat_adapter))


def chat_body(**overrides):
    body = {
        "model": "cheap",
        "messages": [{"role": "user", "content": "hello there"}],
    }
    body.update(overrides)
    return body


def sent_request(chat_adapter) -> ChatRequest:
    return chat_adapter.complete.await_args.kwargs["chat_request"]


def test_a_completion_is_returned_in_openai_format(client):
    response = client.post("/v1/chat/completions", json=chat_body())

    assert response.status_code == 200
    assert response.headers["X-Tollgate-Cache"] == "miss"
    body = response.json()
    assert body["id"].startswith("chatcmpl-")
    assert body["object"] == "chat.completion"
    assert isinstance(body["created"], int)
    # the model that answered, not the "cheap" policy that was asked for
    assert body["model"] == "claude-haiku-4-5"
    assert body["choices"] == [{
        "index": 0, "message": {"role": "assistant", "content": "fresh llm reply"}, "finish_reason": "stop",
    }]
    assert body["usage"] == {"prompt_tokens": 12, "completion_tokens": 5, "total_tokens": 17}


def test_a_cache_hit_is_marked_in_the_header(client, chat_adapter):
    chat_adapter.complete.return_value = LLMInvocationResult("cached reply", 0, 0, model="cheap", cached=True)

    response = client.post("/v1/chat/completions", json=chat_body())

    assert response.headers["X-Tollgate-Cache"] == "hit"
    assert response.json()["usage"] == {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}


def test_the_request_reaches_the_adapter_as_a_chat_request(client, chat_adapter):
    messages = [
        {"role": "system", "content": "Reply in French."},
        {"role": "user", "content": "hi"},
        {"role": "assistant", "content": "bonjour"},
        {"role": "user", "content": "how are you?"},
    ]

    client.post("/v1/chat/completions", json=chat_body(
        messages=messages, temperature=0.2, top_p=0.9, stop="END", max_completion_tokens=64,
        cache_type="semantic", cache_match_score=0.8,
    ))

    assert sent_request(chat_adapter) == ChatRequest(
        model="cheap",
        messages=[Message(**message) for message in messages],
        params=GenerationParams(max_tokens=64, temperature=0.2, top_p=0.9, stop=["END"]),
        cache_type="semantic",
        cache_match_score=0.8,
        cache_ttl=3600,
    )


def test_x_cache_ttl_header_sets_the_cache_ttl(client, chat_adapter):
    client.post("/v1/chat/completions", json=chat_body(cache_type="exact"), headers={"X-Cache-TTL": "120"})

    assert sent_request(chat_adapter).cache_ttl == 120


@pytest.mark.parametrize("ttl", ["abc", "0", "-5"])
def test_an_invalid_x_cache_ttl_is_a_400_naming_the_header(client, chat_adapter, ttl):
    """It used to crash with a 500 (abc) or fail later inside the cache worker (0, -5)."""
    response = client.post("/v1/chat/completions", json=chat_body(cache_type="exact"), headers={"X-Cache-TTL": ttl})

    assert response.status_code == 400
    assert response.json()["error"]["param"] == "X-Cache-TTL"
    chat_adapter.complete.assert_not_awaited()


def test_the_user_set_by_auth_reaches_the_adapter(chat_adapter):
    app = build_app(chat_adapter)

    @app.middleware("http")
    async def fake_auth(request, call_next):
        request.scope.setdefault("state", {})["user_id"] = "payments:alice"
        return await call_next(request)

    TestClient(app).post("/v1/chat/completions", json=chat_body())

    assert chat_adapter.complete.await_args.kwargs["user_id"] == "payments:alice"


def test_model_not_found_is_an_openai_404(client, chat_adapter):
    chat_adapter.complete.side_effect = ModelSemanticNotFound("The model 'nope' does not exist.")

    response = client.post("/v1/chat/completions", json=chat_body(model="nope"))

    assert response.status_code == 404
    assert response.json()["error"] == {
        "message": "The model 'nope' does not exist.", "type": "invalid_request_error", "param": None,
        "code": "model_not_found",
    }


def test_an_invalid_request_is_an_openai_400_naming_the_field(client, chat_adapter):
    response = client.post("/v1/chat/completions", json=chat_body(temperature=5))

    assert response.status_code == 400
    error = response.json()["error"]
    assert error["type"] == "invalid_request_error"
    assert error["param"] == "temperature"
    chat_adapter.complete.assert_not_awaited()


def test_an_unsupported_feature_is_rejected_with_a_readable_message(client):
    response = client.post("/v1/chat/completions", json=chat_body(stream=True))

    assert response.status_code == 400
    assert response.json()["error"]["message"] == "stream=true is not supported yet"
