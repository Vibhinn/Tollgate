from dataclasses import dataclass

from ..ports import JobQueueRepositoryInterface
from ..factory import ApplicationRepositoryFactory

@dataclass
class ApplicationState:
    repo_manager: ApplicationRepositoryFactory
    job_manager: JobQueueRepositoryInterface
