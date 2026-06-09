from openai import AsyncOpenAI
from anthropic import AsyncAnthropic
from google import genai
from model2vec import StaticModel
from typing import overload, Literal

from src.utils.types import LLM_PROVIDER

class LLMConnection:
    _openai_conn: AsyncOpenAI = None
    _anthropic_conn: AsyncAnthropic = None
    _gemini_conn: genai.Client = None
    _model2vec_conn: StaticModel = None

    @classmethod
    def initialize(cls, openai_key: str, anthropic_key: str, gemini_key: str, model2vec_model: str):
        cls._openai_conn = AsyncOpenAI(api_key=openai_key)
        cls._anthropic_conn = AsyncAnthropic(api_key=anthropic_key)
        cls._gemini_conn = genai.Client(api_key=gemini_key)
        cls._model2vec_conn = StaticModel.from_pretrained(model2vec_model)

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