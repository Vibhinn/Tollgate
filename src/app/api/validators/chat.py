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

    messages: list[Message]
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    cache_type: CACHE_TYPE | None = None
    cache_match_score: float = Field(default=0.9, ge=0.0, le=1.0)
