from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.utils.types import ATOMIC_COUNTERS


class MetricsRepositoryInterface(ABC):
    @abstractmethod
    async def increment(self, counter: ATOMIC_COUNTERS) -> None:
        ...

    @abstractmethod
    async def record_model_call(self, model_name: str, input_tokens: int, output_tokens: int) -> None:
        ...

    @abstractmethod
    async def record_model_error(self, model_name: str) -> None:
        ...

    @abstractmethod
    async def read_counters(self) -> dict[str, int]:
        """Every gateway counter, 0 when it was never incremented."""
        ...

    @abstractmethod
    async def read_model_stats(self, model_names: list[str]) -> dict[str, dict[str, int]]:
        """Model -> requests, errors, input_tokens, output_tokens."""
        ...

    @abstractmethod
    async def ping(self) -> bool:
        ...
