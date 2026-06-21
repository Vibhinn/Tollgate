import time
from datetime import datetime

from src.utils.types import Message, AnalyticsJobData
from src.utils.config import ROUTING_TABLE
from src.llm import LLMRepositoryFactory

from .adapters import RouterAdapter

class RouterRepository:
    def __init__(self, llm_repo_factory: LLMRepositoryFactory, router_adapter: RouterAdapter):
        self.routing_table = ROUTING_TABLE
        self.llm_repo_factory = llm_repo_factory
        self.router_adapter = router_adapter

    async def invoke_model(self, model_name: str, message: list[Message]) -> str:
        repository_name: str = self.routing_table.get(model_name).get("provider")
        repository = self.llm_repo_factory.get_repo(repository_name)

        if not repository:
            return ""

        start: float = time.monotonic()
        model_response = await repository.invoke(message[-1].content, model_name)
        latency_ms: float = (time.monotonic() - start)*1000

        analytics_object = AnalyticsJobData(
            model_name=model_name,
            input_tokens=model_response.usage.input_tokens,
            output_tokens=model_response.usage.output_tokens,
            latency_ms=latency_ms,
            timestamp=datetime.utcnow().isoformat()
        )

        await self.router_adapter.add_job_to_queue(analytics_object)
        return model_response.content[0].text

    async def get_best_model(self, requirement: str) -> str:
        return await self.router_adapter.get_best_model(requirement)
