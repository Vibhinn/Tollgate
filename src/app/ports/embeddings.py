from typing import TYPE_CHECKING
from abc import ABC, abstractmethod

if TYPE_CHECKING:
    from numpy import ndarray

class VectorEmbeddingRepositoryInterface(ABC):
    @abstractmethod
    async def create_vector_embeddings(self, content: str) -> ndarray:
        ...
