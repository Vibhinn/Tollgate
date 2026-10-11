import pytest
from fastapi import FastAPI, HTTPException, Request
from fastapi.testclient import TestClient

from src.app.api.middleware import request_metrics as request_metrics_module
from src.app.api.middleware import RequestMetricsMiddleware
from src.app.injector.dependency_container import DependencyContainer
from src.jobs import RedisStreamRepository
from src.utils.types import LLMInvocationResult, TokenIdentity

ALICE = TokenIdentity(user_id="payments:alice", team="payments", name="alice", token_id="e72bb248c316", role="user")


class FakeJobQueue:
    def __init__(self):
        self.jobs = []
        self.fail = False

    async def create_job(self, stream, data):
        if self.fail:
            raise ConnectionError("redis down")
        self.jobs.append((stream, data))


@pytest.fixture
def job_queue(monkeypatch):
    queue = FakeJobQueue()
    test_container = DependencyContainer()
    test_container.register(RedisStreamRepository, lambda: queue)
    monkeypatch.setattr(request_metrics_module, "container", test_container)
    return queue


@pytest.fixture
def client(job_queue):
    app = FastAPI()

    @app.get("/v1/answer")
    async def answer(request: Request):
        # what auth and the chat endpoint leave in the request state
        request.state.identity = ALICE
        request.state.completion = LLMInvocationResult("hi", 12, 5, model="gpt-4o", cache_outcome="miss")
        return {"ok": True}

    @app.get("/v1/cached")
    async def cached(request: Request):
        request.state.identity = ALICE
        request.state.completion = LLMInvocationResult("hi", 0, 0, model="cheap", cache_outcome="semantic_hit")
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


def only_event(job_queue):
    assert len(job_queue.jobs) == 1
    stream, event = job_queue.jobs[0]
    assert stream == "analytics"
    return event


def test_an_answered_request_becomes_one_event_with_who_what_and_how_much(client, job_queue):
    client.get("/v1/answer")

    event = only_event(job_queue)
    assert {key: value for key, value in event.items() if key != "timestamp"} == {
        "kind": "request", "status": 200, "rejected_by": None, "cache_outcome": "miss", "model": "gpt-4o",
        "input_tokens": 12, "output_tokens": 5, "team": "payments", "name": "alice", "token_id": "e72bb248c316",
    }


def test_a_cache_hit_records_no_model(client, job_queue):
    client.get("/v1/cached")

    event = only_event(job_queue)
    assert (event["cache_outcome"], event["model"]) == ("semantic_hit", None)


@pytest.mark.parametrize("path, status", [("/v1/missing", 404), ("/v1/crash", 500)])
def test_failures_are_events_too_without_an_identity(client, job_queue, path, status):
    client.get(path)

    event = only_event(job_queue)
    assert (event["status"], event["team"], event["model"]) == (status, None, None)


def test_docs_and_the_metrics_stream_are_not_events(client, job_queue):
    client.get("/docs")
    client.get("/api/v1/metrics")

    assert job_queue.jobs == []


def test_a_metrics_outage_never_fails_the_request(client, job_queue):
    job_queue.fail = True

    assert client.get("/v1/answer").status_code == 200
