from src.app.ports import RankingRepositoryInterface
from src.utils.types import CacheType

from ..connection import CacheConnection

_UNAVAILABLE_KEY_PREFIX = "model:unavailable:"


class RedisRankingRepository(RankingRepositoryInterface):
    def __init__(self):
        self.cache_conn = CacheConnection.get_connection(CacheType.EXACT)

    async def update_score(self, key: str, member: str, score: float) -> None:
        await self.cache_conn.zadd(key, {member: score})

    async def get_score(self, key: str, member: str) -> float | None:
        return await self.cache_conn.zscore(key, member)

    async def get_top(self, key):
        result = await self.cache_conn.zrange(key, 0, 0)
        return result[0] if result else None

    async def get_top_available(self, key: str, limit: int = 10) -> str | None:
        candidates = await self.cache_conn.zrange(key, 0, limit - 1)
        available = await self.filter_available(candidates)
        return available[0] if available else None

    async def mark_unavailable(self, model_name: str, ttl: int) -> None:
        await self.cache_conn.set(f"{_UNAVAILABLE_KEY_PREFIX}{model_name}", "1", ex=ttl)

    async def filter_available(self, model_names: list[str]) -> list[str]:
        if not model_names:
            return []
        flags = await self.cache_conn.mget([f"{_UNAVAILABLE_KEY_PREFIX}{name}" for name in model_names])
        return [name for name, flag in zip(model_names, flags) if flag is None]