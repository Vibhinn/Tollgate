from typing import override, TYPE_CHECKING

from src.app.ports import VectorEmbeddingRepositoryInterface
from ..connection import LLMConnection

if TYPE_CHECKING:
    from numpy import ndarray

class Model2VecRepository(VectorEmbeddingRepositoryInterface):
    def __init__(self):
        self.embedding_model = LLMConnection.get_connection("EMBEDDING")
    @override
    async def create_vector_embeddings(self, content: str) -> ndarray:
        embedding = self.embedding_model.encode([content])
        return embedding
