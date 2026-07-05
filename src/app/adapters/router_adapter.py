from typing import TYPE_CHECKING
from ..intelligence import intelligence_layer

if TYPE_CHECKING:
    from src.app.ports import JobQueueRepositoryInterface, RankingRepositoryInterface
    from src.utils.types import REDIS_STREAM_NAMES

class RouterAdapter:
    def __init__(self, job_queue_manager: JobQueueRepositoryInterface, ranking_repo: RankingRepositoryInterface):
        self.job_queue_manager = job_queue_manager
        self.ranking_repo = ranking_repo
        self.magic_command_map: dict = {
            "cheap": "model:ranking:cost",
            "fast": "model:ranking:latency"
        }

    async def add_job_to_queue(self, collection_name: REDIS_STREAM_NAMES, data: dict) -> None:
        await self.job_queue_manager.create_job(collection_name, data)

    async def get_best_model(self, requirement: str):
        key: str | None = self.magic_command_map.get(requirement)

        if not key:
            return None

        return await self.ranking_repo.get_top(key)

    async def identify_model_intelligently(self, user_message: str):
        model = await intelligence_layer.classify(user_message)
        return model