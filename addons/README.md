# SuperDeploy Addon System

## Overview

The SuperDeploy addon system provides a plugin-based architecture where each service (PostgreSQL, Redis, RabbitMQ, etc.) is a self-contained module with its own configuration, templates, and deployment logic.

## Architecture Principles

### Single Responsibility Principle (SRP)
- **orchestration/addon-deployer**: Handles template rendering and orchestration
- **addon ansible.yml**: Handles service-specific deployment logic only

### Don't Repeat Yourself (DRY)
- Template rendering happens in ONE place: `render-templates.yml`
- All metadata variables are automatically passed to templates
- No duplicate template rendering code in addon files

## Addon Structure

```
addons/<addon-name>/
├── addon.yml           # Metadata and configuration schema
├── compose.yml.j2      # Docker compose template
├── env.yml             # Environment variable definitions
├── ansible.yml         # Deployment tasks (NO template rendering)
└── templates/          # Additional templates (optional)
    └── *.j2
```

## Creating a New Addon

### 1. Create addon.yml

Define your addon metadata:

```yaml
name: myservice
description: My awesome service
version: "1.0"
category: database  # database | cache | queue | proxy | monitoring

# Resource requirements
resources:
  memory: 512M
  cpu: 0.5
  disk: 10G

# Health check
healthcheck:
  command: "curl -f http://localhost:8080/health"
  interval: 10s
  timeout: 5s
  retries: 5
  start_period: 30s

# Monitoring
monitoring:
  enabled: true
  metrics_port: 9090
  dashboard: myservice-overview.json
```

### 2. Create compose.yml.j2

Your Docker compose template with access to all metadata:

```jinja2
  {{ addon_name }}:
    image: myservice:{{ version }}
    container_name: {{ project_name }}-{{ addon_name }}
    restart: unless-stopped
    environment:
      MY_VAR: ${MY_VAR}
    volumes:
      - {{ addon_name }}-data:/data
    networks:
      - {{ project_name }}-network
    expose:
      - "8080"
    healthcheck:
      test: ["CMD-SHELL", "{{ healthcheck.command }}"]
      interval: {{ healthcheck.interval }}
      timeout: {{ healthcheck.timeout }}
      retries: {{ healthcheck.retries }}
      start_period: {{ healthcheck.start_period }}
    deploy:
      resources:
        limits:
          memory: {{ resources.memory }}
          cpus: '{{ resources.cpu }}'
    {% if monitoring.enabled %}
    labels:
      - "prometheus.scrape=true"
      - "prometheus.port={{ monitoring.metrics_port }}"
      - "project={{ project_name }}"
      - "service={{ addon_name }}"
    {% endif %}
```

**Available Variables in Templates:**
- `addon_name`: Name of the addon
- `project_name`: Name of the project
- `version`: Version from addon.yml
- `healthcheck`: Healthcheck config from addon.yml
- `resources`: Resource limits from addon.yml
- `monitoring`: Monitoring config from addon.yml
- `addon_env_vars`: Dict of all environment variables

### 3. Create env.yml

Define environment variables:

```yaml
variables:
  MY_VAR:
    required: true
    from_project: "addons.myservice.my_var"
    default: "default_value"
```

### 4. Create ansible.yml

**IMPORTANT**: Do NOT render compose.yml.j2 here! It's already rendered by the orchestrator.

Focus ONLY on service-specific deployment logic:

```yaml
---
# MyService Addon Deployment Tasks

- name: Create {{ addon_name }} directories
  file:
    path: "{{ item }}"
    state: directory
    owner: "{{ superdeploy_user }}"
    group: "{{ superdeploy_group | default(superdeploy_user) }}"
    mode: '0755'
  loop:
    - "{{ addon_base_path }}/{{ addon_name }}"
    - "{{ addon_base_path }}/{{ addon_name }}/data"

# Note: docker-compose.yml is already rendered by orchestration/addon-deployer/tasks/render-templates.yml
# This keeps the deployment logic clean and focused on service-specific tasks

- name: Render {{ addon_name }} environment file
  template:
    src: "{{ addon_path }}/templates/myservice.env.j2"
    dest: "{{ addon_base_path }}/{{ addon_name }}/.env"
    owner: "{{ superdeploy_user }}"
    group: "{{ superdeploy_group | default(superdeploy_user) }}"
    mode: '0600'

- name: Start {{ addon_name }} services
  community.docker.docker_compose_v2:
    project_src: "{{ addon_base_path }}/{{ addon_name }}"
    state: present
    pull: true
  become_user: "{{ superdeploy_user }}"

- name: Wait for {{ addon_name }} to be ready
  wait_for:
    host: localhost
    port: 8080
    delay: 5
    timeout: 60
    state: started

- name: Verify {{ addon_name }} health
  uri:
    url: "http://localhost:8080/health"
    status_code: 200
  register: health_check
  until: health_check.status == 200
  retries: 10
  delay: 3
```

