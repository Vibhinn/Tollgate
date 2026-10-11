from __future__ import annotations

from typing import TYPE_CHECKING
from starlette.datastructures import Headers

from .base import BaseMiddleware, TOKEN_VALUE_STATE_KEY, IDENTITY_STATE_KEY
from src.cache import RedisRepository
from .exemptions import EXEMPT_PATHS
from src.app.exceptions.handlers import openai_error
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
            await openai_error(401, "Missing bearer token in the Authorization header.", "invalid_request_error", "invalid_api_key")(scope, receive, send)
            return

        token: str = auth_header.removeprefix("Bearer ")

        identity = await self.redis_repo.get_identity(token)
        if identity is None:
            await openai_error(401, "Invalid, expired or revoked Tollgate token.", "invalid_request_error", "invalid_api_key")(scope, receive, send)
            return

        state = scope.setdefault("state", {})
        state[TOKEN_VALUE_STATE_KEY] = identity.user_id
        state[IDENTITY_STATE_KEY] = identity
        await self.app(scope, receive, send)
