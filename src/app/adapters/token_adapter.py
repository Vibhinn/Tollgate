import secrets
import json
from typing import TYPE_CHECKING

from src.utils.types import ApplicationRepositoryType

if TYPE_CHECKING:
    from ..factory import ApplicationRepositoryFactory

class GenerateAccessTokenAdapter:
    def __init__(self, repo_manager: ApplicationRepositoryFactory):
        self.repo_manager = repo_manager
        self.kv_cache_repo = self.repo_manager.get_repo(ApplicationRepositoryType.EXACT_CACHE)

    async def generate_and_save_token(self, requirement: str, user_role: str, ttl: int) -> str:
        token: str = f"tg_{secrets.token_urlsafe(32)}"

        value = json.dumps({
            "requirement": requirement,
            "user_role": user_role
        })

        await self.kv_cache_repo.save(key=f"token:{token}", value=value, timeout=ttl)
        return token