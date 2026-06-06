from typing import Literal, TypedDict

REDIS_STREAM_NAMES = Literal["RESPONSE_CACHE"]
REPOSITORY_TYPE = Literal["EMBEDDING", "DATABASE", "VECTOR_DB", "CACHE", "ROUTER"]
ADAPTER_TYPE = Literal["CHAT"]
CONFIGURATION_SECTIONS = Literal["OPENAI", "ANTHROPIC", "LLAMA"]
CONFIGURATION_OPTIONS = Literal["ENDPOINT", "API_KEY"]


class CacheJobData(TypedDict):
    cache_type: Literal["exact", "semantic"]
    user_message: str
    model_response: str
    timeout: int
