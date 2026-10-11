from collections import Counter as Tally

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from src.app.api.middleware import request_metrics as request_metrics_module
from src.app.api.middleware import RequestMetricsMiddleware
from src.app.injector.dependency_container import DependencyContainer
from src.cache import RedisMetricsRepository
from src.utils.types import RedisAtomicCounters


class FakeMetricsRepo:
    def __init__(self):
        self.counts = Tally()
        self.fail = False

    async def increment(self, counter):
        if self.fail:
            raise ConnectionError("redis down")
        self.counts[counter] += 1


@pytest.fixture
def metrics_repo(monkeypatch):
    repo = FakeMetricsRepo()
    test_container = DependencyContainer()
    test_container.register(RedisMetricsRepository, lambda: repo)
    monkeypatch.setattr(request_metrics_module, "container", test_container)
    return repo


@pytest.fixture
def client(metrics_repo):
    app = FastAPI()

    @app.get("/v1/ok")
    async def ok():
        return {"ok": True}

    @app.get("/v1/missing")
    async def missing():
        raise HTTPException(status_code=404)

    @app.get("/v1/crash")
    async def crash():
        raise RuntimeError("bug")

    @app.get("/api/v1/metrics")
    async def metrics():
        return {}

    app.add_middleware(RequestMetricsMiddleware)
    return TestClient(app, raise_server_exceptions=False)


def test_responses_are_counted_by_status_class(client, metrics_repo):
    client.get("/v1/ok")
    client.get("/v1/ok")
    client.get("/v1/missing")
    client.get("/v1/crash")

    assert metrics_repo.counts == {
        RedisAtomicCounters.RESPONSES_2XX: 2,
        RedisAtomicCounters.RESPONSES_4XX: 1,
        RedisAtomicCounters.RESPONSES_5XX: 1,
    }


def test_docs_and_the_metrics_stream_are_not_counted(client, metrics_repo):
    client.get("/docs")
    client.get("/api/v1/metrics")

    assert metrics_repo.counts == {}


def test_a_metrics_outage_never_fails_the_request(client, metrics_repo):
    metrics_repo.fail = True

    assert client.get("/v1/ok").status_code == 200
