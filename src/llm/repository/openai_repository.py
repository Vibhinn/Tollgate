from typing import TYPE_CHECKING

from src.app.ports import LLMRepositoryInterface
from ..connection import LLMConnection

if TYPE_CHECKING:
    from openai.types.chat import ChatCompletion


class OpenAIRepository(LLMRepositoryInterface):
    def __init__(self):
        self.openai_client = LLMConnection.get_connection("OPENAI")

    async def invoke(self, message: str, model_name: str) -> "ChatCompletion":
        response = await self.openai_client.chat.completions.create(
            model=model_name,
            messages=[{"role": "user", "content": message}],
        )
        return response
