from abc import ABC, abstractmethod

from src.utils.types import Message

class LLMRepositoryInterface(ABC):
    @abstractmethod
    async def invoke(self, message: list[Message], model_name: str):
        ...