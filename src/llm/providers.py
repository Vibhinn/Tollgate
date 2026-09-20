from openai import AsyncOpenAI
from anthropic import AsyncAnthropic
from google import genai
from model2vec import StaticModel

from src.utils.types import LLMProvider, ConfigurationSection, ConfigurationOption

providers = {
    LLMProvider.OPENAI: lambda key: AsyncOpenAI(api_key=key),
    LLMProvider.ANTHROPIC: lambda key: AsyncAnthropic(api_key=key),
    LLMProvider.GEMINI: lambda key: genai.Client(api_key=key),
}

embedding_model = {
    LLMProvider.EMBEDDING: lambda config: StaticModel.from_pretrained(
        config.get_config(ConfigurationSection.EMBEDDING, ConfigurationOption.MODEL_NAME),
        force_download=False,
    )
}
