from __future__ import annotations

import asyncio
import random
from typing import TYPE_CHECKING

from fastapi import FastAPI, Request
from starlette.responses import JSONResponse

from .base import BaseMiddleware
from .exemptions import EXEMPT_PATHS
from src.cache import RedisRepository
from src.utils.config import Config
from src.utils.types import ConfigurationSection, ConfigurationOption, RedisAtomicCounters

if TYPE_CHECKING:
    from src.app.ports import CacheRepositoryInterface

BASE_RETRY_AFTER_SECONDS: int = 2
RETRY_AFTER_JITTER_SECONDS: int = 2


class BackpressureMiddleware(BaseMiddleware):
    def __init__(self, app: FastAPI):
        self.app = app
        self.redis_repo: CacheRepositoryInterface = RedisRepository()
        self.max_in_flight: int = int(Config().get_config(ConfigurationSection.BACKPRESSURE, ConfigurationOption.MAX_IN_FLIGHT))

        @self.app.middleware("http")
        async def shed_load(request: Request, call_next):
            if request.url.path in EXEMPT_PATHS:
                return await call_next(request)

            try:
                in_flight: int = await self.redis_repo.increment(RedisAtomicCounters.IN_FLIGHT)
            except Exception:
                return JSONResponse(
                    status_code=503,
                    content={"detail": "Temporary downstream outage"}
                )

            if in_flight > self.max_in_flight:
                await self.redis_repo.decrement(RedisAtomicCounters.IN_FLIGHT)
                await self.redis_repo.increment(RedisAtomicCounters.SHED)
                retry_after: int = BASE_RETRY_AFTER_SECONDS + random.randint(0, RETRY_AFTER_JITTER_SECONDS)
                return JSONResponse(
                    status_code=503,
                    content={"detail": "Gateway is overloaded. Try again shortly."},
                    headers={"Retry-After": str(retry_after)},
                )

            try:
                return await call_next(request)
            finally:
                await asyncio.shield(self.redis_repo.decrement(RedisAtomicCounters.IN_FLIGHT))
