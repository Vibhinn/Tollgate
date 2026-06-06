from typing import Literal

from app.factory.repository_factory import RepositoryManagementFactory

class ChatAdapter:
    def __init__(self, repo_manager: RepositoryManagementFactory):
        self.repo_manager = repo_manager
        self.embedding_repo = self.repo_manager.get_repo("EMBEDDING")
        self.vector_db_repo = self.repo_manager.get_repo("VECTOR_DB")
        self.kv_cache_repo = self.repo_manager.get_repo("CACHE")

    async def check_cache(self, message: str) -> str:
        embedding = await self.embedding_repo.create_vector_embeddings(message)
        db_result = await self.vector_db_repo.search(embedding)
        return db_result

    async def add_to_cache(self, message: str, model_output: str, cache_type: Literal["semantic", "exact"], timeout: float) -> bool:
        if cache_type == "semantic":
            embedding = await self.embedding_repo.create_vector_embeddings(message)
            save_output = await self.vector_db_repo.add_to_cache(embedding)
            return True if save_output else False

        elif cache_type == "exact":
            self.kv_cache_repo.add_to_cache()
        return False