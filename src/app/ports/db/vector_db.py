from abc import ABC, abstractmethod

from numpy import ndarray

class VectorDBRepository(ABC):
    @abstractmethod
    async def add_to_cache(self, message: str):
        ...

    @abstractmethod
    async def search(self, embedding: ndarray):
        ...