from watchfiles import awatch

from src.app.ports import RankingRepositoryInterface

from ..connection import CacheConnection

class RedisRankingRepository(RankingRepositoryInterface):
    def __init__(self):
        self.cache_conn = CacheConnection.get_connection("EXACT")

    async def update_score(self, key: str, member: str, score: float) -> None:
        await self.cache_conn.zadd(key, {member: score})

    async def get_score(self, key: str, member: str) -> float | None:
        return await self.cache_conn.zscore(key, member)

    async def get_top(self, key):
        result = await self.cache_conn.zrange(key, 0, 0)
        return result[0] if result else None