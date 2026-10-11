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
    async def get_top_available(self, key: str, candidates: list[str] | None = None) -> str | None:
        """The best-ranked model that isn't benched; with candidates, only among those."""
        ...

    @abstractmethod
    async def mark_unavailable(self, model_name: str, ttl: int) -> None:
        ...

    @abstractmethod
    async def filter_available(self, model_names: list[str]) -> list[str]:
        ...

    @abstractmethod
    async def seconds_until_available(self, model_names: list[str]) -> int | None:
        """Seconds until the first benched model among these is back; None when none is benched."""
        ...
