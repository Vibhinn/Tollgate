from __future__ import annotations

import time
from typing import TYPE_CHECKING

from starlette.datastructures import Headers, MutableHeaders
from starlette.responses import JSONResponse

from .base import BaseMiddleware, TOKEN_VALUE_STATE_KEY
from ..limiter.store import RateLimiterStore
from src.cache import RedisRepository
from .exemptions import EXEMPT_PATHS

from src.utils.types import RedisAtomicCounters
from src.app.injector import container

if TYPE_CHECKING:
    from starlette.types import ASGIApp, Scope, Receive, Send, Message
    from src.app.ports import CacheRepositoryInterface


class RateLimitingMiddleware(BaseMiddleware):
    def __init__(self, app: ASGIApp):
        self.app = app
        self.rate_limiter: RateLimiterStore = container.resolve(RateLimiterStore)
        self.redis_repo: CacheRepositoryInterface = container.resolve(RedisRepository)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        if scope["path"] in EXEMPT_PATHS:
            await self.redis_repo.increment(RedisAtomicCounters.SUCCESSFUL)
            await self.app(scope, receive, send)
            return

        auth_header: str | None = Headers(scope=scope).get("Authorization")

        if not auth_header:
            await self.redis_repo.increment(RedisAtomicCounters.REJECTED)
            await JSONResponse(
                status_code=401,
                content={"detail":"No auth token in Header."}
            )(scope, receive, send)
            return

        user_id: str | None = scope.get("state", {}).get(TOKEN_VALUE_STATE_KEY)
        if user_id is None:
            user_id = await self.redis_repo.get_user_id(auth_header.removeprefix("Bearer "))

        bucket = self.rate_limiter.get_user_bucket(user_id)

        if not bucket.request_allowed():
            await self.redis_repo.increment(RedisAtomicCounters.RATE_LIMITED)
            retry_after = bucket.get_reset_time() - time.time()
            await JSONResponse(
                status_code=429,
                content={"detail": "Too many requests. Try again later."},
                headers={
                    "Retry-After": str(max(1, int(retry_after))),
                    "X-RateLimit-Limit": str(bucket.max_tokens),
                    "X-RateLimit-Remaining": str(bucket.get_remaining()),
                    "X-RateLimit-Reset": str(int(bucket.get_reset_time())),
                },
            )(scope, receive, send)
            return

        async def send_with_rate_limit_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                headers["X-RateLimit-Limit"] = str(bucket.max_tokens)
                headers["X-RateLimit-Remaining"] = str(bucket.get_remaining())
                headers["X-RateLimit-Reset"] = str(int(bucket.get_reset_time()))
            await send(message)

        await self.app(scope, receive, send_with_rate_limit_headers)
        await self.redis_repo.increment(RedisAtomicCounters.SUCCESSFUL)
