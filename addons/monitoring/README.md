# Shared Monitoring Addon

This addon provides shared Grafana and Prometheus monitoring infrastructure for all SuperDeploy projects.

## Overview

The monitoring addon is a **shared addon**, meaning only one instance runs across all projects. It provides:

- **Prometheus**: Metrics collection and storage for all projects
- **Grafana**: Visualization dashboards with project-based filtering
- **Service Discovery**: Automatic discovery of Docker containers with Prometheus labels
- **Project Isolation**: Each project gets its own datasource and dashboard folder

## Features

### Prometheus Features

- Automatic scrape configuration for all projects
- Project-based labels for filtering (project, environment, vm, tags)
- Node exporter integration for system metrics
- Docker metrics integration
- Service discovery via Docker labels
- Configurable retention period (default: 15 days)

### Grafana Features

- Single admin interface for all projects
- Project-specific datasources with pre-filtered queries
- Automatic dashboard provisioning per project
- Tag-based filtering across projects
- Dark theme by default
- Secure authentication (no anonymous access)

## Configuration

### addon.yml

The main configuration file defines:

- Environment variables (Grafana URL, admin credentials, Prometheus URL)
- Docker compose settings (ports, volumes, networks)
- Health checks for both services
- Resource requirements

### Environment Variables

| Variable | Description | Default | Secret |
|----------|-------------|---------|--------|
| `GRAFANA_URL` | Grafana dashboard URL | `http://monitoring:3000` | No |
| `GRAFANA_ADMIN_USER` | Grafana admin username | `admin` | No |
| `GRAFANA_ADMIN_PASSWORD` | Grafana admin password | Auto-generated | Yes |
| `PROMETHEUS_URL` | Prometheus server URL | `http://monitoring:9090` | No |
| `PROMETHEUS_RETENTION` | Data retention period | `15d` | No |
| `MONITORING_HOST` | Monitoring server hostname | `monitoring` | No |

## Usage

### Adding Monitoring to a Project

In your `project.yml`:

```yaml
project: myproject

# Enable shared monitoring
monitoring:
  enabled: true
  shared: true
  tags:
    - production
    - api-services
```

### Accessing Dashboards

1. Navigate to `http://<monitoring-host>:3000`
2. Login with admin credentials
3. Select project from dropdown or navigate to project folder
4. View metrics filtered by project tags

### Adding Metrics to Your Services

Add Prometheus labels to your Docker containers:

```yaml
services:
  myapp:
    image: myapp:latest
    labels:
      - "prometheus.scrape=true"
      - "prometheus.port=8000"
      - "prometheus.path=/metrics"
      - "superdeploy.project=myproject"
      - "superdeploy.service=api"
```

## Project-Based Filtering

### Prometheus Labels

All metrics are automatically labeled with:

- `project`: Project name
- `environment`: Environment (production, staging, etc.)
- `vm`: VM identifier (core, worker, etc.)
- `service`: Service name
- `tag_1`, `tag_2`, etc.: Custom tags from project config

### Example Queries

Filter metrics by project:
```promql
up{project="myproject"}
```

Filter by project and service:
```promql
http_requests_total{project="myproject", service="api"}
```

Filter by tags:
```promql
cpu_usage{tag_1="production"}
```

## Configuration Generators

The addon includes Python utilities for generating configurations:

### PrometheusConfigGenerator

Generates Prometheus scrape configs for all projects:

```python
from config_generator import PrometheusConfigGenerator

projects = [
    {
        'name': 'myproject',
        'host': '10.0.1.2',
        'targets': ['10.0.1.2:8000'],
        'tags': ['production', 'api']
    }
]

generator = PrometheusConfigGenerator()
config = generator.generate_config(projects)
generator.save_config(config, Path('/etc/prometheus/prometheus.yml'))
```

### GrafanaDatasourceGenerator

Generates Grafana datasource provisioning:

