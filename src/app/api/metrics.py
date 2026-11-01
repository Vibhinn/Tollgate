from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse

from ..injector import get_metrics_adapter, get_metrics_snapshot_manager
from ..adapters import MetricsAdapter
from .middleware.base import IDENTITY_STATE_KEY

from src.app.helpers import MetricsEventsSnapshotManager

metrics_api_router = APIRouter(prefix="/api/v1", tags=["metrics"])

@metrics_api_router.get(path="/metrics", tags=["metrics"])
async def stream_metrics(request: Request,
                         interval: int = Query(default=2, ge=1, le=60, description="Seconds between snapshots"),
                         metrics_adapter: MetricsAdapter = Depends(get_metrics_adapter),
                         metrics_snapshot_manager: MetricsEventsSnapshotManager = Depends(get_metrics_snapshot_manager)):
    identity = getattr(request.state, IDENTITY_STATE_KEY, None)
    snapshot = metrics_snapshot_manager.get_metrics_snapshot(metrics_adapter, identity, interval)
    return StreamingResponse(snapshot, media_type="text/event-stream",
                             headers={
                                        "Cache-Control": "no-cache",
                                        "X-Accel-Buffering": "no",
                                    })
