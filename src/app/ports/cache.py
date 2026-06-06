from typing import Any
from abc import ABC, abstractmethod

class CacheRepository(ABC):
    @abstractmethod
    async def save(self, key: Any, value: Any, timeout: int) -> None:
        ...

    @abstractmethod
    async def search(self, key: Any) -> Any:
        ...