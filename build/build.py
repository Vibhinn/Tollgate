from typing import TYPE_CHECKING

from starlette.responses import JSONResponse

from src.llm import LLMRepositoryFactory
from src.llm import LLMConnection

from src.router import RouterRepository

from src.app.adapters import RouterAdapter
from src.app.intelligence import RoutingIntelligenceLayer
from src.app.factory import ApplicationRepositoryFactory
from src.app.adapters import ChatAdapter, GenerateAccessTokenAdapter
from src.app.migrations import BaseMigration
from src.app.injector import container
from src.app.exceptions import ModelSemanticNotFound

from src.jobs import JobQueueConnection
from src.jobs import RedisStreamRepository
from src.jobs.helpers import AddToCache, AnalyticsJobHelper

from src.utils.config import Config
from src.utils.types import ApplicationRepositoryType, RedisStreamName

from src.cache import CacheConnection

from .installation import MiddlewareInstallation, APIRouterInstallation

if TYPE_CHECKING:
    from fastapi import FastAPI

class Builder:
    def __init__(self, app: FastAPI):
        self.app: FastAPI = app
        self.config = Config()

    def build_and_initialize_app(self):
        self.__create_and_initialize_connections()

        self.__install_middleware()
        self.__install_routers()

        self.__register_exception_handlers()
        self.__register_dependencies()
        self.__setup_job_manager()

    def __install_middleware(self):
        MiddlewareInstallation.install_middleware(self.app)

    def __install_routers(self):
        APIRouterInstallation.install_api_routers(self.app)

    @staticmethod
    def __register_dependencies():
        container.register(ApplicationRepositoryFactory, lambda: ApplicationRepositoryFactory())
        container.register(LLMRepositoryFactory, lambda: LLMRepositoryFactory(
                                                                        container.resolve(Config)))

        container.register(RouterRepository, lambda: RouterRepository(container.resolve(LLMRepositoryFactory),
                                                                        container.resolve(RouterAdapter),
                                                                        container.resolve(Config)))

        container.register(ChatAdapter, lambda: ChatAdapter(container.resolve(ApplicationRepositoryFactory),
                                                                        container.resolve(RedisStreamRepository),
                                                                        container.resolve(RouterRepository)))

        container.register(GenerateAccessTokenAdapter, lambda: GenerateAccessTokenAdapter(
                                                                        container.resolve(ApplicationRepositoryFactory)))

        container.register(Config, lambda : Config())

        container.register(RoutingIntelligenceLayer, lambda: RoutingIntelligenceLayer(
                                                                        container.resolve(ApplicationRepositoryFactory)))

        container.register(RouterAdapter, lambda: RouterAdapter(
                                                                        container.resolve(RedisStreamRepository),
                                                                        container.resolve(ApplicationRepositoryFactory).get_repo(ApplicationRepositoryType.RANKING),
                                                                        container.resolve(RoutingIntelligenceLayer),
                                                                        container.resolve(LLMRepositoryFactory)))

        container.register(BaseMigration, lambda: BaseMigration())

    @staticmethod
    def __setup_job_manager():
        repo_factory = container.resolve(ApplicationRepositoryFactory)
        add_to_cache = AddToCache(
            exact_cache=repo_factory.get_repo(ApplicationRepositoryType.EXACT_CACHE),
            embedding_repo=repo_factory.get_repo(ApplicationRepositoryType.EMBEDDING),
            vector_cache=repo_factory.get_repo(ApplicationRepositoryType.VECTOR_CACHE)
        )

        scheduler = RedisStreamRepository()
        scheduler.register_helper(RedisStreamName.RESPONSE_CACHE, add_to_cache)
        container.register(RedisStreamRepository, lambda: scheduler, singleton=True)

        analytics_helper = AnalyticsJobHelper(
            ranking_repo=repo_factory.get_repo(ApplicationRepositoryType.RANKING)
        )
        scheduler.register_helper(RedisStreamName.ANALYTICS, analytics_helper)

    def __register_exception_handlers(self):
        @self.app.exception_handler(ModelSemanticNotFound)
        async def handle_model_not_found(request, exc):
            return JSONResponse(status_code=404, content={"detail": str(exc)})

    def __create_and_initialize_connections(self):
        CacheConnection.initialize()
        LLMConnection.initialize(self.config)
        JobQueueConnection.initialize()




