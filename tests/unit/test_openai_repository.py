from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.llm.connection import LLMConnection
from src.llm.repository.openai_repository import OpenAIRepository


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

    result = await repo.invoke("hello", "gpt-4o")

    openai_client.chat.completions.create.assert_awaited_once_with(
        model="gpt-4o",
        messages=[{"role": "user", "content": "hello"}],
    )
    assert result.content == "hi there"
    assert result.input_tokens == 12
    assert result.output_tokens == 34
