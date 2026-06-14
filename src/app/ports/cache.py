from typing import Any
from abc import ABC, abstractmethod

class CacheRepositoryInterface(ABC):
    @abstractmethod
    async def check_token_validity(self, token: str) -> bool:
        ...

    @abstractmethod
    async def get_user_id(self, token: str) -> str:
        ...

    @abstractmethod
    async def save(self, key: Any, value: Any, timeout: int) -> None:
        ...

    @abstractmethod
    async def search(self, key: Any) -> Any:
        ...