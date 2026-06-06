from typing import Any
from abc import ABC, abstractmethod

class CacheRepository(ABC):
    @abstractmethod
    async def add_to_cache(self, key: Any, value: Any) -> None:
        ...

class TTLCacheRepository(CacheRepository):
    @abstractmethod
    async def add_to_cache(self, key: Any, value: Any, timeout: int = 3600) -> None:
        ...
