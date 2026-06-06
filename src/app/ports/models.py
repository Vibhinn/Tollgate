from abc import ABC, abstractmethod

class LargeLanguageModel(ABC):
    @abstractmethod
    async def invoke(self, message: str):
        ...