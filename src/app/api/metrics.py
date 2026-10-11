import asyncio
import json
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse

from ..injector import get_metrics_adapter
from ..adapters import MetricsAdapter
from .middleware.base import IDENTITY_STATE_KEY
from src.utils.types import TokenIdentity

metrics_api_router = APIRouter(prefix="/api/v1", tags=["metrics"])

SSE_HEADERS = {
    "Cache-Control": "no-cache",
    # stops nginx and similar proxies from buffering the stream
    "X-Accel-Buffering": "no",
}


async def metrics_events(metrics_adapter: MetricsAdapter, identity: TokenIdentity | None,
                         interval: int) -> AsyncIterator[str]:
    # Starlette cancels this generator when the client disconnects
    while True:
        snapshot = metrics_adapter.snapshot_for(identity)
        if snapshot is not None:
            yield f"event: metrics\ndata: {json.dumps(snapshot)}\n\n"
        await asyncio.sleep(interval)


@metrics_api_router.get(path="/metrics", tags=["metrics"])
async def stream_metrics(request: Request,
                         interval: int = Query(default=2, ge=1, le=60, description="Seconds between snapshots"),
                         metrics_adapter: MetricsAdapter = Depends(get_metrics_adapter)):
    """Server-sent events: one `metrics` event every `interval` seconds. Admin tokens also get the
    breakdown per team, user and token."""
    identity = getattr(request.state, IDENTITY_STATE_KEY, None)
    return StreamingResponse(metrics_events(metrics_adapter, identity, interval), media_type="text/event-stream",
                             headers=SSE_HEADERS)