```python
from config_generator import GrafanaDatasourceGenerator

generator = GrafanaDatasourceGenerator()
datasources = generator.generate_datasources(projects)
generator.save_datasources(datasources, Path('/etc/grafana/provisioning/datasources/datasources.yml'))
```

### GrafanaDashboardGenerator

Generates Grafana dashboard provisioning:

```python
from config_generator import GrafanaDashboardGenerator

generator = GrafanaDashboardGenerator()
dashboards = generator.generate_dashboard_config(projects)
generator.save_dashboard_config(dashboards, Path('/etc/grafana/provisioning/dashboards/dashboards.yml'))
```

## Deployment

### Ansible Deployment

The `ansible.yml` file handles:

1. Creating monitoring directories
2. Generating Prometheus configuration
3. Generating Grafana provisioning files
4. Deploying Prometheus container
5. Deploying Grafana container
6. Waiting for services to be healthy
7. Displaying access URLs

### Manual Deployment

```bash
# Generate configurations
python config_generator.py

# Deploy with Docker Compose (addon-generated compose file)
cd /opt/superdeploy/shared/monitoring
docker compose up -d

# Check health
curl http://localhost:9090/-/healthy
curl http://localhost:3000/api/health
```

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│              Shared Monitoring Infrastructure                │
│                                                              │
│  ┌────────────────────────────────────────────────────┐    │
│  │              Grafana (Single Instance)             │    │
│  │  • Datasources: project-a, project-b, project-c    │    │
│  │  • Dashboards with project filter dropdown         │    │
│  │  • Tags: project, environment, service             │    │
│  └────────────────────┬───────────────────────────────┘    │
│                       │                                     │
│  ┌────────────────────▼───────────────────────────────┐    │
│  │           Prometheus (Single Instance)             │    │
│  │  • Scrape configs per project                      │    │
│  │  • Labels: project, vm, service                    │    │
│  │  • Service discovery via Docker                    │    │
│  └────────────────────┬───────────────────────────────┘    │
└────────────────────────┼────────────────────────────────────┘
                         │
         ┌───────────────┼───────────────┐
         │               │               │
         ▼               ▼               ▼
    ┌─────────┐    ┌─────────┐    ┌─────────┐
    │Project A│    │Project B│    │Project C│
    │Metrics  │    │Metrics  │    │Metrics  │
    └─────────┘    └─────────┘    └─────────┘
```

## Health Checks

### Prometheus

- Endpoint: `http://localhost:9090/-/healthy`
- Interval: 30s
- Timeout: 10s
- Retries: 3

### Grafana

- Endpoint: `http://localhost:3000/api/health`
- Interval: 30s
- Timeout: 10s
- Retries: 3

## Troubleshooting

### Prometheus Not Scraping

1. Check Prometheus targets: `http://localhost:9090/targets`
2. Verify project configuration includes correct targets
3. Check network connectivity between Prometheus and project VMs
4. Verify Docker labels on containers

### Grafana Datasource Issues

1. Check datasource configuration: Settings → Data Sources
2. Test datasource connection
3. Verify Prometheus URL is accessible from Grafana
4. Check project labels in queries

### Missing Metrics

1. Verify service exposes metrics endpoint
2. Check Prometheus labels on container
3. Verify scrape config includes the service
4. Check Prometheus logs for scrape errors

## Security

- Grafana admin password is auto-generated and stored securely
- No anonymous access allowed
- Sign-up disabled by default
- All communication over internal Docker network
- Prometheus and Grafana not exposed externally (use reverse proxy)

## Resource Requirements

- Memory: 2GB (1GB Prometheus + 1GB Grafana)
- CPU: 1 core
- Disk: 50GB (for metrics retention)

## Future Enhancements

- Alertmanager integration for notifications
- Loki integration for log aggregation
- Multi-region federation
- Custom dashboard templates per project type
- Automated backup of Grafana dashboards
- Metrics retention policies per project
