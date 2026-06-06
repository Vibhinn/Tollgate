from abc import ABC, abstractmethod

class CreateVectorEmbedding(ABC):
    @abstractmethod
    async def create_vector_embeddings(self, content: str):
        ...