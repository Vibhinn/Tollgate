"""The flow a dashboard uses: log in with the admin credentials, then read the full metrics with the
session token. Real auth, token storage (on fakeredis) and adapters; only the metrics data is canned."""
import json
from unittest.mock import MagicMock

import pytest
from fakeredis import FakeAsyncRedis
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.testclient import TestClient

from src.app.adapters import AdminAdapter, MetricsAdapter
from src.app.api import admin_api_router, metrics_api_router
from src.app.api import metrics as metrics_module
from src.app.api.middleware import auth as auth_module, AuthenticationMiddleware
from src.app.exceptions import InvalidAdminCredentials
from src.app.exceptions.classes import ErrorSpec
from src.app.exceptions.handlers import status_handler, validation_error_handler
from src.app.injector.dependency_container import DependencyContainer
from src.app.injector.inject import get_admin_adapter, get_metrics_adapter
from src.cache import RedisRepository
from src.cache.connection import CacheConnection
from src.utils.crypto import hash_password
from tests.conftest import FakeConfig

ADMIN_VIEW = {"requests": {"total": 3}, "teams": {"payments": {"requests": 3}}}
GATEWAY_VIEW = {"requests": {"total": 3}}


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(CacheConnection, "get_connection",
                        classmethod(lambda cls, t: FakeAsyncRedis(decode_responses=True)))
    token_repo = RedisRepository()

    auth_container = DependencyContainer()
    auth_container.register(RedisRepository, lambda: token_repo)
    monkeypatch.setattr(auth_module, "container", auth_container)

    async def one_event(adapter, identity, interval):
        yield f"event: metrics\ndata: {json.dumps(adapter.snapshot_for(identity))}\n\n"
    monkeypatch.setattr(metrics_module, "metrics_events", one_event)

    config = FakeConfig({"admin": {"username": "root", "password_hash": hash_password("correct horse")}})
    aggregator = MagicMock(snapshot=GATEWAY_VIEW, admin_snapshot=ADMIN_VIEW)

    app = FastAPI()
    app.include_router(admin_api_router)
    app.include_router(metrics_api_router)
    app.add_middleware(AuthenticationMiddleware)
    app.add_exception_handler(InvalidAdminCredentials,
                              status_handler(ErrorSpec(401, "invalid_request_error", "invalid_credentials")))
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.dependency_overrides[get_admin_adapter] = lambda: AdminAdapter(config, token_repo)
    app.dependency_overrides[get_metrics_adapter] = lambda: MetricsAdapter(aggregator)
    return TestClient(app)


def read_metrics(client, token):
    response = client.get("/api/v1/metrics", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    return json.loads(response.text.split("data: ", 1)[1])


def test_logging_in_needs_no_token_and_the_session_sees_the_full_metrics(client):
    login = client.post("/api/v1/admin/login", json={"username": "root", "password": "correct horse"})

    assert login.status_code == 200
    body = login.json()
    assert body["session_token"].startswith("tg_")
    assert (body["token_type"], body["expires_in"]) == ("bearer", 43_200)
    assert read_metrics(client, body["session_token"]) == ADMIN_VIEW


def test_wrong_credentials_are_an_openai_401(client):
    response = client.post("/api/v1/admin/login", json={"username": "root", "password": "guess"})

    assert response.status_code == 401
    assert response.json()["error"] == {
        "message": "Invalid admin username or password.", "type": "invalid_request_error", "param": None,
        "code": "invalid_credentials",
    }


@pytest.mark.parametrize("body", [{"username": "root"}, {"username": "", "password": "x"}])
def test_a_malformed_login_is_a_400(client, body):
    response = client.post("/api/v1/admin/login", json=body)

    assert response.status_code == 400


def test_the_metrics_still_need_a_token(client):
    assert client.get("/api/v1/metrics").status_code == 401
