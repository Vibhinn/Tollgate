from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from google.genai import types
from google.genai.errors import ClientError, ServerError

from src.app.exceptions import (
    ModelProviderServerError, RateLimitedFromModelProvider,
    PermissionDeniedForModel, APIKeyInvalidOrExpired, BadRequestToModel,
)
from src.llm.connection import LLMConnection
from src.llm.repository.gemini_repository import GeminiRepository


def make_raw_response(text="hi there", prompt_token_count=12, candidates_token_count=34):
    return SimpleNamespace(
        text=text,
        usage_metadata=SimpleNamespace(
            prompt_token_count=prompt_token_count,
            candidates_token_count=candidates_token_count,
        ),
    )


@pytest.fixture
def gemini_client(monkeypatch):
    client = MagicMock()
    client.aio.models.generate_content = AsyncMock(return_value=make_raw_response())
    monkeypatch.setattr(LLMConnection, "get_connection", classmethod(lambda cls, p: client))
    return client


async def test_invoke_normalizes_raw_sdk_response(gemini_client):
    repo = GeminiRepository()

    result = await repo.invoke("hello", "gemini-2.0-flash", 4096)

    gemini_client.aio.models.generate_content.assert_awaited_once_with(
        model="gemini-2.0-flash",
        contents="hello",
        config=types.GenerateContentConfig(max_output_tokens=4096),
    )
    assert result.content == "hi there"
    assert result.input_tokens == 12
    assert result.output_tokens == 34


@pytest.mark.parametrize(
    "status_code, expected_domain_exception",
    [
        (429, RateLimitedFromModelProvider),
        (403, PermissionDeniedForModel),
        (401, APIKeyInvalidOrExpired),
        (404, BadRequestToModel),
    ],
)
async def test_invoke_maps_client_errors_to_domain_exceptions(gemini_client, status_code, expected_domain_exception):
    sdk_exception = ClientError(status_code, {"error": {"message": "boom"}})
    gemini_client.aio.models.generate_content.side_effect = sdk_exception
    repo = GeminiRepository()

    with pytest.raises(expected_domain_exception) as exc_info:
        await repo.invoke("hello", "gemini-2.0-flash", 4096)

    assert exc_info.value.__cause__ is sdk_exception


async def test_invoke_maps_server_error_to_model_provider_server_error(gemini_client):
    sdk_exception = ServerError(500, {"error": {"message": "outage"}})
    gemini_client.aio.models.generate_content.side_effect = sdk_exception
    repo = GeminiRepository()

    with pytest.raises(ModelProviderServerError) as exc_info:
        await repo.invoke("hello", "gemini-2.0-flash", 4096)

    assert exc_info.value.__cause__ is sdk_exception
