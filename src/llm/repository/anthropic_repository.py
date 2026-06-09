from src.app.ports import LargeLanguageModel
from ..connection import LLMConnection


class AnthropicRepository(LargeLanguageModel):
    def __init__(self):
        self.anthropic_client = LLMConnection.get_connection("ANTHROPIC")

    async def invoke(self, message: str):
        pass
