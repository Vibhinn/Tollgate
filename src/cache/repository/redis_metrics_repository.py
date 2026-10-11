from typing import override

from src.app.ports import MetricsRepositoryInterface
from src.utils.types import CacheType, RedisAtomicCounters, ATOMIC_COUNTERS

from ..connection import CacheConnection

_MODEL_STATS_KEY_PREFIX = "model:stats:"
_MODEL_STAT_FIELDS = ("requests", "errors", "input_tokens", "output_tokens")


class RedisMetricsRepository(MetricsRepositoryInterface):
    def __init__(self):
        self.cache_conn = CacheConnection.get_connection(CacheType.EXACT)

    @override
    async def increment(self, counter: ATOMIC_COUNTERS) -> None:
        await self.cache_conn.incr(counter)

    @override
    async def record_model_call(self, model_name: str, input_tokens: int, output_tokens: int) -> None:
        key = f"{_MODEL_STATS_KEY_PREFIX}{model_name}"
        pipe = self.cache_conn.pipeline(transaction=False)
        pipe.hincrby(key, "requests", 1)
        pipe.hincrby(key, "input_tokens", input_tokens)
        pipe.hincrby(key, "output_tokens", output_tokens)
        await pipe.execute()

    @override
    async def record_model_error(self, model_name: str) -> None:
        await self.cache_conn.hincrby(f"{_MODEL_STATS_KEY_PREFIX}{model_name}", "errors", 1)

    @override
    async def read_counters(self) -> dict[str, int]:
        names = [counter.value for counter in RedisAtomicCounters]
        values = await self.cache_conn.mget(names)
        return {name: int(value or 0) for name, value in zip(names, values)}

    @override
    async def read_model_stats(self, model_names: list[str]) -> dict[str, dict[str, int]]:
        if not model_names:
            return {}
        pipe = self.cache_conn.pipeline(transaction=False)
        for model_name in model_names:
            pipe.hgetall(f"{_MODEL_STATS_KEY_PREFIX}{model_name}")
        rows = await pipe.execute()
        return {
            model_name: {field: int(row.get(field, 0)) for field in _MODEL_STAT_FIELDS}
            for model_name, row in zip(model_names, rows)
        }

    @override
    async def ping(self) -> bool:
        try:
            return bool(await self.cache_conn.ping())
        except Exception:
            return False
