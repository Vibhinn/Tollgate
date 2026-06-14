from ..ports import JobQueueRepositoryInterface
from ..validators import Message
from ..factory import RepositoryManagementFactory

from src.router import RouterRepository
from src.utils.types import CacheJobData

class ChatAdapter:
    def __init__(self, repo_manager: RepositoryManagementFactory, job_manager: JobQueueRepositoryInterface):
        self.repo_manager = repo_manager
        self.embedding_repo = self.repo_manager.get_repo("EMBEDDING")
        self.vector_db_repo = self.repo_manager.get_repo("VECTOR_CACHE")
        self.kv_cache_repo = self.repo_manager.get_repo("EXACT_CACHE")
        self.router_repo = RouterRepository()
        self.job_queue_manager = job_manager

    async def check_cache(self, message: str) -> str:
        #exact cache search
        answer = await self.kv_cache_repo.search(message)
        if answer: return answer
        else:
            embedding = await self.embedding_repo.create_vector_embeddings(message)
            db_result = await self.vector_db_repo.search(embedding)
            return db_result

    async def query_llm(self, model_name: str, message: list[Message]) -> object:
        if model_name in {"fast", "cheap", "smart"}:
            model = await self.router_repo.get_best_model(model_name)
            return await self.router_repo.invoke_model(model_name=model, message=message)
        return await self.router_repo.invoke_model(model_name=model_name, message=message)

    async def add_job_to_queue(self, collection_name: str, data: dict):
        validated_data = CacheJobData(**data)
        await self.job_queue_manager.create_job(collection_name, validated_data)
