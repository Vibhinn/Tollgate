from abc import ABC, abstractmethod

class JobQueueRepositoryInterface(ABC):
    @abstractmethod
    async def create_job(self, collection_name: str, data: object):
        ...