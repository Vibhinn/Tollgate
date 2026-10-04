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
from src.llm.repository.openai_repository import OpenAIRepository
from src.utils.types import Message

HELLO = [Message(role="user", content="hello")]


def make_raw_response(text="hi there", prompt_tokens=12, completion_tokens=34):
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=text))],
        usage=SimpleNamespace(prompt_tokens=prompt_tokens, completion_tokens=completion_tokens),
    )


@pytest.fixture
def openai_client(monkeypatch):
    client = AsyncMock()
    client.chat.completions.create.return_value = make_raw_response()
    monkeypatch.setattr(LLMConnection, "get_connection", classmethod(lambda cls, p: client))
    return client


async def test_invoke_normalizes_raw_sdk_response(openai_client):
    repo = OpenAIRepository()

    result = await repo.invoke(HELLO, "gpt-4o", 4096)

    openai_client.chat.completions.create.assert_awaited_once_with(
        model="gpt-4o",
        messages=[{"role": "user", "content": "hello"}],
        max_tokens=4096,
    )
    assert result.content == "hi there"
    assert result.input_tokens == 12
    assert result.output_tokens == 34


def make_status_error(error_cls, status_code):
    request = httpx.Request("POST", "https://api.openai.com/v1/chat/completions")
    response = httpx.Response(status_code, request=request, json={"error": {"message": "boom"}})
    return error_cls("boom", response=response, body=None)


async def test_invoke_sends_the_whole_conversation_and_temperature(openai_client):
    messages = [
        Message(role="developer", content="Reply in French."),
        Message(role="user", content="hi"),
        Message(role="assistant", content="bonjour"),
        Message(role="user", content="how are you?"),
    ]
    repo = OpenAIRepository()

    await repo.invoke(messages, "gpt-4o", 4096, temperature=0.2)

    openai_client.chat.completions.create.assert_awaited_once_with(
        model="gpt-4o",
        messages=[
            {"role": "developer", "content": "Reply in French."},
            {"role": "user", "content": "hi"},
            {"role": "assistant", "content": "bonjour"},
            {"role": "user", "content": "how are you?"},
        ],
        max_tokens=4096,
        temperature=0.2,
    )


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
    openai_client, error_cls, status_code, expected_domain_exception
):
    sdk_exception = make_status_error(error_cls, status_code)
    openai_client.chat.completions.create.side_effect = sdk_exception
    repo = OpenAIRepository()

    with pytest.raises(expected_domain_exception) as exc_info:
        await repo.invoke(HELLO, "gpt-4o", 4096)

    assert exc_info.value.__cause__ is sdk_exception


async def test_invoke_maps_connection_error_to_api_error(openai_client):
    sdk_exception = openai.APIConnectionError(
        request=httpx.Request("POST", "https://api.openai.com/v1/chat/completions")
    )
    openai_client.chat.completions.create.side_effect = sdk_exception
    repo = OpenAIRepository()

    with pytest.raises(APIError) as exc_info:
        await repo.invoke(HELLO, "gpt-4o", 4096)

    assert exc_info.value.__cause__ is sdk_exception
