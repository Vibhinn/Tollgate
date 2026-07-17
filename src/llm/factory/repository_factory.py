from typing import TYPE_CHECKING

from ..repository.openai_repository import OpenAIRepository
from ..repository.anthropic_repository import AnthropicRepository
from ..repository.gemini_repository import GeminiRepository

if TYPE_CHECKING:
    from src.app.ports import LLMRepositoryInterface
    from src.utils.config import Config

class LLMRepositoryFactory:
    def __init__(self, config: Config):
        self.config: Config = config

        self.repo_map: dict[str, LLMRepositoryInterface] = {
            "openai": OpenAIRepository(),
            "anthropic": AnthropicRepository(),
            "gemini": GeminiRepository(),
        }

    def __build_repo_map(self):
        pass

    def get_repo(self, model_name: str) -> LLMRepositoryInterface | None:
        return self.repo_map.get(model_name)