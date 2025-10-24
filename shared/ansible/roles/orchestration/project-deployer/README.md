# Project Deployer Role

## Overview

The `project-deployer` role orchestrates the deployment of project-specific application services. It creates the project directory structure, deploys application containers, configures inter-service networking, and integrates with project-level monitoring.

## Responsibilities

1. Create project directory structure
2. Deploy application services from project.yml apps section
3. Generate docker-compose files for applications
4. Configure inter-service networking
5. Setup project-level monitoring targets

## Requirements

### Required Variables

- `project_name`: Name of the project (e.g., "cheapa")
- `project_config`: Parsed project.yml configuration
- `project_base_path`: Base path for project deployment (default: `/opt/superdeploy/projects/{{ project_name }}`)

### Optional Variables

- `superdeploy_user`: User for file ownership (default: "superdeploy")
- `superdeploy_group`: Group for file ownership (default: "superdeploy")
- `apps`: Application configurations from project.yml (default: extracted from project_config)
- `network_subnet`: Docker network subnet (default: "172.20.0.0/24")
- `monitoring_enabled`: Enable monitoring integration (default: false)

## Usage

### In Playbook

```yaml
- name: Deploy project applications
  hosts: all
  roles:
    - role: orchestration/project-deployer
      vars:
        project_name: "cheapa"
        project_config: "{{ project_yml_parsed }}"
```

### With Extra Vars

```bash
ansible-playbook site.yml \
  --extra-vars "project_name=cheapa" \
  --extra-vars "project_config={{ lookup('file', 'projects/cheapa/project.yml') | from_yaml }}"
```

## Directory Structure Created

```
/opt/superdeploy/projects/<project_name>/
├── compose/              # Docker compose files
├── data/                 # Application data
│   ├── api/
│   ├── dashboard/
│   └── services/
├── logs/                 # Application logs
└── backups/              # Application backups
```

## Project Configuration Schema

The role expects the following structure in `project.yml`:

```yaml
project: "cheapa"

apps:
  api:
    path: "/path/to/api"
    port: 8000
    vm: "core"
  dashboard:
    path: "/path/to/dashboard"
    port: 8010
    vm: "core"

network:
  subnet: "172.20.0.0/24"

monitoring:
  enabled: true
```

## Error Handling

The role validates required variables at the start and fails with clear error messages if any are missing:

```
[PROJECT-DEPLOYER] ERROR: Missing required variables
  - Expected: project_name, project_config, project_base_path
  - Found: project_name=undefined, project_config=undefined, project_base_path=undefined
  - Fix: Ensure these variables are passed to the project-deployer role
  - Docs: See shared/ansible/roles/orchestration/project-deployer/README.md
```

## Tasks

### main.yml
- Validates required variables
- Sets default values for optional variables
- Creates project directory structure
- Includes application deployment tasks
- Includes monitoring integration tasks

### deploy-apps.yml
- Deploys application services from project.yml
- Generates docker-compose files for applications
- Configures inter-service networking

### setup-monitoring.yml
- Configures project-level monitoring targets
- Adds services to Prometheus scrape config

## Dependencies

None. This role is self-contained.

## Tags

- `project-deployer`: Run all project deployment tasks
- `project-structure`: Only create directory structure
- `project-apps`: Only deploy applications
- `project-monitoring`: Only setup monitoring

## Examples

### Deploy Complete Project

```bash
ansible-playbook site.yml --tags project-deployer
```

### Only Create Directory Structure

```bash
ansible-playbook site.yml --tags project-structure
```

### Only Deploy Applications

```bash
ansible-playbook site.yml --tags project-apps
```
