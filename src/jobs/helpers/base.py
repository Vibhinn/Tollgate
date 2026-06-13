from abc import ABC, abstractmethod

class BaseHelper(ABC):
    @abstractmethod
    async def execute(self, *args):
        ...