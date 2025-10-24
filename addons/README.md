# SuperDeploy Addons

This directory contains **addon templates** - reusable service definitions that are instantiated per-project with project-specific configurations.

## Template vs Instance Architecture

**Key Concept:** Addons in this directory are **templates**, not deployed services. When you create a project, SuperDeploy instantiates project-specific instances from these templates.

### Example: Forgejo Addon

```
Template Location:
  superdeploy/addons/forgejo/     ← Template definition (reusable)

Deployed Instances:
  cheapa-forgejo                   ← Instance for "cheapa" project
  myapp-forgejo                    ← Instance for "myapp" project
  demo-forgejo                     ← Instance for "demo" project
```

Each project gets its own isolated Forgejo instance with:
- Separate Docker container (`cheapa-forgejo`, `myapp-forgejo`)
- Separate data volumes
- Separate network namespace
- Project-specific configuration from `project.yml`

### Why This Architecture?

**Benefits:**
- **Reusability:** Define addon structure once, use for unlimited projects
- **Consistency:** All projects use the same proven addon patterns
- **Isolation:** Each project's services are completely independent
- **Maintainability:** Update addon template, all future deployments benefit
- **No Code Changes:** Add new projects without modifying addon code

**This is why Forgejo exists in `superdeploy/addons/`** - it's a template that gets instantiated as `[project-name]-forgejo` for each project.

## Addon Template Structure

Each addon template is a subdirectory with the following required files:

```
addon-name/
├── addon.yml           # Metadata and configuration schema
├── compose.yml.j2      # Docker compose template (Jinja2)
├── env.yml             # Environment variable definitions
├── ansible.yml         # Ansible deployment tasks
└── templates/          # Additional configuration templates (optional)
    └── config.j2
```

These template files are **never modified** during deployment. Instead, they are rendered with project-specific values to create instance configurations.

## Template to Instance Relationship

Understanding the relationship between addon templates and deployed instances is crucial:

### Directory Structure

```
superdeploy/
├── addons/                              # TEMPLATES (reusable definitions)
│   ├── forgejo/
│   │   ├── addon.yml
│   │   ├── compose.yml.j2              # Template with {{ project_name }} variables
│   │   ├── env.yml
│   │   └── ansible.yml
│   ├── postgres/
│   ├── redis/
│   └── rabbitmq/
│
└── projects/                            # INSTANCES (deployed configurations)
    ├── cheapa/
    │   ├── project.yml                  # Project-specific configuration
    │   ├── .passwords.yml               # Auto-generated secrets
    │   └── compose/
    │       ├── docker-compose.core.yml  # Rendered from templates
    │       └── docker-compose.apps.yml
    │
    └── myapp/
        ├── project.yml
        ├── .passwords.yml
        └── compose/
            ├── docker-compose.core.yml
            └── docker-compose.apps.yml
```

### Instantiation Flow

```
Template                Configuration           Instance
────────                ─────────────           ────────

addons/postgres/   +    project.yml       →    cheapa-postgres
  addon.yml             core_services:           (container)
  compose.yml.j2          postgres:
  env.yml                   port: 5432
  ansible.yml               database: cheapa_db

                    +    .passwords.yml
                           POSTGRES_PASSWORD: xxx

                    =    projects/cheapa/compose/
                           docker-compose.core.yml
                           (rendered compose file)
```

### Multiple Projects, Same Template

One template can create many isolated instances:

```
Template: addons/forgejo/

Instances:
  ├── cheapa-forgejo      (port 3001, org: cheapaio)
  ├── myapp-forgejo       (port 3002, org: myapp-org)
  └── demo-forgejo        (port 3003, org: demo-org)

Each instance:
  - Separate container
  - Separate data volume
  - Separate network
  - Independent configuration
  - No shared state
```

## Creating a New Addon Template

To create a new addon template:

1. Create a new directory in `superdeploy/addons/` with your addon name (e.g., `postgres`)
2. Create the four required template files following the schema below
3. Use Jinja2 variables for project-specific values (e.g., `{{ project_name }}`)
4. Test your addon template by deploying it in a sample project
5. Verify that multiple projects can use the same template without conflicts

## File Schemas

### addon.yml

```yaml
name: addon-name
description: Brief description of the service
version: "1.0"
category: database  # database | cache | queue | proxy | monitoring

env_vars:
  - name: VAR_NAME
    description: Variable description
    default: "default_value"
    required: true
    secret: false
    generate: false  # Auto-generate secure value

compose:
  volumes:
    - data-volume
  ports: []
  networks:
    - project-network
  expose:
    - "5432"

resources:
  memory: 512M
  cpu: 0.5
  disk: 10G

healthcheck:
  command: "health check command"
  interval: 10s
  timeout: 5s
  retries: 5
  start_period: 30s

requires: []  # List of addon dependencies
conflicts: []  # List of conflicting addons
shared: false  # Single instance across all projects

monitoring:
  enabled: true
  metrics_port: 9187
  dashboard: dashboard.json
```

