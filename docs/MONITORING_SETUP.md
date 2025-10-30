# Monitoring Setup Guide

## Quick Start

Monitoring is automatically configured when you deploy the orchestrator and projects.

### 1. Deploy Orchestrator with Monitoring

```bash
# Edit orchestrator config
vim shared/orchestrator/config.yml
```

Enable monitoring:

```yaml
monitoring:
  enabled: true
  scrape_interval: "15s"
  retention: "15d"
  
# Optional: Domain access
caddy:
  enabled: true
  
monitoring:
  grafana_domain: "grafana.yourdomain.com"
  prometheus_domain: "prometheus.yourdomain.com"
```

Deploy:

```bash
superdeploy orchestrator up
```

### 2. Deploy Projects

Projects automatically register with monitoring:

```bash
superdeploy up -p myproject
```

This will:
- ✅ Deploy project infrastructure
- ✅ Enable Caddy metrics on port 2019
- ✅ Update Prometheus to scrape project metrics
- ✅ Reload Prometheus configuration

### 3. Access Dashboards

```bash
# Get orchestrator IP
superdeploy orchestrator status

# Access Grafana
http://<orchestrator-ip>:3000
Username: admin
Password: <from shared/orchestrator/.env>
```

## Pre-Built Dashboards

### 1. SuperDeploy Overview

**Location:** Dashboards → SuperDeploy → SuperDeploy - Overview

**Metrics:**
- Total projects and services
- Services up/down count
- HTTP request rates by project
- Response time (p95) by project
- Error rates by project
- Top endpoints by request count

**Use Cases:**
- Quick health check of all projects
- Identify which projects have issues
- Compare performance across projects

### 2. Project Detail

**Location:** Dashboards → SuperDeploy → Project Detail

**Metrics:**
- Service health status
- Request rate (5m average)
- Response time distribution (p50, p95, p99)
- HTTP status code breakdown
- Error rate trends (4xx, 5xx)
- Request/response sizes
- Top endpoints by traffic
- Slowest endpoints

**Use Cases:**
- Deep dive into specific project
- Identify slow endpoints
- Track error patterns
- Monitor traffic patterns

### 3. Infrastructure

**Location:** Dashboards → SuperDeploy → Infrastructure

**Metrics:**
- CPU usage by project
- Memory usage by project
- Network I/O by project
- Active connections
- Goroutines (Go services)
- GC pause time
- Process uptime

**Use Cases:**
- Resource utilization monitoring
- Capacity planning
- Identify resource leaks
- Track service stability

### 4. Alerts & Health

**Location:** Dashboards → SuperDeploy → Alerts & Health

**Metrics:**
- Active alerts count
- Critical vs warning alerts
- Alert history timeline
- Alerts by category
- Service health status
- Error rate trends

**Use Cases:**
- Monitor active incidents
- Track alert patterns
- Quick health overview
- Incident response

## Automatic Alerts

### Critical Alerts

| Alert | Condition | Duration | Action |
|-------|-----------|----------|--------|
| ServiceDown | Service unavailable | 2 minutes | Check service logs, restart if needed |
| PrometheusTargetDown | Prometheus down | 1 minute | Check orchestrator, restart monitoring |

### Warning Alerts

| Alert | Condition | Duration | Action |
|-------|-----------|----------|--------|
| HighErrorRate | 5xx errors > 5% | 5 minutes | Check application logs, investigate errors |
| SlowResponseTime | p95 > 2 seconds | 10 minutes | Optimize slow endpoints, scale if needed |
| HighCPUUsage | CPU > 80% | 10 minutes | Scale up or optimize code |
| HighMemoryUsage | Memory > 2GB | 10 minutes | Check for memory leaks, scale up |
| TooManyGoroutines | Goroutines > 10k | 10 minutes | Check for goroutine leaks |
| HighRequestRate | Requests > 1000/s | 5 minutes | Possible DDoS, check traffic patterns |
| DiskSpaceLow | Free space < 20% | 10 minutes | Clean up logs, expand disk |

## Metrics Collected

### HTTP Metrics (from Caddy)

All HTTP traffic is automatically monitored:

```
caddy_http_requests_total{project="myproject", status="200"}
caddy_http_request_duration_seconds{project="myproject"}
caddy_http_request_size_bytes{project="myproject"}
caddy_http_response_size_bytes{project="myproject"}
caddy_http_requests_in_flight{project="myproject"}
```

### System Metrics (from Go services)

If your service is written in Go:

```
process_cpu_seconds_total{project="myproject"}
process_resident_memory_bytes{project="myproject"}
go_goroutines{project="myproject"}
go_gc_duration_seconds{project="myproject"}
```

### Custom Metrics

Add custom metrics to your application:

**Python Example:**

```python
from prometheus_client import Counter, Histogram, generate_latest

# Define metrics
requests_total = Counter('app_requests_total', 'Total requests', ['method', 'endpoint'])
request_duration = Histogram('app_request_duration_seconds', 'Request duration')

# Use in your code
@app.route('/api/users')
def get_users():
    requests_total.labels(method='GET', endpoint='/api/users').inc()
    with request_duration.time():
        # Your code here
        return jsonify(users)

# Expose metrics endpoint
@app.route('/metrics')
def metrics():
    return generate_latest()
```

**Docker Labels:**

```yaml
# In your docker-compose.yml
services:
  myapp:
    labels:
      - "prometheus.scrape=true"
      - "prometheus.port=8000"
      - "prometheus.path=/metrics"
      - "superdeploy.project=myproject"
      - "superdeploy.service=api"
```

