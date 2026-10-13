from __future__ import annotations

import redis.asyncio as redis

from typing import TYPE_CHECKING

from src.cache import CacheConnection
from src.utils.types import CacheType, QueueType

if TYPE_CHECKING:
    from src.utils.types import QUEUE_TYPE

class JobQueueConnection:
    _redis_stream_conn: redis.Redis | None = None

    @classmethod
    def initialize(cls):
        cls._redis_stream_conn = CacheConnection.get_connection(CacheType.EXACT)

    @classmethod
    def get_connection(cls, queue_type: QUEUE_TYPE) -> redis.Redis:
        connection_map = {
            QueueType.REDIS_STREAM: cls._redis_stream_conn
        }
        conn = connection_map.get(queue_type)
        if not conn:
            raise ValueError(f"Queue {queue_type} not initialized or unknown")
        return conn
