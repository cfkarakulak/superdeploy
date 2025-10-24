# Ansible Addon System Migration

## Overview

This document describes the migration of SuperDeploy's Ansible roles from hardcoded service deployment to a dynamic addon-based architecture.

## What Changed

### Before: Hardcoded Service Logic

The old `core-services` role had hardcoded logic for each service:

```yaml
- name: Wait for PostgreSQL to be ready
  shell: |
    docker exec {{ project_name }}-postgres pg_isready
  when: "'postgres' in core_services"

- name: Wait for RabbitMQ to be ready
  shell: |
    docker exec {{ project_name }}-rabbitmq rabbitmq-diagnostics ping
  when: "'rabbitmq' in core_services"
```

**Problems:**
- Service-specific logic in core role
- Hard to add new services
- Difficult to maintain
- No separation of concerns

### After: Addon-Based Architecture

The new system dynamically includes addon tasks:

```yaml
- name: Deploy PostgreSQL addon
  include_tasks: "{{ superdeploy_root }}/addons/postgres/ansible.yml"
  vars:
    addon_name: postgres
    version: "{{ addon_configs_dict.postgres.version | default('15-alpine') }}"
  when: "'postgres' in enabled_addons_list"
```

**Benefits:**
- No service-specific logic in core role
- Easy to add new addons
- Each addon is self-contained
- Clean separation of concerns

## Files Modified

### 1. Core Services Role

**File:** `superdeploy/shared/ansible/roles/core-services/tasks/main.yml`

**Changes:**
- Removed hardcoded service deployment logic
- Added dynamic addon task inclusion
- Added JSON parsing for addon configurations
- Added password file parsing
- Improved tagging system

**Key Features:**
- Parses `enabled_addons` JSON from CLI
- Parses `addon_configs` JSON from CLI
- Loads passwords from `.passwords.yml`
- Dynamically includes addon ansible.yml files
- Passes addon-specific variables

### 2. Monitoring Role (New)

**Files:**
- `superdeploy/shared/ansible/roles/monitoring/tasks/main.yml`
- `superdeploy/shared/ansible/roles/monitoring/handlers/main.yml`

**Purpose:**
- Deploy shared Grafana/Prometheus for all projects
- Generate dynamic Prometheus scrape configs
- Generate dynamic Grafana datasources
- Support project-based filtering

### 3. Main Playbook

**File:** `superdeploy/shared/ansible/playbooks/site.yml`

**Changes:**
- Added monitoring role before core-services
- Monitoring deploys shared infrastructure
- Core-services deploys project-specific addons

### 4. CLI Command

**File:** `superdeploy/cli/commands/up.py`

**Changes:**
- Build `addon_configs` JSON from project config
- Build `enabled_addons` JSON from project config
- Pass JSON variables to Ansible

### 5. Addon Ansible Files

**Updated:**
- `superdeploy/addons/rabbitmq/ansible.yml` - Fixed variable names
- `superdeploy/addons/mongodb/ansible.yml` - Fixed variable names
- `superdeploy/addons/caddy/ansible.yml` - Fixed undefined variables

## Variable Flow

### From Project Config to Ansible

1. **Project Config (project.yml)**
   ```yaml
   core_services:
     postgres:
       version: "15-alpine"
       user: "myproject_user"
     redis:
       version: "7-alpine"
   ```

2. **Python CLI (up.py)**
   ```python
   addon_configs = {
       "postgres": {"version": "15-alpine", "user": "myproject_user"},
       "redis": {"version": "7-alpine"}
   }
   enabled_addons = ["postgres", "redis"]
   ```

3. **Ansible Variables**
   ```bash
   -e 'enabled_addons=["postgres","redis"]'
   -e 'addon_configs={"postgres":{"version":"15-alpine"}}'
   ```

4. **Core Services Role**
   ```yaml
   enabled_addons_list: ["postgres", "redis"]
   addon_configs_dict: {"postgres": {"version": "15-alpine"}}
   ```

5. **Addon Tasks**
   ```yaml
   version: "15-alpine"
   postgres_user: "myproject_user"
   ```

## Addon Variables

Each addon receives standardized variables:

### Common Variables
- `project_name`: Project name
- `addon_name`: Addon name
- `version`: Addon version
- `passwords_data`: Parsed passwords

### Service-Specific Variables
- **PostgreSQL**: `postgres_user`, `postgres_password`, `postgres_db`
- **Redis**: `redis_password`
- **RabbitMQ**: `rabbitmq_user`, `rabbitmq_password`
- **MongoDB**: `mongodb_user`, `mongodb_password`, `mongodb_db`
- **Caddy**: `caddy_domain`, `caddy_email`

## Tagging System

The new system uses hierarchical tags:

### Role-Level Tags
- `monitoring`: Shared monitoring deployment
- `core-services`: Project-specific services

### Category Tags
- `database`: All database addons
- `cache`: All cache addons
- `queue`: All queue addons
- `proxy`: All proxy addons

### Addon-Specific Tags
- `postgres`, `redis`, `rabbitmq`, `mongodb`, `caddy`

