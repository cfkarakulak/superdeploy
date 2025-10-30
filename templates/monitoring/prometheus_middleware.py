"""
Prometheus metrics middleware for Python web applications
Tracks HTTP requests: path, method, status, duration
"""
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
import time

# Metrics
http_requests_total = Counter(
    'app_http_requests_total',
    'Total HTTP requests',
    ['method', 'path', 'status']
)

http_request_duration_seconds = Histogram(
    'app_http_request_duration_seconds',
    'HTTP request latency in seconds',
    ['method', 'path']
)

http_requests_in_progress = Gauge(
    'app_http_requests_in_progress',
    'HTTP requests currently in progress',
    ['method', 'path']
)


def setup_metrics(app):
    """
    Auto-detect framework and setup metrics
    Usage: setup_metrics(app)
    """
    app_type = type(app).__name__
    
    if 'FastAPI' in app_type or 'Starlette' in app_type:
        return _setup_fastapi(app)
    elif 'Flask' in app_type:
        return _setup_flask(app)
    else:
        raise ValueError(f"Unsupported framework: {app_type}")


def _setup_fastapi(app):
    """Setup for FastAPI/Starlette"""
    from fastapi import Request, Response
    from starlette.middleware.base import BaseHTTPMiddleware
    
    class MetricsMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request: Request, call_next):
            path = request.url.path
            method = request.method
            
            http_requests_in_progress.labels(method=method, path=path).inc()
            start = time.time()
            
            try:
                response = await call_next(request)
                status = response.status_code
            except Exception:
                status = 500
                raise
            finally:
                duration = time.time() - start
                http_requests_total.labels(method=method, path=path, status=status).inc()
                http_request_duration_seconds.labels(method=method, path=path).observe(duration)
                http_requests_in_progress.labels(method=method, path=path).dec()
            
            return response
    
    app.add_middleware(MetricsMiddleware)
    
    @app.get('/metrics')
    async def metrics():
        return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
    
    return app


def _setup_flask(app):
    """Setup for Flask"""
    from flask import request, g
    
    @app.before_request
    def before():
        g.start = time.time()
        path = request.path
        method = request.method
        http_requests_in_progress.labels(method=method, path=path).inc()
    
    @app.after_request
    def after(response):
        duration = time.time() - g.get('start', time.time())
        path = request.path
        method = request.method
        status = response.status_code
        
        http_requests_total.labels(method=method, path=path, status=status).inc()
        http_request_duration_seconds.labels(method=method, path=path).observe(duration)
        http_requests_in_progress.labels(method=method, path=path).dec()
        
        return response
    
    @app.route('/metrics')
    def metrics():
        return generate_latest(), 200, {'Content-Type': CONTENT_TYPE_LATEST}
    
    return app
