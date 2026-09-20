from typing import override

from src.app.ports import LLMRepositoryInterface
from src.utils.types import LLMProvider, LLMInvocationResult

from ..connection import LLMConnection


class OpenAIRepository(LLMRepositoryInterface):
    @override
    def __init__(self):
        self.openai_client = LLMConnection.get_connection(LLMProvider.OPENAI)

    @override
    async def invoke(self, message: str, model_name: str, max_tokens: int) -> LLMInvocationResult:
        response = await self.openai_client.chat.completions.create(
            model=model_name,
            messages=[{"role": "user", "content": message}],
            max_tokens=max_tokens,
        )
        return LLMInvocationResult(
            content=response.choices[0].message.content,
            input_tokens=response.usage.prompt_tokens,
            output_tokens=response.usage.completion_tokens,
        )
