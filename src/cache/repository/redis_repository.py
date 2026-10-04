import json
from typing import override, Any

from src.app.ports import CacheRepositoryInterface
from src.utils.types import CacheType, ATOMIC_COUNTERS
from src.utils.tokens import hash_token, token_key
from ..connection import CacheConnection

class RedisRepository(CacheRepositoryInterface):
    def __init__(self):
        self.cache_conn = CacheConnection.get_connection(CacheType.EXACT)

    @override
    async def get_user_id(self, token: str) -> str | None:
        stored = await self.cache_conn.get(token_key(hash_token(token)))
        if not stored:
            return None
        try:
            return json.loads(stored).get("user_id")
        except (ValueError, AttributeError):
            return None

    @override
    async def save(self, key: Any, value: Any, timeout: int | None = None) -> None:
        await self.cache_conn.set(key, value, ex=timeout)

    @override
    async def search(self, key: Any) -> Any:
        return await self.cache_conn.get(key)

    @override
    async def increment(self, key: ATOMIC_COUNTERS) -> int:
        return await self.cache_conn.incr(key)

    @override
    async def decrement(self, key: ATOMIC_COUNTERS) -> int:
        return await self.cache_conn.decr(key)

