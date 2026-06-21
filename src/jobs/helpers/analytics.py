import json

from typing import override

from src.app.ports import RankingRepositoryInterface
from src.utils.types import AnalyticsJobData, StreamPayload
from src.router.core.pricing import PRICING_TABLE
from .base import BaseHelper

ALPHA = 0.1

class AnalyticsJobHelper(BaseHelper):
    def __init__(self, ranking_repo: RankingRepositoryInterface):
        self.ranking_repo = ranking_repo

    @override
    async def execute(self, data: StreamPayload):
        payload: AnalyticsJobData = json.loads(data["payload"])

        model = payload["model_name"]
        cost = self.__calculate_cost(model, payload["input_tokens"], payload["output_tokens"])
        latency = payload["latency_ms"]

        await self.__update_ema("model:ranking:cost", model, cost)
        await self.__update_ema("model:ranking:latency", model, latency)

    async def __update_ema(self, key: str, member: str, new_value: float):
      old = await self.ranking_repo.get_score(key, member)
      ema = new_value if old is None else ALPHA * new_value + (1 - ALPHA) * old
      await self.ranking_repo.update_score(key, member, ema)

    @staticmethod
    def __calculate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
        rates = PRICING_TABLE.get(model, {"input": 0, "output": 0})
        return (input_tokens * rates["input"] + output_tokens * rates["output"]) / 1_000_000
