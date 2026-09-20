from unittest.mock import MagicMock

import pytest

from src.llm.connection import LLMConnection
from src.llm.factory.repository_factory import LLMRepositoryFactory
from src.llm.repository.openai_repository import OpenAIRepository
from src.llm.repository.anthropic_repository import AnthropicRepository
from src.llm.repository.gemini_repository import GeminiRepository


@pytest.fixture
def factory(fake_config, monkeypatch):
    # Each provider repository fetches its client from LLMConnection at
    # construction time; stub that out so this test targets
    # LLMRepositoryFactory's wiring, not LLMConnection itself (see
    # test_llm_connection.py for that layer's own tests).
    monkeypatch.setattr(LLMConnection, "get_connection", classmethod(lambda cls, provider: MagicMock()))

    # The shared fake_config fixture has no "models" section by default, so
    # LLMRepositoryFactory would never actually build any repos - give it one
    # with every provider configured (non-"NOT_CONFIGURED") so get_repo has
    # something real to return.
    fake_config._data = {
        **fake_config._data,
        "models": {
            "openai": {"api_key": "fake-openai-key"},
            "anthropic": {"api_key": "fake-anthropic-key"},
            "gemini": {"api_key": "fake-gemini-key"},
        },
    }
    return LLMRepositoryFactory(fake_config)


def test_get_repo_returns_openai_repository(factory):
    assert isinstance(factory.get_repo("openai"), OpenAIRepository)


def test_get_repo_returns_anthropic_repository(factory):
    assert isinstance(factory.get_repo("anthropic"), AnthropicRepository)


def test_get_repo_returns_gemini_repository(factory):
    assert isinstance(factory.get_repo("gemini"), GeminiRepository)


def test_get_repo_returns_none_for_unknown_provider(factory):
    assert factory.get_repo("unknown-provider") is None


def test_get_repo_returns_same_instance_on_repeated_calls(factory):
    first = factory.get_repo("openai")
    second = factory.get_repo("openai")
    assert first is second
