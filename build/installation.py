from fastapi import FastAPI
from src.app.api import AuthenticationMiddleware, RateLimitingMiddleware, BackpressureMiddleware, RequestMetricsMiddleware
from src.app.api import chat_api_router, models_api_router, metrics_api_router, admin_api_router

class MiddlewareInstallation:
    @staticmethod
    def install_middleware(app: FastAPI):
        # the last one added runs first: RequestMetricsMiddleware sees every response, including the
        # 401 / 429 / 503 the others send themselves
        middlewares = [RateLimitingMiddleware, AuthenticationMiddleware, BackpressureMiddleware, RequestMetricsMiddleware]
        for middleware in middlewares:
            print("Installing middleware - ", middleware.__name__)
            app.add_middleware(middleware)

class APIRouterInstallation:
    @staticmethod
    def install_api_routers(app: FastAPI):
        routers = [chat_api_router, models_api_router, metrics_api_router, admin_api_router]
        for api_router in routers:
            app.include_router(api_router)
