from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.app.api.models import models_api_router
from src.app.injector.inject import get_models_adapter


@pytest.fixture
def models_adapter():
    adapter = MagicMock()
    adapter.list_models.return_value = {"cheap": "tollgate", "gpt-4o": "openai"}
    return adapter


@pytest.fixture
def client(models_adapter):
    app = FastAPI()
    app.include_router(models_api_router)
    app.dependency_overrides[get_models_adapter] = lambda: models_adapter
    return TestClient(app)


def test_models_endpoint_lists_models_in_openai_format(client):
    response = client.get("/v1/models")

    assert response.status_code == 200
    body = response.json()
    assert body["object"] == "list"
    assert [(model["id"], model["owned_by"], model["object"]) for model in body["data"]] == [
        ("cheap", "tollgate", "model"), ("gpt-4o", "openai", "model"),
    ]
    assert all(isinstance(model["created"], int) for model in body["data"])


def test_models_endpoint_returns_an_empty_list_when_nothing_is_available(client, models_adapter):
    models_adapter.list_models.return_value = {}

    assert client.get("/v1/models").json() == {"object": "list", "data": []}
