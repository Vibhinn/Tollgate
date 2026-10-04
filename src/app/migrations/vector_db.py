from typing import get_args

from src.app.exceptions import SemanticCacheNotReachable
from .base import BaseMigration
from src.cache import CacheConnection
from qdrant_client.models import VectorParams, Distance, PayloadSchemaType
from src.utils.types import VECTOR_REPOSITORY_COLLECTIONS, CacheType, VectorRepositoryCollection

class CreateSemanticCacheCollection(BaseMigration):
    async def up(self):
        try:
            client = CacheConnection.get_connection(CacheType.SEMANTIC)

            for required_collection in get_args(VECTOR_REPOSITORY_COLLECTIONS):
                collection_exists: bool = await client.collection_exists(required_collection)

                if not collection_exists:
                    await client.create_collection(
                        collection_name=required_collection,
                        vectors_config=VectorParams(size=256, distance=Distance.COSINE)
                    )

            await client.create_payload_index(
                collection_name=VectorRepositoryCollection.SEMANTIC_CACHE,
                field_name="context_hash",
                field_schema=PayloadSchemaType.KEYWORD,
            )

        except Exception as e:
            raise SemanticCacheNotReachable("The semantic cache is not reachable. Please try again") from e