from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.utils.types import StreamPayload

class BaseHelper(ABC):
    @abstractmethod
    async def execute(self, data: StreamPayload):
        ...