from typing import get_args

from .base import BaseMigration
from src.cache import CacheConnection
from qdrant_client.models import VectorParams, Distance
from src.utils.types import VECTOR_REPOSITORY_COLLECTIONS, CacheType

class CreateSemanticCacheCollection(BaseMigration):
    def up(self):

        client = CacheConnection.get_connection(CacheType.SEMANTIC)

        for required_collection in get_args(VECTOR_REPOSITORY_COLLECTIONS):
            if not client.collection_exists(required_collection):
                client.create_collection(
                    collection_name=required_collection,
                    vectors_config=VectorParams(size=256, distance=Distance.COSINE)
                )