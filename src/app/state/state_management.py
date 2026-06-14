from dataclasses import dataclass

from ..ports import JobQueueRepositoryInterface
from ..factory import RepositoryManagementFactory, AdapterManagementFactory

@dataclass
class ApplicationState:
    repo_manager: RepositoryManagementFactory
    adapter_manager: AdapterManagementFactory
    job_manager: JobQueueRepositoryInterface
