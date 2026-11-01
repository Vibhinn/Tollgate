from fastapi import APIRouter, Request, Depends, Header
from fastapi.responses import JSONResponse

from src.app.helpers import TollgateResponseBuilder
from ..injector import get_chat_adapter, get_tollgate_response_builder

from ..adapters import ChatAdapter
from .validators import ChatModel
from .middleware.base import TOKEN_VALUE_STATE_KEY, COMPLETION_STATE_KEY

chat_api_router = APIRouter(prefix="/v1", tags=["chat"])

CACHE_STATUS_HEADER = "X-Tollgate-Cache"
DEFAULT_CACHE_TTL_SECONDS = 3600


@chat_api_router.post(path="/chat/completions", tags=["chat"])
async def chat_complete(request: Request, user_requirement: ChatModel,
                        chat_adapter: ChatAdapter = Depends(get_chat_adapter),
                        tollgate_response_builder: TollgateResponseBuilder = Depends(get_tollgate_response_builder)):

    cache_ttl = int(request.headers.get("X-Cache-TTL", DEFAULT_CACHE_TTL_SECONDS))
    result = await chat_adapter.complete(
        user_id=request.scope.get("state", {}).get(TOKEN_VALUE_STATE_KEY),
        chat_request=user_requirement.to_chat_request(cache_ttl),
    )
    setattr(request.state, COMPLETION_STATE_KEY, result)
    return JSONResponse(
        status_code=200,
        content=tollgate_response_builder.build_response(result),
        headers={CACHE_STATUS_HEADER: "hit" if result.cached else "miss"},
    )
