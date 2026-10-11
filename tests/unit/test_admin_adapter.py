from unittest.mock import AsyncMock

import pytest

from src.app.adapters import AdminAdapter
from src.app.exceptions import InvalidAdminCredentials
from src.utils.crypto import hash_password
from tests.conftest import FakeConfig


@pytest.fixture
def token_repo():
    repo = AsyncMock()
    repo.create_token.return_value = "tg_session"
    return repo


@pytest.fixture
def adapter(token_repo):
    config = FakeConfig({"admin": {"username": "root", "password_hash": hash_password("correct horse")}})
    return AdminAdapter(config, token_repo)


async def test_the_right_credentials_get_a_12_hour_admin_session(adapter, token_repo):
    session = await adapter.login("root", "correct horse")

    assert session == {"session_token": "tg_session", "token_type": "bearer", "expires_in": 43_200}
    token_repo.create_token.assert_awaited_once_with("admin", "dashboard-session", "admin", 43_200)


@pytest.mark.parametrize("username, password", [
    ("root", "wrong"),
    ("someone-else", "correct horse"),
    ("ROOT", "correct horse"),
])
async def test_wrong_credentials_get_no_session(adapter, token_repo, username, password):
    with pytest.raises(InvalidAdminCredentials):
        await adapter.login(username, password)

    token_repo.create_token.assert_not_awaited()
