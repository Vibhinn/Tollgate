from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.app.ports import JobQueueRepositoryInterface, RankingRepositoryInterface

class RouterAdapter:
    def __init__(self, job_queue_manager: JobQueueRepositoryInterface, ranking_repo: RankingRepositoryInterface):
        self.job_queue_manager = job_queue_manager
        self.ranking_repo = ranking_repo
        self.magic_command_map: dict = {
            "cheap": "model:ranking:cost",
            "fast": "model:ranking:latency"
        }

    async def add_job_to_queue(self, data: dict) -> None:
        await self.job_queue_manager.create_job("ANALYTICS", data)

    async def get_best_model(self, requirement: str):
        key: str | None = self.magic_command_map.get(requirement)

        if not key:
            return None

        return await self.ranking_repo.get_top(key)