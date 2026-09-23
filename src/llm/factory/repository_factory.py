from typing import TYPE_CHECKING

from ..repository import AnthropicRepository, GeminiRepository, OpenAIRepository

from src.utils.types import ConfigurationSection, ConfigurationEnums, ConfigurationOption, LLMProvider

if TYPE_CHECKING:
    from src.app.ports import LLMRepositoryInterface
    from src.utils.config import Config

class LLMRepositoryFactory:
    def __init__(self, config: Config):
        self.config: Config = config
        self.repo_map: dict = {}

        self.repository_providers: dict = {
            LLMProvider.OPENAI: OpenAIRepository,
            LLMProvider.ANTHROPIC: AnthropicRepository,
            LLMProvider.GEMINI: GeminiRepository,
        }

        configured_models = self.config.get_entire_config_section(ConfigurationSection.MODELS)
        for provider in configured_models.keys():
            configured_api_key: str = config.get_config(ConfigurationSection.MODELS, ConfigurationOption.API_KEY, provider)
            if configured_api_key == ConfigurationEnums.API_KEY_NOT_CONFIGURED.value:
                continue

            self.repo_map[provider] = self.repository_providers[provider]()

    def get_repo(self, model_name: str) -> LLMRepositoryInterface | None:
        return self.repo_map.get(model_name, None)