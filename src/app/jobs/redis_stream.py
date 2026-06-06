import asyncio
import threading
from src.cache import redis_client
from ..types import REDIS_STREAM_NAMES, CacheJobData

from typing import Callable, overload

class BackgroundJobCreator:
    """Creates redis stream jobs and runs a background worker to process them"""

    def __init__(self):
        self.redis_client = redis_client
        self._helper_registry: dict[str, Callable] = {}
        self._worker_thread = threading.Thread(target=self._run_worker, daemon=True)
        self._loop = asyncio.new_event_loop()

    def register_helper(self, stream_name: REDIS_STREAM_NAMES, helper: Callable):
        self._helper_registry[stream_name] = helper

    def start(self):
        self._worker_thread.start()

    def _run_worker(self):
        self._loop.run_until_complete(self._listen())

    async def _listen(self):
        while True:
            messages = await self.redis_client.xread(
                {stream: "$" for stream in self._helper_registry.keys()},
                block=1000
            )
            for stream, entries in messages:
                for entry_id, data in entries:
                    helper = self._helper_registry.get(stream)
                    if helper:
                        await helper(data)

    @overload
    async def create_job(self, stream_name: REDIS_STREAM_NAMES.RESPONSE_CACHE, data: CacheJobData) -> None:
        ...

    @overload
    async def create_job(self, stream_name: REDIS_STREAM_NAMES.VECTORIZE, data: CacheJobData) -> None:
        ...

    async def create_job(self, stream_name: REDIS_STREAM_NAMES, data: CacheJobData):
        await self.redis_client.xadd(stream_name, data)