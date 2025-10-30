"""
Prometheus metrics middleware for Python applications
Auto-tracks HTTP requests with path, method, status code
"""
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
from functools import wraps
import time

# Metrics
http_requests_total = Counter(
    'app_http_requests_total',
    'Total HTTP requests',
    ['method', 'path', 'status']
)

http_request_duration_seconds = Histogram(
    'app_http_request_duration_seconds',
    'HTTP request latency',
    ['method', 'path']
)

http_requests_in_progress = Gauge(
    'app_http_requests_in_progress',
    'HTTP requests in progress',
    ['method', 'path']
)

# Flask middleware
def setup_flask_metrics(app):
    """Setup Prometheus metrics for Flask app"""
    
    @app.before_request
    def before_request():
        from flask import request, g
        g.start_time = time.time()
        
        # Track in-progress requests
        path = request.path
        method = request.method
        http_requests_in_progress.labels(method=method, path=path).inc()
    
    @app.after_request
    def after_request(response):
        from flask import request, g
        
        # Calculate duration
        duration = time.time() - g.get('start_time', time.time())
        
        path = request.path
        method = request.method
        status = response.status_code
        
        # Record metrics
        http_requests_total.labels(method=method, path=path, status=status).inc()
        http_request_duration_seconds.labels(method=method, path=path).observe(duration)
        http_requests_in_progress.labels(method=method, path=path).dec()
        
        return response
    
    @app.route('/metrics')
    def metrics():
        """Prometheus metrics endpoint"""
        return generate_latest(), 200, {'Content-Type': CONTENT_TYPE_LATEST}
    
    return app

# FastAPI middleware
def setup_fastapi_metrics(app):
    """Setup Prometheus metrics for FastAPI app"""
    from fastapi import Request, Response
    from starlette.middleware.base import BaseHTTPMiddleware
    
    class PrometheusMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request: Request, call_next):
            path = request.url.path
            method = request.method
            
            # Track in-progress
            http_requests_in_progress.labels(method=method, path=path).inc()
            
            start_time = time.time()
            
            try:
                response = await call_next(request)
                status = response.status_code
            except Exception as e:
                status = 500
                raise
            finally:
                # Record metrics
                duration = time.time() - start_time
                http_requests_total.labels(method=method, path=path, status=status).inc()
                http_request_duration_seconds.labels(method=method, path=path).observe(duration)
                http_requests_in_progress.labels(method=method, path=path).dec()
            
            return response
    
    app.add_middleware(PrometheusMiddleware)
    
    @app.get('/metrics')
    async def metrics():
        """Prometheus metrics endpoint"""
        return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
    
    return app

# Django middleware
class DjangoPrometheusMiddleware:
    """Django middleware for Prometheus metrics"""
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        path = request.path
        method = request.method
        
        # Track in-progress
        http_requests_in_progress.labels(method=method, path=path).inc()
        
        start_time = time.time()
        
        response = self.get_response(request)
        
        # Record metrics
        duration = time.time() - start_time
        status = response.status_code
        
        http_requests_total.labels(method=method, path=path, status=status).inc()
        http_request_duration_seconds.labels(method=method, path=path).observe(duration)
        http_requests_in_progress.labels(method=method, path=path).dec()
        
        return response

# Django metrics view
def django_metrics_view(request):
    """Django view for Prometheus metrics"""
    from django.http import HttpResponse
    return HttpResponse(generate_latest(), content_type=CONTENT_TYPE_LATEST)
