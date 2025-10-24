# Addon Deployer Role

## Overview

The `addon-deployer` role is a generic orchestrator that deploys addons based on project configuration. It handles the complete lifecycle of addon deployment including:

- Loading and validating addon metadata
- Generating environment variables from multiple sources
- Rendering templates (docker-compose.yml and other configs)
- Executing addon-specific deployment tasks
- Verifying addon health after deployment

## Architecture

This role follows a dynamic, configuration-driven approach where all addon deployments are orchestrated through a consistent pattern:

1. **Load addon metadata** (`addon.yml`) - defines addon properties, dependencies, and health checks
2. **Generate environment variables** (`env.yml`) - merges values from project.yml, secrets, and defaults
3. **Render templates** (`compose.yml.j2`, etc.) - generates configuration files with environment variables
4. **Execute deployment** (`ansible.yml`) - runs addon-specific deployment tasks
5. **Verify health** - checks if addon is operational

## Required Variables

These variables must be provided when using this role:

- `project_name` - Name of the project being deployed
- `project_config` - Parsed project.yml configuration (dictionary)
- `addons_base_path` - Base path where addon data will be deployed (default: `/opt/superdeploy/projects/{{ project_name }}/addons`)

## Optional Variables

These variables have defaults but can be overridden:

- `enabled_addons` - List of addon names to deploy (default: `[]`)
- `addon_configs` - Dictionary of addon-specific configurations from project.yml (default: `{}`)
- `project_secrets` - Dictionary of secrets from .passwords.yml (default: `{}`)
- `superdeploy_user` - User for file ownership (default: `superdeploy`)
- `superdeploy_group` - Group for file ownership (default: `superdeploy`)
- `addons_source_path` - Path to addon source files (default: `{{ playbook_dir }}/../../../addons`)
- `addon_health_check_timeout` - Health check timeout in seconds (default: `300`)
- `addon_health_check_retries` - Number of health check retries (default: `30`)
- `addon_health_check_delay` - Delay between health check retries in seconds (default: `10`)

## Usage

### Basic Usage

```yaml
- name: Deploy addons
  include_role:
    name: orchestration/addon-deployer
  vars:
    project_name: "myproject"
    project_config: "{{ project_yml_content }}"
    enabled_addons:
      - postgres
      - redis
      - monitoring
    addon_configs:
      postgres:
        version: "15-alpine"
        port: 5432
      redis:
        version: "7-alpine"
        port: 6379
    project_secrets:
      POSTGRES_PASSWORD: "secret123"
      REDIS_PASSWORD: "secret456"
```

### With Project Configuration

```yaml
- name: Load project configuration
  include_vars:
    file: "projects/{{ project_name }}/project.yml"
    name: project_config

- name: Load project secrets
  include_vars:
    file: "projects/{{ project_name }}/.passwords.yml"
    name: project_secrets

- name: Deploy addons
  include_role:
    name: orchestration/addon-deployer
  vars:
    enabled_addons: "{{ project_config.addons.keys() | list }}"
    addon_configs: "{{ project_config.addons }}"
```

## Addon Structure

Each addon must follow this structure:

```
addons/
└── addon-name/
    ├── addon.yml           # Metadata (required)
    ├── env.yml             # Environment variable definitions (required)
    ├── compose.yml.j2      # Docker compose template (optional)
    ├── ansible.yml         # Deployment tasks (optional)
    └── templates/          # Additional templates (optional)
        ├── config.yml.j2
        └── other.conf.j2
```

### addon.yml Schema

```yaml
name: addon-name
description: "Addon description"
version: "1.0"
category: database|cache|queue|proxy|monitoring|infrastructure
required: false  # true for infrastructure addons like Forgejo
dependencies: []  # List of other addon names required
ports:
  - name: main
    default: 5432
    description: "Main service port"
healthcheck:
  command: "pg_isready -U user"  # Shell command
  # OR
  url: "http://localhost:8080/health"  # HTTP endpoint
  status_code: 200
  interval: 10s
  timeout: 5s
  retries: 5
```

### env.yml Schema

```yaml
variables:
  VAR_NAME:
    source: config|secret|runtime
    description: "Variable description"
    required: true|false
    default: "default_value"
    # For config source:
    from_project: "path.to.value.in.project.yml"
    # For secret source:
    from_secrets: "SECRET_KEY_NAME"
    # For runtime source:
    from_ansible: "ansible_variable_name"
```

## Environment Variable Resolution

Variables are resolved in this priority order:

1. **Secrets** (`from_secrets`) - Highest priority, from .passwords.yml
2. **Project Config** (`from_project`) - From project.yml
3. **Defaults** (`default`) - Fallback value
4. **Runtime** (`from_ansible`) - Ansible facts/variables

Example:

```yaml
variables:
  POSTGRES_PASSWORD:
    source: secret
    from_secrets: "POSTGRES_PASSWORD"
    required: true
    # Will use value from project_secrets['POSTGRES_PASSWORD']
  
  POSTGRES_PORT:
    source: config
    from_project: "addons.postgres.port"
    default: "5432"
    # Will use project_config['addons']['postgres']['port'] or default to 5432
  
  POSTGRES_HOST:
    source: runtime
    from_ansible: "ansible_host"
    # Will use Ansible's ansible_host variable
```

