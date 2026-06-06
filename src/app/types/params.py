from typing import Literal, TypedDict

REDIS_STREAM_NAMES = Literal["VECTORIZE", "RESPONSE_CACHE"]
REPOSITORY_TYPE = Literal["EMBEDDING", "DATABASE", "VECTOR_DB", "CACHE", "ROUTER"]
ADAPTER_TYPE = Literal["CHAT"]


class CacheJobData(TypedDict):
    cache_type: Literal["exact", "semantic"]
    user_message: str
    model_response: str
    timeout: int
