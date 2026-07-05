from typing import TYPE_CHECKING

from ..repository.openai_repository import OpenAIRepository
from ..repository.anthropic_repository import AnthropicRepository

if TYPE_CHECKING:
    from src.app.ports import LLMRepositoryInterface

class LLMRepositoryFactory:
    def __init__(self):
        self.repo_map: dict[str, LLMRepositoryInterface] = {
            "openai": OpenAIRepository(),
            "anthropic": AnthropicRepository()
        }

    def get_repo(self, model_name: str) -> LLMRepositoryInterface | None:
        return self.repo_map.get(model_name)