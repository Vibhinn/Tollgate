from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.app.api.middleware import auth as auth_module
from src.app.api.middleware import AuthenticationMiddleware
from src.app.injector.dependency_container import DependencyContainer
from src.cache import RedisRepository


@pytest.fixture
def test_container(monkeypatch):
    """Isolated container so fakes never leak into the app-wide one."""
    test_container = DependencyContainer()
    monkeypatch.setattr(auth_module, "container", test_container)
    return test_container


@pytest.fixture
def redis_repo(test_container):
    repo = AsyncMock()
    test_container.register(RedisRepository, lambda: repo)
    return repo


@pytest.fixture
def client(redis_repo):
    app = FastAPI()

    @app.get("/api/v1/chat/completions")
    async def protected():
        return {"ok": True}


    app.add_middleware(AuthenticationMiddleware)
    return TestClient(app)


def test_exempt_path_bypasses_auth_entirely(client, redis_repo):
    response = client.get("/docs")

    assert response.status_code == 200
    redis_repo.get_user_id.assert_not_called()


def test_missing_authorization_header_returns_401(client):
    response = client.get("/api/v1/chat/completions")

    assert response.status_code == 401
    assert response.json() == {"detail": "Token not sent in header"}


def test_non_bearer_authorization_header_returns_401(client):
    response = client.get("/api/v1/chat/completions", headers={"Authorization": "Basic abc123"})

    assert response.status_code == 401


def test_invalid_token_returns_401(client, redis_repo):
    redis_repo.get_user_id.return_value = None

    response = client.get("/api/v1/chat/completions", headers={"Authorization": "Bearer tg_bad"})

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid token"}
    redis_repo.get_user_id.assert_awaited_once_with("tg_bad")


def test_valid_token_allows_request_through(client, redis_repo):
    redis_repo.get_user_id.return_value = "user-1"

    response = client.get("/api/v1/chat/completions", headers={"Authorization": "Bearer tg_good"})

    assert response.status_code == 200
    assert response.json() == {"ok": True}
