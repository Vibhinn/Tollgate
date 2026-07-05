from fastapi import FastAPI

from src.llm import LLMRepositoryFactory
from src.router import RouterRepository
from src.app.adapters import RouterAdapter
from src.app.factory import ApplicationRepositoryFactory
from src.app.adapters import ChatAdapter, GenerateAccessTokenAdapter
from src.app.migrations import BaseMigration
from src.app.injector import container

from src.jobs import JobQueueConnection
from src.jobs import RedisStreamRepository
from src.jobs.helpers import AddToCache, AnalyticsJobHelper

from src.utils.config import Config
from src.cache import CacheConnection
from src.llm import LLMConnection

from .installation import MiddlewareInstallation, APIRouterInstallation

class Builder:
    def __init__(self, app: FastAPI):
        self.app = app
        self.config = Config()

    def build_and_initialize_app(self):
        MiddlewareInstallation.install_middleware(self.app)
        APIRouterInstallation.install_api_routers(self.app)
        self.__create_and_initialize_connections()
        self.__register_dependencies()
        self.__setup_job_manager()

    @staticmethod
    def __register_dependencies():
        container.register(ApplicationRepositoryFactory, lambda: ApplicationRepositoryFactory())
        container.register(LLMRepositoryFactory, lambda: LLMRepositoryFactory())
        container.register(RouterRepository, lambda: RouterRepository(container.resolve(LLMRepositoryFactory), container.resolve(RouterAdapter)))

        container.register(ChatAdapter, lambda: ChatAdapter(container.resolve(ApplicationRepositoryFactory),
                                                            container.resolve(RedisStreamRepository),
                                                            container.resolve(RouterRepository)))

        container.register(GenerateAccessTokenAdapter, lambda: GenerateAccessTokenAdapter(
                                                            container.resolve(ApplicationRepositoryFactory)))
        container.register(Config, lambda : Config())
        container.register(RouterAdapter, lambda: RouterAdapter(
            container.resolve(RedisStreamRepository),
            container.resolve(ApplicationRepositoryFactory).get_repo("RANKING")
        ))

    @staticmethod
    def __setup_job_manager():
        repo_factory = container.resolve(ApplicationRepositoryFactory)
        add_to_cache = AddToCache(
            exact_cache=repo_factory.get_repo("EXACT_CACHE"),
            embedding_repo=repo_factory.get_repo("EMBEDDING"),
            vector_cache=repo_factory.get_repo("VECTOR_CACHE")
        )

        scheduler = RedisStreamRepository()
        scheduler.register_helper("RESPONSE_CACHE", add_to_cache)
        scheduler.register_helper("ANALYTICS", None)
        container.register(RedisStreamRepository, lambda: scheduler, singleton=True)

        analytics_helper = AnalyticsJobHelper(
            ranking_repo=repo_factory.get_repo("RANKING")
        )
        scheduler.register_helper("ANALYTICS", analytics_helper)

    def __create_and_initialize_connections(self):
        CacheConnection.initialize()
        LLMConnection.initialize(
            openai_key=self.config.get_config("OPENAI", "API_KEY"),
            anthropic_key=self.config.get_config("ANTHROPIC", "API_KEY"),
            gemini_key=self.config.get_config("GEMINI", "API_KEY"),
            model2vec_model=self.config.get_config("EMBEDDING", "MODEL_NAME")
        )
        JobQueueConnection.initialize()
        BaseMigration.run_all()




