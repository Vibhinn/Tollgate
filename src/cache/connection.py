import redis.asyncio as redis
from qdrant_client import AsyncQdrantClient
from typing import overload, Literal, TYPE_CHECKING

from src.utils.types import CacheType

if TYPE_CHECKING:
    from src.utils.types import CACHE_TYPE

class CacheConnection:
    _redis_conn: redis.Redis = None
    _vector_db_conn: AsyncQdrantClient = None

    @classmethod
    def initialize(cls):
        cls._redis_conn = redis.Redis(host="localhost", port=6379, decode_responses=True)
        cls._vector_db_conn = AsyncQdrantClient(host="localhost", port=6333)

    @overload
    @classmethod
    def get_connection(cls, connection_type: Literal[CacheType.EXACT]) -> redis.Redis: ...

    @overload
    @classmethod
    def get_connection(cls, connection_type: Literal[CacheType.SEMANTIC]) -> AsyncQdrantClient: ...

    @classmethod
    def get_connection(cls, connection_type: CACHE_TYPE):
        connection_map = {
            CacheType.EXACT: cls._redis_conn,
            CacheType.SEMANTIC: cls._vector_db_conn
        }
        return connection_map[connection_type]