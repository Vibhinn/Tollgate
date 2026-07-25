from typing import TYPE_CHECKING, override

from src.app.ports import LLMRepositoryInterface
from src.utils.types import LLMProvider

from ..connection import LLMConnection

if TYPE_CHECKING:
    from google.genai.types import GenerateContentResponse

class GeminiRepository(LLMRepositoryInterface):
    @override
    def __init__(self):
        self.gemini_client = LLMConnection.get_connection(LLMProvider.GEMINI)

    @override
    async def invoke(self, message: str, model_name: str) -> "GenerateContentResponse":
        response = await self.gemini_client.aio.models.generate_content(
            model=model_name,
            contents=message,
        )
        return response
