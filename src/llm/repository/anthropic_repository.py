from src.app.ports import LLMRepositoryInterface
from src.utils.types import LLMProvider, LLMInvocationResult
from src.utils.decorators import throws_exception
from ..connection import LLMConnection

class AnthropicRepository(LLMRepositoryInterface):
    def __init__(self):
        self.anthropic_client = LLMConnection.get_connection(LLMProvider.ANTHROPIC)

    @throws_exception()
    async def invoke(self, message: str, model_name: str, max_tokens: int) -> LLMInvocationResult:
        response = await self.anthropic_client.messages.create(
            model=model_name,
            messages=[
                {
                    "role": "user",
                    "content": message,
                }
            ],
            max_tokens=max_tokens
        )

        return LLMInvocationResult(
            content=response.content[0].text,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
        )