### Task-Level Tags
- `setup`: Directory and network creation
- `config`: Configuration file management
- `secrets`: Password handling
- `deploy`: Container deployment
- `healthcheck`: Health checks
- `verify`: Verification tasks

### Example Usage

```bash
# Deploy only databases
ansible-playbook ... --tags database

# Deploy PostgreSQL and Redis
ansible-playbook ... --tags postgres,redis

# Setup and deploy all addons
ansible-playbook ... --tags setup,addons

# Deploy monitoring only
ansible-playbook ... --tags monitoring
```

## Adding New Addons

To add a new addon to the Ansible system:

### 1. Create Addon Ansible File

Create `superdeploy/addons/{addon_name}/ansible.yml`:

```yaml
---
# {AddonName} Addon Deployment Tasks

- name: Create {{ addon_name }} data directory
  file:
    path: "/opt/superdeploy/projects/{{ project_name }}/data/{{ addon_name }}"
    state: directory
    owner: superdeploy
    group: superdeploy
    mode: '0755'

- name: Deploy {{ addon_name }} container
  docker_container:
    name: "{{ project_name }}-{{ addon_name }}"
    image: "{image}:{{ version }}"
    state: started
    restart_policy: unless-stopped
    # ... container config
```

### 2. Add to Core Services Role

Edit `superdeploy/shared/ansible/roles/core-services/tasks/main.yml`:

```yaml
- name: Deploy {AddonName} addon
  include_tasks: "{{ superdeploy_root }}/addons/{addon_name}/ansible.yml"
  vars:
    addon_name: {addon_name}
    version: "{{ addon_configs_dict.{addon_name}.version | default('latest') }}"
    # Add addon-specific variables
  when: "'{addon_name}' in enabled_addons_list"
  tags:
    - {addon_name}
    - {category}
    - addons
```

### 3. Test

```bash
# Test addon deployment
ansible-playbook -i inventories/dev.ini playbooks/site.yml \
  --tags {addon_name} \
  -e "project_name=test" \
  -e 'enabled_addons=["{addon_name}"]' \
  -e 'addon_configs={{"{addon_name}": {}}}'
```

## Migration Checklist

- [x] Refactor core-services role to use addon system
- [x] Remove hardcoded service deployment logic
- [x] Implement dynamic task inclusion
- [x] Create monitoring role for shared Grafana/Prometheus
- [x] Update main playbook to include monitoring role
- [x] Update CLI to pass addon configurations
- [x] Fix addon ansible.yml variable names
- [x] Add comprehensive tagging system
- [x] Create documentation (README files)
- [ ] Test with existing projects
- [ ] Update deployment documentation
- [ ] Train team on new system

## Testing

### Test Individual Addons

```bash
# Test PostgreSQL addon
ansible-playbook ... --tags postgres -e 'enabled_addons=["postgres"]'

# Test Redis addon
ansible-playbook ... --tags redis -e 'enabled_addons=["redis"]'
```

### Test Multiple Addons

```bash
# Test all databases
ansible-playbook ... --tags database -e 'enabled_addons=["postgres","mongodb"]'
```

### Test Full Deployment

```bash
# Test complete deployment
ansible-playbook ... --tags core-services -e 'enabled_addons=["postgres","redis","rabbitmq"]'
```

## Troubleshooting

### Addon Not Deploying

1. Check if addon is in `enabled_addons_list`:
   ```yaml
   - name: Debug enabled addons
     debug:
       var: enabled_addons_list
   ```

2. Check if addon ansible.yml exists:
   ```bash
   ls -la superdeploy/addons/{addon_name}/ansible.yml
   ```

3. Check Ansible syntax:
   ```bash
   ansible-playbook --syntax-check playbooks/site.yml
   ```

### Variable Not Passed to Addon

1. Check addon_configs_dict:
   ```yaml
   - name: Debug addon configs
     debug:
       var: addon_configs_dict
   ```

2. Check variable in addon task:
   ```yaml
   - name: Debug version
     debug:
       var: version
   ```

### Password Not Found

1. Check passwords_data:
   ```yaml
   - name: Debug passwords
     debug:
       var: passwords_data
   ```

2. Verify .passwords.yml exists:
   ```bash
   cat /opt/superdeploy/projects/{project}/.passwords.yml
   ```

## Benefits

### For Developers
- Easy to add new addons
- Self-contained addon logic
- Clear variable contracts
- Better testing isolation

### For Operations
- Consistent deployment patterns
- Better error messages
- Granular control with tags
- Easier troubleshooting

### For Maintenance
- No service-specific code in core
- Each addon is independent
- Clear separation of concerns
- Easier to update individual addons

## Next Steps

1. Test with existing projects
2. Update deployment documentation
3. Create addon development guide
4. Add more addons (Elasticsearch, MinIO, etc.)
5. Implement addon dependency resolution
6. Add addon conflict detection

## See Also

- [Core Services Role README](roles/core-services/README.md)
- [Monitoring Role README](roles/monitoring/README.md)
- [Addon System Design](../../.kiro/specs/addon-system-architecture/design.md)
- [Implementation Tasks](../../.kiro/specs/addon-system-architecture/tasks.md)
