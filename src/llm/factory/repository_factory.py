from src.app.ports import LLMRepositoryInterface
from ..repository.openai_repository import OpenAIRepository
from ..repository.anthropic_repository import AnthropicRepository

class LLMRepositoryFactory:
    def __init__(self):
        self.repo_map: dict[str, LLMRepositoryInterface] = {
            "openai": OpenAIRepository(),
            "anthropic": AnthropicRepository()
        }

    def get_repo(self, model_name: str) -> LLMRepositoryInterface | None:
        return self.repo_map.get(model_name)