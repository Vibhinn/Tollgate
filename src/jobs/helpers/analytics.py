import json

from typing import override, TYPE_CHECKING

from src.app.ports import RankingRepositoryInterface
from .base import BaseHelper

if TYPE_CHECKING:
    from src.utils.types import AnalyticsJobData, StreamPayload

ALPHA = 0.1

class AnalyticsJobHelper(BaseHelper):
    def __init__(self, ranking_repo: RankingRepositoryInterface):
        self.ranking_repo = ranking_repo

    @override
    async def execute(self, data: StreamPayload):
        payload: AnalyticsJobData = json.loads(data["payload"])

        model = payload["model_name"]
        latency = payload["latency_ms"]

        await self.__update_ema("model:ranking:latency", model, latency)

    async def __update_ema(self, key: str, member: str, new_value: float):
      old = await self.ranking_repo.get_score(key, member)
      ema = new_value if old is None else ALPHA * new_value + (1 - ALPHA) * old
      await self.ranking_repo.update_score(key, member, ema)
