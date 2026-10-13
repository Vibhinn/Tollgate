from __future__ import annotations

import redis as redis_sync
import redis.asyncio as redis
from qdrant_client import AsyncQdrantClient
from typing import overload, Literal, TYPE_CHECKING

from src.utils.types import CacheType, ConfigurationEnums, ConfigurationSection, ConfigurationOption

if TYPE_CHECKING:
    from src.utils.types import CACHE_TYPE
    from src.utils.config import Config

class CacheConnection:
    _redis_conn: redis.Redis | None = None
    _vector_db_conn: AsyncQdrantClient | None = None

    @classmethod
    def initialize(cls, config: Config):
        cls._redis_conn = redis.Redis(**cls._redis_settings(config), max_connections=1000)

        qdrant_api_key = config.get_config(ConfigurationSection.QDRANT, ConfigurationOption.API_KEY)
        cls._vector_db_conn = AsyncQdrantClient(
            host=config.get_config(ConfigurationSection.QDRANT, ConfigurationOption.HOST),
            port=int(config.get_config(ConfigurationSection.QDRANT, ConfigurationOption.PORT)),
            api_key=None if qdrant_api_key == ConfigurationEnums.API_KEY_NOT_CONFIGURED.value else qdrant_api_key,
            https=config.get_config(ConfigurationSection.QDRANT, ConfigurationOption.HTTPS) == "true",
            pool_size=1000,
            prefer_grpc=True,
            check_compatibility=False,
        )

    @staticmethod
    def _redis_settings(config: Config) -> dict:
        redis_password = config.get_config(ConfigurationSection.REDIS, ConfigurationOption.PASSWORD)
        return {
            "host": config.get_config(ConfigurationSection.REDIS, ConfigurationOption.HOST),
            "port": int(config.get_config(ConfigurationSection.REDIS, ConfigurationOption.PORT)),
            "password": None if redis_password == ConfigurationEnums.API_KEY_NOT_CONFIGURED.value else redis_password,
            "ssl": config.get_config(ConfigurationSection.REDIS, ConfigurationOption.TLS) == "true",
            "decode_responses": True,
            "socket_timeout": 3.0,
            "socket_connect_timeout": 3.0,
        }

    @classmethod
    def create_sync_redis(cls, config: Config) -> redis_sync.Redis:
        """A blocking client, for code that runs on its own thread (the log shipper), not on the event loop."""
        return redis_sync.Redis(**cls._redis_settings(config))

    @overload
    @classmethod
    def get_connection(cls, connection_type: Literal[CacheType.EXACT]) -> redis.Redis: ...

    @overload
    @classmethod
    def get_connection(cls, connection_type: Literal[CacheType.SEMANTIC]) -> AsyncQdrantClient: ...

    @classmethod
    def get_connection(cls, connection_type: CACHE_TYPE) -> redis.Redis | AsyncQdrantClient:
        connection_map = {
            CacheType.EXACT: cls._redis_conn,
            CacheType.SEMANTIC: cls._vector_db_conn
        }
        conn = connection_map[connection_type]
        if conn is None:
            raise ValueError(f"Cache {connection_type} not initialized: call CacheConnection.initialize first")
        return conn