import time

from fastapi import APIRouter, Depends

from ..injector import get_models_adapter
from ..adapters import ModelsAdapter

models_api_router = APIRouter(prefix="/v1", tags=["models"])

# OpenAI requires a creation time; the model list is fixed for the life of the process
_MODELS_CREATED_AT = int(time.time())


@models_api_router.get(path="/models", tags=["models"])
async def list_models(models_adapter: ModelsAdapter = Depends(get_models_adapter)):
    return {
        "object": "list",
        "data": [
            {"id": model_id, "object": "model", "created": _MODELS_CREATED_AT, "owned_by": owner}
            for model_id, owner in models_adapter.list_models().items()
        ],
    }
