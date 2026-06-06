from typing import override, Any

from src.app.ports import CacheRepository
from ..connection import redis_client

class RedisRepository(CacheRepository):
    def __init__(self):
        self.cache_conn = redis_client

    async def check_token_validity(self, token: str) -> bool:
        return True if self.cache_conn.get(f"token:{token}") else False

    async def get_user_id(self, token: str) -> str:
        return self.cache_conn.get(f"token{token}")

    @override
    async def save(self, key: Any, value: Any, timeout: int | None = None) -> None:
        await self.cache_conn.set(key, value, ex=timeout)

    @override
    async def search(self, key: Any) -> Any:
        pass

