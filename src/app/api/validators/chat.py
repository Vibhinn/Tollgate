from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator

from src.utils.types import CACHE_TYPE, Message, GenerationParams, ChatRequest


class ChatModel(BaseModel):
    model: str
    messages: list[Message] = Field(min_length=1)

    temperature: float | None = Field(default=None, ge=0.0, le=2.0)
    top_p: float | None = Field(default=None, ge=0.0, le=1.0)
    stop: str | list[str] | None = None
    max_tokens: int | None = Field(default=None, ge=1)
    max_completion_tokens: int | None = Field(default=None, ge=1)

    stream: bool | None = None
    n: int | None = None
    tools: Any = None
    tool_choice: Any = None
    functions: Any = None
    function_call: Any = None
    response_format: dict | None = None

    cache_type: CACHE_TYPE | None = None
    cache_match_score: float = Field(default=0.9, ge=0.0, le=1.0)

    @field_validator("messages")
    @classmethod
    def validate_messages(cls, v):
        if not any(message.role == "user" for message in v):
            raise ValueError("messages must contain at least one user message")
        return v

    @field_validator("stop")
    @classmethod
    def validate_stop(cls, v):
        stop = [v] if isinstance(v, str) else v
        if stop is not None and len(stop) > 4:
            raise ValueError("stop accepts at most 4 sequences")
        return stop

    @model_validator(mode="after")
    def reject_unsupported_features(self):
        if self.stream:
            raise ValueError("stream=true is not supported yet")
        if self.n not in (None, 1):
            raise ValueError("n must be 1")
        if any(value is not None for value in (self.tools, self.tool_choice, self.functions, self.function_call)):
            raise ValueError("tools and function calling are not supported yet")
        if self.response_format is not None and self.response_format.get("type") != "text":
            raise ValueError("only response_format {'type': 'text'} is supported for now")
        return self

    def generation_params(self) -> GenerationParams:
        return GenerationParams(
            max_tokens=self.max_completion_tokens or self.max_tokens,
            temperature=self.temperature,
            top_p=self.top_p,
            stop=self.stop,
        )

    def to_chat_request(self, cache_ttl: int) -> ChatRequest:
        return ChatRequest(
            model=self.model,
            messages=self.messages,
            params=self.generation_params(),
            cache_type=self.cache_type,
            cache_match_score=self.cache_match_score,
            cache_ttl=cache_ttl,
        )
