from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.utils.types import RateLimitDecision


class RateLimiterInterface(ABC):
    @abstractmethod
    async def acquire(self, user_id: str) -> RateLimitDecision:
        """Takes one token from the user's bucket if it has one."""
        ...
