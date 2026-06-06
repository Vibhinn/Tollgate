from typing import Literal

from pydantic import BaseModel

class Message(BaseModel):
    role: str
    content: str

class ChatModel(BaseModel):
    model: str
    messages: list[Message]
    temperature: float = 0.7
    cache_type: Literal["semantic", "exact"]
    model: str