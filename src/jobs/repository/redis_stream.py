import asyncio
import json
import threading
from src.cache import CacheConnection
from ..helpers.base import BaseHelper
from src.utils.types import REDIS_STREAM_NAMES, CacheJobData

from src.app.ports import JobQueueRepositoryInterface

from typing import overload

class RedisStreamRepository(JobQueueRepositoryInterface):
    """Creates redis stream jobs and runs a background worker to process them"""

    def __init__(self):
        self.redis_client = CacheConnection.get_connection("EXACT")
        self._helper_registry: dict[str, BaseHelper] = {}
        self._worker_thread = threading.Thread(target=self._run_worker, daemon=True)
        self._loop = asyncio.new_event_loop()

    def register_helper(self, stream_name: REDIS_STREAM_NAMES, helper: BaseHelper):
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
                        await helper.execute(data)

    @overload
    async def create_job(self, stream_name: REDIS_STREAM_NAMES.RESPONSE_CACHE, data: CacheJobData) -> None:
        ...

    @overload
    async def create_job(self, stream_name: REDIS_STREAM_NAMES.VECTORIZE, data: CacheJobData) -> None:
        ...

    async def create_job(self, stream_name: REDIS_STREAM_NAMES, data: CacheJobData):
        await self.redis_client.xadd(stream_name, {"payload": json.dumps(data)})