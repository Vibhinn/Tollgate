from fastapi import FastAPI
from src.app.api import AuthenticationMiddleware, RateLimitingMiddleware, BackpressureMiddleware
from src.app.api import chat_api_router

class MiddlewareInstallation:
    @staticmethod
    def install_middleware(app: FastAPI):
        middlewares = [RateLimitingMiddleware, AuthenticationMiddleware, BackpressureMiddleware]
        for middleware in middlewares:
            print("Installing middleware - ", middleware.__name__)
            app.add_middleware(middleware)

class APIRouterInstallation:
    @staticmethod
    def install_api_routers(app: FastAPI):
        routers = [chat_api_router]
        for api_router in routers:
            app.include_router(api_router)
