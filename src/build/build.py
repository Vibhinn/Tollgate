from fastapi import FastAPI

from src.app.jobs.helpers import AddToCache
from src.app.types import REDIS_STREAM_NAMES
from src.app.jobs import BackgroundJobCreator
from src.utils.config import Config
from .installation import MiddlewareInstallation, APIRouterInstallation
from src.app.factory import RepositoryManagementFactory, AdapterManagementFactory

class Builder:
    def __init__(self, app: FastAPI):
        self.app = app
        self.config = Config()

    def build_and_initialize_app(self):
        MiddlewareInstallation.install_middleware(self.app)
        APIRouterInstallation.install_api_routers(self.app)

        self.app.state.repo_manager = RepositoryManagementFactory()
        self.app.state.adapter_manager = AdapterManagementFactory(self.app.state.repo_manager)

        self.__setup_job_scheduler()

    def __setup_job_scheduler(self):
        scheduler = BackgroundJobCreator()

        scheduler.register_helper(REDIS_STREAM_NAMES.RESPONSE_CACHE, AddToCache(self.app.state.repo_manager))
        scheduler.start()

        self.app.state.job_scheduler = scheduler

