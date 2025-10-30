# Monitoring Addon - Prometheus & Grafana

## Overview

Automatic monitoring system with pre-configured dashboards and alerts for all SuperDeploy projects.

## Features

### 📊 Pre-Built Dashboards

1. **SuperDeploy Overview**
   - Total projects and services
   - Services up/down status
   - HTTP request rates by project
   - Response time (p95) by project
   - Error rates by project
   - Top endpoints by request count

2. **Project Detail** (per-project)
   - Service health status
   - Request rate (5m average)
   - Response time distribution (p50, p95, p99)
   - HTTP status code breakdown
   - Error rate trends
   - Request/response sizes
   - Top endpoints by traffic
   - Slowest endpoints

3. **Infrastructure**
   - CPU usage by project
   - Memory usage by project
   - Network I/O by project
   - Active connections
   - Goroutines (Go services)
   - GC pause time
   - Process uptime

### 🚨 Alert Rules

Automatic alerts for:
- **Service Down** - Service unavailable for 2+ minutes
- **High Error Rate** - 5xx errors > 5% for 5 minutes
- **Slow Response Time** - p95 > 2s for 10 minutes
- **High CPU Usage** - CPU > 80% for 10 minutes
- **High Memory Usage** - Memory > 2GB for 10 minutes
- **Too Many Goroutines** - > 10,000 goroutines
- **High Request Rate** - > 1000 req/s (potential DDoS)
- **Disk Space Low** - < 20% free space

### 📈 Metrics Collected

From Caddy (automatic):
- `caddy_http_requests_total` - Total HTTP requests
- `caddy_http_request_duration_seconds` - Request latency
- `caddy_http_request_size_bytes` - Request sizes
- `caddy_http_response_size_bytes` - Response sizes
- `caddy_http_requests_in_flight` - Active connections

From Go services (if available):
- `process_cpu_seconds_total` - CPU usage
- `process_resident_memory_bytes` - Memory usage
- `go_goroutines` - Goroutine count
- `go_gc_duration_seconds` - GC pause time
- `process_start_time_seconds` - Process uptime

## Access

### Direct Access (IP-based)

```bash
# Grafana
http://<orchestrator-ip>:3000
Username: admin
Password: <from .env>

# Prometheus
http://<orchestrator-ip>:9090
```

### Domain Access (with Caddy)

If you configured domains in `shared/orchestrator/config.yml`:

```yaml
caddy:
  enabled: true

monitoring:
  enabled: true
  grafana_domain: "grafana.yourdomain.com"
  prometheus_domain: "prometheus.yourdomain.com"
```

Then access via:
- https://grafana.yourdomain.com
- https://prometheus.yourdomain.com

## Configuration

### Enable Monitoring

In `shared/orchestrator/config.yml`:

```yaml
monitoring:
  enabled: true
  scrape_interval: "15s"
  retention: "15d"
  grafana_domain: "grafana.example.com"  # Optional
  prometheus_domain: "prometheus.example.com"  # Optional
```

### Project Metrics

Projects automatically expose metrics on port 2019 (Caddy admin port).

Prometheus scrapes:
- `http://<project-vm-ip>:2019/metrics`

### Custom Metrics

Add custom metrics to your apps by exposing Prometheus-format metrics:

```python
# Python example with prometheus_client
from prometheus_client import Counter, Histogram, generate_latest

request_count = Counter('app_requests_total', 'Total requests')
request_duration = Histogram('app_request_duration_seconds', 'Request duration')

@app.route('/metrics')
def metrics():
    return generate_latest()
```

Then add to your app's Docker labels:

```yaml
labels:
  - "prometheus.scrape=true"
  - "prometheus.port=8000"
  - "prometheus.path=/metrics"
```

## Dashboards

### Importing Custom Dashboards

1. Go to Grafana → Dashboards → Import
2. Upload JSON file or paste dashboard ID
3. Select "Prometheus" as datasource

### Popular Community Dashboards

- **Node Exporter Full** - ID: 1860
- **Docker Container Metrics** - ID: 193
- **Caddy Metrics** - ID: 14280
- **PostgreSQL Database** - ID: 9628

