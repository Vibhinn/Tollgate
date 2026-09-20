from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

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

    result = await repo.invoke("hello", "gemini-2.0-flash")

    gemini_client.aio.models.generate_content.assert_awaited_once_with(
        model="gemini-2.0-flash",
        contents="hello",
    )
    assert result.content == "hi there"
    assert result.input_tokens == 12
    assert result.output_tokens == 34
