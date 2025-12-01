"""
Prometheus Metrics Controller for Cara Framework

Usage:
1. Copy this file to your app/controllers/ directory
2. Run: python craft routes:generate
3. Access metrics at: GET /api/metrics

The @routes.api() decorator with @get annotation will auto-generate the route.
"""

import gc
import sys
import time

from cara.http import Controller, Request, Response


class MetricsController(Controller):
    """
    Prometheus metrics controller for Cara applications.

    Exposes basic application metrics in Prometheus text format.
    No authentication required for metrics endpoint.

    @routes.api()
        @get(path="/metrics", method="metrics", as="metrics")
    """

    _start_time = time.time()

    async def metrics(
        self,
        request: Request,
        response: Response,
    ) -> Response:
        """
        Prometheus metrics endpoint.

        Expected: GET /api/metrics
        No authentication required.

        Returns metrics in Prometheus text format for scraping.
        """
        import resource

        # Calculate uptime
        uptime = time.time() - self._start_time

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

        # Build Prometheus metrics
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

        return response.make(
            metrics_text,
            status=200,
            headers={"Content-Type": "text/plain; charset=utf-8"},
        )
