from abc import ABC, abstractmethod

class JobRepositoryInterface(ABC):
    @abstractmethod
    async def create_job(self, collection_name: str, data: object):
        ...