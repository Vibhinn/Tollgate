import asyncio
import json
import socket
import uuid
from typing import overload, Literal, TYPE_CHECKING

from src.cache import CacheConnection
from src.app.ports import JobQueueRepositoryInterface
from src.utils.types import CacheType, RedisStreamName
from src.app.exceptions import KVCacheNotReachable

if TYPE_CHECKING:
    from ..helpers.base import BaseHelper
    from src.utils.types import REDIS_STREAM_NAMES, CacheJobData, StreamPayload

GROUP_NAME: str = "tollgate-workers"
MAX_DELIVERIES: int = 5
CLAIM_IDLE_MS: int = 30_000


class RedisStreamRepository(JobQueueRepositoryInterface):
    """Creates redis stream jobs and runs a background worker to process them"""

    def __init__(self):
        self.redis_client = CacheConnection.get_connection(CacheType.EXACT)
        self._helper_registry: dict[str, BaseHelper] = {}
        self._task: asyncio.Task | None = None
        self._consumer_name: str = f"{socket.gethostname()}--{uuid.uuid4().hex[:8]}"


    def register_helper(self, stream_name: REDIS_STREAM_NAMES, helper: BaseHelper) -> None:
        self._helper_registry[stream_name] = helper


    async def _create_groups(self):
        for stream in self._helper_registry.keys():
            try:
                await self.redis_client.xgroup_create(
                    name=stream, groupname=GROUP_NAME, id="0", mkstream=True
                )
            except Exception as e:
                if "BUSYGROUP" not in str(e):
                    raise


    def start(self) -> None:
        #it has started in the main app lifespan event. The IDE does not reference it, hence the confusion
        try:
            self._task = asyncio.create_task(self._run())
            self._task.add_done_callback(self._on_task_done)
        except Exception as e:
            raise KVCacheNotReachable("Sorry, redis service is not available") from e


    def _on_task_done(self, task: asyncio.Task) -> None:
        if task.cancelled():
            return
        consumer_death_exception: BaseException | None = task.exception()
        if consumer_death_exception:
            self.start()


    async def _run(self):
        await self._create_groups()
        while True:
            await self._reclaim_stale_entries()
            await self._read_new_entries()


    async def _reclaim_stale_entries(self):
        for stream in self._helper_registry.keys():
            _, claimed, _ = await self.redis_client.xautoclaim(
                name=stream,
                groupname=GROUP_NAME,
                consumername=self._consumer_name,
                min_idle_time=CLAIM_IDLE_MS,
                start_id="0-0",
                count=50
            )

            for entry_id, data in claimed:
                await self._process(stream, entry_id, data)


    async def _read_new_entries(self):
        streams: dict = dict.fromkeys(self._helper_registry.keys(), ">")
        messages: list = await self.redis_client.xreadgroup(
            groupname=GROUP_NAME,
            consumername=self._consumer_name,
            streams=streams,
            count=10,
            block=1000
        )

        for stream, entries in messages:
            for entry_id, data in entries:
                await self._process(stream, entry_id, data)


    async def _process(self, stream: str, entry_id: str, data: StreamPayload):
        helper = self._helper_registry.get(stream)
        if not helper:
            await self._handle_failure(stream, entry_id, data)
            return

        try:
            await helper.execute(data)
            await self.redis_client.xack(stream, GROUP_NAME, entry_id)
        except Exception:
            await self._handle_failure(stream, entry_id, data)


    async def _handle_failure(self, stream: str, entry_id: str, data: StreamPayload):
        pending = await self.redis_client.xpending_range(
            name=stream, groupname=GROUP_NAME, min=entry_id, max=entry_id, count=1
        )
        deliveries = pending[0]["times_delivered"] if pending else 1

        if deliveries >= MAX_DELIVERIES:
            await self.redis_client.xadd(f"{stream}:dead", data, maxlen=1000, approximate=True)
            await self.redis_client.xack(stream, GROUP_NAME, entry_id)

    @overload
    async def create_job(self, stream_name: Literal[RedisStreamName.RESPONSE_CACHE], data: CacheJobData) -> None: ...

    @overload
    async def create_job(self, stream_name: Literal[RedisStreamName.ANALYTICS], data: CacheJobData) -> None: ...

    async def create_job(self, stream_name: REDIS_STREAM_NAMES, data: CacheJobData):
        payload: StreamPayload = {"payload": json.dumps(data)}
        await self.redis_client.xadd(stream_name, payload, maxlen=1000, approximate=True)  # type: ignore