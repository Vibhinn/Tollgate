from typing import override

from src.app.ports import LLMRepositoryInterface
from ..connection import LLMConnection
from src.app.validators import Message

class OpenAIRepository(LLMRepositoryInterface):
    def __init__(self):
        self.openai_client = LLMConnection.get_connection("OPENAI")

    @override
    async def invoke(self, message: list[Message], model_name: str):
        model_response = await self.openai_client.chat.completions.create(
            model=model_name,
            messages=message
        )
        return model_response.choices[0].message.content


