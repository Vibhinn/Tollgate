from abc import ABC, abstractmethod

class LLMRepositoryInterface(ABC):
    @abstractmethod
    async def invoke(self, message: str, model_name: str):
        ...