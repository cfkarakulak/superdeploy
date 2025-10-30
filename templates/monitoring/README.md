# Application Metrics - Quick Setup

## Python (Flask)

```python
# requirements.txt
prometheus-client==0.19.0

# app.py
from flask import Flask
from prometheus_middleware import setup_flask_metrics

app = Flask(__name__)
setup_flask_metrics(app)  # Add this line!

@app.route('/')
def index():
    return 'Hello World'

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000)
```

## Python (FastAPI)

```python
# requirements.txt
prometheus-client==0.19.0

# main.py
from fastapi import FastAPI
from prometheus_middleware import setup_fastapi_metrics

app = FastAPI()
setup_fastapi_metrics(app)  # Add this line!

@app.get('/')
def index():
    return {'message': 'Hello World'}
```

## Python (Django)

```python
# requirements.txt
prometheus-client==0.19.0

# settings.py
MIDDLEWARE = [
    'prometheus_middleware.DjangoPrometheusMiddleware',  # Add this!
    # ... other middleware
]

# urls.py
from prometheus_middleware import django_metrics_view

urlpatterns = [
    path('metrics/', django_metrics_view),  # Add this!
    # ... other urls
]
```

## Node.js (Express)

```bash
npm install prom-client
```

```javascript
// app.js
const express = require('express');
const { setupExpressMetrics } = require('./prometheus_middleware');

const app = express();
setupExpressMetrics(app);  // Add this line!

app.get('/', (req, res) => {
  res.send('Hello World');
});

app.listen(8000);
```

## Go

```go
// go.mod
require github.com/prometheus/client_golang v1.17.0

// main.go
package main

import (
    "net/http"
    "yourapp/monitoring"
)

func main() {
    mux := http.NewServeMux()
    
    // Your routes
    mux.HandleFunc("/", handleIndex)
    
    // Metrics endpoint
    mux.Handle("/metrics", monitoring.MetricsHandler())
    
    // Wrap with middleware
    handler := monitoring.PrometheusMiddleware(mux)
    
    http.ListenAndServe(":8000", handler)
}
```

## Prometheus Configuration

Add to your app's docker-compose labels:

```yaml
services:
  api:
    labels:
      - "prometheus.scrape=true"
      - "prometheus.port=8000"
      - "prometheus.path=/metrics"
```

## Metrics Exposed

- `app_http_requests_total{method, path, status}` - Total requests
- `app_http_request_duration_seconds{method, path}` - Request latency
- `app_http_requests_in_progress{method, path}` - Active requests

## Grafana Queries

```promql
# Requests per second by endpoint
rate(app_http_requests_total[5m])

# Top 10 endpoints
topk(10, sum by (path) (rate(app_http_requests_total[5m])))

# Slowest endpoints (p95)
histogram_quantile(0.95, sum by (path, le) (rate(app_http_request_duration_seconds_bucket[5m])))

# Error rate by endpoint
sum by (path) (rate(app_http_requests_total{status=~"5.."}[5m]))
```
