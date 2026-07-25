from typing import TYPE_CHECKING, override

from src.app.ports import LLMRepositoryInterface
from src.utils.types import LLMProvider

from ..connection import LLMConnection

if TYPE_CHECKING:
    from openai.types.chat import ChatCompletion


class OpenAIRepository(LLMRepositoryInterface):
    @override
    def __init__(self):
        self.openai_client = LLMConnection.get_connection(LLMProvider.OPENAI)

    @override
    async def invoke(self, message: str, model_name: str) -> "ChatCompletion":
        response = await self.openai_client.chat.completions.create(
            model=model_name,
            messages=[{"role": "user", "content": message}],
        )
        return response
