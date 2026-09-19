from fastapi import APIRouter, Request

transcription_api_router = APIRouter(prefix="/api/v1", tags=["audio"])

@transcription_api_router.post(path="/audio/transcribe", tags=["audio"])
async def transcribe_audio(request: Request):
    pass
