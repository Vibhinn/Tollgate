from src.app.ports import LLMRepositoryInterface
from ..connection import LLMConnection


class AnthropicRepository(LLMRepositoryInterface):
    def __init__(self):
        self.anthropic_client = LLMConnection.get_connection("ANTHROPIC")

    async def invoke(self, message: str):
        pass
