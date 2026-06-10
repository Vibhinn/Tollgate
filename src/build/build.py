from fastapi import FastAPI

from src.app.ports import JobQueueRepositoryInterface
from src.jobs import JobQueueConnection
from src.app.state import ApplicationState
from src.jobs.helpers import AddToCache
from src.jobs import RedisStreamRepository
from src.app.factory import RepositoryManagementFactory, AdapterManagementFactory

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

        repo_manager = RepositoryManagementFactory()
        adapter_manager = AdapterManagementFactory(repo_manager)
        job_manager = self.__setup_job_manager(repo_manager)

        self.app.state.application = ApplicationState(
            repo_manager=repo_manager,
            adapter_manager=adapter_manager,
            job_manager=job_manager
        )

    def __setup_job_manager(self, repo_manager: RepositoryManagementFactory) -> JobQueueRepositoryInterface:
        scheduler = RedisStreamRepository()

        scheduler.register_helper("RESPONSE_CACHE", AddToCache(repo_manager))
        scheduler.start()

        return scheduler

    def __create_and_initialize_connections(self):
        CacheConnection.initialize()
        LLMConnection.initialize(
            openai_key=self.config.get_config("OPENAI", "API_KEY"),
            anthropic_key=self.config.get_config("ANTHROPIC", "API_KEY"),
            gemini_key=self.config.get_config("GEMINI", "API_KEY"),
            model2vec_model=self.config.get_config("EMBEDDING", "MODEL_NAME")
        )
        JobQueueConnection.initialize()


