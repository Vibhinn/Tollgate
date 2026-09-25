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
            "rate_limiter": {
                "max_tokens": "5",
                "refill_rate": "1",
                "time_interval": "1.0",
            },
            "gateway": {
                "default_model": "claude-opus-4-6",
                "default_temperature": "0.7",
            },
        }

    def get_entire_config_section(self, section):
        return self._data.get(section, {})

    def get_config(self, section, option, sub_section=None):
        value = self._data[section]
        if sub_section:
            path = sub_section if isinstance(sub_section, list) else [sub_section]
            for key in path:
                value = value[key]
        return value[option]


@pytest.fixture
def fake_config():
    return FakeConfig()


@pytest.fixture
def sample_messages():
    return [Message(role="user", content="What is the capital of France?")]


@pytest.fixture
def fake_embedding():
    return np.zeros((1, 256), dtype=float)
