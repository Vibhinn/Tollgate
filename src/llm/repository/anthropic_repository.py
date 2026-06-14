from src.app.ports import LLMRepositoryInterface
from ..connection import LLMConnection


class AnthropicRepository(LLMRepositoryInterface):
    def __init__(self):
        self.anthropic_client = LLMConnection.get_connection("ANTHROPIC")

    async def invoke(self, message: str, model_name: str) -> str:
        response = await self.anthropic_client.messages.create(
            model=model_name,
            max_tokens=100,
            messages=[
                {
                    "role": "user",
                    "content": message,
                }
            ],
        )

        return response.content[0].text