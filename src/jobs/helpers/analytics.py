import json

from .base import BaseHelper
from src.utils.types import StreamPayload, AnalyticsJobData
from .pricing import PRICING_TABLE

class AnalyticsJobHelper(BaseHelper):
    def __init__(self, redis_client):
        self.redis_client = redis_client

    async def execute(self, data: StreamPayload):
        payload: AnalyticsJobData = json.loads(data["payload"])

        model = payload["model_name"]
        cost = self.__calculate_cost(model, payload["input_tokens"], payload["output_tokens"])

        analytics_event = {
            **payload,
            "cost_usd": cost
        }

        await self.redis_client.publish("ANALYTICS_CHANNEL", json.dumps(analytics_event))

    @staticmethod
    def __calculate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
        rates = PRICING_TABLE.get(model, {"input": 0, "output": 0})
        return (input_tokens * rates["input"] + output_tokens * rates["output"]) / 1_000_000
