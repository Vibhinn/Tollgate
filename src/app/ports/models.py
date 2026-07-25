from abc import ABC, abstractmethod

class LLMRepositoryInterface(ABC):
    @abstractmethod
    def __init__(self, llm_connection_object):
        ...
    @abstractmethod
    async def invoke(self, message: str, model_name: str):
        ...