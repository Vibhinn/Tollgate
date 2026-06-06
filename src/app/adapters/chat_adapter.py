from typing import Literal

from app.factory.repository_factory import RepositoryManagementFactory

class ChatAdapter:
    def __init__(self, repo_manager: RepositoryManagementFactory):
        self.repo_manager = repo_manager
        self.embedding_repo = self.repo_manager.get_repo("EMBEDDING")
        self.vector_db_repo = self.repo_manager.get_repo("VECTOR_CACHE")
        self.kv_cache_repo = self.repo_manager.get_repo("EXACT_CACHE")

    async def check_cache(self, message: str) -> str:
        #exact cache search
        answer = await self.kv_cache_repo.search(message)
        if answer: return answer
        else:
            embedding = await self.embedding_repo.create_vector_embeddings(message)
            db_result = await self.vector_db_repo.search(embedding)
            return db_result