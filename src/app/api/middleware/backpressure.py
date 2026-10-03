from __future__ import annotations

import asyncio
import random
from typing import TYPE_CHECKING

from starlette.responses import JSONResponse

from .base import BaseMiddleware
from .exemptions import EXEMPT_PATHS
from src.cache import RedisRepository
from src.utils.config import Config
from src.utils.types import ConfigurationSection, ConfigurationOption, RedisAtomicCounters
from src.app.injector import container

if TYPE_CHECKING:
    from starlette.types import ASGIApp, Scope, Receive, Send
    from src.app.ports import CacheRepositoryInterface

BASE_RETRY_AFTER_SECONDS: int = 2
RETRY_AFTER_JITTER_SECONDS: int = 2


class BackpressureMiddleware(BaseMiddleware):
    def __init__(self, app: ASGIApp):
        self.app = app
        self.redis_repo: CacheRepositoryInterface = container.resolve(RedisRepository)
        self.configuration: Config = container.resolve(Config)
        self.max_in_flight: int = int(self.configuration.get_config(ConfigurationSection.BACKPRESSURE, ConfigurationOption.MAX_IN_FLIGHT))

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["path"] in EXEMPT_PATHS:
            await self.app(scope, receive, send)
            return

        try:
            in_flight: int = await self.redis_repo.increment(RedisAtomicCounters.IN_FLIGHT)
        except Exception:
            response = JSONResponse(
                status_code=503,
                content={"detail": "Temporary downstream outage"}
            )
            await response(scope, receive, send)
            return

        if in_flight > self.max_in_flight:
            await self.redis_repo.decrement(RedisAtomicCounters.IN_FLIGHT)
            await self.redis_repo.increment(RedisAtomicCounters.SHED)
            retry_after: int = BASE_RETRY_AFTER_SECONDS + random.randint(0, RETRY_AFTER_JITTER_SECONDS)
            response = JSONResponse(
                status_code=503,
                content={"detail": "Gateway is overloaded. Try again shortly."},
                headers={"Retry-After": str(retry_after)},
            )
            await response(scope, receive, send)
            return

        try:
            await self.app(scope, receive, send)
        finally:
            await asyncio.shield(self.redis_repo.decrement(RedisAtomicCounters.IN_FLIGHT))
