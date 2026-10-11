import time
import uuid

from fastapi import APIRouter, Request, Depends, Header
from fastapi.responses import JSONResponse

from ..injector import get_chat_adapter

from ..adapters import ChatAdapter
from .validators import ChatModel
from .middleware.base import TOKEN_VALUE_STATE_KEY, COMPLETION_STATE_KEY
from src.utils.types import LLMInvocationResult

chat_api_router = APIRouter(prefix="/v1", tags=["chat"])

CACHE_STATUS_HEADER = "X-Tollgate-Cache"
DEFAULT_CACHE_TTL_SECONDS = 3600


def chat_completion(result: LLMInvocationResult) -> dict:
    return {
        "id": f"chatcmpl-{uuid.uuid4().hex}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": result.model,
        "choices": [{
            "index": 0,
            "message": {"role": "assistant", "content": result.content},
            "finish_reason": result.finish_reason,
        }],
        "usage": {
            "prompt_tokens": result.input_tokens,
            "completion_tokens": result.output_tokens,
            "total_tokens": result.input_tokens + result.output_tokens,
        },
    }


@chat_api_router.post(path="/chat/completions", tags=["chat"])
async def chat_complete(request: Request, user_requirement: ChatModel,
                        cache_ttl: int = Header(default=DEFAULT_CACHE_TTL_SECONDS, alias="X-Cache-TTL", gt=0),
                        chat_adapter: ChatAdapter = Depends(get_chat_adapter)):
    result = await chat_adapter.complete(
        user_id=request.scope.get("state", {}).get(TOKEN_VALUE_STATE_KEY),
        chat_request=user_requirement.to_chat_request(cache_ttl),
    )
    # picked up by RequestMetricsMiddleware for the per-team / per-token usage metrics
    setattr(request.state, COMPLETION_STATE_KEY, result)
    return JSONResponse(
        status_code=200,
        content=chat_completion(result),
        headers={CACHE_STATUS_HEADER: "hit" if result.cached else "miss"},
    )
