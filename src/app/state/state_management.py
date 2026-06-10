from dataclasses import dataclass

from src.app.ports import JobQueueRepositoryInterface
from src.app.factory import RepositoryManagementFactory, AdapterManagementFactory

@dataclass
class ApplicationState:
    repo_manager: RepositoryManagementFactory
    adapter_manager: AdapterManagementFactory
    job_manager: JobQueueRepositoryInterface
