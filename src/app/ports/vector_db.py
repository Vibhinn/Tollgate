from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from numpy import ndarray

class VectorDBRepositoryInterface(ABC):
    @abstractmethod
    async def save(self, embedding: ndarray, user_message: str, model_response: str):
        ...

    @abstractmethod
    async def search(self, embedding: ndarray, score_threshold: float = 0.9):
        ...