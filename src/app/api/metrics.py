import os
import psutil
from fastapi import APIRouter, Request

metrics_api_router = APIRouter(prefix="/api/v1", tags=["metrics"])
process_pid = os.getpid()
process_metrics_client = psutil.Process(process_pid)

@metrics_api_router.get("/metrics")
async def get_all_metrics(request: Request):
    """Gets all the metrics"""

    result = {"cpu": None,
              "memory": {
                  #all memory
              },
              "latency": {
                  #all latencies
              },
              "calls received": None,
              "successful": None,
              "failed requests": None,
              "rate limited": None,
              "redis health": None,
              "qdrant health": None}