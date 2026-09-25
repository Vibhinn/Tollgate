from typing import overload, Literal, TYPE_CHECKING

from .providers import providers, embedding_model

from openai import AsyncOpenAI
from anthropic import AsyncAnthropic
from google import genai
from model2vec import StaticModel

from src.utils.types import (ConfigurationEnums, LLMProvider, ConfigurationSection,
                             ConfigurationOption, ConfigurationValue)
from src.utils.config import ROUTING_TABLE

if TYPE_CHECKING:
    from src.utils.types import LLM_PROVIDER
    from src.utils.config import Config


class LLMConnection:
    _connections: dict = {}

    @classmethod
    def initialize(cls, config: Config):
        configured_models = config.get_entire_config_section(ConfigurationSection.MODELS)

        for provider in configured_models.keys():
            if provider == LLMProvider.SELF_HOSTED:
                cls._initialize_self_hosted_models(config, configured_models[provider])
                continue

            configured_api_key: str = config.get_config(ConfigurationSection.MODELS, ConfigurationOption.API_KEY, provider)
            if configured_api_key == ConfigurationEnums.API_KEY_NOT_CONFIGURED.value:
                ## API key is not configured there, so continue
                continue

            factory = providers.get(provider)
            cls._connections[provider] = factory(configured_api_key)

        cls._connections[LLMProvider.EMBEDDING] = embedding_model[LLMProvider.EMBEDDING](config)

    @classmethod
    def _initialize_self_hosted_models(cls, config: Config, aliases: dict) -> None:
        factory = providers[LLMProvider.SELF_HOSTED]

        for alias in aliases:
            path = [LLMProvider.SELF_HOSTED, alias]
            endpoint: str = config.get_config(ConfigurationSection.MODELS, ConfigurationOption.ENDPOINT, path)
            model_name: str = config.get_config(ConfigurationSection.MODELS, ConfigurationOption.MODEL_NAME, path)

            api_key: str = config.get_config(ConfigurationSection.MODELS, ConfigurationOption.API_KEY, path)
            if api_key == ConfigurationEnums.API_KEY_NOT_CONFIGURED.value:
                api_key = ConfigurationValue.SELF_HOSTED_NO_AUTH_PLACEHOLDER

            cls._connections[alias] = factory(endpoint, api_key)

            ROUTING_TABLE[alias] = {"provider": alias, "model": model_name}

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

    @overload
    @classmethod
    def get_connection(cls, provider: Literal[LLMProvider.SELF_HOSTED]) -> AsyncOpenAI: ...

    @classmethod
    def get_connection(cls, provider: LLM_PROVIDER):
        conn = cls._connections.get(provider)
        if not conn:
            raise ValueError(f"Provider {provider} not initialized or unknown")
        return conn
