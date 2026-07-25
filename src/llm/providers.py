from openai import AsyncOpenAI
from anthropic import AsyncAnthropic
from google import genai

from src.cache import CacheConnection
from src.utils.types import LLMProvider, CacheType

providers = {
    LLMProvider.OPENAI: lambda key: AsyncOpenAI(api_key=key),
    LLMProvider.ANTHROPIC: lambda key: AsyncAnthropic(api_key=key),
    LLMProvider.GEMINI: lambda key: genai.Client(api_key=key),
}

embedding_model = {
    LLMProvider.EMBEDDING: lambda: CacheConnection.get_connection(CacheType.SEMANTIC)
}
