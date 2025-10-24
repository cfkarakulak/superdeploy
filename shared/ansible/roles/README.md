# Ansible Roles

This directory contains Ansible roles organized into logical layers for SuperDeploy infrastructure management.

## Architecture

The role structure follows a layered architecture:

```
roles/
├── system/              # Foundation layer (OS-level)
│   ├── base/           # System packages, users, directories
│   ├── docker/         # Docker installation & configuration
│   ├── security/       # Firewall, SSH hardening
│   └── monitoring-agent/ # Node exporter, system metrics
├── orchestration/      # Deployment layer
│   ├── addon-deployer/    # Generic addon deployment orchestrator
│   └── project-deployer/  # Project-specific deployment orchestrator
└── monitoring/         # Legacy monitoring role (to be migrated)
```

## Role Layers

### System Layer (Foundation)

These roles provide the foundational OS-level setup and are executed first in the deployment process.

#### system/base
**Purpose:** OS-level setup, users, directories, time sync, mail

**Responsibilities:**
- Install essential packages (curl, git, vim, htop, etc.)
- Create superdeploy user and groups
- Configure swap
- Setup chrony for time sync
- Configure postfix for mail
- Create base directory structure

**Variables:**
```yaml
superdeploy_user: "superdeploy"
superdeploy_group: "superdeploy"
base_directories:
  - /opt/superdeploy
  - /opt/backups
swap_size_mb: 2048
```

#### system/docker
**Purpose:** Docker installation and daemon configuration

**Responsibilities:**
- Add Docker GPG key and repository
- Install Docker CE, CLI, containerd, compose plugin
- Configure Docker daemon (logging, storage driver, ulimits)
- Add superdeploy user to docker group
- Enable and start Docker service

**Variables:**
```yaml
docker_log_max_size: "10m"
docker_log_max_file: "3"
docker_storage_driver: "overlay2"
```

#### system/security
**Purpose:** Firewall, SSH hardening, security policies

**Responsibilities:**
- Configure UFW firewall with dynamic port rules
- Harden SSH configuration
- Setup fail2ban (optional)
- Configure security limits

**Variables:**
```yaml
allowed_ports:
  - 22    # SSH
  - 80    # HTTP
  - 443   # HTTPS
  - "{{ forgejo_port }}"  # Dynamic from project config
  - "{{ app_ports }}"     # Dynamic from apps config
```

**Note:** Firewall rules are dynamically generated from `project.yml` configuration.

#### system/monitoring-agent
**Purpose:** Install node exporter and log forwarding for system-level metrics

**Responsibilities:**
- Install and configure node_exporter
- Setup log forwarding to project monitoring
- Configure system metric collection

**Variables:**
```yaml
node_exporter_version: "1.7.0"
prometheus_endpoint: "{{ monitoring_prometheus_url }}"
```

### Orchestration Layer (Deployment)

These roles orchestrate the deployment of addons and project-specific services.

#### orchestration/addon-deployer
**Purpose:** Generic addon deployment orchestrator

**Responsibilities:**
- Load addon metadata from `addon.yml`
- Validate addon configuration from `project.yml`
- Generate environment variables from `env.yml` + project config
- Render `compose.yml.j2` templates
- Execute addon-specific `ansible.yml` tasks
- Verify addon health after deployment

**Variables:**
```yaml
project_name: "myproject"
project_config: "{{ project_yml_parsed }}"
enabled_addons: ["postgres", "redis", "forgejo"]
addon_configs:
  postgres:
    version: "15-alpine"
    port: 5432
  forgejo:
    version: "1.21"
    port: 3001
```

**Deployment Flow:**
1. Loop through enabled addons
2. Load addon metadata
3. Merge configuration (env.yml + project.yml + secrets)
4. Render templates
5. Execute deployment tasks
6. Verify health

#### orchestration/project-deployer
**Purpose:** Deploy project-specific application services