### compose.yml.j2

Jinja2 template for Docker compose service definition. Available variables:
- `project_name`: Project name
- `addon_name`: Addon name
- All metadata fields
- Project-specific overrides

### env.yml

```yaml
variables:
  VAR_NAME:
    source: runtime  # runtime | secret | config
    value: "${VAR_VALUE}"

github_secrets:
  - SECRET_NAME
```

### ansible.yml

Ansible tasks for deploying the addon. Standard Ansible task format.

## Available Addons

### Infrastructure Addons (Required)

#### Forgejo
**Category:** Infrastructure  
**Description:** Git server with CI/CD capabilities (Forgejo + Actions Runner)  
**Version:** 1.21  
**Ports:** 3001 (web), 2222 (SSH)  
**Dependencies:** PostgreSQL (internal)

**Why Forgejo is in `superdeploy/addons/`:**

Forgejo exists as a **reusable template** in the addons directory, not as a single shared instance. Each project gets its own isolated Forgejo instance:

- **Template:** `superdeploy/addons/forgejo/` (reusable definition)
- **Instances:** `cheapa-forgejo`, `myapp-forgejo`, `demo-forgejo` (deployed containers)

This architecture allows:
- Each project to have independent CI/CD infrastructure
- Project-specific organizations and repositories
- Isolated runner environments
- No cross-project interference

**Per-Project Instantiation:**

When you create a project, SuperDeploy instantiates a project-specific Forgejo instance:

```yaml
# projects/cheapa/project.yml
infrastructure:
  forgejo:
    version: "1.21"
    port: 3001
    admin_user: "admin"
    org: "cheapaio"
    repo: "superdeploy"
    ssh_port: 2222
```

**Deployed Instance:** `cheapa-forgejo` container with:
- Web UI: `http://vm-ip:3001`
- SSH: `ssh://vm-ip:2222`
- Organization: `cheapaio`
- Repository: `cheapaio/superdeploy`
- Dedicated runner: `cheapa-forgejo-runner`

**Setup Tasks (per instance):**
- Admin user creation
- Organization and repository setup
- Runner registration and configuration
- Secrets synchronization from GitHub

### Database Addons

#### PostgreSQL
**Category:** Database  
**Description:** Relational database  
**Version:** 15-alpine  
**Port:** 5432  
**Dependencies:** None

#### MongoDB
**Category:** Database  
**Description:** NoSQL document database  
**Version:** 7-alpine  
**Port:** 27017  
**Dependencies:** None

### Cache Addons

#### Redis
**Category:** Cache  
**Description:** In-memory data store  
**Version:** 7-alpine  
**Port:** 6379  
**Dependencies:** None

### Queue Addons

#### RabbitMQ
**Category:** Queue  
**Description:** Message broker  
**Version:** 3.12-management-alpine  
**Ports:** 5672 (AMQP), 15672 (Management UI)  
**Dependencies:** None

### Proxy Addons

#### Caddy
**Category:** Proxy  
**Description:** Reverse proxy and web server  
**Version:** 2-alpine  
**Ports:** 80 (HTTP), 443 (HTTPS)  
**Dependencies:** None

### Monitoring Addons

#### Monitoring Stack
**Category:** Monitoring  
**Description:** Prometheus + Grafana monitoring stack  
**Version:** Latest  
**Ports:** 9090 (Prometheus), 3000 (Grafana)  
**Dependencies:** None

**Features:**
- Automatic service discovery
- Pre-configured dashboards
- Alert rules
- Multi-project support

## How Addons Are Instantiated

When you deploy a project, SuperDeploy instantiates addon templates into project-specific instances:

### Instantiation Process

1. **Load Template:** `addon-deployer` role reads addon template from `superdeploy/addons/[addon-name]/`
2. **Merge Configuration:** Combines values from multiple sources:
   - `addon.yml` (template defaults)
   - `project.yml` (project-specific overrides)
   - `.passwords.yml` (auto-generated secrets)
   - `env.yml` (environment variable definitions)
3. **Render Templates:** Generates project-specific files:
   - `compose.yml.j2` → `projects/[project]/compose/docker-compose.core.yml`
   - Template variables include: `project_name`, `addon_name`, all config values
4. **Execute Deployment:** Runs `ansible.yml` tasks with project context
5. **Health Check:** Verifies service instance is healthy
6. **Post-Setup:** Executes addon-specific setup tasks (e.g., Forgejo admin creation)

