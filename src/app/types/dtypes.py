from typing import TypedDict, Literal
from .params import CACHE_TYPE

class CacheJobData(TypedDict):
    cache_type: CACHE_TYPE
    user_message: str
    model_response: str
    timeout: int
