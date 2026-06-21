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