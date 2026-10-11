from __future__ import annotations

from typing import TYPE_CHECKING

from .base import BaseMiddleware
from .exemptions import EXEMPT_PATHS, LONG_LIVED_PATHS
from src.cache import RedisMetricsRepository
from src.utils.types import RedisAtomicCounters
from src.app.injector import container

if TYPE_CHECKING:
    from starlette.types import ASGIApp, Scope, Receive, Send, Message
    from src.app.ports import MetricsRepositoryInterface

_COUNTER_BY_STATUS_CLASS = {
    2: RedisAtomicCounters.RESPONSES_2XX,
    4: RedisAtomicCounters.RESPONSES_4XX,
    5: RedisAtomicCounters.RESPONSES_5XX,
}


class RequestMetricsMiddleware(BaseMiddleware):
    """Counts every response by status class. Installed outermost, so it also sees the
    401, 429 and 503 that auth, rate limiting and backpressure send themselves."""

    def __init__(self, app: ASGIApp):
        self.app = app
        self.metrics_repo: MetricsRepositoryInterface = container.resolve(RedisMetricsRepository)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["path"] in EXEMPT_PATHS or scope["path"] in LONG_LIVED_PATHS:
            await self.app(scope, receive, send)
            return

        status_code = 500   # if the app raises before responding, the client gets a 500

        async def send_and_capture_status(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
            await send(message)

        try:
            await self.app(scope, receive, send_and_capture_status)
        finally:
            # counted after the response is sent, so it never delays it
            await self._count(status_code)

    async def _count(self, status_code: int) -> None:
        counter = _COUNTER_BY_STATUS_CLASS.get(status_code // 100)
        if counter is None:
            return
        try:
            await self.metrics_repo.increment(counter)
        except Exception:
            pass
