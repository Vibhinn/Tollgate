from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import openai
import pytest

from src.app.exceptions import (
    ModelProviderServerError, RateLimitedFromModelProvider,
    PermissionDeniedForModel, APIKeyInvalidOrExpired, BadRequestToModel, APIError,
)
from src.llm.connection import LLMConnection
from src.llm.repository.self_hosted_model_repository import SelfHostedModelRepository


def make_raw_response(text="hi there", prompt_tokens=12, completion_tokens=34):
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=text))],
        usage=SimpleNamespace(prompt_tokens=prompt_tokens, completion_tokens=completion_tokens),
    )


@pytest.fixture
def self_hosted_client(monkeypatch):
    client = AsyncMock()
    client.chat.completions.create.return_value = make_raw_response()
    monkeypatch.setattr(LLMConnection, "get_connection", classmethod(lambda cls, alias: client))
    return client


def test_init_fetches_the_connection_registered_for_its_own_alias(monkeypatch):
    """Regression test: SelfHostedModelRepository used to always look up the
    single shared LLMProvider.SELF_HOSTED key, so two aliases (e.g. Ollama
    and llama.cpp) would collide on the same connection. It must look up its
    own alias instead."""
    get_connection = AsyncMock()
    monkeypatch.setattr(LLMConnection, "get_connection", classmethod(lambda cls, alias: f"connection-for-{alias}"))

    ollama_repo = SelfHostedModelRepository("ollama-llama3")
    llamacpp_repo = SelfHostedModelRepository("llamacpp-mistral")

    assert ollama_repo.self_hosted_model_client == "connection-for-ollama-llama3"
    assert llamacpp_repo.self_hosted_model_client == "connection-for-llamacpp-mistral"


async def test_invoke_normalizes_raw_sdk_response(self_hosted_client):
    repo = SelfHostedModelRepository("ollama-llama3")

    result = await repo.invoke("hello", "llama3", 4096)

    self_hosted_client.chat.completions.create.assert_awaited_once_with(
        model="llama3",
        messages=[{"role": "user", "content": "hello"}],
        max_tokens=4096,
    )
    assert result.content == "hi there"
    assert result.input_tokens == 12
    assert result.output_tokens == 34


def make_status_error(error_cls, status_code):
    request = httpx.Request("POST", "http://localhost:11434/v1/chat/completions")
    response = httpx.Response(status_code, request=request, json={"error": {"message": "boom"}})
    return error_cls("boom", response=response, body=None)


@pytest.mark.parametrize(
    "error_cls, status_code, expected_domain_exception",
    [
        (openai.RateLimitError, 429, RateLimitedFromModelProvider),
        (openai.AuthenticationError, 401, APIKeyInvalidOrExpired),
        (openai.PermissionDeniedError, 403, PermissionDeniedForModel),
        (openai.BadRequestError, 400, BadRequestToModel),
        (openai.InternalServerError, 500, ModelProviderServerError),
    ],
)
async def test_invoke_maps_provider_errors_to_domain_exceptions(
    self_hosted_client, error_cls, status_code, expected_domain_exception
):
    sdk_exception = make_status_error(error_cls, status_code)
    self_hosted_client.chat.completions.create.side_effect = sdk_exception
    repo = SelfHostedModelRepository("ollama-llama3")

    with pytest.raises(expected_domain_exception) as exc_info:
        await repo.invoke("hello", "llama3", 4096)

    assert exc_info.value.__cause__ is sdk_exception


async def test_invoke_maps_connection_error_to_api_error(self_hosted_client):
    sdk_exception = openai.APIConnectionError(
        request=httpx.Request("POST", "http://localhost:11434/v1/chat/completions")
    )
    self_hosted_client.chat.completions.create.side_effect = sdk_exception
    repo = SelfHostedModelRepository("ollama-llama3")

    with pytest.raises(APIError) as exc_info:
        await repo.invoke("hello", "llama3", 4096)

    assert exc_info.value.__cause__ is sdk_exception
