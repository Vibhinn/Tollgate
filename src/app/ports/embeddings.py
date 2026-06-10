from abc import ABC, abstractmethod

class VectorEmbeddingRepositoryInterface(ABC):
    @abstractmethod
    async def create_vector_embeddings(self, content: str):
        ...