from fastapi import APIRouter, Request

image_api_router = APIRouter(prefix="/api/v1", tags=["images"])

@image_api_router.post(path="/images/generation", tags=["images"])
async def generate_images(request: Request):
    pass
