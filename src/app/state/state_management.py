from dataclasses import dataclass

from src.app.factory import RepositoryManagementFactory, AdapterManagementFactory
from src.jobs import RedisStreamRepository

@dataclass
class ApplicationState:
    repo_manager: RepositoryManagementFactory
    adapter_manager: AdapterManagementFactory
    job_manager: RedisStreamRepository
