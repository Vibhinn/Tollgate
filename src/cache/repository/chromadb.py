from typing import override

from numpy import ndarray

from src.app.ports import VectorDBRepository
from ..connection import storage_collection

class ChromaDBRepository(VectorDBRepository):
    def __init__(self):
        self.collection = storage_collection

    @override
    async def add_to_cache(self, embedding: ndarray) -> bool:
        self.collection.add(
            embeddings=[embedding]
        )
        return True

    @override
    async def search(self, embedding: ndarray):
        result = await self.collection.query(
            query_embeddings=[embedding],
            n_results=1
        )
        return result
