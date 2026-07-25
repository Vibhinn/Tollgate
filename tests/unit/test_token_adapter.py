import json
from unittest.mock import AsyncMock

import pytest

from src.app.adapters.token_adapter import GenerateAccessTokenAdapter


class FakeRepoManager:
    def __init__(self, exact_cache):
        self._exact_cache = exact_cache

    def get_repo(self, repo_type):
        assert repo_type == "exact_cache"
        return self._exact_cache


@pytest.fixture
def exact_cache():
    return AsyncMock()


@pytest.fixture
def adapter(exact_cache):
    return GenerateAccessTokenAdapter(FakeRepoManager(exact_cache))


async def test_generated_token_has_expected_prefix(adapter):
    token = await adapter.generate_and_save_token("chat", "user", 3600)
    assert token.startswith("tg_")
    assert len(token) > len("tg_")


async def test_generated_tokens_are_unique(adapter):
    token_a = await adapter.generate_and_save_token("chat", "user", 3600)
    token_b = await adapter.generate_and_save_token("chat", "user", 3600)
    assert token_a != token_b


async def test_saves_token_metadata_with_correct_key_and_ttl(adapter, exact_cache):
    token = await adapter.generate_and_save_token("image", "admin", 1296000)

    exact_cache.save.assert_awaited_once()
    call_kwargs = exact_cache.save.await_args.kwargs
    assert call_kwargs["key"] == f"token:{token}"
    assert call_kwargs["timeout"] == 1296000
    assert json.loads(call_kwargs["value"]) == {"requirement": "image", "user_role": "admin"}
