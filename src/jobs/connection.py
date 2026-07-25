import redis

from typing import overload, Literal, TYPE_CHECKING

from src.cache import CacheConnection
from src.utils.types import CacheType, QueueType

if TYPE_CHECKING:
    from src.utils.types import QUEUE_TYPE

class JobQueueConnection:
    _redis_stream_conn: redis.Redis = None

    @classmethod
    def initialize(cls):
        cls._redis_stream_conn = CacheConnection.get_connection(CacheType.EXACT)

    @overload
    @classmethod
    def get_connection(cls, queue_type: Literal[QueueType.REDIS_STREAM]) -> redis.Redis: ...

    @classmethod
    def get_connection(cls, queue_type: QUEUE_TYPE):
        connection_map = {
            QueueType.REDIS_STREAM: cls._redis_stream_conn
        }
        conn = connection_map.get(queue_type)
        if not conn:
            raise ValueError(f"Queue {queue_type} not initialized or unknown")
        return conn
