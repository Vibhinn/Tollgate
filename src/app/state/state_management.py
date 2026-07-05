from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..ports import JobQueueRepositoryInterface
    from ..factory import ApplicationRepositoryFactory

@dataclass
class ApplicationState:
    repo_manager: ApplicationRepositoryFactory
    job_manager: JobQueueRepositoryInterface
