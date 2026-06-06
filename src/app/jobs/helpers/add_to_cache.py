from src.app.types import CacheJobData

from .base import BaseHelper
from ...factory import RepositoryManagementFactory


class AddToCache(BaseHelper):
    def __init__(self, repo_factory: RepositoryManagementFactory):
        self.repo_factory = repo_factory

    async def execute(self, data: CacheJobData):
        cache_type: str = data.get("cache_type")

        if cache_type == "exact":
            caching_repo = self.repo_factory.get_repo("EXACT_CACHE")
            await caching_repo.add_to_cache(
                key=data.get("user_message"),
                value=data.get("model_response"),
                timeout=data.get("timeout")
            )

        elif cache_type == "semantic":
            embedding_repo = self.repo_factory.get_repo("EMBEDDING")
            embeddings = await embedding_repo.create_vector_embeddings(data.get("user_message"))

            caching_repo = self.repo_factory.get_repo("VECTOR_CACHE")
            await  caching_repo.add_to_cache()


