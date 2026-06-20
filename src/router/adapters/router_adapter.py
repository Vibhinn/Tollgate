from src.app.ports import JobQueueRepositoryInterface


class RouterAdapter:
    def __init__(self, job_queue_manager: JobQueueRepositoryInterface):
        self.job_queue_manager = job_queue_manager

    async def add_analytics_job_to_queue(self, data: dict) -> None:
        pass