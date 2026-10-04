from pydantic import BaseModel, Field, field_validator

from src.utils.types import CACHE_TYPE, Message
from src.utils.config import ROUTING_TABLE

class ChatModel(BaseModel):
    model: str

    @field_validator("model")
    @classmethod
    def validate_model(cls, v):
        if v not in ROUTING_TABLE and v not in ["fast", "cheap", "smart"]:
            raise ValueError(f"Unknown model: {v}. Available: {list(ROUTING_TABLE.keys())}")
        return v

    messages: list[Message] = Field(min_length=1)

    @field_validator("messages")
    @classmethod
    def validate_messages(cls, v):
        if not any(message.role == "user" for message in v):
            raise ValueError("messages must contain at least one user message")
        return v

    # None leaves it to the provider: reasoning models reject anything but their default
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)
    cache_type: CACHE_TYPE | None = None
    cache_match_score: float = Field(default=0.9, ge=0.0, le=1.0)
    max_tokens: int
