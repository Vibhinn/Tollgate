import asyncio
from typing import override, TYPE_CHECKING

from src.app.ports import VectorEmbeddingRepositoryInterface
from src.utils.types import LLMProvider
from ..connection import LLMConnection

if TYPE_CHECKING:
    from numpy import ndarray

class Model2VecRepository(VectorEmbeddingRepositoryInterface):
    def __init__(self):
        self.embedding_model = LLMConnection.get_connection(LLMProvider.EMBEDDING)

    @override
    async def create_vector_embeddings(self, content: str) -> ndarray:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self.embedding_model.encode, [content])