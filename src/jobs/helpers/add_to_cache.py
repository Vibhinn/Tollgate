import json
from typing import override, TYPE_CHECKING
from src.utils.types import CacheJobData, CacheType
from .base import BaseHelper

if TYPE_CHECKING:
    from src.utils.types import StreamPayload
    from src.app.ports import CacheRepositoryInterface, VectorEmbeddingRepositoryInterface, VectorDBRepositoryInterface


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

        if cache_type == CacheType.EXACT:
            await self.exact_cache.save(
                key=payload.get("user_message"),
                value=payload.get("model_response"),
                timeout=payload.get("timeout")
            )

        elif cache_type == CacheType.SEMANTIC:
            embedding = await self.embedding_repo.create_vector_embeddings(payload.get("user_message"))
            await self.vector_cache.save(
                embedding=embedding,
                user_message=payload.get("user_message"),
                model_response=payload.get("model_response")
            )

