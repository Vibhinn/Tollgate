from __future__ import annotations

from typing import TYPE_CHECKING
from starlette.datastructures import Headers
from starlette.responses import JSONResponse

from .base import BaseMiddleware, TOKEN_VALUE_STATE_KEY
from src.cache import RedisRepository
from .exemptions import EXEMPT_PATHS
from src.app.injector import container

if TYPE_CHECKING:
    from starlette.types import ASGIApp, Scope, Receive, Send
    from src.app.ports import CacheRepositoryInterface

class AuthenticationMiddleware(BaseMiddleware):
    def __init__(self, app: ASGIApp):
        self.app = app
        self.redis_repo: CacheRepositoryInterface = container.resolve(RedisRepository)
        self.exempt_paths = EXEMPT_PATHS

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["path"] in self.exempt_paths:
            await self.app(scope, receive, send)
            return

        auth_header: str | None = Headers(scope=scope).get("Authorization")

        if not auth_header or not auth_header.startswith("Bearer "):
            await JSONResponse(status_code=401, content={"detail": "Token not sent in header"})(scope, receive, send)
            return

        token: str = auth_header.removeprefix("Bearer ")

        token_value: str | None = await self.redis_repo.get_user_id(token)
        if not token_value:
            await JSONResponse(status_code=401, content={"detail": "Invalid token"})(scope, receive, send)
            return

        scope.setdefault("state", {})[TOKEN_VALUE_STATE_KEY] = token_value
        await self.app(scope, receive, send)