## Common Queries

### Request Rate

```promql
# Total requests per second
sum(rate(caddy_http_requests_total[5m]))

# By project
sum by (project) (rate(caddy_http_requests_total[5m]))

# By status code
sum by (status) (rate(caddy_http_requests_total{project="myproject"}[5m]))
```

### Response Time

```promql
# p95 response time
histogram_quantile(0.95, sum(rate(caddy_http_request_duration_seconds_bucket[5m])) by (le))

# By project
histogram_quantile(0.95, sum by (project, le) (rate(caddy_http_request_duration_seconds_bucket[5m])))

# Average response time
sum(rate(caddy_http_request_duration_seconds_sum[5m])) / sum(rate(caddy_http_request_duration_seconds_count[5m]))
```

### Error Rate

```promql
# 5xx error rate
sum(rate(caddy_http_requests_total{status=~"5.."}[5m])) / sum(rate(caddy_http_requests_total[5m])) * 100

# By project
sum by (project) (rate(caddy_http_requests_total{status=~"5.."}[5m])) / sum by (project) (rate(caddy_http_requests_total[5m])) * 100
```

### Resource Usage

```promql
# CPU usage
sum by (project) (rate(process_cpu_seconds_total[5m])) * 100

# Memory usage (MB)
sum by (project) (process_resident_memory_bytes) / 1024 / 1024

# Goroutines
sum by (project) (go_goroutines)
```

## Troubleshooting

### No Data in Grafana

**Problem:** Dashboards show "No data"

**Solutions:**

1. Check Prometheus targets:
   ```bash
   curl http://<orchestrator-ip>:9090/api/v1/targets
   ```

2. Verify project metrics are exposed:
   ```bash
   curl http://<project-vm-ip>:2019/metrics
   ```

3. Check firewall rules:
   ```bash
   # On orchestrator
   gcloud compute firewall-rules list | grep metrics
   ```

4. Manually update monitoring:
   ```bash
   superdeploy up -p myproject --skip-terraform --skip-ansible
   ```

### Metrics Not Updating

**Problem:** Metrics are stale or not updating

**Solutions:**

1. Check Prometheus scrape interval (default: 15s)

2. Verify services are running:
   ```bash
   ssh orchestrator
   docker ps | grep -E "prometheus|grafana"
   ```

3. Check Prometheus logs:
   ```bash
   docker logs superdeploy-prometheus
   ```

4. Reload Prometheus:
   ```bash
   docker exec superdeploy-prometheus kill -HUP 1
   ```

### Dashboard Not Loading

**Problem:** Dashboard shows errors or doesn't load

**Solutions:**

1. Check Grafana provisioning:
   ```bash
   docker exec superdeploy-grafana ls -la /etc/grafana/provisioning/dashboards/json/
   ```

2. Verify datasource:
   - Go to Configuration → Data Sources
   - Test Prometheus connection

3. Restart Grafana:
   ```bash
   docker restart superdeploy-grafana
   ```

### High Memory Usage

**Problem:** Prometheus using too much memory

**Solutions:**

1. Reduce retention period:
   ```yaml
   # In shared/orchestrator/config.yml
   monitoring:
     retention: "7d"  # Instead of 15d
   ```

2. Reduce scrape frequency:
   ```yaml
   monitoring:
     scrape_interval: "30s"  # Instead of 15s
   ```

3. Add resource limits:
   ```yaml
   # In monitoring compose.yml
   deploy:
     resources:
       limits:
         memory: 2G
   ```

## Best Practices

### 1. Set Up Alerting

Configure Alertmanager for notifications:

```yaml
# In shared/orchestrator/config.yml
monitoring:
  alertmanager_url: "alertmanager:9093"
```

### 2. Regular Backups

Backup Grafana dashboards and Prometheus data:

```bash
superdeploy backup -p orchestrator
```

### 3. Monitor the Monitors

Set up external monitoring (e.g., UptimeRobot) for:
- Grafana availability
- Prometheus availability

### 4. Dashboard Organization

- Use folders to organize dashboards
- Tag dashboards appropriately
- Set appropriate refresh intervals (30s-1m)
- Add descriptions to panels

### 5. Query Optimization

- Use recording rules for expensive queries
- Limit time ranges in dashboards
- Use appropriate scrape intervals

### 6. Security

- Change default Grafana password
- Use HTTPS for domain access
- Restrict Prometheus access
- Enable authentication

## Advanced Configuration

### Custom Scrape Configs

Add custom targets to Prometheus:

```yaml
# In prometheus.yml.j2
scrape_configs:
  - job_name: 'node-exporter'
    static_configs:
      - targets: ['node-exporter:9100']
```

### Recording Rules

Create recording rules for expensive queries:

```yaml
# In recording-rules.yml
groups:
  - name: performance
    interval: 30s
    rules:
      - record: job:request_rate:5m
        expr: sum by (job) (rate(http_requests_total[5m]))
```

### Grafana Plugins

Install additional plugins:

```yaml
# In compose.yml
environment:
  - GF_INSTALL_PLUGINS=grafana-piechart-panel,grafana-worldmap-panel
```

## Resources

- [Prometheus Documentation](https://prometheus.io/docs/)
- [Grafana Documentation](https://grafana.com/docs/)
- [PromQL Basics](https://prometheus.io/docs/prometheus/latest/querying/basics/)
- [Dashboard Best Practices](https://grafana.com/docs/grafana/latest/best-practices/)
- [Alert Rule Examples](https://awesome-prometheus-alerts.grep.to/)
