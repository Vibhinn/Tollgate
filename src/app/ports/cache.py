from typing import Any
from abc import ABC, abstractmethod

class CacheRepositoryInterface(ABC):
    @abstractmethod
    async def get_user_id(self, token: str) -> str | None:
        ...

    @abstractmethod
    async def save(self, key: Any, value: Any, timeout: int) -> None:
        ...

    @abstractmethod
    async def search(self, key: Any) -> Any:
        ...

    @abstractmethod
    async def increment(self, key: str) -> int:
        ...

    @abstractmethod
    async def decrement(self, key: str) -> int:
        ...