## Common Patterns

### Service with Database

If your service needs a database, add it as a dependency:

```yaml
# addon.yml
requires:
  - postgres
```

### Service with Custom Configuration

Use the templates/ directory for additional config files:

```yaml
# ansible.yml
- name: Render custom config
  template:
    src: "{{ addon_path }}/templates/myconfig.yml.j2"
    dest: "{{ addon_base_path }}/{{ addon_name }}/config/myconfig.yml"
```

### Service with Initialization

Add initialization tasks after service starts:

```yaml
# ansible.yml
- name: Initialize {{ addon_name }}
  shell: |
    docker exec {{ project_name }}-{{ addon_name }} /init.sh
  register: init_result
  changed_when: "'initialized' in init_result.stdout"
```

## Anti-Patterns (DON'T DO THIS)

### ❌ Rendering compose.yml.j2 in ansible.yml

```yaml
# DON'T DO THIS - It's already rendered!
- name: Render docker-compose.yml
  template:
    src: "{{ addon_path }}/compose.yml.j2"
    dest: "{{ addon_base_path }}/{{ addon_name }}/docker-compose.yml"
```

### ❌ Manually passing metadata variables

```yaml
# DON'T DO THIS - Variables are automatically available
- name: Some task
  vars:
    healthcheck: "{{ addon_metadata.healthcheck }}"
    monitoring: "{{ addon_metadata.monitoring }}"
```

### ❌ Hardcoding values

```yaml
# DON'T DO THIS
image: postgres:15-alpine  # Use {{ version }} instead

# DO THIS
image: postgres:{{ version }}
```

## Testing Your Addon

1. Add your addon to a project's `project.yml`:
```yaml
addons:
  myservice:
    version: "1.0"
    my_var: "test_value"
```

2. Run deployment:
```bash
superdeploy up myproject
```

3. Verify:
```bash
# Check if service is running
docker ps | grep myservice

# Check logs
docker logs myproject-myservice

# Check health
curl http://localhost:8080/health
```

## Troubleshooting

### Template variable undefined

If you get `'variable_name' is undefined`:
1. Check if the variable is defined in `addon.yml`
2. Verify the variable name matches exactly
3. Use `| default({})` for optional variables

### Service not starting

1. Check docker-compose.yml was rendered:
```bash
cat /opt/superdeploy/projects/myproject/addons/myservice/docker-compose.yml
```

2. Check environment variables:
```bash
cat /opt/superdeploy/projects/myproject/addons/myservice/.env
```

3. Check Docker logs:
```bash
docker logs myproject-myservice
```

## Best Practices

1. **Keep ansible.yml focused**: Only service-specific deployment logic
2. **Use metadata**: Define everything in addon.yml
3. **Provide defaults**: Use `| default()` for optional values
4. **Document variables**: Add descriptions in env.yml
5. **Test health checks**: Ensure healthcheck commands work
6. **Monitor resources**: Set appropriate resource limits
7. **Add labels**: Use labels for monitoring and organization

## Examples

See existing addons for reference:
- `postgres/` - Simple database addon
- `rabbitmq/` - Message queue with management UI
- `forgejo/` - Complex addon with multiple services
- `monitoring/` - Shared addon with nested healthchecks


## Addon Validation

SuperDeploy includes a comprehensive validation system to ensure addon quality and consistency.

### Running Validation

```bash
# Validate all addons
superdeploy validate addons

# Validate specific addon
superdeploy validate addons -a postgres

# Validate addons for a project
superdeploy validate addons -p cheapa
```

### Validation Checks

#### 1. Required Files
- ✅ `addon.yml` must exist
- ✅ `compose.yml.j2` or `docker-compose.yml.j2` must exist
- ℹ️ `ansible.yml` is optional but recommended

#### 2. Metadata Fields
Required fields in `addon.yml`:
- ✅ `name`: Addon identifier
- ✅ `description`: Human-readable description
- ✅ `version`: Version string
- ✅ `category`: One of: database, cache, queue, proxy, infrastructure, monitoring, storage

#### 3. Environment Variables
Each env_var must have:
- ✅ `name`: Variable name
- ✅ `description`: What it's for
- ✅ `required`: Boolean flag
- ⚠️ `secret`: Boolean flag (recommended)
- ⚠️ `default`: Default value (if not required)

