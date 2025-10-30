# Prometheus Metrics Middleware

Auto-detects your framework and adds `/metrics` endpoint with request tracking.

## Quick Start (3 Steps)

### 1. Copy the middleware file
```bash
# From your app directory
cp ../../superdeploy/templates/monitoring/prometheus_middleware.py .
```

Or download directly:
```bash
curl -o prometheus_middleware.py https://raw.githubusercontent.com/superdeploy/templates/monitoring/prometheus_middleware.py
```

### 2. Add to your app

**FastAPI / Starlette:**
```python
from fastapi import FastAPI
from prometheus_middleware import setup_metrics

app = FastAPI()
setup_metrics(app)  # That's it!
```

**Flask:**
```python
from flask import Flask
from prometheus_middleware import setup_metrics

app = Flask(__name__)
setup_metrics(app)  # That's it!
```

### 3. Add dependency
```bash
# requirements.txt
prometheus-client==0.19.0
```

Then redeploy:
```bash
superdeploy deploy -p myproject -a api
```

## What It Tracks

- **Request Count**: `app_http_requests_total{method, path, status}`
- **Request Duration**: `app_http_request_duration_seconds{method, path}`
- **Active Requests**: `app_http_requests_in_progress{method, path}`

## Metrics Endpoint

After setup, metrics are available at: `http://your-app:port/metrics`

## Requirements

```bash
pip install prometheus-client
```

## How It Works

1. Auto-detects your framework (FastAPI or Flask)
2. Adds middleware to track all HTTP requests
3. Creates `/metrics` endpoint automatically
4. Labels include: method, path, status code

## Example Metrics Output

```
# HELP app_http_requests_total Total HTTP requests
# TYPE app_http_requests_total counter
app_http_requests_total{method="GET",path="/api/users",status="200"} 42.0

# HELP app_http_request_duration_seconds HTTP request latency
# TYPE app_http_request_duration_seconds histogram
app_http_request_duration_seconds_sum{method="GET",path="/api/users"} 1.23
app_http_request_duration_seconds_count{method="GET",path="/api/users"} 42
```

## Grafana Integration

These metrics work automatically with SuperDeploy's Endpoint Analytics dashboard:
- Top 10 hottest endpoints
- Top 10 slowest endpoints  
- Request rate by endpoint
- Error rate by endpoint
- Response time distribution

## Notes

- Metrics are collected per-process (not shared across workers)
- Path parameters are preserved (e.g., `/users/123` not `/users/{id}`)
- For high-cardinality paths, consider path normalization
