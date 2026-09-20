from typing import override

from src.app.ports import LLMRepositoryInterface
from src.utils.types import LLMProvider, LLMInvocationResult

from ..connection import LLMConnection

class GeminiRepository(LLMRepositoryInterface):
    @override
    def __init__(self):
        self.gemini_client = LLMConnection.get_connection(LLMProvider.GEMINI)

    @override
    async def invoke(self, message: str, model_name: str) -> LLMInvocationResult:
        response = await self.gemini_client.aio.models.generate_content(
            model=model_name,
            contents=message,
        )
        return LLMInvocationResult(
            content=response.text,
            input_tokens=response.usage_metadata.prompt_token_count,
            output_tokens=response.usage_metadata.candidates_token_count,
        )
