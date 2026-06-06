from openai import AsyncOpenAI

from typing import override

from src.app.ports import LargeLanguageModel
from src.utils import Config


class OpenAIRepository(LargeLanguageModel):
    def __init__(self):
        self.config = Config()
        self.api_key = self.config.get_config("OPENAI", "API_KEY")
        self.api_endpoint = self.config.get_config("OPENAI", "ENDPOINT")

        self.openai_client = AsyncOpenAI(
            api_key=self.api_key
        )

    @override
    async def invoke(self, message: str):
        model_response = await self.openai_client.chat.completions.create(

        )