## Standardized Variables Passed to Addons

When executing addon-specific `ansible.yml`, these variables are automatically provided:

- `addon_name` - Name of the addon being deployed
- `addon_path` - Source path of the addon
- `addon_deployment_path` - Target deployment path
- `addon_base_path` - Base path for all addons
- `project_name` - Project name
- `superdeploy_user` - User for file ownership
- `superdeploy_group` - Group for file ownership
- `addon_config` - Addon-specific configuration from project.yml
- `env_vars` - Dictionary of all generated environment variables
- `version` - Addon version (from env vars or metadata)

## Error Handling

The role provides clear error messages following this format:

```
[ADDON-DEPLOYER] ERROR: <description>
  - Expected: <what should be present>
  - Found: <what was found>
  - Fix: <actionable steps>
  - Docs: <reference to documentation>
```

Common errors:

1. **Missing required variable**
   - Check project.yml has the required configuration
   - Check .passwords.yml has the required secrets

2. **Addon not found**
   - Verify addon exists in addons directory
   - Check addon name spelling

3. **Dependency not satisfied**
   - Add required addon to enabled_addons list
   - Check addon.yml for dependency information

4. **Invalid addon metadata**
   - Ensure addon.yml exists and is valid YAML
   - Verify required fields (name, description, category)

## Health Checks

Health checks are optional but recommended. They verify the addon is operational after deployment.

### HTTP Health Check

```yaml
healthcheck:
  url: "http://localhost:8080/health"
  status_code: 200
  timeout: 5s
```

### Command Health Check

```yaml
healthcheck:
  command: "pg_isready -U postgres"
  interval: 10s
  timeout: 5s
  retries: 5
```

If a health check fails, a warning is displayed but deployment continues. Manual verification is recommended.

## Special Handling: Forgejo

Forgejo is treated as a required infrastructure addon and is automatically included in the deployment even if not explicitly listed in `enabled_addons`. This ensures the CI/CD infrastructure is always available.

## Examples

### Example 1: Deploy Database Addons

```yaml
- name: Deploy database addons
  include_role:
    name: orchestration/addon-deployer
  vars:
    project_name: "myapp"
    project_config:
      addons:
        postgres:
          version: "15-alpine"
          port: 5432
          database: "myapp_db"
        redis:
          version: "7-alpine"
          port: 6379
    enabled_addons:
      - postgres
      - redis
    project_secrets:
      POSTGRES_PASSWORD: "{{ lookup('password', '/dev/null length=32') }}"
      REDIS_PASSWORD: "{{ lookup('password', '/dev/null length=32') }}"
```

### Example 2: Deploy All Project Addons

```yaml
- name: Load project configuration
  include_vars:
    file: "projects/{{ project_name }}/project.yml"
    name: project_yml

- name: Load project secrets
  include_vars:
    file: "projects/{{ project_name }}/.passwords.yml"
    name: secrets

- name: Deploy all enabled addons
  include_role:
    name: orchestration/addon-deployer
  vars:
    project_config: "{{ project_yml }}"
    enabled_addons: "{{ project_yml.addons.keys() | list }}"
    addon_configs: "{{ project_yml.addons }}"
    project_secrets: "{{ secrets }}"
```

## Testing

To test the addon-deployer role:

1. Create a test project configuration
2. Create test addons with minimal metadata
3. Run the role with test data
4. Verify files are created correctly
5. Verify environment variables are generated correctly
6. Verify templates are rendered correctly

## Troubleshooting

### Addon not deploying

1. Check addon exists: `ls -la {{ addons_source_path }}/{{ addon_name }}`
2. Check addon.yml is valid: `ansible-playbook --syntax-check`
3. Check logs: `ansible-playbook -vvv`

### Environment variables not set correctly

1. Check env.yml definitions
2. Verify project.yml has required values
3. Verify .passwords.yml has required secrets
4. Check variable resolution priority

### Templates not rendering

1. Check compose.yml.j2 exists
2. Verify Jinja2 syntax is correct
3. Check all variables used in template are defined
4. Test template rendering: `ansible-playbook --check`

### Health check failing

1. Check service is actually running: `docker ps`
2. Check service logs: `docker logs {{ project_name }}-{{ addon_name }}`
3. Verify health check command/URL is correct
4. Increase timeout/retries if service is slow to start

## Contributing

When adding new features to the addon-deployer role:

1. Maintain backward compatibility with existing addons
2. Follow the established error message format
3. Add appropriate debug messages with verbosity levels
4. Update this README with new features
5. Test with multiple addon types

## Related Documentation

- [Addon System Overview](../../../../addons/README.md)
- [Project Configuration Schema](../../../../docs/ARCHITECTURE.md)
- [Deployment Guide](../../../../docs/DEPLOYMENT.md)
