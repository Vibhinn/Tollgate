from dataclasses import dataclass
from pydantic import BaseModel, field_validator
from typing import TypedDict, Literal
from .params import CACHE_TYPE

# OpenAI finish reasons; every provider's stop reason is mapped onto one of these
FINISH_REASON = Literal["stop", "length", "content_filter"]


class Message(BaseModel):
    role: Literal["system", "developer", "user", "assistant"]
    content: str

    @field_validator("content", mode="before")
    @classmethod
    def join_text_parts(cls, value):
        """OpenAI also accepts content as [{"type": "text", "text": ...}, ...]. Parts are joined here
        so cache keys and providers only ever see a string."""
        if not isinstance(value, list):
            return value
        texts = []
        for part in value:
            part_type = part.get("type") if isinstance(part, dict) else None
            if part_type != "text" or not isinstance(part.get("text"), str):
                raise ValueError(f"Only text content parts are supported, got '{part_type}'")
            texts.append(part["text"])
        return "\n".join(texts)


def last_user_message(messages: list[Message]) -> Message:
    for message in reversed(messages):
        if message.role == "user":
            return message
    raise ValueError("messages must contain at least one user message")

@dataclass(frozen=True)
class GenerationParams:
    """Sampling options passed through to the provider. None means the provider's default."""
    max_tokens: int | None = None
    temperature: float | None = None
    top_p: float | None = None
    stop: list[str] | None = None


CACHE_OUTCOME = Literal["exact_hit", "semantic_hit", "miss"]


@dataclass
class LLMInvocationResult:
    content: str
    input_tokens: int
    output_tokens: int
    finish_reason: FINISH_REASON = "stop"
    model: str = ""     # the routing alias that answered, set by the router
    cache_outcome: CACHE_OUTCOME | None = None

    @property
    def cached(self) -> bool:
        return self.cache_outcome in ("exact_hit", "semantic_hit")


@dataclass(frozen=True)
class TokenIdentity:
    """Who a token belongs to, as the auth middleware hands it to the rest of the request."""
    user_id: str        # team:name
    team: str
    name: str
    token_id: str       # the short ID from `tollgate token list`
    role: str


@dataclass(frozen=True)
class ChatRequest:
    """A chat completion request, free of HTTP and pydantic, as the adapter receives it."""
    model: str
    messages: list[Message]
    params: GenerationParams
    cache_type: CACHE_TYPE | None = None
    cache_match_score: float = 0.9
    cache_ttl: int = 3600

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
    succeeded: bool     # False: the provider failed; only the model's error count changes


class RequestEventData(TypedDict):
    """One per HTTP request, pushed to the analytics stream by RequestMetricsMiddleware."""
    kind: Literal["request"]
    status: int
    rejected_by: Literal["rate_limit", "backpressure"] | None
    cache_outcome: CACHE_OUTCOME | None
    model: str | None
    input_tokens: int
    output_tokens: int
    team: str | None        # None when the request never got past auth
    name: str | None
    token_id: str | None
    timestamp: str