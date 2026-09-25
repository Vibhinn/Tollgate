from typing import get_args

from src.app.exceptions import SemanticCacheNotReachable
from .base import BaseMigration
from src.cache import CacheConnection
from qdrant_client.models import VectorParams, Distance
from src.utils.types import VECTOR_REPOSITORY_COLLECTIONS, CacheType
from src.utils.decorators import throws_exception

@throws_exception(ValueError)
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

        except Exception as e:
            raise SemanticCacheNotReachable("The semantic cache is not reachable. Please try again") from e