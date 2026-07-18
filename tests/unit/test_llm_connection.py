"""Regression tests for src.llm.connection.LLMConnection.

KNOWN BUG (confirmed, not speculative): `initialize()` stores each configured
provider's client in `cls._connections[provider]`, but `get_connection()`
reads from `cls._openai_conn` / `cls._anthropic_conn` / `cls._gemini_conn` /
`cls._model2vec_conn` - attributes that are never assigned anywhere in the
class. As a result, `get_connection()` always raises AttributeError, for
every provider, regardless of configuration. This means every real LLM call
in the app is currently broken end-to-end (OpenAIRepository, AnthropicRepository,
GeminiRepository, and Model2VecRepository all call `get_connection()` in
their constructors). These tests document the current behavior so the
maintainer notices immediately once the underlying bug is fixed - at that
point `test_get_connection_currently_raises_due_to_attribute_mismatch`
should start failing and can be replaced with a real "returns the
initialized connection" assertion.
"""
import pytest

from src.llm.connection import LLMConnection


@pytest.fixture(autouse=True)
def reset_connections():
    original = dict(LLMConnection._connections)
    LLMConnection._connections = {}
    yield
    LLMConnection._connections = original


def test_get_connection_currently_raises_due_to_attribute_mismatch():
    LLMConnection._connections["OPENAI"] = object()

    with pytest.raises(AttributeError, match="_openai_conn"):
        LLMConnection.get_connection("OPENAI")


def test_initialize_skips_unconfigured_providers(fake_config):
    config_data = {
        "MODELS": {
            "OPENAI": {"API_KEY": "NOT_CONFIGURED"},
        }
    }
    fake_config._data = config_data

    LLMConnection.initialize(fake_config)

    assert "OPENAI" not in LLMConnection._connections
