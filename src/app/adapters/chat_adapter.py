from __future__ import annotations

from typing import TYPE_CHECKING

from src.utils.types import ApplicationRepositoryType, VectorRepositoryCollection, last_user_message

if TYPE_CHECKING:
    from src.router import RouterRepository
    from ..factory import ApplicationRepositoryFactory
    from ..ports import JobQueueRepositoryInterface
    from src.cache.keys import CacheKeys
    from src.utils.types import Message
    from src.utils.types import REDIS_STREAM_NAMES

class ChatAdapter:
    def __init__(self, repo_manager: ApplicationRepositoryFactory,
                 job_manager: JobQueueRepositoryInterface,
                 router_manager: RouterRepository):
        self.repo_manager = repo_manager
        self.embedding_repo = self.repo_manager.get_repo(ApplicationRepositoryType.EMBEDDING)
        self.vector_db_repo = self.repo_manager.get_repo(ApplicationRepositoryType.VECTOR_CACHE)
        self.kv_cache_repo = self.repo_manager.get_repo(ApplicationRepositoryType.EXACT_CACHE)
        self.router_repo = router_manager
        self.job_queue_manager = job_manager

    async def check_cache(self, cache_keys: CacheKeys, score_threshold: float) -> str | None:
        try:
            answer = await self.kv_cache_repo.search(cache_keys.exact_key)
            if answer:
                return answer
            else:
                embedding = await self.embedding_repo.create_vector_embeddings(cache_keys.prompt)
                return await self.vector_db_repo.search(
                    VectorRepositoryCollection.SEMANTIC_CACHE, embedding, score_threshold, context_hash=cache_keys.context_hash
                )
        except Exception:
            return None

    async def query_llm(self, model_name: str, messages: list[Message], max_tokens: int, temperature: float | None = None) -> str:
        if model_name in {"fast", "cheap", "smart"}:
            recommended_model = await self.router_repo.get_best_model(
                model_name,
                user_message=last_user_message(messages) if model_name == "smart" else None
            )
            return await self.router_repo.invoke_model(model_name=recommended_model, messages=messages, max_tokens=max_tokens,
                                                       model_selection_policy=model_name, temperature=temperature)
        else:
            return await self.router_repo.invoke_model(model_name=model_name, messages=messages, max_tokens=max_tokens,
                                                       temperature=temperature)

    async def add_job_to_queue(self, collection_name: REDIS_STREAM_NAMES, data: dict):
        await self.job_queue_manager.create_job(collection_name, data)
