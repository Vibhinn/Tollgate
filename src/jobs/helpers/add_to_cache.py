import json
from typing import override
from src.utils.types import CacheJobData, StreamPayload
from src.app.ports import CacheRepositoryInterface, VectorEmbeddingRepositoryInterface, VectorDBRepositoryInterface
from .base import BaseHelper


class AddToCache(BaseHelper):
    def __init__(
            self,
            exact_cache: CacheRepositoryInterface,
            embedding_repo: VectorEmbeddingRepositoryInterface,
            vector_cache: VectorDBRepositoryInterface
    ):
        self.exact_cache = exact_cache
        self.embedding_repo = embedding_repo
        self.vector_cache = vector_cache

    @override
    async def execute(self, data: StreamPayload):
        payload_raw = data.get("payload")
        if payload_raw is None:
            raise ValueError("Missing 'payload' in job data")

        payload: CacheJobData = CacheJobData(**json.loads(payload_raw))
        cache_type = payload.get("cache_type")

        if cache_type == "EXACT":
            await self.exact_cache.save(
                key=payload.get("user_message"),
                value=payload.get("model_response"),
                timeout=payload.get("timeout")
            )

        elif cache_type == "SEMANTIC":
            embedding = await self.embedding_repo.create_vector_embeddings(payload.get("user_message"))
            await self.vector_cache.save(
                embedding=embedding,
                user_message=payload.get("user_message"),
                model_response=payload.get("model_response")
            )

