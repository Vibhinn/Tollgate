import time

from fastapi import FastAPI, Request
from starlette.responses import JSONResponse

from .base import BaseMiddleware
from ..limiter.store import RateLimiterStore
from src.cache import RedisRepository
from ..ports import CacheRepository


class RateLimitingMiddleware(BaseMiddleware):
    def __init__(self, app: FastAPI):
        self.app = app
        self.rate_limiter = RateLimiterStore()
        self.redis_repo: CacheRepository = RedisRepository()

        @self.app.middleware("http")
        async def rate_limit(request: Request, call_next):
            auth_header: str | None = request.headers.get("Authorization")
            token: str = "mock" or auth_header.removeprefix("Bearer ")
            user_id: str = "mockuser" or await self.redis_repo.get_user_id(token)

            bucket = self.rate_limiter.get_user_bucket(user_id)

            if not bucket.request_allowed():
                retry_after = bucket.get_reset_time() - time.time()
                return JSONResponse(
                    status_code=429,
                    content={"detail": "Too many requests. Try again later."},
                    headers={
                        "Retry-After": str(max(1, int(retry_after))),
                        "X-RateLimit-Limit": str(bucket.max_tokens),
                        "X-RateLimit-Remaining": str(bucket.get_remaining()),
                        "X-RateLimit-Reset": str(int(bucket.get_reset_time())),
                    },
                )

            response = await call_next(request)
            response.headers["X-RateLimit-Limit"] = str(bucket.max_tokens)
            response.headers["X-RateLimit-Remaining"] = str(bucket.get_remaining())
            response.headers["X-RateLimit-Reset"] = str(int(bucket.get_reset_time()))
            return response
