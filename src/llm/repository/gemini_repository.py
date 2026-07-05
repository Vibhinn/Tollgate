from typing import TYPE_CHECKING

from src.app.ports import LLMRepositoryInterface
from ..connection import LLMConnection

if TYPE_CHECKING:
    from google.genai.types import GenerateContentResponse

class GeminiRepository(LLMRepositoryInterface):
    def __init__(self):
        self.gemini_client = LLMConnection.get_connection("GEMINI")

    async def invoke(self, message: str, model_name: str) -> "GenerateContentResponse":
        response = await self.gemini_client.aio.models.generate_content(
            model=model_name,
            contents=message,
        )
        return response
