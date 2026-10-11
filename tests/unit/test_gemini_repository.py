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
from src.utils.types import Message, GenerationParams

HELLO = [Message(role="user", content="hello")]


def make_raw_response(text="hi there", prompt_token_count=12, candidates_token_count=34, finish_reason=types.FinishReason.STOP):
    return SimpleNamespace(
        text=text,
        candidates=[SimpleNamespace(finish_reason=finish_reason)],
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

    result = await repo.invoke(HELLO, "gemini-2.0-flash", GenerationParams(max_tokens=4096))

    gemini_client.aio.models.generate_content.assert_awaited_once_with(
        model="gemini-2.0-flash",
        contents=[types.Content(role="user", parts=[types.Part(text="hello")])],
        config=types.GenerateContentConfig(max_output_tokens=4096, temperature=None, top_p=None, stop_sequences=None,
                                          system_instruction=None),
    )
    assert result.content == "hi there"
    assert result.input_tokens == 12
    assert result.output_tokens == 34


async def test_invoke_sends_the_whole_conversation_with_system_instruction_and_temperature(gemini_client):
    messages = [
        Message(role="system", content="Reply in French."),
        Message(role="user", content="hi"),
        Message(role="assistant", content="bonjour"),
        Message(role="user", content="how are you?"),
    ]
    repo = GeminiRepository()

    await repo.invoke(messages, "gemini-2.0-flash", GenerationParams(max_tokens=4096, temperature=0.2))

    gemini_client.aio.models.generate_content.assert_awaited_once_with(
        model="gemini-2.0-flash",
        contents=[
            types.Content(role="user", parts=[types.Part(text="hi")]),
            types.Content(role="model", parts=[types.Part(text="bonjour")]),
            types.Content(role="user", parts=[types.Part(text="how are you?")]),
        ],
        config=types.GenerateContentConfig(
            max_output_tokens=4096, temperature=0.2, top_p=None, stop_sequences=None, system_instruction="Reply in French."
        ),
    )


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
        await repo.invoke(HELLO, "gemini-2.0-flash", GenerationParams(max_tokens=4096))

    assert exc_info.value.__cause__ is sdk_exception


async def test_invoke_maps_server_error_to_model_provider_server_error(gemini_client):
    sdk_exception = ServerError(500, {"error": {"message": "outage"}})
    gemini_client.aio.models.generate_content.side_effect = sdk_exception
    repo = GeminiRepository()

    with pytest.raises(ModelProviderServerError) as exc_info:
        await repo.invoke(HELLO, "gemini-2.0-flash", GenerationParams(max_tokens=4096))

    assert exc_info.value.__cause__ is sdk_exception


async def test_invoke_passes_top_p_and_stop_sequences(gemini_client):
    await GeminiRepository().invoke(HELLO, "gemini-2.0-flash", GenerationParams(top_p=0.5, stop=["END"]))

    config = gemini_client.aio.models.generate_content.await_args.kwargs["config"]
    assert config.top_p == 0.5
    assert config.stop_sequences == ["END"]


@pytest.mark.parametrize("finish_reason, expected", [
    (types.FinishReason.STOP, "stop"),
    (types.FinishReason.MAX_TOKENS, "length"),
    (types.FinishReason.SAFETY, "content_filter"),
    (types.FinishReason.RECITATION, "content_filter"),
])
async def test_invoke_maps_the_finish_reason(gemini_client, finish_reason, expected):
    gemini_client.aio.models.generate_content.return_value = make_raw_response(finish_reason=finish_reason)

    result = await GeminiRepository().invoke(HELLO, "gemini-2.0-flash", GenerationParams())

    assert result.finish_reason == expected


async def test_invoke_returns_empty_content_when_the_answer_was_blocked(gemini_client):
    gemini_client.aio.models.generate_content.return_value = make_raw_response(
        text=None, candidates_token_count=None, finish_reason=types.FinishReason.SAFETY,
    )

    result = await GeminiRepository().invoke(HELLO, "gemini-2.0-flash", GenerationParams())

    assert (result.content, result.output_tokens, result.finish_reason) == ("", 0, "content_filter")
