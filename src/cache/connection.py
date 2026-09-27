from __future__ import annotations

import redis.asyncio as redis
from qdrant_client import AsyncQdrantClient
from typing import overload, Literal, TYPE_CHECKING

from src.utils.types import CacheType, ConfigurationEnums, ConfigurationSection, ConfigurationOption

if TYPE_CHECKING:
    from src.utils.types import CACHE_TYPE
    from src.utils.config import Config

class CacheConnection:
    _redis_conn: redis.Redis = None
    _vector_db_conn: AsyncQdrantClient = None

    @classmethod
    def initialize(cls, config: Config):
        redis_password = config.get_config(ConfigurationSection.REDIS, ConfigurationOption.PASSWORD)
        cls._redis_conn = redis.Redis(
            host=config.get_config(ConfigurationSection.REDIS, ConfigurationOption.HOST),
            port=int(config.get_config(ConfigurationSection.REDIS, ConfigurationOption.PORT)),
            password=None if redis_password == ConfigurationEnums.API_KEY_NOT_CONFIGURED.value else redis_password,
            ssl=config.get_config(ConfigurationSection.REDIS, ConfigurationOption.TLS) == "true",
            decode_responses=True,
            socket_timeout=3.0,
            socket_connect_timeout=3.0,
            max_connections=1000,
        )

        qdrant_api_key = config.get_config(ConfigurationSection.QDRANT, ConfigurationOption.API_KEY)
        cls._vector_db_conn = AsyncQdrantClient(
            host=config.get_config(ConfigurationSection.QDRANT, ConfigurationOption.HOST),
            port=int(config.get_config(ConfigurationSection.QDRANT, ConfigurationOption.PORT)),
            api_key=None if qdrant_api_key == ConfigurationEnums.API_KEY_NOT_CONFIGURED.value else qdrant_api_key,
            https=config.get_config(ConfigurationSection.QDRANT, ConfigurationOption.HTTPS) == "true",
        )

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