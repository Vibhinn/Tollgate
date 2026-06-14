from abc import ABC, abstractmethod

from src.utils.types import StreamPayload


class BaseHelper(ABC):
    @abstractmethod
    async def execute(self, data: StreamPayload):
        ...