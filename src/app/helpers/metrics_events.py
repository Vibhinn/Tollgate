import json
import asyncio

from ..adapters import MetricsAdapter
from src.utils.types import TokenIdentity

class MetricsEventsSnapshotManager:
    @staticmethod
    async def get_metrics_snapshot(metrics_adapter: MetricsAdapter,
                                    identity: TokenIdentity | None,
                                    interval: int):
        while True:
            snapshot = metrics_adapter.snapshot_for(identity)
            if snapshot is not None:
                yield f"event: metrics\ndata: {json.dumps(snapshot)}\n\n"
            await asyncio.sleep(interval)
