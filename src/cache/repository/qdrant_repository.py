from uuid import uuid4
from typing import override

from numpy import ndarray
from ..connection import CacheConnection
from qdrant_client.models import PointStruct

from src.app.ports import VectorDBRepositoryInterface


class QdrantRepository(VectorDBRepositoryInterface):
    def __init__(self):
        self.client = CacheConnection.get_connection("SEMANTIC")
        self.collection_name = "semantic_cache"

    @override
    async def save(
        self,
        embedding: ndarray,
        user_message: str,
        model_response: str
    ):
        self.client.upsert(
            collection_name=self.collection_name,
            points=[
                PointStruct(
                    id=str(uuid4()),
                    vector=embedding.tolist(),
                    payload={
                        "user_message": user_message,
                        "model_response": model_response
                    }
                )
            ]
        )

    @override
    async def search(self, embedding: ndarray):
        print("Embedding shape - ", embedding.shape)
        results = self.client.query_points(
            collection_name=self.collection_name,
            query=embedding[0].tolist(),
            limit=1,
            score_threshold=0.9
        )

        if not results.points:
            return None

        print("The result is - ", results)

        return {
            "response": results.points[0].payload["model_response"]
        }