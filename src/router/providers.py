ROUTING_TABLE = {
    # OpenAI
    "gpt-4o": {"provider": "openai", "model": "gpt-4o"},
    "gpt-4o-mini": {"provider": "openai", "model": "gpt-4o-mini"},
    "gpt-4-turbo": {"provider": "openai", "model": "gpt-4-turbo"},
    "gpt-3.5-turbo": {"provider": "openai", "model": "gpt-3.5-turbo"},
    "o1": {"provider": "openai", "model": "o1"},
    "o3-mini": {"provider": "openai", "model": "o3-mini"},

    # Anthropic
    "claude-opus-4-6": {"provider": "anthropic", "model": "claude-opus-4-6"},
    "claude-sonnet-4-6": {"provider": "anthropic", "model": "claude-sonnet-4-6"},
    "claude-haiku-4-5": {"provider": "anthropic", "model": "claude-haiku-4-5-20251001"},

    # Gemini
    "gemini-2.0-flash": {"provider": "gemini", "model": "gemini-2.0-flash"},
    "gemini-2.0-flash-lite": {"provider": "gemini", "model": "gemini-2.0-flash-lite"},
    "gemini-1.5-pro": {"provider": "gemini", "model": "gemini-1.5-pro"},
}