from fastapi import FastAPI, Request
from starlette.responses import JSONResponse

from .base import BaseMiddleware
from src.cache import RedisRepository
from ..ports import CacheRepositoryInterface


class AuthenticationMiddleware(BaseMiddleware):
    def __init__(self, app: FastAPI):
        self.app = app
        self.redis_repo: CacheRepositoryInterface = RedisRepository()
        self.exempt_paths = {"/docs", "/openapi.json"}

        @self.app.middleware("http")
        async def check_api_token(request: Request, call_next):
            if request.url.path in self.exempt_paths:
                return await call_next(request)

            auth_header: str | None = request.headers.get("Authorization")

            if not auth_header or not auth_header.startswith("Bearer "):
                return JSONResponse(status_code=401, content={"detail": "Token not sent in header"})

            token: str = auth_header.removeprefix("Bearer ")

            token_valid: bool = await self.redis_repo.check_token_validity(token)
            if token_valid:
                return await call_next(request)

            return JSONResponse(status_code=401, content={"detail": "Invalid token"})