from src.utils.types import LLMProvider

PROVIDERS = {
    "OpenAI": {
        "config_key": LLMProvider.OPENAI,
        "models": ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-3.5-turbo", "o1", "o3-mini"],
    },
    "Anthropic": {
        "config_key": LLMProvider.ANTHROPIC,
        "models": ["claude-opus-4-6", "claude-sonnet-4-6", "claude-haiku-4-5"],
    },
    "Gemini": {
        "config_key": LLMProvider.GEMINI,
        "models": ["gemini-3.5-flash", "gemini-3.5-flash-lite"],
    },
}

DEFAULT_EMBEDDING_MODEL = "minishlab/potion-base-8M"

DATABASE = ["SQLITE", "POSTGRESQL", "MYSQL"]