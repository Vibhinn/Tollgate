from abc import ABC, abstractmethod

from src.app.validators import Message

class LargeLanguageModel(ABC):
    @abstractmethod
    async def invoke(self, message: list[Message], model_name: str):
        ...