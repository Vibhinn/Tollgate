from __future__ import annotations

import logging
import math
import time
from typing import TYPE_CHECKING

from starlette.datastructures import Headers, MutableHeaders

from .base import BaseMiddleware, TOKEN_VALUE_STATE_KEY, REJECTED_BY_STATE_KEY
from src.cache import RedisRepository, RedisRateLimiter
from .exemptions import EXEMPT_PATHS
from src.app.exceptions.handlers import openai_error

from src.app.injector import container

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from starlette.types import ASGIApp, Scope, Receive, Send, Message
    from src.app.ports import CacheRepositoryInterface, RateLimiterInterface
    from src.utils.types import RateLimitDecision


class RateLimitingMiddleware(BaseMiddleware):
    def __init__(self, app: ASGIApp):
        self.app = app
        self.rate_limiter: RateLimiterInterface = container.resolve(RedisRateLimiter)
        self.redis_repo: CacheRepositoryInterface = container.resolve(RedisRepository)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        if scope["path"] in EXEMPT_PATHS:
            await self.app(scope, receive, send)
            return

        auth_header: str | None = Headers(scope=scope).get("Authorization")

        if not auth_header:
            await openai_error(401, "Missing bearer token in the Authorization header.", "invalid_request_error",
                               "invalid_api_key")(scope, receive, send)
            return

        user_id: str | None = scope.get("state", {}).get(TOKEN_VALUE_STATE_KEY)
        if user_id is None:
            user_id = await self.redis_repo.get_user_id(auth_header.removeprefix("Bearer "))

        try:
            decision = await self.rate_limiter.acquire(user_id or "unknown")
        except Exception as exc:
            # fail open: a Redis hiccup in the limiter must not turn every request into an error
            logger.warning("rate limiter unavailable, request let through (%r)", exc)
            await self.app(scope, receive, send)
            return

        limit_headers = self._limit_headers(decision)

        if not decision.allowed:
            scope.setdefault("state", {})[REJECTED_BY_STATE_KEY] = "rate_limit"
            retry_after = max(1, math.ceil(decision.reset_at - time.time()))
            await openai_error(
                429, "Too many requests. Try again later.", "rate_limit_error", "rate_limit_exceeded",
                headers={"Retry-After": str(retry_after), **limit_headers},
            )(scope, receive, send)
            return

        async def send_with_rate_limit_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                MutableHeaders(scope=message).update(limit_headers)
            await send(message)

        await self.app(scope, receive, send_with_rate_limit_headers)

    @staticmethod
    def _limit_headers(decision: RateLimitDecision) -> dict[str, str]:
        return {
            "X-RateLimit-Limit": str(decision.limit),
            "X-RateLimit-Remaining": str(decision.remaining),
            "X-RateLimit-Reset": str(int(decision.reset_at)),
        }