### Exporting Dashboards

```bash
# Export dashboard as JSON
curl -u admin:password http://localhost:3000/api/dashboards/uid/<dashboard-uid> > dashboard.json
```

## Troubleshooting

### No Data in Grafana

1. Check Prometheus targets:
   ```bash
   curl http://localhost:9090/api/v1/targets
   ```

2. Verify project VMs are exposing metrics:
   ```bash
   curl http://<project-vm-ip>:2019/metrics
   ```

3. Check firewall rules allow port 2019 from orchestrator

### Metrics Not Updating

1. Check Prometheus scrape interval (default: 15s)
2. Verify services are running:
   ```bash
   docker ps | grep -E "prometheus|grafana"
   ```

3. Check Prometheus logs:
   ```bash
   docker logs superdeploy-prometheus
   ```

### Dashboard Not Loading

1. Check Grafana provisioning:
   ```bash
   docker exec superdeploy-grafana ls -la /etc/grafana/provisioning/dashboards/json/
   ```

2. Restart Grafana:
   ```bash
   docker restart superdeploy-grafana
   ```

### High Memory Usage

Reduce Prometheus retention:

```yaml
monitoring:
  retention: "7d"  # Instead of 15d
```

## Best Practices

### 1. Set Up Alerts

Configure Alertmanager for notifications:

```yaml
monitoring:
  alertmanager_url: "alertmanager:9093"
```

### 2. Regular Backups

Backup Grafana dashboards and Prometheus data:

```bash
superdeploy backup -p orchestrator
```

### 3. Monitor the Monitors

Set up external monitoring for Prometheus/Grafana uptime.

### 4. Optimize Queries

Use recording rules for expensive queries:

```yaml
# In prometheus.yml
recording_rules:
  - record: job:http_requests:rate5m
    expr: sum by (job) (rate(http_requests_total[5m]))
```

### 5. Dashboard Organization

- Use folders to organize dashboards by project
- Tag dashboards appropriately
- Set appropriate refresh intervals (30s-1m)

## Advanced Configuration

### Custom Scrape Configs

Add to `prometheus.yml.j2`:

```yaml
scrape_configs:
  - job_name: 'custom-exporter'
    static_configs:
      - targets: ['exporter:9100']
```

### Recording Rules

Create `recording-rules.yml`:

```yaml
groups:
  - name: performance
    interval: 30s
    rules:
      - record: job:request_rate:5m
        expr: sum by (job) (rate(http_requests_total[5m]))
```

### Grafana Plugins

Install plugins in compose file:

```yaml
environment:
  - GF_INSTALL_PLUGINS=grafana-piechart-panel,grafana-worldmap-panel
```

## Metrics Reference

### HTTP Metrics

| Metric | Type | Description |
|--------|------|-------------|
| `caddy_http_requests_total` | Counter | Total HTTP requests |
| `caddy_http_request_duration_seconds` | Histogram | Request latency |
| `caddy_http_request_size_bytes` | Histogram | Request body size |
| `caddy_http_response_size_bytes` | Histogram | Response body size |
| `caddy_http_requests_in_flight` | Gauge | Active requests |

### System Metrics

| Metric | Type | Description |
|--------|------|-------------|
| `process_cpu_seconds_total` | Counter | CPU time used |
| `process_resident_memory_bytes` | Gauge | Memory usage |
| `process_open_fds` | Gauge | Open file descriptors |
| `process_start_time_seconds` | Gauge | Process start time |

### Go Runtime Metrics

| Metric | Type | Description |
|--------|------|-------------|
| `go_goroutines` | Gauge | Number of goroutines |
| `go_threads` | Gauge | Number of OS threads |
| `go_gc_duration_seconds` | Summary | GC pause duration |
| `go_memstats_alloc_bytes` | Gauge | Allocated memory |

## Resources

- [Prometheus Documentation](https://prometheus.io/docs/)
- [Grafana Documentation](https://grafana.com/docs/)
- [PromQL Basics](https://prometheus.io/docs/prometheus/latest/querying/basics/)
- [Grafana Dashboard Best Practices](https://grafana.com/docs/grafana/latest/best-practices/)
