from fastapi import FastAPI

from src.app.state import ApplicationState
from src.app.jobs.helpers import AddToCache
from src.app.jobs import BackgroundJobCreator
from src.utils import Config
from .installation import MiddlewareInstallation, APIRouterInstallation
from src.app.factory import RepositoryManagementFactory, AdapterManagementFactory

class Builder:
    def __init__(self, app: FastAPI):
        self.app = app
        self.config = Config()

    def build_and_initialize_app(self):
        MiddlewareInstallation.install_middleware(self.app)
        APIRouterInstallation.install_api_routers(self.app)

        repo_manager = RepositoryManagementFactory()
        adapter_manager = AdapterManagementFactory(repo_manager)
        job_manager = self.__setup_job_manager()

        self.app.state.application = ApplicationState(
            repo_manager=repo_manager,
            adapter_manager=adapter_manager,
            job_manager=job_manager
        )

    def __setup_job_manager(self) -> BackgroundJobCreator:
        scheduler = BackgroundJobCreator()

        scheduler.register_helper("RESPONSE_CACHE", AddToCache(self.app.state.repo_manager))
        scheduler.start()

        return scheduler

