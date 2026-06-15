from pydantic import BaseModel
from typing import TypedDict, Literal
from .params import CACHE_TYPE

class Message(BaseModel):
    role: Literal["system", "developer", "user", "assistant"]
    content: str

class CacheJobData(TypedDict):
    cache_type: CACHE_TYPE
    user_message: str
    model_response: str
    timeout: int

class StreamPayload(TypedDict):
    payload: str
