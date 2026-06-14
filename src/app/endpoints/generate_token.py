from fastapi import APIRouter, Depends, Request
from starlette.responses import JSONResponse

from ..validators import GenerateTokenRequest
from ..adapters import GenerateAccessTokenAdapter

from ..injector import get_generate_token_adapter

generate_access_token_router = APIRouter(prefix="/api/v1", tags=["generate"])

@generate_access_token_router.post(path="/chat/generate", tags=["generate"])
async def generate_chat_token(request: Request, requirements: GenerateTokenRequest, generate_token_adapter: GenerateAccessTokenAdapter = Depends(get_generate_token_adapter)):
    token_requirement = requirements.token_requirement
    user_role = requirements.role
    ttl: int = requirements.lifetime

    token = await generate_token_adapter.generate_and_save_token(token_requirement, user_role, ttl)
    return JSONResponse(
        status_code=200,
        content={
            "token": token
        }
    )