from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from starlette.responses import JSONResponse
from fastapi.testclient import TestClient

from src.app.api.chat import chat_api_router
from src.app.injector.inject import get_chat_adapter
from src.app.exceptions import ModelSemanticNotFound


@pytest.fixture
def chat_adapter():
    return AsyncMock()


@pytest.fixture
def client(chat_adapter):
    app = FastAPI()
    app.include_router(chat_api_router)

    @app.exception_handler(ModelSemanticNotFound)
    async def handle_model_not_found(request, exc):
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    app.dependency_overrides[get_chat_adapter] = lambda: chat_adapter
    return TestClient(app)


def chat_body(**overrides):
    body = {
        "model": "cheap",
        "messages": [{"role": "user", "content": "hello there"}],
        "max_tokens": 4096,
    }
    body.update(overrides)
    return body


def test_returns_cached_answer_without_calling_llm(client, chat_adapter):
    chat_adapter.check_cache.return_value = "cached reply"

    response = client.post("/api/v1/chat/completions", json=chat_body())

    assert response.status_code == 200
    assert response.json() == {"role": "model", "message": "cached reply"}
    chat_adapter.query_llm.assert_not_called()


def test_cache_miss_invokes_llm_and_returns_assistant_message(client, chat_adapter):
    chat_adapter.check_cache.return_value = None
    chat_adapter.query_llm.return_value = "fresh llm reply"

    response = client.post("/api/v1/chat/completions", json=chat_body())

    assert response.status_code == 200
    assert response.json() == {"role": "assistant", "message": "fresh llm reply"}


def test_no_cache_type_does_not_enqueue_caching_job(client, chat_adapter):
    chat_adapter.check_cache.return_value = None
    chat_adapter.query_llm.return_value = "fresh llm reply"

    client.post("/api/v1/chat/completions", json=chat_body())

    chat_adapter.add_job_to_queue.assert_not_called()


def test_cache_type_enqueues_response_cache_job_with_default_ttl(client, chat_adapter):
    chat_adapter.check_cache.return_value = None
    chat_adapter.query_llm.return_value = "fresh llm reply"

    client.post("/api/v1/chat/completions", json=chat_body(cache_type="semantic"))

    chat_adapter.add_job_to_queue.assert_called_once()
    args, _ = chat_adapter.add_job_to_queue.call_args
    assert args[0] == "response_cache"
    job_data = args[1]
    assert job_data["cache_type"] == "semantic"
    assert job_data["prompt"] == "hello there"
    assert job_data["exact_key"].startswith("cache:exact:")
    assert job_data["model_response"] == "fresh llm reply"
    assert job_data["timeout"] == 3600


def test_cache_lookup_and_cache_job_use_the_same_keys(client, chat_adapter):
    chat_adapter.check_cache.return_value = None
    chat_adapter.query_llm.return_value = "fresh llm reply"

    client.post("/api/v1/chat/completions", json=chat_body(cache_type="exact"))

    looked_up = chat_adapter.check_cache.call_args.args[0]
    job_data = chat_adapter.add_job_to_queue.call_args.args[1]
    assert job_data["exact_key"] == looked_up.exact_key
    assert job_data["context_hash"] == looked_up.context_hash


def test_whole_conversation_and_temperature_reach_the_llm(client, chat_adapter):
    chat_adapter.check_cache.return_value = None
    chat_adapter.query_llm.return_value = "fresh llm reply"
    messages = [
        {"role": "system", "content": "Reply in French."},
        {"role": "user", "content": "hi"},
        {"role": "assistant", "content": "bonjour"},
        {"role": "user", "content": "how are you?"},
    ]

    client.post("/api/v1/chat/completions", json=chat_body(messages=messages, temperature=0.2))

    call_kwargs = chat_adapter.query_llm.call_args.kwargs
    assert [message.model_dump() for message in call_kwargs["messages"]] == messages
    assert call_kwargs["temperature"] == 0.2


def test_x_cache_ttl_header_overrides_default_timeout(client, chat_adapter):
    chat_adapter.check_cache.return_value = None
    chat_adapter.query_llm.return_value = "fresh llm reply"

    client.post(
        "/api/v1/chat/completions",
        json=chat_body(cache_type="exact"),
        headers={"X-Cache-TTL": "120"},
    )

    job_data = chat_adapter.add_job_to_queue.call_args.args[1]
    assert job_data["timeout"] == 120


def test_unrecognized_model_request_returns_422(client, chat_adapter):
    response = client.post("/api/v1/chat/completions", json=chat_body(model="not-a-real-model"))

    assert response.status_code == 422
    chat_adapter.check_cache.assert_not_called()


def test_model_semantic_not_found_is_mapped_to_404(client, chat_adapter):
    chat_adapter.check_cache.return_value = None
    chat_adapter.query_llm.side_effect = ModelSemanticNotFound("Sorry, model type smart is not recognized")

    response = client.post("/api/v1/chat/completions", json=chat_body(model="smart"))

    assert response.status_code == 404
    assert response.json() == {"detail": "Sorry, model type smart is not recognized"}


def test_cache_keys_are_scoped_to_the_user_set_by_auth(chat_adapter):
    app = FastAPI()
    app.include_router(chat_api_router)
    app.dependency_overrides[get_chat_adapter] = lambda: chat_adapter

    @app.middleware("http")
    async def fake_auth(request, call_next):
        request.scope.setdefault("state", {})["user_id"] = request.headers["X-Test-User"]
        return await call_next(request)

    chat_adapter.check_cache.return_value = "cached reply"
    client = TestClient(app)

    client.post("/api/v1/chat/completions", json=chat_body(), headers={"X-Test-User": "alice"})
    client.post("/api/v1/chat/completions", json=chat_body(), headers={"X-Test-User": "bob"})

    alice_keys, bob_keys = (call.args[0] for call in chat_adapter.check_cache.call_args_list)
    assert alice_keys.exact_key != bob_keys.exact_key
    assert alice_keys.context_hash != bob_keys.context_hash
