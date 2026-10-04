from dataclasses import dataclass
from pydantic import BaseModel
from typing import TypedDict, Literal
from .params import CACHE_TYPE

class Message(BaseModel):
    role: Literal["system", "developer", "user", "assistant"]
    content: str


def last_user_message(messages: list[Message]) -> Message:
    for message in reversed(messages):
        if message.role == "user":
            return message
    raise ValueError("messages must contain at least one user message")

@dataclass
class LLMInvocationResult:
    content: str
    input_tokens: int
    output_tokens: int

class CacheJobData(TypedDict):
    cache_type: CACHE_TYPE
    exact_key: str
    context_hash: str
    prompt: str
    model_response: str
    timeout: int

class StreamPayload(TypedDict):
    payload: str

class AnalyticsJobData(TypedDict):
    model_name: str
    input_tokens: int
    output_tokens: int
    latency_ms: float
    timestamp: str