from abc import ABC, abstractmethod
from typing import TYPE_CHECKING
from src.utils.types import VECTOR_REPOSITORY_COLLECTIONS

if TYPE_CHECKING:
    from numpy import ndarray

class VectorDBRepositoryInterface(ABC):
    @abstractmethod
    async def save(self, embedding: ndarray, collection: VECTOR_REPOSITORY_COLLECTIONS, user_message: str, model_response: str) -> None:
        ...

    @abstractmethod
    async def search(self, collection: VECTOR_REPOSITORY_COLLECTIONS, embedding: ndarray, score_threshold: float = 0.9) -> str:
        ...
