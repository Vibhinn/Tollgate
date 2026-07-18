"""Shared fixtures for the Tollgate test suite.

Tests avoid touching real Redis/Qdrant/LLM providers or the checked-in
config.yaml (whose secrets are only decryptable with the local, gitignored
.tollgate.key). Everything talks to fakes that satisfy the same port
interfaces the production code depends on.
"""
import numpy as np
import pytest

from src.utils.types import Message


class FakeConfig:
    """Drop-in replacement for src.utils.config.Config, no file/crypto I/O."""

    def __init__(self, data: dict | None = None):
        self._data = data or {
            "RATE_LIMITER": {
                "MAX_TOKENS": "5",
                "REFILL_RATE": "1",
                "TIME_INTERVAL": "1.0",
            },
            "GATEWAY": {
                "DEFAULT_MODEL": "claude-opus-4-6",
                "DEFAULT_TEMPERATURE": "0.7",
            },
        }

    def get_entire_config_section(self, section):
        return self._data.get(section, {})

    def get_config(self, section, option, sub_section=None):
        if sub_section:
            return self._data[section][sub_section][option]
        return self._data[section][option]


@pytest.fixture
def fake_config():
    return FakeConfig()


@pytest.fixture
def sample_messages():
    return [Message(role="user", content="What is the capital of France?")]


@pytest.fixture
def fake_embedding():
    return np.zeros((1, 256), dtype=float)
