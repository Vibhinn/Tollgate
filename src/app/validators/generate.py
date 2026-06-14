from typing import Literal

from pydantic import BaseModel, Field

class GenerateTokenRequest(BaseModel):
    token_requirement: Literal["chat", "image", "audio"]
    role: Literal["user", "admin"]
    lifetime: int = Field(default=1296000)
