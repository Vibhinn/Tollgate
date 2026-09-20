from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.utils.types import LLMInvocationResult

class LLMRepositoryInterface(ABC):
    @abstractmethod
    def __init__(self, llm_connection_object):
        ...
    @abstractmethod
    async def invoke(self, message: str, model_name: str) -> "LLMInvocationResult":
        ...