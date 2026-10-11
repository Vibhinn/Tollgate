from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from .base import BaseMiddleware, IDENTITY_STATE_KEY, REJECTED_BY_STATE_KEY, COMPLETION_STATE_KEY
from .exemptions import EXEMPT_PATHS, LONG_LIVED_PATHS
from src.jobs import RedisStreamRepository
from src.utils.types import RedisStreamName, RequestEventData
from src.app.injector import container
from src.app.exceptions.handlers import ERROR_CODE_STATE_KEY

if TYPE_CHECKING:
    from starlette.types import ASGIApp, Scope, Receive, Send, Message
    from src.app.ports import JobQueueRepositoryInterface
    from src.utils.types import TokenIdentity, LLMInvocationResult


class RequestMetricsMiddleware(BaseMiddleware):
    """Pushes one event per request to the analytics stream; AnalyticsHelper adds them up.
    Installed outermost, so it also sees the 401, 429 and 503 the other middlewares send,
    and reads what they and the endpoint left in the request state."""

    def __init__(self, app: ASGIApp):
        self.app = app
        self.job_queue: JobQueueRepositoryInterface = container.resolve(RedisStreamRepository)

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
            # pushed after the response is sent, so it never delays it
            await self._push(self._event(status_code, scope.get("state", {})))

    @staticmethod
    def _event(status_code: int, state: dict) -> RequestEventData:
        identity: TokenIdentity | None = state.get(IDENTITY_STATE_KEY)
        completion: LLMInvocationResult | None = state.get(COMPLETION_STATE_KEY)
        return RequestEventData(
            kind="request",
            status=status_code,
            rejected_by=state.get(REJECTED_BY_STATE_KEY),
            error_code=state.get(ERROR_CODE_STATE_KEY),
            cache_outcome=completion.cache_outcome if completion else None,
            # a cache hit didn't use a model
            model=completion.model if completion and not completion.cached else None,
            input_tokens=completion.input_tokens if completion else 0,
            output_tokens=completion.output_tokens if completion else 0,
            team=identity.team if identity else None,
            name=identity.name if identity else None,
            token_id=identity.token_id if identity else None,
            timestamp=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        )

    async def _push(self, event: RequestEventData) -> None:
        # a metrics outage must never fail the request
        try:
            await self.job_queue.create_job(RedisStreamName.ANALYTICS, event)
        except Exception:
            pass
