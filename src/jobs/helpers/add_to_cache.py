from typing import override
from src.utils.types import CacheJobData
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
    @override
    async def execute(self, data: CacheJobData):
        cache_type = data.get("cache_type")

        if cache_type == "exact":
            await self.exact_cache.save(
                key=data.get("user_message"),
                value=data.get("model_response"),
                timeout=data.get("timeout")
            )

        elif cache_type == "semantic":
            embedding = await self.embedding_repo.create_vector_embeddings(data.get("user_message"))
            await self.vector_cache.save(
                embedding=embedding,
                user_message=data.get("user_message"),
                model_response=data.get("model_response").content
            )

