import redis.asyncio as redis
from qdrant_client import QdrantClient
from typing import overload, Literal
from src.utils.types import CACHE_TYPE

class CacheConnection:
    _redis_conn: redis.Redis = None
    _vector_db_conn: QdrantClient = None

    @classmethod
    def initialize(cls):
        cls._redis_conn = redis.Redis(host="localhost", port=6333, decode_responses=True)
        cls._vector_db_conn = QdrantClient(host="localhost", port=6333)

    @overload
    @classmethod
    def get_connection(cls, connection_type: Literal["EXACT"]) -> redis.Redis: ...

    @overload
    @classmethod
    def get_connection(cls, connection_type: Literal["SEMANTIC"]) -> QdrantClient: ...

    @classmethod
    def get_connection(cls, connection_type: CACHE_TYPE):
        connection_map = {
            "EXACT": cls._redis_conn,
            "SEMANTIC": cls._vector_db_conn
        }
        return connection_map[connection_type]