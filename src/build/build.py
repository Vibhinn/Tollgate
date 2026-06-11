from fastapi import FastAPI

from src.app.factory import RepositoryManagementFactory, AdapterManagementFactory
from src.app.injector import container
from src.app.adapters import ChatAdapter

from src.jobs import JobQueueConnection
from src.jobs import RedisStreamRepository
from src.jobs.helpers import AddToCache

from src.utils import Config
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

    def __register_dependencies(self):
        container.register(RepositoryManagementFactory, lambda: RepositoryManagementFactory())
        container.register(AdapterManagementFactory,
                           lambda: AdapterManagementFactory(container.resolve(RepositoryManagementFactory)))
        container.register(ChatAdapter, lambda: ChatAdapter(container.resolve(RepositoryManagementFactory)))

    def __setup_job_manager(self):
        scheduler = RedisStreamRepository()
        scheduler.register_helper("RESPONSE_CACHE", AddToCache(container.resolve(RepositoryManagementFactory)))
        scheduler.start()
        container.register(RedisStreamRepository, lambda: scheduler, singleton=True)

    def __create_and_initialize_connections(self):
        CacheConnection.initialize()
        LLMConnection.initialize(
            openai_key=self.config.get_config("OPENAI", "API_KEY"),
            anthropic_key=self.config.get_config("ANTHROPIC", "API_KEY"),
            gemini_key=self.config.get_config("GEMINI", "API_KEY"),
            model2vec_model=self.config.get_config("EMBEDDING", "MODEL_NAME")
        )
        JobQueueConnection.initialize()


