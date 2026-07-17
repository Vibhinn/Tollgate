from typing import overload, Literal, TYPE_CHECKING

from .providers import providers

from openai import AsyncOpenAI
from anthropic import AsyncAnthropic
from google import genai
from model2vec import StaticModel

from src.utils.types import ConfigurationEnums

if TYPE_CHECKING:
    from src.utils.types import LLM_PROVIDER
    from src.utils.config import Config

class LLMConnection:
    _connections: dict = {}

    @classmethod
    def initialize(cls, config: Config):
        configured_models = config.get_entire_config_section("MODELS")

        for provider in configured_models.keys():
            configured_api_key: str = config.get_config("MODELS", "API_KEY", provider)
            if configured_api_key == ConfigurationEnums.API_KEY_NOT_CONFIGURED.value:
                ## API key is not configured there, so continue
                continue

            factory = providers.get(provider)
            cls._connections[provider] = factory(config.get_config("MODELS", "API_KEY", provider))


    @overload
    @classmethod
    def get_connection(cls, provider: Literal["OPENAI"]) -> AsyncOpenAI: ...

    @overload
    @classmethod
    def get_connection(cls, provider: Literal["ANTHROPIC"]) -> AsyncAnthropic: ...

    @overload
    @classmethod
    def get_connection(cls, provider: Literal["GEMINI"]) -> genai.Client: ...

    @overload
    @classmethod
    def get_connection(cls, provider: Literal["EMBEDDING"]) -> StaticModel: ...

    @classmethod
    def get_connection(cls, provider: LLM_PROVIDER):
        connection_map = {
            "OPENAI": cls._openai_conn,
            "ANTHROPIC": cls._anthropic_conn,
            "GEMINI": cls._gemini_conn,
            "EMBEDDING": cls._model2vec_conn
        }
        conn = connection_map.get(provider)
        if not conn:
            raise ValueError(f"Provider {provider} not initialized or unknown")
        return conn