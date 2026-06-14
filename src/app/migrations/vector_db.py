from .base import BaseMigration
from src.cache import CacheConnection
from qdrant_client.models import VectorParams, Distance

class CreateSemanticCacheCollection(BaseMigration):
    def up(self):

        client = CacheConnection.get_connection("SEMANTIC")
        collections = client.get_collections().collections

        if not any(c.name == "semantic_cache" for c in collections):
            client.create_collection(
                collection_name="semantic_cache",
                vectors_config=VectorParams(size=256, distance=Distance.COSINE)
            )