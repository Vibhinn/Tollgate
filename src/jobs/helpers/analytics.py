from __future__ import annotations

import json

from typing import override, TYPE_CHECKING

from src.app.ports import RankingRepositoryInterface, MetricsRepositoryInterface
from .base import BaseHelper

if TYPE_CHECKING:
    from src.utils.types import AnalyticsJobData, StreamPayload

ALPHA = 0.1

class AnalyticsHelper(BaseHelper):
    def __init__(self, ranking_repo: RankingRepositoryInterface, metrics_repo: MetricsRepositoryInterface):
        self.ranking_repo = ranking_repo
        self.metrics_repo = metrics_repo

    @override
    async def execute(self, data: StreamPayload):
        payload: AnalyticsJobData = json.loads(data["payload"])

        model = payload["model_name"]

        # jobs queued before the succeeded field existed were all successes
        if not payload.get("succeeded", True):
            await self.metrics_repo.record_model_error(model)
            return

        await self.__update_ema("model:ranking:latency", model, payload["latency_ms"])
        await self.metrics_repo.record_model_call(model, payload["input_tokens"], payload["output_tokens"])

    async def __update_ema(self, key: str, member: str, new_value: float):
      old = await self.ranking_repo.get_score(key, member)
      ema = new_value if old is None else ALPHA * new_value + (1 - ALPHA) * old
      await self.ranking_repo.update_score(key, member, ema)
