from typing import TYPE_CHECKING

from ..exceptions import ModelSemanticNotFound

if TYPE_CHECKING:
    from src.router import RouterRepository
    from ..factory import ApplicationRepositoryFactory
    from ..ports import JobQueueRepositoryInterface
    from ..validators import Message
    from src.utils.types import REDIS_STREAM_NAMES

class ChatAdapter:
    def __init__(self, repo_manager: ApplicationRepositoryFactory,
                 job_manager: JobQueueRepositoryInterface,
                 router_manager: RouterRepository):
        self.repo_manager = repo_manager
        self.embedding_repo = self.repo_manager.get_repo("EMBEDDING")
        self.vector_db_repo = self.repo_manager.get_repo("VECTOR_CACHE")
        self.kv_cache_repo = self.repo_manager.get_repo("EXACT_CACHE")
        self.router_repo = router_manager
        self.job_queue_manager = job_manager

    async def check_cache(self, message: str) -> str:
        #exact cache search
        answer = await self.kv_cache_repo.search(message)
        if answer:
            return answer
        else:
            embedding = await self.embedding_repo.create_vector_embeddings(message)
            db_result = await self.vector_db_repo.search("semantic_cache",embedding)
            return db_result

    async def query_llm(self, model_name: str, messages: list[Message]) -> str:
        if model_name in {"fast", "cheap", "smart"}:
            recommended_model = await self.router_repo.get_best_model(
                model_name,
                user_message=messages[-1] if model_name == "smart" else None
            )
            return await self.router_repo.invoke_model(model_name=recommended_model, messages=messages)
        else:
            return await self.router_repo.invoke_model(model_name=model_name, messages=messages)

    async def add_job_to_queue(self, collection_name: REDIS_STREAM_NAMES, data: dict):
        await self.job_queue_manager.create_job(collection_name, data)
