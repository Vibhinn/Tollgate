from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.app.api.middleware import rate_limiting as rate_limiting_module
from src.app.api.middleware import auth as auth_module
from src.app.api.middleware import RateLimitingMiddleware, AuthenticationMiddleware
from src.app.api.limiter import RateLimiterStore
from src.app.injector.dependency_container import DependencyContainer
from src.cache import RedisRepository


class FakeBucket:
    def __init__(self, allowed=True, max_tokens=10, remaining=9, reset_time=1_100.0):
        self.max_tokens = max_tokens
        self._allowed = allowed
        self._remaining = remaining
        self._reset_time = reset_time

    def request_allowed(self):
        return self._allowed

    def get_remaining(self):
        return self._remaining

    def get_reset_time(self):
        return self._reset_time


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
def rate_limiter_store(test_container):
    store = MagicMock()
    test_container.register(RateLimiterStore, lambda: store)
    return store


@pytest.fixture
def build_client(redis_repo, rate_limiter_store):
    def _build(bucket: FakeBucket):
        rate_limiter_store.get_user_bucket.return_value = bucket

        app = FastAPI()

        @app.get("/api/v1/chat/completions")
        async def protected():
            return {"ok": True}

        @app.post("/api/v1/chat/generate")
        async def exempt():
            return {"ok": True}

        app.add_middleware(RateLimitingMiddleware)
        return TestClient(app)

    return _build


def test_exempt_path_bypasses_rate_limiting(build_client, redis_repo):
    client = build_client(FakeBucket(allowed=False))

    response = client.post("/api/v1/chat/generate")

    assert response.status_code == 200
    redis_repo.get_user_id.assert_not_called()


def test_missing_authorization_header_returns_401(build_client):
    client = build_client(FakeBucket())

    response = client.get("/api/v1/chat/completions")

    assert response.status_code == 401
    assert response.json() == {"detail": "No auth token in Header."}


def test_allowed_request_passes_through_with_rate_limit_headers(build_client):
    bucket = FakeBucket(allowed=True, max_tokens=10, remaining=9, reset_time=1_100.0)
    client = build_client(bucket)

    response = client.get("/api/v1/chat/completions", headers={"Authorization": "Bearer tg_good"})

    assert response.status_code == 200
    assert response.headers["X-RateLimit-Limit"] == "10"
    assert response.headers["X-RateLimit-Remaining"] == "9"
    assert response.headers["X-RateLimit-Reset"] == "1100"


def test_denied_request_returns_429_with_retry_after(build_client):
    bucket = FakeBucket(allowed=False, max_tokens=10, remaining=0, reset_time=1_100.0)
    client = build_client(bucket)

    response = client.get("/api/v1/chat/completions", headers={"Authorization": "Bearer tg_good"})

    assert response.status_code == 429
    assert response.json() == {"detail": "Too many requests. Try again later."}
    assert response.headers["X-RateLimit-Limit"] == "10"
    assert response.headers["X-RateLimit-Remaining"] == "0"
    assert "Retry-After" in response.headers


def test_bucket_is_looked_up_by_user_id_resolved_from_token(build_client, redis_repo, rate_limiter_store):
    redis_repo.get_user_id.return_value = "resolved-user-42"
    client = build_client(FakeBucket(allowed=True))

    client.get("/api/v1/chat/completions", headers={"Authorization": "Bearer tg_good"})

    redis_repo.get_user_id.assert_awaited_once_with("tg_good")
    rate_limiter_store.get_user_bucket.assert_called_once_with("resolved-user-42")


def test_auth_and_rate_limiting_together_look_the_token_up_once(redis_repo, rate_limiter_store, test_container, monkeypatch):
    monkeypatch.setattr(auth_module, "container", test_container)
    redis_repo.get_user_id.return_value = "resolved-user-42"
    rate_limiter_store.get_user_bucket.return_value = FakeBucket(allowed=True)

    app = FastAPI()

    @app.get("/api/v1/chat/completions")
    async def protected():
        return {"ok": True}

    # same order as production: auth runs first, rate limiting reuses its lookup
    app.add_middleware(RateLimitingMiddleware)
    app.add_middleware(AuthenticationMiddleware)

    response = TestClient(app).get("/api/v1/chat/completions", headers={"Authorization": "Bearer tg_good"})

    assert response.status_code == 200
    redis_repo.get_user_id.assert_awaited_once_with("tg_good")
    rate_limiter_store.get_user_bucket.assert_called_once_with("resolved-user-42")
