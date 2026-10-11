from __future__ import annotations

import sys
from typing import TYPE_CHECKING

from src.utils.types import CacheJobData, RedisStreamName, VectorRepositoryCollection, RedisAtomicCounters

if TYPE_CHECKING:
    from src.app.ports import (CacheRepositoryInterface, VectorEmbeddingRepositoryInterface,
                               VectorDBRepositoryInterface, JobQueueRepositoryInterface, MetricsRepositoryInterface)
    from src.utils.types import CACHE_TYPE, ATOMIC_COUNTERS, ChatRequest
    from .keys import CacheKeyBuilder, CacheKeys


class ResponseCache:
    """Everything about caching model answers: the keys, the lookup (exact, then semantic)
    and queueing the write, which a background job performs."""

    def __init__(self,
                 exact_cache: CacheRepositoryInterface,
                 embedding_repo: VectorEmbeddingRepositoryInterface,
                 vector_cache: VectorDBRepositoryInterface,
                 job_manager: JobQueueRepositoryInterface,
                 key_builder: CacheKeyBuilder,
                 metrics_repo: MetricsRepositoryInterface):
        self.exact_cache = exact_cache
        self.embedding_repo = embedding_repo
        self.vector_cache = vector_cache
        self.job_manager = job_manager
        self.key_builder = key_builder
        self.metrics_repo = metrics_repo

    def build_keys(self, user_id: str | None, chat_request: ChatRequest) -> CacheKeys:
        return self.key_builder.build_cache_keys(
            user_id=user_id,
            model=chat_request.model,
            params=chat_request.params,
            messages=chat_request.messages,
        )

    async def lookup(self, cache_keys: CacheKeys, score_threshold: float) -> str | None:
        """A cache outage is a miss: the request still gets answered by the model."""
        answer, counter = await self._search(cache_keys, score_threshold)
        await self._count(counter)
        return answer

    async def _search(self, cache_keys: CacheKeys, score_threshold: float) -> tuple[str | None, ATOMIC_COUNTERS]:
        try:
            answer = await self.exact_cache.search(cache_keys.exact_key)
            if answer:
                return answer, RedisAtomicCounters.CACHE_EXACT_HITS
            embedding = await self.embedding_repo.create_vector_embeddings(cache_keys.prompt)
            answer = await self.vector_cache.search(
                VectorRepositoryCollection.SEMANTIC_CACHE, embedding, score_threshold, context_hash=cache_keys.context_hash
            )
            if answer:
                return answer, RedisAtomicCounters.CACHE_SEMANTIC_HITS
        except Exception:
            pass
        return None, RedisAtomicCounters.CACHE_MISSES

    async def _count(self, counter: ATOMIC_COUNTERS) -> None:
        # a metrics outage must never turn a cache hit into an error
        try:
            await self.metrics_repo.increment(counter)
        except Exception:
            pass

    async def store(self, cache_keys: CacheKeys, content: str, cache_type: CACHE_TYPE, ttl: int) -> None:
        """Best effort, like lookup: the answer is already paid for, so a cache outage
        must not cost the client its response."""
        job_data = CacheJobData(
            cache_type=cache_type,
            exact_key=cache_keys.exact_key,
            context_hash=cache_keys.context_hash,
            prompt=cache_keys.prompt,
            model_response=content,
            timeout=ttl,
        )
        try:
            await self.job_manager.create_job(RedisStreamName.RESPONSE_CACHE, job_data)
        except Exception as exc:
            print(f"WARNING: could not queue the cache write, the answer is returned uncached ({exc!r})", file=sys.stderr)
