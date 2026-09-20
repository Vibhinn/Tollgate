from unittest.mock import AsyncMock

import pytest

from src.cache.connection import CacheConnection
from src.app.migrations.vector_db import CreateSemanticCacheCollection


@pytest.fixture
def qdrant_client(monkeypatch):
    client = AsyncMock()
    monkeypatch.setattr(CacheConnection, "get_connection", classmethod(lambda cls, t: client))
    return client


async def test_creates_missing_collections(qdrant_client):
    qdrant_client.collection_exists.return_value = False

    await CreateSemanticCacheCollection().up()

    created_names = {call.kwargs["collection_name"] for call in qdrant_client.create_collection.call_args_list}
    assert created_names == {"semantic_cache", "intelligence_classifier_cache"}


async def test_skips_existing_collections(qdrant_client):
    qdrant_client.collection_exists.return_value = True

    await CreateSemanticCacheCollection().up()

    qdrant_client.create_collection.assert_not_awaited()


async def test_vector_params_use_256_dim_cosine_distance(qdrant_client):
    from qdrant_client.models import Distance

    qdrant_client.collection_exists.return_value = False

    await CreateSemanticCacheCollection().up()

    vectors_config = qdrant_client.create_collection.call_args_list[0].kwargs["vectors_config"]
    assert vectors_config.size == 256
    assert vectors_config.distance == Distance.COSINE
