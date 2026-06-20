from src.app.ports import JobQueueRepositoryInterface

from src.utils.types import AnalyticsJobData

class RouterAdapter:
    def __init__(self, job_queue_manager: JobQueueRepositoryInterface):
        self.job_queue_manager = job_queue_manager

    async def add_job_to_queue(self, data: dict) -> None:
        await self.job_queue_manager.create_job("ANALYTICS", data)