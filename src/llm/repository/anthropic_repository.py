from src.app.ports import LargeLanguageModel


class AnthropicRepository(LargeLanguageModel):
    def __init__(self):
        pass

    async def invoke(self, message: str):
        pass
