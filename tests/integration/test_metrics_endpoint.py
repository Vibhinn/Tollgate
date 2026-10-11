import json
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.testclient import TestClient

from src.app.api import metrics as metrics_module
from src.app.api.metrics import metrics_api_router, metrics_events
from src.app.exceptions.handlers import validation_error_handler
from src.app.injector.inject import get_metrics_adapter
from src.utils.types import TokenIdentity

SNAPSHOT = {"uptime_seconds": 12, "requests": {"total": 3}}


@pytest.fixture
def metrics_adapter():
    adapter = MagicMock()
    adapter.snapshot_for.return_value = SNAPSHOT
    return adapter


def parse_events(body: str) -> list[tuple[str, dict]]:
    events = []
    for block in body.strip().split("\n\n"):
        fields = dict(line.split(": ", 1) for line in block.splitlines())
        events.append((fields["event"], json.loads(fields["data"])))
    return events


class EndOfTest(Exception):
    pass


async def test_the_stream_sends_a_snapshot_every_interval(metrics_adapter, monkeypatch):
    sleeps = []

    async def fake_sleep(seconds):
        sleeps.append(seconds)
        if len(sleeps) == 3:
            raise EndOfTest   # end the otherwise endless stream

    monkeypatch.setattr(metrics_module.asyncio, "sleep", fake_sleep)

    chunks = []
    with pytest.raises(EndOfTest):
        async for chunk in metrics_events(metrics_adapter, identity=None, interval=5):
            chunks.append(chunk)

    assert parse_events("".join(chunks)) == [("metrics", SNAPSHOT)] * 3
    assert sleeps == [5, 5, 5]


@pytest.fixture
def client(metrics_adapter, monkeypatch):
    async def one_event(adapter, identity, interval):
        yield f"event: metrics\ndata: {json.dumps(adapter.snapshot_for(identity))}\n\n"
    monkeypatch.setattr(metrics_module, "metrics_events", one_event)

    app = FastAPI()
    app.include_router(metrics_api_router)
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.dependency_overrides[get_metrics_adapter] = lambda: metrics_adapter
    return TestClient(app)


def test_the_endpoint_is_a_server_sent_event_stream(client):
    response = client.get("/api/v1/metrics")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert response.headers["cache-control"] == "no-cache"
    assert parse_events(response.text) == [("metrics", SNAPSHOT)]


@pytest.mark.parametrize("interval", ["0", "61", "abc"])
def test_an_out_of_range_interval_is_a_400(client, interval):
    response = client.get(f"/api/v1/metrics?interval={interval}")

    assert response.status_code == 400
    assert response.json()["error"]["param"] == "interval"


async def test_nothing_is_sent_until_the_first_snapshot_exists(metrics_adapter, monkeypatch):
    metrics_adapter.snapshot_for.side_effect = [None, SNAPSHOT]
    sleeps = []

    async def fake_sleep(seconds):
        sleeps.append(seconds)
        if len(sleeps) == 2:
            raise EndOfTest

    monkeypatch.setattr(metrics_module.asyncio, "sleep", fake_sleep)

    chunks = []
    with pytest.raises(EndOfTest):
        async for chunk in metrics_events(metrics_adapter, identity=None, interval=1):
            chunks.append(chunk)

    assert parse_events("".join(chunks)) == [("metrics", SNAPSHOT)]


def test_the_view_depends_on_the_token_that_opened_the_stream(metrics_adapter, monkeypatch):
    admin = TokenIdentity(user_id="ops:dashboard", team="ops", name="dashboard", token_id="abc123", role="admin")

    async def one_event(adapter, identity, interval):
        yield f"event: metrics\ndata: {json.dumps(adapter.snapshot_for(identity))}\n\n"
    monkeypatch.setattr(metrics_module, "metrics_events", one_event)

    app = FastAPI()
    app.include_router(metrics_api_router)
    app.dependency_overrides[get_metrics_adapter] = lambda: metrics_adapter

    @app.middleware("http")
    async def fake_auth(request, call_next):
        request.state.identity = admin
        return await call_next(request)

    TestClient(app).get("/api/v1/metrics")

    metrics_adapter.snapshot_for.assert_called_once_with(admin)
