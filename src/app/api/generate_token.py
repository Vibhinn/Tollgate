from fastapi import APIRouter, Depends, Request
from starlette.responses import JSONResponse

from .validators import GenerateTokenRequest
from ..adapters import GenerateAccessTokenAdapter
from src.utils.config import Config
from src.utils.crypto import verify_password

from ..injector import get_generate_token_adapter, get_config_object

generate_access_token_router = APIRouter(prefix="/api/v1", tags=["generate"])

@generate_access_token_router.post(path="/chat/generate", tags=["generate"])
async def generate_chat_token(
    request: Request,
    requirements: GenerateTokenRequest,
    generate_token_adapter: GenerateAccessTokenAdapter = Depends(get_generate_token_adapter),
    config: Config = Depends(get_config_object),
):
    token_requirement = requirements.token_requirement
    user_role = requirements.role
    admin_password: str | None = requirements.password
    ttl: int = requirements.lifetime

    if user_role == "admin":
        stored_hash = config.get_config("admin", "password_hash")
        if not admin_password or not verify_password(admin_password, stored_hash):
            return JSONResponse(status_code=401, content={"detail": "Invalid admin password"})

    token = await generate_token_adapter.generate_and_save_token(token_requirement, user_role, ttl)
    return JSONResponse(
        status_code=200,
        content={
            "token": token
        }
    )