from src.app.ports import LargeLanguageModel
from ..repository.openai_repository import OpenAIRepository
from ..repository.anthropic_repository import AnthropicRepository

class LLMRepositoryFactory:
    def __init__(self):
        self.repo_map: dict[str, LargeLanguageModel] = {
            "openai": OpenAIRepository(),
            "anthropic": AnthropicRepository()
        }

    def get_repo(self, model_name: str) -> LargeLanguageModel | None:
        return self.repo_map.get(model_name)