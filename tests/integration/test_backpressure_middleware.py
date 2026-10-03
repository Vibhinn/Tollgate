import asyncio
from collections import defaultdict

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.app.api.middleware import backpressure as backpressure_module
from src.app.api.middleware import BackpressureMiddleware
from src.utils.types import RedisAtomicCounters


class FakeCounterRepo:
    """Behaves like redis INCR/DECR so the counter logic is tested, not mocked away."""

    def __init__(self):
        self.counters: dict[str, int] = defaultdict(int)
        self.fail = False

    async def increment(self, key):
        if self.fail:
            raise ConnectionError("redis down")
        self.counters[key] += 1
        return self.counters[key]

    async def decrement(self, key):
        self.counters[key] -= 1
        return self.counters[key]


class FakeConfig:
    def __init__(self, data: dict):
        self._data = data

    def get_config(self, section, option):
        return self._data[section][option]


@pytest.fixture
def redis_repo(monkeypatch):
    repo = FakeCounterRepo()
    monkeypatch.setattr(backpressure_module, "RedisRepository", lambda: repo)
    return repo


@pytest.fixture
def build_client(redis_repo, monkeypatch):
    def _build(max_in_flight: int = 2, handler=None):
        monkeypatch.setattr(backpressure_module, "Config", lambda: FakeConfig({"backpressure": {"max_in_flight": str(max_in_flight)}}))

        app = FastAPI()

        @app.get("/api/v1/chat/completions")
        async def protected():
            if handler:
                return await handler()
            return {"ok": True}

        @app.post("/api/v1/chat/generate")
        async def exempt():
            return {"ok": True}

        BackpressureMiddleware(app)
        return TestClient(app, raise_server_exceptions=False)

    return _build


def test_request_under_limit_passes_and_releases_its_slot(build_client, redis_repo):
    client = build_client(max_in_flight=2)

    response = client.get("/api/v1/chat/completions")

    assert response.status_code == 200
    assert redis_repo.counters[RedisAtomicCounters.IN_FLIGHT] == 0
    assert redis_repo.counters[RedisAtomicCounters.SHED] == 0


def test_request_over_limit_is_shed_with_retry_after(build_client, redis_repo):
    client = build_client(max_in_flight=2)
    redis_repo.counters[RedisAtomicCounters.IN_FLIGHT] = 2  # two requests already being processed

    response = client.get("/api/v1/chat/completions")

    assert response.status_code == 503
    assert response.json() == {"detail": "Gateway is overloaded. Try again shortly."}
    retry_after = int(response.headers["Retry-After"])
    assert backpressure_module.BASE_RETRY_AFTER_SECONDS <= retry_after <= (
        backpressure_module.BASE_RETRY_AFTER_SECONDS + backpressure_module.RETRY_AFTER_JITTER_SECONDS
    )
    assert redis_repo.counters[RedisAtomicCounters.IN_FLIGHT] == 2  # shed request gave its slot back
    assert redis_repo.counters[RedisAtomicCounters.SHED] == 1


def test_slot_is_released_when_handler_raises(build_client, redis_repo):
    async def boom():
        raise RuntimeError("provider exploded")

    client = build_client(max_in_flight=2, handler=boom)

    response = client.get("/api/v1/chat/completions")

    assert response.status_code == 500
    assert redis_repo.counters[RedisAtomicCounters.IN_FLIGHT] == 0


def test_concurrent_requests_beyond_limit_are_shed(redis_repo, monkeypatch):
    monkeypatch.setattr(backpressure_module, "Config", lambda: FakeConfig({"backpressure": {"max_in_flight": "2"}}))
    release = asyncio.Event()

    app = FastAPI()

    @app.get("/api/v1/chat/completions")
    async def slow():
        await release.wait()
        return {"ok": True}

    BackpressureMiddleware(app)

    async def run():
        import httpx
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            first_two = [asyncio.create_task(client.get("/api/v1/chat/completions")) for _ in range(2)]
            while redis_repo.counters[RedisAtomicCounters.IN_FLIGHT] < 2:
                await asyncio.sleep(0)
            third = await client.get("/api/v1/chat/completions")
            release.set()
            return third, await asyncio.gather(*first_two)

    third, first_two = asyncio.run(run())

    assert third.status_code == 503
    assert [r.status_code for r in first_two] == [200, 200]
    assert redis_repo.counters[RedisAtomicCounters.IN_FLIGHT] == 0


def test_exempt_path_skips_backpressure(build_client, redis_repo):
    client = build_client(max_in_flight=1)
    redis_repo.counters[RedisAtomicCounters.IN_FLIGHT] = 5

    response = client.post("/api/v1/chat/generate")

    assert response.status_code == 200
    assert redis_repo.counters[RedisAtomicCounters.IN_FLIGHT] == 5


def test_redis_down_fails_closed_without_reaching_the_handler(build_client, redis_repo):
    handler_called = False

    async def handler():
        nonlocal handler_called
        handler_called = True
        return {"ok": True}

    client = build_client(max_in_flight=1, handler=handler)
    redis_repo.fail = True

    response = client.get("/api/v1/chat/completions")

    assert response.status_code == 503
    assert handler_called is False


def test_max_in_flight_is_read_from_config(build_client, redis_repo):
    client = build_client(max_in_flight=120)
    redis_repo.counters[RedisAtomicCounters.IN_FLIGHT] = 119

    assert client.get("/api/v1/chat/completions").status_code == 200

    redis_repo.counters[RedisAtomicCounters.IN_FLIGHT] = 120

    assert client.get("/api/v1/chat/completions").status_code == 503
