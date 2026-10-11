from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Literal, TYPE_CHECKING

if TYPE_CHECKING:
    from src.utils.types import RequestEventData

ENTITY_KIND = Literal["team", "user", "token"]


class MetricsRepositoryInterface(ABC):
    @abstractmethod
    async def record_request(self, event: RequestEventData) -> None:
        """Adds one request to the gateway totals and to its team, user (team:name) and token."""
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
    async def read_entity_stats(self, kind: ENTITY_KIND) -> dict[str, dict[str, Any]]:
        """Every team, user or token seen so far -> its totals, plus its per-model usage under "models"."""
        ...

    @abstractmethod
    async def ping(self) -> bool:
        ...
