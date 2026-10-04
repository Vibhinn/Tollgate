from __future__ import annotations

from uuid import uuid4
from typing import override, TYPE_CHECKING

from ..connection import CacheConnection
from qdrant_client.models import PointStruct, Filter, FieldCondition, MatchValue

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
        model_response: str,
        context_hash: str | None = None
    ):
        payload = {"user_message": user_message, "model_response": model_response}
        if context_hash is not None:
            payload["context_hash"] = context_hash

        await self.client.upsert(
            collection_name=collection,
            points=[
                PointStruct(
                    id=str(uuid4()),
                    vector=embedding[0].tolist(),
                    payload=payload
                )
            ]
        )

    @override
    async def search(self, collection: VECTOR_REPOSITORY_COLLECTIONS, embedding: ndarray,
                     score_threshold: float = 0.9, context_hash: str | None = None) -> str | None:
        query_filter = None
        if context_hash is not None:
            query_filter = Filter(must=[FieldCondition(key="context_hash", match=MatchValue(value=context_hash))])

        results = await self.client.query_points(
            collection_name=collection,
            query=embedding[0].tolist(),
            query_filter=query_filter,
            limit=1,
            score_threshold=score_threshold
        )

        if not results.points:
            return None
        return results.points[0].payload["model_response"]
