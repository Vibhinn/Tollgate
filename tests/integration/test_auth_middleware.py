from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from src.app.api.middleware import auth as auth_module
from src.app.api.middleware import AuthenticationMiddleware
from src.app.injector.dependency_container import DependencyContainer
from src.cache import RedisRepository
from src.utils.types import TokenIdentity

ALICE = TokenIdentity(user_id="payments:alice", team="payments", name="alice", token_id="e72bb248c316", role="user")


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
    redis_repo.get_identity.assert_not_called()


def test_missing_authorization_header_returns_401(client):
    response = client.get("/api/v1/chat/completions")

    assert response.status_code == 401
    assert response.json() == {"error": {"message": "Missing bearer token in the Authorization header.", "type": "invalid_request_error", "param": None, "code": "invalid_api_key"}}


def test_non_bearer_authorization_header_returns_401(client):
    response = client.get("/api/v1/chat/completions", headers={"Authorization": "Basic abc123"})

    assert response.status_code == 401


def test_invalid_token_returns_401(client, redis_repo):
    redis_repo.get_identity.return_value = None

    response = client.get("/api/v1/chat/completions", headers={"Authorization": "Bearer tg_bad"})

    assert response.status_code == 401
    assert response.json() == {"error": {"message": "Invalid, expired or revoked Tollgate token.", "type": "invalid_request_error", "param": None, "code": "invalid_api_key"}}
    redis_repo.get_identity.assert_awaited_once_with("tg_bad")


def test_valid_token_allows_request_through(client, redis_repo):
    redis_repo.get_identity.return_value = ALICE

    response = client.get("/api/v1/chat/completions", headers={"Authorization": "Bearer tg_good"})

    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_the_identity_is_handed_to_the_rest_of_the_request(redis_repo):
    redis_repo.get_identity.return_value = ALICE
    app = FastAPI()

    @app.get("/v1/whoami")
    async def whoami(request: Request):
        return {"user_id": request.state.user_id, "role": request.state.identity.role}

    app.add_middleware(AuthenticationMiddleware)

    response = TestClient(app).get("/v1/whoami", headers={"Authorization": "Bearer tg_good"})

    assert response.json() == {"user_id": "payments:alice", "role": "user"}
