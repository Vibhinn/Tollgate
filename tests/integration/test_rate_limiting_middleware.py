import time
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.app.api.middleware import rate_limiting as rate_limiting_module
from src.app.api.middleware import auth as auth_module
from src.app.api.middleware import RateLimitingMiddleware, AuthenticationMiddleware
from src.app.injector.dependency_container import DependencyContainer
from src.cache import RedisRepository, RedisRateLimiter
from src.utils.types import TokenIdentity, RateLimitDecision

ALLOWED = RateLimitDecision(allowed=True, limit=10, remaining=9, reset_at=1_100.0)


@pytest.fixture
def test_container(monkeypatch):
    """Isolated container so fakes never leak into the app-wide one."""
    test_container = DependencyContainer()
    monkeypatch.setattr(rate_limiting_module, "container", test_container)
    return test_container


@pytest.fixture
def redis_repo(test_container):
    repo = AsyncMock()
    repo.get_user_id.return_value = "user-1"
    test_container.register(RedisRepository, lambda: repo)
    return repo


@pytest.fixture
def rate_limiter(test_container):
    limiter = AsyncMock()
    limiter.acquire.return_value = ALLOWED
    test_container.register(RedisRateLimiter, lambda: limiter)
    return limiter


def build_app() -> FastAPI:
    app = FastAPI()

    @app.get("/api/v1/chat/completions")
    async def protected():
        return {"ok": True}

    app.add_middleware(RateLimitingMiddleware)
    return app


@pytest.fixture
def client(redis_repo, rate_limiter):
    return TestClient(build_app())


def test_exempt_path_bypasses_rate_limiting(client, redis_repo, rate_limiter):
    response = client.get("/docs")

    assert response.status_code == 200
    redis_repo.get_user_id.assert_not_called()
    rate_limiter.acquire.assert_not_awaited()


def test_missing_authorization_header_returns_401(client):
    response = client.get("/api/v1/chat/completions")

    assert response.status_code == 401
    assert response.json() == {"error": {"message": "Missing bearer token in the Authorization header.", "type": "invalid_request_error", "param": None, "code": "invalid_api_key"}}


def test_allowed_request_passes_through_with_rate_limit_headers(client):
    response = client.get("/api/v1/chat/completions", headers={"Authorization": "Bearer tg_good"})

    assert response.status_code == 200
    assert response.headers["X-RateLimit-Limit"] == "10"
    assert response.headers["X-RateLimit-Remaining"] == "9"
    assert response.headers["X-RateLimit-Reset"] == "1100"


def test_denied_request_returns_429_with_retry_after_until_the_next_refill(client, rate_limiter):
    rate_limiter.acquire.return_value = RateLimitDecision(allowed=False, limit=10, remaining=0,
                                                          reset_at=time.time() + 2.3)

    response = client.get("/api/v1/chat/completions", headers={"Authorization": "Bearer tg_good"})

    assert response.status_code == 429
    assert response.json() == {"error": {"message": "Too many requests. Try again later.", "type": "rate_limit_error", "param": None, "code": "rate_limit_exceeded"}}
    assert response.headers["X-RateLimit-Limit"] == "10"
    assert response.headers["X-RateLimit-Remaining"] == "0"
    assert response.headers["Retry-After"] == "3"     # rounded up, never 0


def test_the_bucket_is_the_user_id_resolved_from_the_token(client, redis_repo, rate_limiter):
    redis_repo.get_user_id.return_value = "resolved-user-42"

    client.get("/api/v1/chat/completions", headers={"Authorization": "Bearer tg_good"})

    redis_repo.get_user_id.assert_awaited_once_with("tg_good")
    rate_limiter.acquire.assert_awaited_once_with("resolved-user-42")


def test_a_limiter_outage_lets_requests_through(client, rate_limiter):
    rate_limiter.acquire.side_effect = ConnectionError("redis down")

    response = client.get("/api/v1/chat/completions", headers={"Authorization": "Bearer tg_good"})

    assert response.status_code == 200
    assert "X-RateLimit-Limit" not in response.headers


def test_auth_and_rate_limiting_together_look_the_token_up_once(redis_repo, rate_limiter, test_container, monkeypatch):
    monkeypatch.setattr(auth_module, "container", test_container)
    redis_repo.get_identity.return_value = TokenIdentity(user_id="resolved-user-42", team="t", name="n",
                                                         token_id="abc", role="user")
    app = build_app()
    # same order as production: auth runs first, rate limiting reuses its lookup
    app.add_middleware(AuthenticationMiddleware)

    response = TestClient(app).get("/api/v1/chat/completions", headers={"Authorization": "Bearer tg_good"})

    assert response.status_code == 200
    redis_repo.get_identity.assert_awaited_once_with("tg_good")
    redis_repo.get_user_id.assert_not_awaited()
    rate_limiter.acquire.assert_awaited_once_with("resolved-user-42")


def test_a_rate_limited_request_is_marked_for_the_metrics_event(redis_repo, rate_limiter):
    rate_limiter.acquire.return_value = RateLimitDecision(allowed=False, limit=10, remaining=0, reset_at=time.time())
    seen_state = {}
    app = build_app()

    async def outer(scope, receive, send):   # stands in for RequestMetricsMiddleware
        await app(scope, receive, send)
        seen_state.update(scope.get("state", {}))

    response = TestClient(outer).get("/api/v1/chat/completions", headers={"Authorization": "Bearer tg_good"})

    assert response.status_code == 429
    assert seen_state["rejected_by"] == "rate_limit"
