from typing import override, Any

from src.app.ports import CacheRepositoryInterface
from src.utils.types import CacheType, ATOMIC_COUNTERS
from ..connection import CacheConnection

class RedisRepository(CacheRepositoryInterface):
    def __init__(self):
        self.cache_conn = CacheConnection.get_connection(CacheType.EXACT)

    @override
    async def check_token_validity(self, token: str) -> bool:
        cache_output: str = await self.cache_conn.get(f"token:{token}")
        return True if cache_output else False

    @override
    async def get_user_id(self, token: str) -> str:
        return await self.cache_conn.get(f"token:{token}")

    @override
    async def save(self, key: Any, value: Any, timeout: int | None = None) -> None:
        await self.cache_conn.set(key, value, ex=timeout)

    @override
    async def search(self, key: Any) -> Any:
        return await self.cache_conn.get(key)

    @override
    async def increment(self, key: ATOMIC_COUNTERS) -> None:
        _ = self.cache_conn.incr(key)

    @override
    async def decrement(self, key: ATOMIC_COUNTERS) -> None:
        _ = self.cache_conn.decr(key)

