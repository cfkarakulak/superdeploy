# System Monitoring Agent Role

This role installs and configures Prometheus Node Exporter for system-level metric collection.

## Purpose

The monitoring-agent role provides system-level observability by:
- Installing Prometheus Node Exporter
- Exposing system metrics (CPU, memory, disk, network, etc.)
- Configuring metric collection for project-specific monitoring
- Supporting dynamic Prometheus endpoint configuration

## Requirements

- Debian/Ubuntu-based system
- Internet access for downloading Node Exporter binary
- Systemd for service management

## Role Variables

### Required Variables

All required variables have defaults in `defaults/main.yml`:

```yaml
node_exporter_version: "1.7.0"
node_exporter_user: "node_exporter"
node_exporter_group: "node_exporter"
node_exporter_port: 9100
```

### Optional Variables (for project monitoring integration)

```yaml
prometheus_endpoint: "http://prometheus:9090"  # Prometheus server URL
project_name: "myproject"                       # Project name for metric labels
environment: "production"                       # Environment label
node_role: "core"                              # Node role label
```

## Dependencies

None

## Example Playbook

### Basic installation (standalone)

```yaml
- hosts: servers
  roles:
    - role: system/monitoring-agent
```

### With project monitoring integration

```yaml
- hosts: servers
  roles:
    - role: system/monitoring-agent
      vars:
        prometheus_endpoint: "http://{{ project_name }}-prometheus:9090"
        project_name: "{{ project.name }}"
        environment: "production"
        node_role: "core"
```

## Collectors

### Enabled by default

- systemd - Systemd unit metrics
- processes - Process statistics
- filesystem - Filesystem statistics
- diskstats - Disk I/O statistics
- netdev - Network interface statistics
- meminfo - Memory statistics
- loadavg - Load average
- cpu - CPU statistics

### Disabled by default

- mdadm - RAID statistics
- zfs - ZFS filesystem statistics
- bcache - Block cache statistics

## Metrics Endpoint

After installation, metrics are available at:
```
http://<host>:9100/metrics
```

## Security

The role implements security hardening:
- Runs as dedicated non-root user
- Systemd security features enabled (NoNewPrivileges, ProtectHome, etc.)
- Read-only access to system information
- Write access only to textfile collector directory

## Handlers

- `restart-node-exporter` - Restarts the Node Exporter service

## Files and Directories

- `/usr/local/bin/node_exporter` - Node Exporter binary
- `/etc/node_exporter/` - Configuration directory
- `/var/lib/node_exporter/textfile_collector/` - Custom metrics directory
- `/etc/systemd/system/node_exporter.service` - Systemd service file

## Integration with Project Monitoring

When `prometheus_endpoint` is configured, the role:
1. Creates project-specific metric labels
2. Generates monitoring configuration file
3. Provides clear output for Prometheus scrape configuration

The Prometheus instance should be configured to scrape this endpoint:

```yaml
scrape_configs:
  - job_name: 'node-exporter'
    static_configs:
      - targets: ['<host>:9100']
        labels:
          project: 'myproject'
```

## Troubleshooting

### Check service status
```bash
systemctl status node_exporter
```

### View logs
```bash
journalctl -u node_exporter -f
```

### Test metrics endpoint
```bash
curl http://localhost:9100/metrics
```

### Verify collectors
```bash
curl http://localhost:9100/metrics | grep "node_exporter_build_info"
```

## License

MIT

## Author

SuperDeploy Team
