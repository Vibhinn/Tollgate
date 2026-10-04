from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.llm.connection import LLMConnection
from src.llm.repository.anthropic_repository import AnthropicRepository
from src.utils.types import Message

HELLO = [Message(role="user", content="hello")]


def make_raw_response(text="hi there", input_tokens=12, output_tokens=34):
    return SimpleNamespace(
        content=[SimpleNamespace(text=text)],
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

    result = await repo.invoke(HELLO, "claude-sonnet-4-6", 4096)

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

    await repo.invoke(messages, "claude-sonnet-4-6", 4096, temperature=0.2)

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
