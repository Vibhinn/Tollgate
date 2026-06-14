from fastapi import FastAPI
from src.app.middleware import AuthenticationMiddleware, RateLimitingMiddleware
from src.app.endpoints import chat_api_router, image_api_router, transcription_api_router, generate_access_token_router

class MiddlewareInstallation:
    @staticmethod
    def install_middleware(app: FastAPI):
        middlewares = [AuthenticationMiddleware, RateLimitingMiddleware]
        for middleware in middlewares:
            print("Installing middleware - ", middleware.__name__)
            middleware(app)

class APIRouterInstallation:
    @staticmethod
    def install_api_routers(app: FastAPI):
        routers = [chat_api_router, transcription_api_router, image_api_router, generate_access_token_router]
        for api_router in routers:
            app.include_router(api_router)
