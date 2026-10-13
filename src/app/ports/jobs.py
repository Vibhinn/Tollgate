from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Literal, Mapping, overload, TYPE_CHECKING

if TYPE_CHECKING:
    from src.utils.types import (REDIS_STREAM_NAMES, RedisStreamName, CacheJobData, AnalyticsJobData,
                                 RequestEventData)


class JobQueueRepositoryInterface(ABC):
    @overload
    async def create_job(self, collection_name: Literal[RedisStreamName.RESPONSE_CACHE], data: CacheJobData) -> None: ...

    @overload
    async def create_job(self, collection_name: Literal[RedisStreamName.ANALYTICS],
                         data: AnalyticsJobData | RequestEventData) -> None: ...

    # a plain mapping until log entries get their own TypedDict
    @overload
    async def create_job(self, collection_name: Literal[RedisStreamName.LOGGING], data: Mapping[str, Any]) -> None: ...

    @abstractmethod
    async def create_job(self, collection_name: REDIS_STREAM_NAMES, data: Mapping[str, Any]) -> None:
        ...
