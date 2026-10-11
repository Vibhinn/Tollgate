from __future__ import annotations

import asyncio
import time
from typing import Any, TYPE_CHECKING

import psutil

from src.utils.types import RedisAtomicCounters as Counter

if TYPE_CHECKING:
    from src.router import RouterRepository
    from src.app.intelligence import RoutingIntelligenceLayer
    from ..ports import MetricsRepositoryInterface, RankingRepositoryInterface, VectorDBRepositoryInterface


class MetricsAdapter:
    """Builds one snapshot of the gateway's metrics. Each part is read on its own, so an outage
    (e.g. Redis down) shows up as null values and a "down" dependency instead of breaking the stream."""

    def __init__(self, metrics_repo: MetricsRepositoryInterface, ranking_repo: RankingRepositoryInterface,
                 vector_db_repo: VectorDBRepositoryInterface, router_manager: RouterRepository,
                 routing_intelligence: RoutingIntelligenceLayer):
        self.metrics_repo = metrics_repo
        self.ranking_repo = ranking_repo
        self.vector_db_repo = vector_db_repo
        self.router_repo = router_manager
        self.routing_intelligence = routing_intelligence
        self._process = psutil.Process()
        self._HEALTH_CHECK_TIMEOUT_SECONDS = 1.0
        self._LATENCY_RANKING_KEY = "model:ranking:latency"

    async def snapshot(self) -> dict[str, Any]:
        counters = await self._read(self.metrics_repo.read_counters())
        return {
            "uptime_seconds": int(time.time() - self._process.create_time()),
            "process": {
                # CPU used since the previous snapshot; the very first one reads 0.0
                "cpu_percent": self._process.cpu_percent(interval=None),
                "memory_mb": round(self._process.memory_info().rss / 1_048_576, 1),
            },
            "requests": self._requests(counters),
            "cache": self._cache(counters),
            "models": await self._models(),
            "dependencies": await self._dependencies(),
        }

    @staticmethod
    def _requests(counters: dict[str, int] | None) -> dict[str, int] | None:
        if counters is None:
            return None
        responses = {status: counters[counter] for status, counter in
                     (("2xx", Counter.RESPONSES_2XX), ("4xx", Counter.RESPONSES_4XX), ("5xx", Counter.RESPONSES_5XX))}
        return {
            "total": sum(responses.values()),
            **responses,
            "rate_limited": counters[Counter.RATE_LIMITED],
            "shed": counters[Counter.SHED],
            "in_flight": counters[Counter.IN_FLIGHT],
        }

    @staticmethod
    def _cache(counters: dict[str, int] | None) -> dict[str, int | float] | None:
        if counters is None:
            return None
        exact, semantic, misses = (counters[Counter.CACHE_EXACT_HITS], counters[Counter.CACHE_SEMANTIC_HITS],
                                   counters[Counter.CACHE_MISSES])
        lookups = exact + semantic + misses
        return {
            "exact_hits": exact,
            "semantic_hits": semantic,
            "misses": misses,
            "hit_rate": round((exact + semantic) / lookups, 4) if lookups else 0.0,
        }

    async def _models(self) -> dict[str, dict[str, Any]] | None:
        model_names = list(self.router_repo.available_models())
        stats = await self._read(self.metrics_repo.read_model_stats(model_names))
        available = await self._read(self.ranking_repo.filter_available(model_names))
        latencies = await self._read(asyncio.gather(
            *(self.ranking_repo.get_score(self._LATENCY_RANKING_KEY, name) for name in model_names)
        ))
        if stats is None or available is None or latencies is None:
            return None
        return {
            name: {
                **stats[name],
                "avg_latency_ms": round(latency) if latency is not None else None,
                # False while the model is benched after provider errors
                "available": name in available,
            }
            for name, latency in zip(model_names, latencies)
        }

    async def _dependencies(self) -> dict[str, str]:
        redis_ok, qdrant_ok = await asyncio.gather(self._ping(self.metrics_repo.ping()),
                                                   self._ping(self.vector_db_repo.ping()))
        return {
            "redis": "ok" if redis_ok else "down",
            "qdrant": "ok" if qdrant_ok else "down",
            # degraded: "smart" routes every prompt as SIMPLE
            "classifier": "ok" if self.routing_intelligence.available else "degraded",
        }

    async def _ping(self, check) -> bool:
        try:
            return await asyncio.wait_for(check, self._HEALTH_CHECK_TIMEOUT_SECONDS)
        except Exception:
            return False

    @staticmethod
    async def _read(awaitable):
        try:
            return await awaitable
        except Exception:
            return None
