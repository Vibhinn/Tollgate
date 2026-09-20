from typing import overload, Literal, TYPE_CHECKING

from .providers import providers, embedding_model

from openai import AsyncOpenAI
from anthropic import AsyncAnthropic
from google import genai
from model2vec import StaticModel

from src.utils.types import ConfigurationEnums, LLMProvider, ConfigurationSection, ConfigurationOption

if TYPE_CHECKING:
    from src.utils.types import LLM_PROVIDER
    from src.utils.config import Config

class LLMConnection:
    _connections: dict = {}

    @classmethod
    def initialize(cls, config: Config):
        configured_models = config.get_entire_config_section(ConfigurationSection.MODELS)

        for provider in configured_models.keys():
            configured_api_key: str = config.get_config(ConfigurationSection.MODELS, ConfigurationOption.API_KEY, provider)
            if configured_api_key == ConfigurationEnums.API_KEY_NOT_CONFIGURED.value:
                ## API key is not configured there, so continue
                continue

            factory = providers.get(provider)
            cls._connections[provider] = factory(configured_api_key)

        cls._connections[LLMProvider.EMBEDDING] = embedding_model[LLMProvider.EMBEDDING](config)

    @overload
    @classmethod
    def get_connection(cls, provider: Literal[LLMProvider.OPENAI]) -> AsyncOpenAI: ...

    @overload
    @classmethod
    def get_connection(cls, provider: Literal[LLMProvider.ANTHROPIC]) -> AsyncAnthropic: ...

    @overload
    @classmethod
    def get_connection(cls, provider: Literal[LLMProvider.GEMINI]) -> genai.Client: ...

    @overload
    @classmethod
    def get_connection(cls, provider: Literal[LLMProvider.EMBEDDING]) -> StaticModel: ...

    @classmethod
    def get_connection(cls, provider: LLM_PROVIDER):
        conn = cls._connections.get(provider)
        if not conn:
            raise ValueError(f"Provider {provider} not initialized or unknown")
        return conn
