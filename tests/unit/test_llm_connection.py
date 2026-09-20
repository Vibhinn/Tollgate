"""Regression tests for src.llm.connection.LLMConnection."""
import importlib
from unittest.mock import MagicMock

import pytest

from src.llm.connection import LLMConnection
from src.utils.types import LLMProvider

# src/llm/__init__.py does `from .providers import providers`, which shadows
# the `providers` submodule with the `providers` dict on the package's own
# namespace - `import src.llm.providers` would resolve to that dict instead
# of the submodule, so fetch the real submodule directly via importlib.
providers_module = importlib.import_module("src.llm.providers")


@pytest.fixture(autouse=True)
def reset_connections():
    original = dict(LLMConnection._connections)
    LLMConnection._connections = {}
    yield
    LLMConnection._connections = original


def test_get_connection_returns_the_initialized_connection():
    LLMConnection._connections["openai"] = "some-connection"

    assert LLMConnection.get_connection("openai") == "some-connection"


def test_get_connection_raises_for_unknown_provider():
    with pytest.raises(ValueError, match="unknown-provider"):
        LLMConnection.get_connection("unknown-provider")


def test_initialize_skips_unconfigured_providers(fake_config, monkeypatch):
    monkeypatch.setattr(providers_module.StaticModel, "from_pretrained", MagicMock())
    config_data = {
        "models": {
            "openai": {"api_key": "NOT_CONFIGURED"},
        },
        "embedding": {"model_name": "irrelevant-for-this-test"},
    }
    fake_config._data = config_data

    LLMConnection.initialize(fake_config)

    assert "openai" not in LLMConnection._connections


def test_initialize_builds_embedding_model_eagerly_from_configured_model_name(fake_config, monkeypatch):
    """Regression test: the embedding connection used to be wired to the
    Qdrant client instead of a real embedding model. This exercises the real
    initialize() path end-to-end (not just the providers.py lambda in
    isolation) to prove the configured model name actually reaches
    StaticModel.from_pretrained, and that it happens once, eagerly, during
    initialize() rather than lazily on a request."""
    fake_config._data = {
        "models": {},
        "embedding": {"model_name": "some/configured-model"},
    }
    fake_static_model = object()
    from_pretrained = MagicMock(return_value=fake_static_model)
    monkeypatch.setattr(providers_module.StaticModel, "from_pretrained", from_pretrained)

    LLMConnection.initialize(fake_config)

    from_pretrained.assert_called_once_with("some/configured-model", force_download=False)
    assert LLMConnection.get_connection(LLMProvider.EMBEDDING) is fake_static_model
