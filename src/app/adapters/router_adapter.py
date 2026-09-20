from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.app.ports import JobQueueRepositoryInterface, RankingRepositoryInterface
    from src.app.intelligence import RoutingIntelligenceLayer
    from src.llm import LLMRepositoryFactory
    from src.utils.types import REDIS_STREAM_NAMES


class RouterAdapter:
    def __init__(
        self,
        job_queue_manager: JobQueueRepositoryInterface,
        ranking_repo: RankingRepositoryInterface,
        intelligence: RoutingIntelligenceLayer,
        llm_repo_factory: LLMRepositoryFactory,
    ):
        self.job_queue_manager = job_queue_manager
        self.ranking_repo = ranking_repo
        self.intelligence = intelligence
        self.llm_repo_factory = llm_repo_factory

    async def add_job_to_queue(self, collection_name: "REDIS_STREAM_NAMES", data: dict) -> None:
        await self.job_queue_manager.create_job(collection_name, data)

    async def get_best_model(self, requirement: str):
        if requirement == "cheap":
            from src.router.core import get_cheapest_model
            return get_cheapest_model(self.llm_repo_factory)
        if requirement == "fast":
            return await self.ranking_repo.get_top("model:ranking:latency")
        return None

    async def identify_model_intelligently(self, user_message: str) -> str:
        return await self.intelligence.classify(user_message)