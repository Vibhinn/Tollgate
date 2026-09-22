from typing import Literal
from pydantic import BaseModel, Field, model_validator


class GenerateTokenRequest(BaseModel):
    token_requirement: Literal["chat", "image", "audio"]
    role: Literal["user", "admin"] = Field(default="user")
    password: str | None = None
    lifetime: int = Field(default=1296000)

    @model_validator(mode="after")
    def validate_admin_password(self):
        if self.role == "admin" and not self.password:
            raise ValueError("Password is required for admin role")

        return self