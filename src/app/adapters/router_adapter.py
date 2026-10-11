from __future__ import annotations

from typing import TYPE_CHECKING

from src.utils.config import ROUTING_TABLE

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
            return await get_cheapest_model(self.llm_repo_factory, self.ranking_repo)
        if requirement == "fast":
            configured_models = [name for name, entry in ROUTING_TABLE.items()
                                 if self.llm_repo_factory.get_repo(entry["provider"]) is not None]
            return await self.ranking_repo.get_top_available("model:ranking:latency", configured_models)
        return None

    async def identify_model_intelligently(self, user_message: str) -> str | None:
        category = await self.intelligence.classify(user_message)

        from src.router.core import resolve_smart_model
        return await resolve_smart_model(category, self.llm_repo_factory, self.ranking_repo)

    async def mark_model_unavailable(self, model_name: str, ttl: int) -> None:
        await self.ranking_repo.mark_unavailable(model_name, ttl)

    async def seconds_until_available(self, model_names: list[str]) -> int | None:
        return await self.ranking_repo.seconds_until_available(model_names)