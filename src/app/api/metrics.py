import asyncio
import json
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse

from ..injector import get_metrics_adapter
from ..adapters import MetricsAdapter

metrics_api_router = APIRouter(prefix="/api/v1", tags=["metrics"])

SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "X-Accel-Buffering": "no",
}


async def metrics_events(metrics_adapter: MetricsAdapter, interval: int) -> AsyncIterator[str]:
    while True:
        snapshot = await metrics_adapter.snapshot()
        yield f"event: metrics\ndata: {json.dumps(snapshot)}\n\n"
        await asyncio.sleep(interval)


@metrics_api_router.get(path="/metrics", tags=["metrics"])
async def stream_metrics(interval: int = Query(default=2, ge=1, le=60, description="Seconds between snapshots"),
                         metrics_adapter: MetricsAdapter = Depends(get_metrics_adapter)):
    return StreamingResponse(metrics_events(metrics_adapter, interval), media_type="text/event-stream",
                             headers=SSE_HEADERS)
