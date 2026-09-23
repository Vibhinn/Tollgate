from abc import ABC, abstractmethod

class RankingRepositoryInterface(ABC):
    @abstractmethod
    async def update_score(self, key: str, member: str, score: float) -> None:
        ...

    @abstractmethod
    async def get_score(self, key: str, member: str) -> float | None:
        ...

    @abstractmethod
    async def get_top(self, key: str) -> str | None:
        ...

    @abstractmethod
    async def get_top_available(self, key: str, limit: int = 10) -> str | None:
        ...

    @abstractmethod
    async def mark_unavailable(self, model_name: str, ttl: int) -> None:
        ...

    @abstractmethod
    async def is_unavailable(self, model_name: str) -> bool:
        ...