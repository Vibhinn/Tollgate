import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import build.build
from build.build import Builder
from src.app.exceptions import (
    ModelSemanticNotFound, BadRequestToModel, RateLimitedFromModelProvider, APIKeyInvalidOrExpired,
    PermissionDeniedForModel, CreditExhaustion, ModelProviderServerError, APIError,
)
from tests.conftest import FakeConfig


@pytest.fixture
def builder(monkeypatch):
    # Builder() loads config.yaml, which tests never read
    monkeypatch.setattr(build.build, "Config", FakeConfig)
    return Builder(FastAPI())


@pytest.fixture
def raise_through_app(builder):
    def _raise(exception: Exception):
        for exception_class, status_code in builder.exception_map.items():
            builder.app.add_exception_handler(exception_class, builder.status_handler(status_code))

        @builder.app.get("/boom")
        async def boom():
            raise exception

        return TestClient(builder.app).get("/boom")
    return _raise


@pytest.mark.parametrize("exception, expected_status", [
    (ModelSemanticNotFound("no such model"), 404),
    (BadRequestToModel("context too long"), 400),
    (RateLimitedFromModelProvider("slow down"), 429),
    # gateway misconfiguration: the client's Tollgate token is fine, so never 401/403
    (APIKeyInvalidOrExpired("bad provider key"), 502),
    (PermissionDeniedForModel("no access"), 502),
    (CreditExhaustion("no credit"), 502),
    (ModelProviderServerError("outage"), 500),
    (APIError("connection reset"), 500),
])
def test_domain_exceptions_map_to_the_right_status(raise_through_app, exception, expected_status):
    response = raise_through_app(exception)

    assert response.status_code == expected_status
    assert response.json() == {"detail": str(exception)}
