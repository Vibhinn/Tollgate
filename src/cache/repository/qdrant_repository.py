from uuid import uuid4
from typing import override, TYPE_CHECKING

from ..connection import CacheConnection
from qdrant_client.models import PointStruct

from src.app.ports import VectorDBRepositoryInterface
from src.utils.types import VECTOR_REPOSITORY_COLLECTIONS, CacheType

if TYPE_CHECKING:
    from numpy import ndarray

class QdrantRepository(VectorDBRepositoryInterface):
    def __init__(self):
        self.client = CacheConnection.get_connection(CacheType.SEMANTIC)

    @override
    async def save(
        self,
        embedding: ndarray,
        collection: VECTOR_REPOSITORY_COLLECTIONS,
        user_message: str,
        model_response: str
    ):
        await self.client.upsert(
            collection_name=collection,
            points=[
                PointStruct(
                    id=str(uuid4()),
                    vector=embedding[0].tolist(),
                    payload={
                        "user_message": user_message,
                        "model_response": model_response
                    }
                )
            ]
        )

    @override
    async def search(self, collection: VECTOR_REPOSITORY_COLLECTIONS, embedding: ndarray, score_threshold: float = 0.9) -> dict:
        print("Embedding shape - ", embedding.shape)
        results = await self.client.query_points(
            collection_name=collection,
            query=embedding[0].tolist(),
            limit=1,
            score_threshold=score_threshold
        )

        if not results.points:
            return {}
        else:
            return {
                "response": results.points[0].payload["model_response"]
            }
