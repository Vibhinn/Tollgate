import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import build.build
from build.build import Builder
from src.app.exceptions import (
    ModelSemanticNotFound, BadRequestToModel, RateLimitedFromModelProvider, APIKeyInvalidOrExpired,
    PermissionDeniedForModel, CreditExhaustion, ModelProviderServerError, APIError, NoHealthyModelAvailable,
)
from src.app.exceptions.handlers import status_handler, unexpected_error_handler
from tests.conftest import FakeConfig


@pytest.fixture
def builder(monkeypatch):
    # Builder() loads config.yaml, which tests never read
    monkeypatch.setattr(build.build, "Config", FakeConfig)
    return Builder(FastAPI())


@pytest.fixture
def raise_through_app(builder):
    def _raise(exception: Exception):
        for exception_class, error_spec in builder.exception_map.items():
            builder.app.add_exception_handler(exception_class, status_handler(error_spec))

        @builder.app.get("/boom")
        async def boom():
            raise exception

        return TestClient(builder.app).get("/boom")
    return _raise


@pytest.mark.parametrize("exception, expected_status, expected_type, expected_code", [
    (ModelSemanticNotFound("no such model"), 404, "invalid_request_error", "model_not_found"),
    (BadRequestToModel("context too long"), 400, "invalid_request_error", None),
    (RateLimitedFromModelProvider("slow down"), 429, "rate_limit_error", "upstream_rate_limited"),
    # gateway misconfiguration: the client's Tollgate token is fine, so never 401/403
    (APIKeyInvalidOrExpired("bad provider key"), 502, "api_error", "upstream_auth_failed"),
    (PermissionDeniedForModel("no access"), 502, "api_error", "upstream_permission_denied"),
    (CreditExhaustion("no credit"), 502, "api_error", "upstream_credit_exhausted"),
    (ModelProviderServerError("outage"), 502, "api_error", "upstream_server_error"),
    (APIError("connection reset"), 502, "api_error", "upstream_connection_error"),
])
def test_domain_exceptions_map_to_openai_errors(raise_through_app, exception, expected_status, expected_type, expected_code):
    response = raise_through_app(exception)

    assert response.status_code == expected_status
    assert response.json() == {
        "error": {"message": str(exception), "type": expected_type, "param": None, "code": expected_code}
    }


@pytest.mark.parametrize("bug", [KeyError("internal_key"), RuntimeError("db password is hunter2")])
def test_an_unexpected_error_is_an_openai_500_that_does_not_leak_details(bug):
    app = FastAPI()
    app.add_exception_handler(Exception, unexpected_error_handler)

    @app.get("/boom")
    async def boom():
        raise bug

    response = TestClient(app, raise_server_exceptions=False).get("/boom")

    assert response.status_code == 500
    assert response.json() == {"error": {
        "message": "The gateway hit an internal error.", "type": "server_error", "param": None, "code": "internal_error",
    }}


def test_no_healthy_model_is_a_503_that_tells_the_client_when_to_retry(raise_through_app):
    response = raise_through_app(NoHealthyModelAvailable("Every model is out of rotation. Retry in 12s.", 12))

    assert response.status_code == 503
    assert response.headers["Retry-After"] == "12"
    assert response.json()["error"]["code"] == "no_model_available"
