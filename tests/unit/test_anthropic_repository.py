from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.llm.connection import LLMConnection
from src.llm.repository.anthropic_repository import AnthropicRepository
from src.utils.types import Message, GenerationParams

HELLO = [Message(role="user", content="hello")]


def make_raw_response(text="hi there", input_tokens=12, output_tokens=34, stop_reason="end_turn"):
    return SimpleNamespace(
        content=[SimpleNamespace(type="text", text=text)],
        stop_reason=stop_reason,
        usage=SimpleNamespace(input_tokens=input_tokens, output_tokens=output_tokens),
    )


@pytest.fixture
def anthropic_client(monkeypatch):
    client = AsyncMock()
    client.messages.create.return_value = make_raw_response()
    monkeypatch.setattr(LLMConnection, "get_connection", classmethod(lambda cls, p: client))
    return client


async def test_invoke_normalizes_raw_sdk_response(anthropic_client):
    repo = AnthropicRepository()

    result = await repo.invoke(HELLO, "claude-sonnet-4-6", GenerationParams(max_tokens=4096))

    anthropic_client.messages.create.assert_awaited_once_with(
        model="claude-sonnet-4-6",
        messages=[{"role": "user", "content": "hello"}],
        max_tokens=4096,
    )
    assert result.content == "hi there"
    assert result.input_tokens == 12
    assert result.output_tokens == 34


async def test_invoke_moves_system_and_developer_messages_into_the_system_param(anthropic_client):
    messages = [
        Message(role="system", content="Reply in French."),
        Message(role="developer", content="Be brief."),
        Message(role="user", content="hi"),
        Message(role="assistant", content="bonjour"),
        Message(role="user", content="how are you?"),
    ]
    repo = AnthropicRepository()

    await repo.invoke(messages, "claude-sonnet-4-6", GenerationParams(max_tokens=4096, temperature=0.2))

    anthropic_client.messages.create.assert_awaited_once_with(
        model="claude-sonnet-4-6",
        messages=[
            {"role": "user", "content": "hi"},
            {"role": "assistant", "content": "bonjour"},
            {"role": "user", "content": "how are you?"},
        ],
        max_tokens=4096,
        system="Reply in French.\n\nBe brief.",
        temperature=0.2,
    )


async def test_invoke_defaults_max_tokens_because_anthropic_requires_it(anthropic_client):
    await AnthropicRepository().invoke(HELLO, "claude-sonnet-4-6", GenerationParams(top_p=0.5, stop=["END"]))

    anthropic_client.messages.create.assert_awaited_once_with(
        model="claude-sonnet-4-6",
        messages=[{"role": "user", "content": "hello"}],
        max_tokens=4096,
        top_p=0.5,
        stop_sequences=["END"],
    )


@pytest.mark.parametrize("stop_reason, expected", [("end_turn", "stop"), ("stop_sequence", "stop"),
                                                   ("max_tokens", "length"), ("refusal", "content_filter")])
async def test_invoke_maps_the_stop_reason_to_an_openai_finish_reason(anthropic_client, stop_reason, expected):
    anthropic_client.messages.create.return_value = make_raw_response(stop_reason=stop_reason)

    result = await AnthropicRepository().invoke(HELLO, "claude-sonnet-4-6", GenerationParams())

    assert result.finish_reason == expected


async def test_invoke_handles_a_refusal_with_no_content_blocks(anthropic_client):
    anthropic_client.messages.create.return_value = SimpleNamespace(
        content=[], stop_reason="refusal", usage=SimpleNamespace(input_tokens=5, output_tokens=0),
    )

    result = await AnthropicRepository().invoke(HELLO, "claude-sonnet-4-6", GenerationParams())

    assert result.content == ""
    assert result.finish_reason == "content_filter"
