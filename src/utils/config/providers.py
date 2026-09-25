from src.utils.types import LLMProvider

ROUTING_TABLE = {
    # OpenAI
    "gpt-4o": {"provider": LLMProvider.OPENAI, "model": "gpt-4o"},
    "gpt-4o-mini": {"provider": LLMProvider.OPENAI, "model": "gpt-4o-mini"},
    "gpt-4-turbo": {"provider": LLMProvider.OPENAI, "model": "gpt-4-turbo"},
    "gpt-3.5-turbo": {"provider": LLMProvider.OPENAI, "model": "gpt-3.5-turbo"},
    "o1": {"provider": LLMProvider.OPENAI, "model": "o1"},
    "o3-mini": {"provider": LLMProvider.OPENAI, "model": "o3-mini"},

    # Anthropic
    "claude-opus-4-6": {"provider": LLMProvider.ANTHROPIC, "model": "claude-opus-4-6"},
    "claude-sonnet-4-6": {"provider": LLMProvider.ANTHROPIC, "model": "claude-sonnet-4-6"},
    "claude-haiku-4-5": {"provider": LLMProvider.ANTHROPIC, "model": "claude-haiku-4-5-20251001"},

    # Gemini
    "gemini-3.5-flash": {"provider": LLMProvider.GEMINI, "model": "gemini-3.5-flash"},
    "gemini-3.5-flash-lite": {"provider": LLMProvider.GEMINI, "model": "gemini-3.5-flash-lite"},
}