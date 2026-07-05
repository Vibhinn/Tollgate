from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.utils.types import REDIS_STREAM_NAMES

class JobQueueRepositoryInterface(ABC):
    @abstractmethod
    async def create_job(self, collection_name: REDIS_STREAM_NAMES, data: object):
        ...