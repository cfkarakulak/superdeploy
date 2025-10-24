# Monitoring Role - Shared Grafana/Prometheus

## Overview

This Ansible role deploys shared Grafana and Prometheus instances that monitor all projects in the SuperDeploy infrastructure. It uses the monitoring addon with dynamic project datasource provisioning.

## Architecture

### Shared Monitoring Concept

Instead of deploying separate Grafana/Prometheus instances for each project, SuperDeploy uses a single shared monitoring infrastructure:

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
│  │  • Federation for multi-region (future)            │    │
│  └────────────────────┬───────────────────────────────┘    │
└────────────────────────┼────────────────────────────────────┘
                         │
         ┌───────────────┼───────────────┐
         │               │               │
         ▼               ▼               ▼
    ┌─────────┐    ┌─────────┐    ┌─────────┐
    │Project A│    │Project B│    │Project C│
    │VM: 10.0 │    │VM: 10.1 │    │VM: 10.2 │
    │Metrics  │    │Metrics  │    │Metrics  │
    │:9090    │    │:9090    │    │:9090    │
    └─────────┘    └─────────┘    └─────────┘
```

## Features

1. **Single Grafana Instance**: One dashboard for all projects with filtering
2. **Single Prometheus Instance**: Centralized metrics collection
3. **Dynamic Datasources**: Automatically provisions datasources for each project
4. **Project Labels**: All metrics tagged with project name
5. **Tag-Based Filtering**: Filter dashboards by project, environment, service

## Usage

### Required Variables

- `superdeploy_root`: Path to SuperDeploy root directory
- `grafana_admin_password`: Grafana admin password
- `monitored_projects`: List of projects to monitor (optional)

### Optional Variables

- `grafana_admin_user`: Grafana admin username (default: "admin")
- `grafana_version`: Grafana Docker image version (default: "latest")
- `prometheus_version`: Prometheus Docker image version (default: "latest")
- `prometheus_retention`: Prometheus data retention period (default: "15d")

### Example Invocation

```bash
ansible-playbook -i inventories/dev.ini playbooks/site.yml --tags monitoring \
  -e "superdeploy_root=/path/to/superdeploy" \
  -e "grafana_admin_password=secure_password" \
  -e 'monitored_projects=[{"project":"myproject","vm":"10.0.1.2"}]'
```

## Directory Structure

```
/opt/superdeploy/monitoring/
├── prometheus/
│   └── prometheus.yml              # Generated Prometheus config
├── grafana/
│   ├── provisioning/
│   │   ├── datasources/
│   │   │   └── datasources.yml     # Generated datasources
│   │   └── dashboards/
│   │       └── dashboards.yml      # Dashboard provisioning
│   └── dashboards/                 # Dashboard JSON files
```

## Templates

The role uses templates from the monitoring addon:

### prometheus.yml.j2

Generates Prometheus scrape configurations for all projects:

```yaml
scrape_configs:
  - job_name: 'project-a-services'
    static_configs:
      - targets: ['project-a-vm:9090']
        labels:
          project: 'project-a'
          environment: 'production'
```

### grafana-datasources.yml.j2

Generates Grafana datasource configurations:

```yaml
datasources:
  - name: 'project-a-prometheus'
    type: 'prometheus'
    url: 'http://prometheus:9090'
    uid: 'project-a-prom'
```

### grafana-dashboards.yml.j2

Configures dashboard provisioning:

```yaml
providers:
  - name: 'default'
    folder: ''
    type: file
    options:
      path: /var/lib/grafana/dashboards
```

## Handlers

### reload prometheus

Reloads Prometheus configuration without restarting:

```bash
curl -X POST http://localhost:9090/-/reload
```

### restart grafana

Restarts Grafana container to pick up new datasources:

```bash
docker restart superdeploy-grafana
```

## Tags

- `monitoring`: All monitoring tasks
- `setup`: Create directories and networks
- `prometheus`: Prometheus-specific tasks
- `grafana`: Grafana-specific tasks
- `config`: Configuration generation
- `datasources`: Datasource provisioning
- `dashboards`: Dashboard provisioning
- `deploy`: Container deployment
- `healthcheck`: Health checks
- `info`: Information display

## Adding Projects to Monitoring

When a new project is deployed, update the `monitored_projects` variable:

```yaml
monitored_projects:
  - project: myproject
    vm: 10.0.1.2
    environment: production
  - project: anotherproject
    vm: 10.0.1.3
    environment: staging
```

Then run:

```bash
ansible-playbook ... --tags monitoring,config
```

This will:
1. Regenerate Prometheus scrape configs
2. Regenerate Grafana datasources
3. Reload Prometheus
4. Restart Grafana

## Accessing Monitoring

### Grafana

- URL: `http://{core_vm_ip}:3000`
- Username: `admin` (or custom)
- Password: From `grafana_admin_password` variable

### Prometheus

- URL: `http://{core_vm_ip}:9090`
- No authentication by default

## Metrics Collection

Projects expose metrics on port 9090 (or custom port). Prometheus scrapes these endpoints with project-specific labels:

```yaml
labels:
  project: myproject
  environment: production
  vm: 10.0.1.2
```

## Dashboard Filtering

Grafana dashboards can filter by:

- **Project**: Select specific project
- **Environment**: production, staging, development
- **Service**: postgres, redis, rabbitmq, etc.

Example dashboard variable:

```json
{
  "name": "project",
  "type": "query",
  "query": "label_values(project)",
  "multi": true
}
```

## Troubleshooting

### Prometheus not scraping

Check Prometheus targets:

```bash
curl http://localhost:9090/api/v1/targets
```

### Grafana datasources not appearing

Restart Grafana:

```bash
docker restart superdeploy-grafana
```

Check provisioning logs:

```bash
docker logs superdeploy-grafana | grep provisioning
```

### Metrics not showing in Grafana

1. Verify Prometheus is scraping: Check targets page
2. Verify datasource is configured: Check Grafana datasources
3. Verify labels are correct: Query Prometheus directly

## Requirements

- Ansible 2.9+
- Docker Python module
- `community.docker` collection
- `ansible.builtin.uri` module

## See Also

- [Core Services Role](../core-services/README.md) - Project-specific service deployment
- [Monitoring Addon](../../../../addons/monitoring/) - Monitoring addon templates
- [Addon System Design](../../../../.kiro/specs/addon-system-architecture/design.md)
