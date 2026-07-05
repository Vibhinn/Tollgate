PROVIDERS = {
    "OpenAI": {
        "config_key": "OPENAI",
        "models": ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-3.5-turbo", "o1", "o3-mini"],
    },
    "Anthropic": {
        "config_key": "ANTHROPIC",
        "models": ["claude-opus-4-6", "claude-sonnet-4-6", "claude-haiku-4-5"],
    },
    "Gemini": {
        "config_key": "GEMINI",
        "models": ["gemini-2.0-flash", "gemini-2.0-flash-lite", "gemini-1.5-pro"],
    },
}

DEFAULT_EMBEDDING_MODEL = "minishlab/potion-base-8M"

DATABASE = ["SQLITE", "POSTGRESQL", "MYSQL"]
