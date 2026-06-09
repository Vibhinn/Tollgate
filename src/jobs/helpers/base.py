from abc import ABC, abstractmethod

from src.app.factory import RepositoryManagementFactory

class BaseHelper(ABC):
    @abstractmethod
    def __init__(self, repo_factory: RepositoryManagementFactory):
        self.repo_manager =repo_factory

    @abstractmethod
    async def execute(self, *args):
        ...