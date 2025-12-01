"""
Prometheus Metrics Endpoint for FastAPI

Usage:
1. Copy this file to your app/api/endpoints/ directory
2. Import and include router in your main router:
   
   from app.api.endpoints import metrics
   router.include_router(metrics.router, tags=["metrics"])

3. Access metrics at: GET /metrics
"""

import gc
import sys
import time

from fastapi import APIRouter
from fastapi.responses import PlainTextResponse

router = APIRouter()

# Track start time for uptime calculation
_start_time = time.time()


@router.get("/metrics", response_class=PlainTextResponse)
async def metrics():
    """
    Prometheus metrics endpoint.
    
    Returns metrics in Prometheus text format for scraping.
    No authentication required.
    """
    import resource

    # Calculate uptime
    uptime = time.time() - _start_time

    # Memory info (works on Linux/macOS)
    rusage = resource.getrusage(resource.RUSAGE_SELF)
    # macOS returns bytes, Linux returns KB - normalize to bytes
    memory_rss = rusage.ru_maxrss
    if sys.platform == "darwin":
        memory_rss = memory_rss  # Already in bytes on macOS
    else:
        memory_rss = memory_rss * 1024  # Convert KB to bytes on Linux

    # GC stats
    gc_stats = gc.get_stats()
    gc_collections = sum(s.get("collections", 0) for s in gc_stats)

    metrics_text = f"""# HELP python_uptime_seconds Process uptime in seconds
# TYPE python_uptime_seconds gauge
python_uptime_seconds {uptime}

# HELP python_memory_rss_bytes Resident set size in bytes
# TYPE python_memory_rss_bytes gauge
python_memory_rss_bytes {memory_rss}

# HELP python_gc_collections_total Total number of garbage collections
# TYPE python_gc_collections_total counter
python_gc_collections_total {gc_collections}

# HELP python_info Python interpreter info
# TYPE python_info gauge
python_info{{version="{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"}} 1

# HELP up Service is up
# TYPE up gauge
up 1
"""

    return metrics_text

