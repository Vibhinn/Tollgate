from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.utils.types import LLMInvocationResult, Message

class LLMRepositoryInterface(ABC):
    @abstractmethod
    def __init__(self):
        ...
    @abstractmethod
    async def invoke(self, messages: list[Message], model_name: str, max_tokens: int, temperature: float | None = None) -> "LLMInvocationResult":
        ...