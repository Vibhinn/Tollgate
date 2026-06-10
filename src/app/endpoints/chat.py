from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from ..state import ApplicationState
from src.utils.types import CacheJobData
from ..validators import ChatModel

chat_api_router = APIRouter(prefix="/api/v1", tags=["chat"])

@chat_api_router.post(path="/chat/completions", tags=["chat"])
async def chat_complete(request: Request, user_requirement: ChatModel):
    app_state: ApplicationState = request.app.state.application

    adapter_manager = app_state.adapter_manager
    chat_adapter = adapter_manager.get_adapter("CHAT")

    user_message: str = user_requirement.messages[-1].content
    requested_model: str = user_requirement.model
    caching_requested: bool = bool(user_requirement.cache_type)

    search_result = await chat_adapter.check_cache(user_message)
    if search_result:
        return JSONResponse(
            status_code=200,
            content={
                "role": "model",
                "message": search_result
            }
        )

    model_response = await chat_adapter.query_llm(model_name=requested_model, message=user_requirement.messages)

    if caching_requested:
        caching_timeout_header = request.headers.get("X-Cache-TTL")
        cache_timeout: int = int(caching_timeout_header) if caching_timeout_header else 3600
        await chat_adapter.add_job_to_queue("RESPONSE_CACHE", CacheJobData(
            cache_type=user_requirement.cache_type if user_requirement.cache_type else "EXACT",
            user_message=user_message,
            model_response=model_response,
            timeout=cache_timeout)
        )

    return JSONResponse(
        status_code=200,
        content={
            "role": "assistant",
            "message": model_response
    }
    )

