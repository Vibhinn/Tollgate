from typing import override

from src.app.ports import CreateVectorEmbedding
from ..connection import embedding_model

from numpy import ndarray

class Model2VecRepository(CreateVectorEmbedding):
    @override
    async def create_vector_embeddings(self, content: str) -> ndarray:
        embedding = embedding_model.encode([content])
        return embedding
