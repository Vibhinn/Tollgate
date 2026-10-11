from typing import Any, TYPE_CHECKING
from abc import ABC, abstractmethod

if TYPE_CHECKING:
    from src.utils.types import TokenIdentity

class CacheRepositoryInterface(ABC):
    @abstractmethod
    async def get_user_id(self, token: str) -> str | None:
        ...

    @abstractmethod
    async def get_identity(self, token: str) -> "TokenIdentity | None":
        ...

    @abstractmethod
    async def create_token(self, team: str, name: str, role: str, ttl_seconds: int) -> str:
        """Stores a new token (only its hash) and returns the token itself."""
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