from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.app.middleware import auth as auth_module
from src.app.middleware.auth import AuthenticationMiddleware


@pytest.fixture
def redis_repo(monkeypatch):
    repo = AsyncMock()
    monkeypatch.setattr(auth_module, "RedisRepository", lambda: repo)
    return repo


@pytest.fixture
def client(redis_repo):
    app = FastAPI()

    @app.get("/api/v1/chat/completions")
    async def protected():
        return {"ok": True}

    @app.post("/api/v1/chat/generate")
    async def exempt():
        return {"ok": True}

    AuthenticationMiddleware(app)
    return TestClient(app)


def test_exempt_path_bypasses_auth_entirely(client, redis_repo):
    response = client.post("/api/v1/chat/generate")

    assert response.status_code == 200
    redis_repo.check_token_validity.assert_not_called()


def test_missing_authorization_header_returns_401(client):
    response = client.get("/api/v1/chat/completions")

    assert response.status_code == 401
    assert response.json() == {"detail": "Token not sent in header"}


def test_non_bearer_authorization_header_returns_401(client):
    response = client.get("/api/v1/chat/completions", headers={"Authorization": "Basic abc123"})

    assert response.status_code == 401


def test_invalid_token_returns_401(client, redis_repo):
    redis_repo.check_token_validity.return_value = False

    response = client.get("/api/v1/chat/completions", headers={"Authorization": "Bearer tg_bad"})

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid token"}
    redis_repo.check_token_validity.assert_awaited_once_with("tg_bad")


def test_valid_token_allows_request_through(client, redis_repo):
    redis_repo.check_token_validity.return_value = True

    response = client.get("/api/v1/chat/completions", headers={"Authorization": "Bearer tg_good"})

    assert response.status_code == 200
    assert response.json() == {"ok": True}
