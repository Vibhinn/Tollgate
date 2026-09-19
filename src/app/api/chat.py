from fastapi import APIRouter, Request, Depends
from fastapi.responses import JSONResponse

from ..injector import get_chat_adapter

from ..adapters import ChatAdapter
from .validators import ChatModel
from src.utils.types import CacheJobData, RedisStreamName

chat_api_router = APIRouter(prefix="/api/v1", tags=["chat"])

@chat_api_router.post(path="/chat/completions", tags=["chat"])
async def chat_complete(request: Request, user_requirement: ChatModel, chat_adapter: ChatAdapter = Depends(get_chat_adapter)):
    user_message: str = user_requirement.messages[-1].content
    requested_model: str = user_requirement.model

    search_result = await chat_adapter.check_cache(user_message)
    if search_result:
        return JSONResponse(
            status_code=200,
            content={
                "role": "model",
                "message": search_result
            }
        )

    model_response = await chat_adapter.query_llm(model_name=requested_model, messages=user_requirement.messages)

    if user_requirement.cache_type:
        caching_timeout_header = request.headers.get("X-Cache-TTL")
        cache_timeout: int = int(caching_timeout_header) if caching_timeout_header else 3600
        job_data = CacheJobData(
            cache_type=user_requirement.cache_type,
            user_message=user_message,
            model_response=model_response,
            timeout=cache_timeout
        )

        await chat_adapter.add_job_to_queue(RedisStreamName.RESPONSE_CACHE, job_data)

    return JSONResponse(
        status_code=200,
        content={
            "role": "assistant",
            "message": model_response
        }
    )