**Responsibilities:**
- Create project directory structure
- Generate project-specific docker-compose files
- Deploy application containers
- Configure inter-service networking
- Setup project-level monitoring targets

**Variables:**
```yaml
project_name: "myproject"
apps:
  api:
    path: "/path/to/api"
    port: 8000
    vm: "core"
  dashboard:
    path: "/path/to/dashboard"
    port: 8010
    vm: "core"
```

## Dynamic Configuration

All roles support dynamic configuration through `project.yml`. This eliminates hardcoded values and allows:

- **Port changes:** Update `project.yml`, redeploy
- **New addons:** Add to `project.yml`, redeploy
- **Multi-project:** Each project has its own configuration
- **No code changes:** Configuration changes don't require code modifications

### Example project.yml

```yaml
project: "myproject"

infrastructure:
  forgejo:
    version: "1.21"
    port: 3001
    admin_user: "admin"
    org: "myorg"
    repo: "superdeploy"

addons:
  postgres:
    version: "15-alpine"
    port: 5432
  redis:
    version: "7-alpine"
    port: 6379

apps:
  api:
    port: 8000
  dashboard:
    port: 8010

network:
  subnet: "172.20.0.0/24"
```

## Deployment Order

Roles are executed in the following order (defined in `playbooks/site.yml`):

1. **System Setup:**
   - system/base
   - system/docker
   - system/security
   - system/monitoring-agent

2. **Addon Deployment:**
   - orchestration/addon-deployer (deploys all enabled addons)

3. **Project Deployment:**
   - orchestration/project-deployer (deploys project applications)

## Variable Precedence

Configuration values are merged with the following precedence (highest to lowest):

1. Secrets (`.passwords.yml`)
2. Project config (`project.yml`)
3. Addon defaults (`env.yml`)
4. Role defaults (`defaults/main.yml`)

## Error Handling

All roles implement:
- **Pre-flight validation:** Check required variables before execution
- **Idempotency:** Safe to re-run multiple times
- **Health checks:** Verify services are healthy after deployment
- **Clear error messages:** Actionable error messages with troubleshooting hints

## Migration Notes

This structure replaces the following legacy roles:

- `system-base` → Split into `system/base`, `system/docker`, `system/security`
- `docker` → Merged into `system/docker`
- `hardening` → Replaced by `system/security`
- `git-server` → Migrated to `addons/forgejo`
- `core-services` → Replaced by `orchestration/addon-deployer`
- `infrastructure` → Replaced by orchestration roles

## Adding New Roles

When adding new roles, follow these guidelines:

1. **Choose the correct layer:**
   - System layer: OS-level, foundational setup
   - Orchestration layer: Deployment and orchestration logic

2. **Use standard structure:**
   ```
   role-name/
   ├── tasks/
   │   └── main.yml
   ├── defaults/
   │   └── main.yml
   ├── handlers/
   │   └── main.yml
   ├── templates/
   └── README.md
   ```

3. **Implement validation:**
   ```yaml
   - name: Validate required variables
     assert:
       that:
         - required_var is defined
       fail_msg: "Missing required variable: required_var"
   ```

4. **Document the role:**
   - Create a README.md with purpose, responsibilities, and variables
   - Add examples of usage
   - Document any dependencies

5. **Make it dynamic:**
   - Read configuration from `project.yml`
   - Avoid hardcoded values
   - Use Jinja2 templates for configuration files

## Testing

Test roles using:

```bash
# Test specific role
ansible-playbook playbooks/site.yml --tags system-base

# Test with specific project
ansible-playbook playbooks/site.yml -e project_name=myproject

# Dry run
ansible-playbook playbooks/site.yml --check
```

## See Also

- [Addon System](../../../addons/README.md)
- [Architecture Documentation](../../../docs/ARCHITECTURE.md)
- [Deployment Documentation](../../../docs/DEPLOYMENT.md)
