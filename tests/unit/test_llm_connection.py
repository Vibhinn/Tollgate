"""Regression tests for src.llm.connection.LLMConnection."""
import importlib
from unittest.mock import MagicMock

import pytest

from src.llm.connection import LLMConnection
from src.utils.config import ROUTING_TABLE
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


@pytest.fixture(autouse=True)
def reset_routing_table():
    # connection.py mutates the real, shared ROUTING_TABLE object in place
    # when registering self-hosted aliases - restore it so tests don't leak
    # state into each other or into unrelated modules that import the same
    # object by reference.
    original = dict(ROUTING_TABLE)
    yield
    ROUTING_TABLE.clear()
    ROUTING_TABLE.update(original)


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


def _self_hosted_config(fake_config, aliases: dict):
    fake_config._data = {
        "models": {"self_hosted": aliases},
        "embedding": {"model_name": "irrelevant-for-this-test"},
    }
    return fake_config


def test_initialize_builds_a_separate_connection_per_self_hosted_alias(fake_config, monkeypatch):
    """Regression test: every self-hosted alias used to be built and stored
    under the single shared LLMProvider.SELF_HOSTED key, so configuring
    Ollama, then llama.cpp, then Apple FM would each silently overwrite the
    last one."""
    monkeypatch.setattr(providers_module.StaticModel, "from_pretrained", MagicMock())
    self_hosted_factory = MagicMock(side_effect=lambda endpoint, key: f"client-for-{endpoint}")
    monkeypatch.setitem(providers_module.providers, LLMProvider.SELF_HOSTED, self_hosted_factory)

    _self_hosted_config(fake_config, {
        "ollama-llama3": {"endpoint": "http://localhost:11434/v1", "model_name": "llama3", "api_key": "NOT_CONFIGURED"},
        "llamacpp-mistral": {"endpoint": "http://localhost:8080/v1", "model_name": "mistral-7b", "api_key": "NOT_CONFIGURED"},
    })

    LLMConnection.initialize(fake_config)

    assert LLMConnection.get_connection("ollama-llama3") == "client-for-http://localhost:11434/v1"
    assert LLMConnection.get_connection("llamacpp-mistral") == "client-for-http://localhost:8080/v1"
    assert self_hosted_factory.call_count == 2


def test_initialize_uses_a_placeholder_api_key_when_self_hosted_model_has_none(fake_config, monkeypatch):
    """openai-python requires a non-empty api_key even when the target server
    (e.g. a local Ollama instance) ignores auth entirely."""
    monkeypatch.setattr(providers_module.StaticModel, "from_pretrained", MagicMock())
    self_hosted_factory = MagicMock()
    monkeypatch.setitem(providers_module.providers, LLMProvider.SELF_HOSTED, self_hosted_factory)

    _self_hosted_config(fake_config, {
        "ollama-llama3": {"endpoint": "http://localhost:11434/v1", "model_name": "llama3", "api_key": "NOT_CONFIGURED"},
    })

    LLMConnection.initialize(fake_config)

    self_hosted_factory.assert_called_once_with("http://localhost:11434/v1", "not-required")


def test_initialize_uses_the_real_api_key_when_self_hosted_model_has_one(fake_config, monkeypatch):
    monkeypatch.setattr(providers_module.StaticModel, "from_pretrained", MagicMock())
    self_hosted_factory = MagicMock()
    monkeypatch.setitem(providers_module.providers, LLMProvider.SELF_HOSTED, self_hosted_factory)

    _self_hosted_config(fake_config, {
        "hosted-vllm": {"endpoint": "https://my-vllm.internal/v1", "model_name": "llama3-70b", "api_key": "sk-real-secret"},
    })

    LLMConnection.initialize(fake_config)

    self_hosted_factory.assert_called_once_with("https://my-vllm.internal/v1", "sk-real-secret")


def test_initialize_registers_each_self_hosted_alias_into_the_routing_table(fake_config, monkeypatch):
    """Self-hosted models are user-defined at setup time, so they can't be
    hardcoded into ROUTING_TABLE like the built-in cloud models - they must
    be merged in dynamically so routing can resolve them by alias."""
    monkeypatch.setattr(providers_module.StaticModel, "from_pretrained", MagicMock())
    monkeypatch.setitem(providers_module.providers, LLMProvider.SELF_HOSTED, MagicMock())

    _self_hosted_config(fake_config, {
        "ollama-llama3": {"endpoint": "http://localhost:11434/v1", "model_name": "llama3", "api_key": "NOT_CONFIGURED"},
    })

    LLMConnection.initialize(fake_config)

    assert ROUTING_TABLE["ollama-llama3"] == {"provider": "ollama-llama3", "model": "llama3"}
