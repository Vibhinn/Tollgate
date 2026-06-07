from typing import Literal

from pydantic import BaseModel, Field

from ..types import CACHE_TYPE

class Message(BaseModel):
    role: Literal["system", "developer", "user", "assistant"]
    content: str

class ChatModel(BaseModel):
    model: str
    messages: list[Message]
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    cache_type: CACHE_TYPE | None = None
