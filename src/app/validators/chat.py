from typing import Literal

from pydantic import BaseModel, Field, field_validator

from src.utils.types import CACHE_TYPE
from src.router import ROUTING_TABLE

class Message(BaseModel):
    role: Literal["system", "developer", "user", "assistant"]
    content: str

class ChatModel(BaseModel):
    model: str

    @field_validator("model")
    @classmethod
    def validate_model(cls, v):
        if v not in ROUTING_TABLE or v not in ["fast", "cheap", "smart"]:
            raise ValueError(f"Unknown model: {v}. Available: {list(ROUTING_TABLE.keys())}")
        return v

    messages: list[Message]
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    cache_type: CACHE_TYPE | None = None
