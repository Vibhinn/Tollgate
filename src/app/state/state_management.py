from dataclasses import dataclass

from src.app.factory import RepositoryManagementFactory, AdapterManagementFactory
from src.app.jobs import BackgroundJobCreator

@dataclass
class ApplicationState:
    repo_manager: RepositoryManagementFactory
    adapter_manager: AdapterManagementFactory
    job_manager: BackgroundJobCreator
