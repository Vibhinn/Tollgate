from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.app.api.generate_token import generate_access_token_router
from src.app.injector.inject import get_generate_token_adapter, get_config_object
from src.utils.crypto import hash_password

ADMIN_PASSWORD = "correct-horse-battery-staple"


@pytest.fixture
def token_adapter():
    return AsyncMock()


@pytest.fixture
def config():
    stub = MagicMock()
    stub.get_config.return_value = hash_password(ADMIN_PASSWORD)
    return stub


@pytest.fixture
def client(token_adapter, config):
    app = FastAPI()
    app.include_router(generate_access_token_router)
    app.dependency_overrides[get_generate_token_adapter] = lambda: token_adapter
    app.dependency_overrides[get_config_object] = lambda: config
    return TestClient(app)


def test_generates_and_returns_token(client, token_adapter):
    token_adapter.generate_and_save_token.return_value = "tg_abc123"

    response = client.post(
        "/api/v1/chat/generate",
        json={"token_requirement": "chat", "role": "user"},
    )

    assert response.status_code == 200
    assert response.json() == {"token": "tg_abc123"}


def test_forwards_requirement_role_and_default_lifetime(client, token_adapter):
    token_adapter.generate_and_save_token.return_value = "tg_abc123"

    client.post(
        "/api/v1/chat/generate",
        json={"token_requirement": "image", "role": "admin", "password": ADMIN_PASSWORD},
    )

    token_adapter.generate_and_save_token.assert_awaited_once_with("image", "admin", 1296000)


def test_admin_role_with_wrong_password_is_rejected(client, token_adapter):
    response = client.post(
        "/api/v1/chat/generate",
        json={"token_requirement": "chat", "role": "admin", "password": "not-the-real-password"},
    )

    assert response.status_code == 401
    token_adapter.generate_and_save_token.assert_not_awaited()


def test_user_role_never_checks_the_admin_password(client, token_adapter, config):
    token_adapter.generate_and_save_token.return_value = "tg_abc123"

    response = client.post("/api/v1/chat/generate", json={"token_requirement": "chat", "role": "user"})

    assert response.status_code == 200
    config.get_config.assert_not_called()


def test_forwards_custom_lifetime(client, token_adapter):
    token_adapter.generate_and_save_token.return_value = "tg_abc123"

    client.post(
        "/api/v1/chat/generate",
        json={"token_requirement": "audio", "role": "user", "lifetime": 60},
    )

    token_adapter.generate_and_save_token.assert_awaited_once_with("audio", "user", 60)


@pytest.mark.parametrize("body", [
    {"token_requirement": "video", "role": "user"},
    {"token_requirement": "chat", "role": "superadmin"},
    {"role": "user"},
])
def test_rejects_invalid_payloads(client, token_adapter, body):
    response = client.post("/api/v1/chat/generate", json=body)

    assert response.status_code == 422
    token_adapter.generate_and_save_token.assert_not_awaited()
