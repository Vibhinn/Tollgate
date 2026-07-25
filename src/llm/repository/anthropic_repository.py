from typing import TYPE_CHECKING

from src.app.ports import LLMRepositoryInterface
from src.utils.types import LLMProvider
from ..connection import LLMConnection

if TYPE_CHECKING:
    from anthropic.types import Message

class AnthropicRepository(LLMRepositoryInterface):
    def __init__(self):
        self.anthropic_client = LLMConnection.get_connection(LLMProvider.ANTHROPIC)

    async def invoke(self, message: str, model_name: str) -> Message:
        response = await self.anthropic_client.messages.create(
            model=model_name,
            messages=[
                {
                    "role": "user",
                    "content": message,
                }
            ],
        )

        return response