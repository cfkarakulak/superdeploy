# Multi-Project Support

SuperDeploy supports multiple isolated projects on the same infrastructure.

## How It Works

### 1. Ansible Inventory

Each project gets its own group in the Ansible inventory:

```ini
# Base hosts
[core]
vm-core-1 ansible_host=34.58.220.96 ansible_user=superdeploy

# Project-specific groups
[project_cheapa:children]
core

[project_cheapa:vars]
project_name=cheapa

[project_myapp:children]
core

[project_myapp:vars]
project_name=myapp
```

### 2. Deployment Isolation

Each project is deployed independently:

```bash
# Deploy cheapa
superdeploy up -p cheapa

# Deploy myapp
superdeploy up -p myapp
```

### 3. Resource Isolation

Each project gets isolated resources:

**Network:**
- `cheapa-network` (172.20.0.0/24)
- `myapp-network` (172.21.0.0/24)

**Containers:**
- `cheapa-postgres`, `cheapa-redis`, `cheapa-api`
- `myapp-postgres`, `myapp-redis`, `myapp-api`

**Data:**
- `/opt/superdeploy/projects/cheapa/`
- `/opt/superdeploy/projects/myapp/`

### 4. Ansible Playbook Execution

The playbook uses project-specific variables:

```yaml
- name: Deploy Infrastructure Addons
  hosts: core
  roles:
    - role: orchestration/addon-deployer
      vars:
        project_name: "{{ project_name }}"  # From inventory
        project_config: "{{ project_config }}"  # From extra-vars
```

### 5. Dynamic Inventory (Future)

For advanced multi-VM setups, use dynamic inventory:

```bash
# List all projects
./shared/ansible/inventories/dynamic.py --list

# Deploy specific project
ansible-playbook -i inventories/dynamic.py playbooks/site.yml --limit project_cheapa
```

## Current Implementation

**Status:** ✅ Working with static inventory

- Each `superdeploy up -p <project>` generates project-specific inventory
- Ansible playbook receives `project_name` variable
- All resources are prefixed with project name
- Complete isolation between projects

## Adding a New Project

```bash
# 1. Initialize project
superdeploy init -p newproject

# 2. Deploy infrastructure
superdeploy up -p newproject

# 3. Sync secrets
superdeploy sync -p newproject
```

That's it! The new project is completely isolated from existing projects.

## Shared vs Project-Specific

**Shared (Single Instance):**
- VM infrastructure (managed by Terraform workspaces)
- Monitoring (Prometheus, Grafana) - optional
- Reverse proxy (Caddy) - optional

**Project-Specific (Per Project):**
- Forgejo (Git server)
- PostgreSQL (Database)
- Redis (Cache)
- RabbitMQ (Message queue)
- Application containers
- Docker networks
- Data volumes

## Benefits

✅ **Cost Efficient:** Share VM infrastructure
✅ **Isolated:** Each project has separate resources
✅ **Scalable:** Add projects without code changes
✅ **Secure:** Network-level isolation
✅ **Simple:** Same commands for all projects