#### 4. Health Check Configuration
- ✅ Must define either `command` or `url`
- ⚠️ Should include `interval`, `timeout`, `retries`, `start_period`
- ℹ️ Category-specific defaults apply if not specified

#### 5. Compose Template
- ⚠️ Should not include `version:` field (deprecated in Compose v2)
- ⚠️ Should include `healthcheck:` section
- ℹ️ Should use Jinja2 variables for configuration

#### 6. Ansible Tasks
Anti-patterns detected:
- ❌ `docker compose up` without `-d` flag
- ❌ Hardcoded `sleep` commands
- ❌ Piping curl to bash
- ❌ Dangerous recursive deletes
- ⚠️ Tasks without `name` field

### Validation Output

```
✓ PASS postgres
  ✓ Required file exists: addon.yml
  ✓ Required file exists: compose.yml.j2
  ✓ Required field present: name
  ✓ Required field present: description
  ✓ Category 'database' is valid
  ✓ Healthcheck method defined (command or url)

✗ FAIL rabbitmq
  ✓ Required file exists: addon.yml
  ✗ Healthcheck missing recommended field: start_period
    → Add 'start_period' to healthcheck section
  ⚠ Anti-pattern detected: sleep \d+
    → Avoid hardcoded sleep, use wait_for or proper health checks

Summary:
  Total addons: 7
  Passed: 6
  Failed: 1
```

### Validation Guidelines

#### Health Check Best Practices

1. **Always define health checks**:
   ```yaml
   healthcheck:
     command: "pg_isready -U ${POSTGRES_USER}"
     interval: 10s
     timeout: 5s
     retries: 5
     start_period: 30s
   ```

2. **Set appropriate start_period**:
   - Fast services (Redis): 10s
   - Medium services (PostgreSQL): 30s
   - Slow services (RabbitMQ): 60-90s

3. **Use service-specific commands**:
   - PostgreSQL: `pg_isready`
   - MongoDB: `mongosh --eval "db.runCommand({ ping: 1 })"`
   - Redis: `redis-cli ping`
   - RabbitMQ: `rabbitmq-diagnostics -q ping`

4. **For HTTP services, use URL checks**:
   ```yaml
   healthcheck:
     url: "http://localhost:8080/health"
     status_code: 200
     timeout: 5s
   ```

#### Ansible Task Best Practices

1. **Always name your tasks**:
   ```yaml
   - name: Start PostgreSQL service
     community.docker.docker_compose_v2:
       project_src: "{{ addon_base_path }}/{{ addon_name }}"
   ```

2. **Use wait_for instead of sleep**:
   ```yaml
   # ❌ Bad
   - shell: sleep 30
   
   # ✅ Good
   - wait_for:
       host: localhost
       port: 5432
       delay: 5
       timeout: 60
   ```

3. **Don't duplicate template rendering**:
   ```yaml
   # ❌ Bad - addon-deployer already does this
   - name: Render compose file
     template:
       src: compose.yml.j2
       dest: "{{ addon_base_path }}/docker-compose.yml"
   
   # ✅ Good - focus on service-specific tasks
   - name: Initialize database
     shell: docker exec {{ project_name }}-postgres psql -c "CREATE DATABASE mydb"
   ```

4. **Use docker compose v2 module**:
   ```yaml
   # ✅ Good
   - name: Start services
     community.docker.docker_compose_v2:
       project_src: "{{ addon_base_path }}/{{ addon_name }}"
       state: present
   ```

#### Environment Variable Guidelines

1. **Mark secrets appropriately**:
   ```yaml
   - name: POSTGRES_PASSWORD
     description: Database password
     required: true
     secret: true      # ✅ Marked as secret
     generate: true    # ✅ Auto-generate
   ```

2. **Provide sensible defaults**:
   ```yaml
   - name: POSTGRES_PORT
     description: PostgreSQL port
     default: "5432"   # ✅ Standard port
     required: true
     secret: false
   ```

3. **Use variable substitution**:
   ```yaml
   - name: POSTGRES_USER
     description: Database username
     default: "${PROJECT}_user"  # ✅ Project-specific
     required: true
   ```

### Auto-Fix (Future)

The `--fix` flag will automatically fix common issues:

```bash
# Auto-fix issues (not yet implemented)
superdeploy validate addons --fix
```

Planned auto-fixes:
- Add missing `start_period` to healthchecks
- Remove deprecated `version:` from compose files
- Add `name` fields to unnamed tasks
- Convert `sleep` to `wait_for` where possible

### Integration with CI/CD

Add validation to your CI pipeline:

```yaml
# .github/workflows/validate.yml
- name: Validate addons
  run: superdeploy validate addons
```

This ensures all addons meet quality standards before deployment.