### Example: PostgreSQL Instantiation

**Template Definition** (`superdeploy/addons/postgres/`):
```yaml
# addon.yml
name: postgres
version: "15-alpine"
port: 5432

# compose.yml.j2
services:
  {{ project_name }}-postgres:
    image: postgres:{{ version }}
    container_name: {{ project_name }}-postgres
    environment:
      POSTGRES_USER: {{ postgres_user }}
      POSTGRES_PASSWORD: {{ postgres_password }}
      POSTGRES_DB: {{ postgres_db }}
    ports:
      - "{{ postgres_port }}:5432"
```

**Project Configuration** (`projects/cheapa/project.yml`):
```yaml
project: cheapa
core_services:
  postgres:
    version: "15-alpine"
    port: 5432
    user: "cheapa_user"
    database: "cheapa_db"
```

**Generated Instance** (`projects/cheapa/compose/docker-compose.core.yml`):
```yaml
services:
  cheapa-postgres:
    image: postgres:15-alpine
    container_name: cheapa-postgres
    environment:
      POSTGRES_USER: cheapa_user
      POSTGRES_PASSWORD: <auto-generated-from-.passwords.yml>
      POSTGRES_DB: cheapa_db
    ports:
      - "5432:5432"
```

**Result:** A `cheapa-postgres` container instance running with project-specific configuration.

## Addon Deployment Process

The deployment process transforms templates into running instances:

1. **Template Loading:** Read addon template files from `superdeploy/addons/[addon-name]/`
2. **Configuration Merging:** Combine template defaults with project-specific values
3. **Template Rendering:** Generate instance-specific compose files and configs
4. **Instance Deployment:** Deploy containers with project-prefixed names
5. **Health Verification:** Ensure instance is running and healthy
6. **Post-Configuration:** Execute addon-specific setup (users, databases, etc.)

## Project-Specific Addon Configuration

All addons support project-specific configuration through `project.yml`. This allows each project to customize addon instances without modifying templates.

### Configuration Examples

#### Example 1: Single Project with Multiple Addons

**Project:** `cheapa`

```yaml
# projects/cheapa/project.yml
project: cheapa

core_services:
  postgres:
    version: "15-alpine"
    port: 5432
    user: "cheapa_user"
    database: "cheapa_db"
  
  redis:
    version: "7-alpine"
    port: 6379
  
  rabbitmq:
    version: "3.12-management-alpine"
    port: 5672
    management_port: 15672

infrastructure:
  forgejo:
    version: "1.21"
    port: 3001
    ssh_port: 2222
    admin_user: "admin"
    org: "cheapaio"
```

**Deployed Instances:**
- `cheapa-postgres` (port 5432)
- `cheapa-redis` (port 6379)
- `cheapa-rabbitmq` (ports 5672, 15672)
- `cheapa-forgejo` (ports 3001, 2222)

#### Example 2: Multiple Projects with Same Addons

**Project A:** `cheapa`
```yaml
project: cheapa
core_services:
  postgres:
    port: 5432
    database: "cheapa_db"
```

**Project B:** `myapp`
```yaml
project: myapp
core_services:
  postgres:
    port: 5433  # Different port to avoid conflicts
    database: "myapp_db"
```

**Deployed Instances:**
- `cheapa-postgres` (port 5432, database: cheapa_db)
- `myapp-postgres` (port 5433, database: myapp_db)

Both use the same PostgreSQL addon template but are completely isolated instances.

#### Example 3: Conditional Addon Deployment

**Development Project:**
```yaml
project: dev-environment
core_services:
  postgres:
    version: "15-alpine"
  redis:
    version: "7-alpine"
# No RabbitMQ - not needed for dev
```

**Production Project:**
```yaml
project: production
core_services:
  postgres:
    version: "15-alpine"
  redis:
    version: "7-alpine"
  rabbitmq:
    version: "3.12-management-alpine"
  monitoring:
    enabled: true
```

Each project deploys only the addons it needs.

### Configuration Override Priority

When instantiating addons, configuration values are merged with the following priority (highest to lowest):

1. **Project-specific values** in `project.yml` (highest priority)
2. **Auto-generated secrets** in `.passwords.yml`
3. **Template defaults** in `addon.yml` (lowest priority)

### Benefits of This Approach

- **No Code Changes:** Add new projects by creating `project.yml` - no addon template modifications needed
- **Flexibility:** Each project can customize addon configuration independently
- **Consistency:** All projects use the same proven addon templates
- **Isolation:** Projects cannot interfere with each other's services
- **Scalability:** Support unlimited projects without template duplication
