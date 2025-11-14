# SuperDeploy Addon System Redesign

## 📋 Table of Contents

1. [Current State Analysis](#current-state-analysis)
2. [Heroku Addon Architecture](#heroku-addon-architecture)
3. [Proposed Architecture](#proposed-architecture)
4. [Implementation Plan](#implementation-plan)
5. [Code Examples](#code-examples)
6. [CLI Commands](#cli-commands)
7. [Migration Guide](#migration-guide)

---

## 🔍 Current State Analysis

### ✅ What Works Well

```yaml
# addons/postgres/addon.yml - Good metadata structure
name: postgres
description: PostgreSQL relational database
version: "15-alpine"
category: database

env_vars:
  - name: POSTGRES_HOST
    description: PostgreSQL hostname
    default: "${CORE_INTERNAL_IP}"
    required: true
  - name: POSTGRES_PASSWORD
    required: true
    secret: true
    generate: true

# Health checks, resource limits, dependencies
healthcheck:
  command: "pg_isready -U ${POSTGRES_USER} -d ${POSTGRES_DB}"
  interval: 10s
  
resources:
  memory: 512M
  cpu: 0.5
  disk: 10G
```

**Strengths:**
- ✅ Clean addon metadata structure
- ✅ Health check definitions
- ✅ Resource limits
- ✅ Environment variable templates
- ✅ Dependencies/conflicts system

---

### ❌ Current Limitations

| Limitation | Description | Example Problem |
|------------|-------------|-----------------|
| **Single Instance** | Only 1 instance per addon type | Can't have 2 PostgreSQL databases |
| **No Attachment System** | No addon → app relationship | Which app uses which DB? Unknown |
| **Manual Configuration** | secrets.yml edited by hand | Add addon → manually add 20+ env vars |
| **No Named Instances** | Can't name addon instances | `primary-db`, `analytics-db` not possible |
| **Hard-coded Variables** | POSTGRES_* is fixed | 2nd DB → POSTGRES2_*? Messy! |
| **No Resource Plans** | All addons same size | Small cache = Large DB in resources |
| **Port Conflicts** | Manual port management | Add 2nd postgres → port conflict! |

---

### Current Configuration (config.yml)

```yaml
# projects/cheapa/config.yml
addons:
  rabbitmq:
    version: 3.12-management-alpine
  postgres:
    version: 15-alpine
  caddy:
    version: 2-alpine

apps:
  api:
    path: /Users/cfkarakulak/Desktop/cheapa.io/code/api
    vm: app
    port: 8000
  services:
    path: /Users/cfkarakulak/Desktop/cheapa.io/code/services
    vm: app
```

**Problems:**
- No way to define multiple postgres instances
- No explicit connection between app and addon
- No resource differentiation

---

### Current Secrets (secrets.yml)

```yaml
# projects/cheapa/secrets.yml
secrets:
  shared:
    # Single PostgreSQL - hardcoded names
    POSTGRES_DB: cheapa_db
    POSTGRES_HOST: 10.1.0.3
    POSTGRES_PASSWORD: IFYy2nisQkXn8im3FhWqNXpEldhnTNhLCiYR5XVwgck
    POSTGRES_PORT: 5432
    POSTGRES_USER: cheapa_user
    
    # Single RabbitMQ
    RABBITMQ_HOST: 10.1.0.3
    RABBITMQ_PASSWORD: fCZyYC5nbIRhxLNNgX7Bggy6F9QDPF1IjwlivsQNSWA
    RABBITMQ_PORT: 5672
    RABBITMQ_USER: cheapa_user
    RABBITMQ_VHOST: /

env_aliases:
  api:
    DB_DATABASE: POSTGRES_DB  # Maps to shared postgres
    DB_HOST: POSTGRES_HOST
    DB_PASSWORD: POSTGRES_PASSWORD
  
  services:
    DB_DATABASE: POSTGRES_DB  # Both apps use SAME database
    DB_HOST: POSTGRES_HOST
    RABBIT_HOST: RABBITMQ_HOST
```

**Problems:**
- All apps share same DATABASE credentials
- No way to give different databases to different apps
- Manual alias mapping for each app
- Adding 2nd database → namespace collision (POSTGRES_* already used)

---

## 🚀 Heroku Addon Architecture

### How Heroku Does It

#### 1. **Provision Named Instances**

```bash
# Create multiple databases with unique names
heroku addons:create heroku-postgresql:hobby-dev --as PRIMARY_DATABASE
heroku addons:create heroku-postgresql:standard-0 --as ANALYTICS_DATABASE
heroku addons:create redis:hobby-dev --as SESSION_STORE
heroku addons:create redis:premium-0 --as CACHE_STORE

# List all addon instances
heroku addons
```

**Output:**
```
Add-on                           Plan           Price      State
───────────────────────────────  ─────────────  ─────────  ───────
primary-database (postgresql-1)  hobby-dev      free       created
analytics-database (postgresql-2) standard-0    $50/month  created
session-store (redis-3)          hobby-dev      free       created
cache-store (redis-4)            premium-0      $15/month  created
```

**Key Points:**
- ✅ Each instance has unique name (`primary-database`, `analytics-database`)
- ✅ Same addon type can have multiple instances
- ✅ Different resource plans (hobby-dev, standard-0, premium-0)
- ✅ Each instance has unique internal ID (postgresql-1, postgresql-2)

---

#### 2. **Auto-Generated Environment Variables**

```bash
# PRIMARY_DATABASE automatically injects:
heroku config | grep PRIMARY
```

**Output:**
```bash
PRIMARY_DATABASE_URL=postgres://user:pass@host:5432/db_primary
DATABASE_URL=postgres://user:pass@host:5432/db_primary  # Default alias

# ANALYTICS_DATABASE automatically injects:
ANALYTICS_DATABASE_URL=postgres://user:pass@host:5433/db_analytics

# SESSION_STORE automatically injects:
SESSION_STORE_URL=redis://default:pass@host:6379
SESSION_STORE_TLS_URL=rediss://default:pass@host:6380

# CACHE_STORE automatically injects:
CACHE_STORE_URL=redis://default:pass@host:6381
```

**Key Points:**
- ✅ Environment variables auto-generated with instance name prefix
- ✅ Default alias (DATABASE_URL for primary database)
- ✅ Different ports for same addon type (5432, 5433 for 2 postgres)
- ✅ No manual configuration needed

---

#### 3. **Addon Attachments**

```bash
# Attach addon to different app with custom alias
heroku addons:attach PRIMARY_DATABASE --app my-worker-app
heroku addons:attach PRIMARY_DATABASE --app my-api-app --as DB
heroku addons:attach ANALYTICS_DATABASE --app my-api-app --as REPORTS_DB

# View all attachments
heroku addons:attachments
```

**Output:**
```
Owning App    Providing Addon          Attached As        Attached To App
────────────  ───────────────────────  ─────────────────  ───────────────
my-api-app    primary-database-123     PRIMARY_DATABASE   my-api-app
my-api-app    analytics-database-456   REPORTS_DB         my-api-app
my-worker-app primary-database-123     DATABASE           my-worker-app
```

**Key Points:**
- ✅ One addon instance can be attached to multiple apps
- ✅ Custom alias per attachment (REPORTS_DB, DATABASE)
- ✅ Clear visibility: which app uses which addon
- ✅ Shared resources possible (my-api-app and my-worker-app share PRIMARY_DATABASE)

---

#### 4. **Addon Info & Management**

```bash
# Get detailed info
heroku addons:info PRIMARY_DATABASE
```

**Output:**
```
=== primary-database
Attachments:  my-api-app::PRIMARY_DATABASE
              my-worker-app::DATABASE
Installed at: 2025-11-10T10:00:00Z
Owning app:   my-api-app
Plan:         heroku-postgresql:standard-0
Price:        $50/month
State:        created
```

```bash
# Upgrade plan
heroku addons:upgrade PRIMARY_DATABASE heroku-postgresql:standard-2

# Destroy addon
heroku addons:destroy PRIMARY_DATABASE
```

---

## 🎯 Proposed Architecture

### Design Principles

1. **Named Instances**: Every addon instance has a unique name
2. **Explicit Attachments**: Clear app → addon relationships
3. **Auto-Configuration**: Environment variables auto-generated
4. **Resource Plans**: Small/Standard/Large tiers
5. **Zero Manual Config**: No hand-editing secrets.yml

---

### New Config Structure

```yaml
# projects/cheapa/config.yml

# =============================================================================
# Named Addon Instances
# =============================================================================
addons:
  # Category: databases
  databases:
    primary:
      type: postgres
      version: 15-alpine
      plan: standard
      options:
        max_connections: 100
        shared_buffers: 256MB
      
    analytics:
      type: postgres
      version: 15-alpine
      plan: large
      options:
        max_connections: 200
        shared_buffers: 512MB
      
    reports:
      type: postgres
      version: 14-alpine  # Different version!
      plan: small
  
  # Category: caches
  caches:
    session:
      type: redis
      version: 7-alpine
      plan: small
      options:
        maxmemory: 256mb
        maxmemory_policy: allkeys-lru
      
    products:
      type: redis
      version: 7-alpine
      plan: large
      options:
        maxmemory: 2gb
  
  # Category: queues
  queues:
    main:
      type: rabbitmq
      version: 3.12-management-alpine
      plan: standard
      options:
        vhost: /
        max_connections: 500
    
    priority:
      type: rabbitmq
      version: 3.12-management-alpine
      plan: small
      options:
        vhost: /priority
  
  # Category: search
  search:
    products:
      type: elasticsearch
      version: 8.10.0
      plan: large
  
  # Reverse proxy (single instance)
  proxy:
    main:
      type: caddy
      version: 2-alpine
      plan: standard

# =============================================================================
# Apps with Explicit Addon Attachments
# =============================================================================
apps:
  api:
    path: /Users/cfkarakulak/Desktop/cheapa.io/code/api
    vm: app
    port: 8000
    domain: api.cheapa.io
    
    # Explicit addon attachments
    addons:
      - addon: databases.primary
        as: DATABASE              # Env prefix: DATABASE_*
        access: readwrite
        
      - addon: databases.analytics
        as: ANALYTICS             # Env prefix: ANALYTICS_*
        access: readonly          # Read-only replica connection
        
      - addon: caches.session
        as: CACHE                 # Env prefix: CACHE_*
        
      - addon: queues.main
        as: RABBITMQ              # Env prefix: RABBITMQ_*
        
      - addon: search.products
        as: ELASTICSEARCH
    
    hooks:
      after_deploy:
        - python craft migrate --database=primary
        - python craft cache:clear
  
  services:
    path: /Users/cfkarakulak/Desktop/cheapa.io/code/services
    vm: app
    # Queue worker - no HTTP port
    
    addons:
      - addon: databases.primary
        as: DB                    # Services uses DB_* prefix
        access: readwrite
        
      - addon: queues.main
        as: QUEUE
        
      - addon: queues.priority
        as: PRIORITY_QUEUE
  
  storefront:
    path: /Users/cfkarakulak/Desktop/cheapa.io/code/storefront
    vm: app
    port: 3000
    domain: cheapa.io
    
    addons:
      - addon: databases.primary
        as: DATABASE
        access: readonly          # Storefront only reads
        
      - addon: caches.products
        as: CACHE
        
      - addon: search.products
        as: SEARCH
```

---

### Auto-Generated Environment Variables

Based on attachments above, SuperDeploy automatically generates:

#### **API App Environment:**

```bash
# databases.primary as DATABASE
DATABASE_URL=postgresql://cheapa_primary_user:xxx@10.1.0.3:5432/cheapa_primary
DATABASE_HOST=10.1.0.3
DATABASE_PORT=5432
DATABASE_USER=cheapa_primary_user
DATABASE_PASSWORD=xxx
DATABASE_NAME=cheapa_primary
DATABASE_SSL=false

# databases.analytics as ANALYTICS (readonly connection)
ANALYTICS_URL=postgresql://cheapa_analytics_readonly:yyy@10.1.0.3:5433/cheapa_analytics
ANALYTICS_HOST=10.1.0.3
ANALYTICS_PORT=5433
ANALYTICS_USER=cheapa_analytics_readonly
ANALYTICS_PASSWORD=yyy
ANALYTICS_NAME=cheapa_analytics
ANALYTICS_READONLY=true

# caches.session as CACHE
CACHE_URL=redis://10.1.0.4:6379
CACHE_HOST=10.1.0.4
CACHE_PORT=6379
CACHE_PASSWORD=zzz

# queues.main as RABBITMQ
RABBITMQ_URL=amqp://cheapa_main_user:aaa@10.1.0.3:5672/
RABBITMQ_HOST=10.1.0.3
RABBITMQ_PORT=5672
RABBITMQ_USER=cheapa_main_user
RABBITMQ_PASSWORD=aaa
RABBITMQ_VHOST=/

# search.products as ELASTICSEARCH
ELASTICSEARCH_URL=http://10.1.0.5:9200
ELASTICSEARCH_HOST=10.1.0.5
ELASTICSEARCH_PORT=9200
```

#### **Services App Environment:**

```bash
# databases.primary as DB (different prefix!)
DB_URL=postgresql://cheapa_primary_user:xxx@10.1.0.3:5432/cheapa_primary
DB_HOST=10.1.0.3
DB_PORT=5432
DB_USER=cheapa_primary_user
DB_PASSWORD=xxx
DB_NAME=cheapa_primary

# queues.main as QUEUE
QUEUE_URL=amqp://cheapa_main_user:aaa@10.1.0.3:5672/
QUEUE_HOST=10.1.0.3
QUEUE_PORT=5672
QUEUE_USER=cheapa_main_user
QUEUE_PASSWORD=aaa
QUEUE_VHOST=/

# queues.priority as PRIORITY_QUEUE
PRIORITY_QUEUE_URL=amqp://cheapa_priority_user:bbb@10.1.0.3:5673/priority
PRIORITY_QUEUE_HOST=10.1.0.3
PRIORITY_QUEUE_PORT=5673
PRIORITY_QUEUE_USER=cheapa_priority_user
PRIORITY_QUEUE_PASSWORD=bbb
PRIORITY_QUEUE_VHOST=/priority
```

**Key Benefits:**
- ✅ No manual env var configuration
- ✅ Same addon, different prefixes per app
- ✅ Clear, predictable naming
- ✅ No env_aliases needed (auto-generated with correct prefix)

---

### Auto-Generated Secrets

```yaml
# projects/cheapa/secrets.yml (AUTO-GENERATED - DO NOT EDIT)
# Generated by: superdeploy cheapa:sync
# Last updated: 2025-11-10T20:00:00Z

# =============================================================================
# Addon Instance Credentials (Auto-Generated)
# =============================================================================
addons:
  postgres:
    primary:
      HOST: 10.1.0.3
      PORT: 5432
      USER: cheapa_primary_user
      PASSWORD: IFYy2nisQkXn8im3FhWqNXpEldhnTNhLCiYR5XVwgck
      DATABASE: cheapa_primary
      READONLY_USER: cheapa_primary_readonly
      READONLY_PASSWORD: readonly_secure_pass_123
      
    analytics:
      HOST: 10.1.0.3
      PORT: 5433  # Auto-allocated different port
      USER: cheapa_analytics_user
      PASSWORD: analytics_secure_pass_456
      DATABASE: cheapa_analytics
      READONLY_USER: cheapa_analytics_readonly
      READONLY_PASSWORD: analytics_readonly_789
      
    reports:
      HOST: 10.1.0.3
      PORT: 5434
      USER: cheapa_reports_user
      PASSWORD: reports_secure_pass_abc
      DATABASE: cheapa_reports
  
  redis:
    session:
      HOST: 10.1.0.4
      PORT: 6379
      PASSWORD: session_redis_pass_def
      
    products:
      HOST: 10.1.0.4
      PORT: 6380  # Different port
      PASSWORD: products_redis_pass_ghi
  
  rabbitmq:
    main:
      HOST: 10.1.0.3
      PORT: 5672
      USER: cheapa_main_user
      PASSWORD: rabbitmq_main_pass_jkl
      VHOST: /
      
    priority:
      HOST: 10.1.0.3
      PORT: 5673
      USER: cheapa_priority_user
      PASSWORD: rabbitmq_priority_pass_mno
      VHOST: /priority
  
  elasticsearch:
    products:
      HOST: 10.1.0.5
      PORT: 9200
      USER: elastic
      PASSWORD: elastic_pass_pqr

# =============================================================================
# Shared Application Secrets (User-Managed)
# =============================================================================
shared:
  DOCKER_ORG: c100394
  DOCKER_TOKEN: dckr_pat_xxx
  REPOSITORY_TOKEN: ghp_xxx
  ORCHESTRATOR_IP: 34.41.217.222

# =============================================================================
# App-Specific Secrets (User-Managed)
# =============================================================================
api:
  API_SECRET_KEY: api_secret_xxx
  JWT_SECRET: jwt_secret_yyy

storefront:
  NEXTAUTH_SECRET: nextauth_secret_zzz
  NEXTAUTH_URL: https://cheapa.io

services:
  # No app-specific secrets
```

---

### Docker Compose Generation

```yaml
# /opt/superdeploy/projects/cheapa/compose/docker-compose.yml
# AUTO-GENERATED - DO NOT EDIT

services:
  # =============================================================================
  # Addon: postgres instances
  # =============================================================================
  postgres-primary:
    image: postgres:15-alpine
    container_name: cheapa_postgres_primary
    restart: unless-stopped
    ports:
      - "5432:5432"
    environment:
      POSTGRES_DB: cheapa_primary
      POSTGRES_USER: cheapa_primary_user
      POSTGRES_PASSWORD: IFYy2nisQkXn8im3FhWqNXpEldhnTNhLCiYR5XVwgck
    volumes:
      - postgres-primary-data:/var/lib/postgresql/data
    networks:
      - cheapa-network
    healthcheck:
      test: ["CMD", "pg_isready", "-U", "cheapa_primary_user", "-d", "cheapa_primary"]
      interval: 10s
      timeout: 5s
      retries: 5
    deploy:
      resources:
        limits:
          memory: 512M
          cpus: '0.5'
    labels:
      - "com.superdeploy.addon=postgres"
      - "com.superdeploy.instance=primary"
      - "com.superdeploy.plan=standard"
  
  postgres-analytics:
    image: postgres:15-alpine
    container_name: cheapa_postgres_analytics
    restart: unless-stopped
    ports:
      - "5433:5432"  # Different external port!
    environment:
      POSTGRES_DB: cheapa_analytics
      POSTGRES_USER: cheapa_analytics_user
      POSTGRES_PASSWORD: analytics_secure_pass_456
    volumes:
      - postgres-analytics-data:/var/lib/postgresql/data
    networks:
      - cheapa-network
    healthcheck:
      test: ["CMD", "pg_isready", "-U", "cheapa_analytics_user", "-d", "cheapa_analytics"]
      interval: 10s
    deploy:
      resources:
        limits:
          memory: 1G       # Large plan
          cpus: '1.0'
    labels:
      - "com.superdeploy.addon=postgres"
      - "com.superdeploy.instance=analytics"
      - "com.superdeploy.plan=large"
  
  # =============================================================================
  # Addon: redis instances
  # =============================================================================
  redis-session:
    image: redis:7-alpine
    container_name: cheapa_redis_session
    restart: unless-stopped
    command: redis-server --maxmemory 256mb --maxmemory-policy allkeys-lru --requirepass session_redis_pass_def
    ports:
      - "6379:6379"
    volumes:
      - redis-session-data:/data
    networks:
      - cheapa-network
    healthcheck:
      test: ["CMD", "redis-cli", "--raw", "incr", "ping"]
      interval: 5s
    deploy:
      resources:
        limits:
          memory: 256M
          cpus: '0.25'
    labels:
      - "com.superdeploy.addon=redis"
      - "com.superdeploy.instance=session"
      - "com.superdeploy.plan=small"
  
  redis-products:
    image: redis:7-alpine
    container_name: cheapa_redis_products
    restart: unless-stopped
    command: redis-server --maxmemory 2gb --maxmemory-policy allkeys-lru --requirepass products_redis_pass_ghi
    ports:
      - "6380:6379"  # Different external port
    volumes:
      - redis-products-data:/data
    networks:
      - cheapa-network
    healthcheck:
      test: ["CMD", "redis-cli", "--raw", "incr", "ping"]
      interval: 5s
    deploy:
      resources:
        limits:
          memory: 2G       # Large plan
          cpus: '1.0'
    labels:
      - "com.superdeploy.addon=redis"
      - "com.superdeploy.instance=products"
      - "com.superdeploy.plan=large"
  
  # =============================================================================
  # Addon: rabbitmq instances
  # =============================================================================
  rabbitmq-main:
    image: rabbitmq:3.12-management-alpine
    container_name: cheapa_rabbitmq_main
    restart: unless-stopped
    ports:
      - "5672:5672"
      - "15672:15672"  # Management UI
    environment:
      RABBITMQ_DEFAULT_USER: cheapa_main_user
      RABBITMQ_DEFAULT_PASS: rabbitmq_main_pass_jkl
      RABBITMQ_DEFAULT_VHOST: /
    volumes:
      - rabbitmq-main-data:/var/lib/rabbitmq
    networks:
      - cheapa-network
    healthcheck:
      test: ["CMD", "rabbitmq-diagnostics", "ping"]
      interval: 10s
    deploy:
      resources:
        limits:
          memory: 512M
          cpus: '0.5'
    labels:
      - "com.superdeploy.addon=rabbitmq"
      - "com.superdeploy.instance=main"
      - "com.superdeploy.plan=standard"
  
  # =============================================================================
  # Applications
  # =============================================================================
  api:
    image: c100394/api:latest
    container_name: cheapa_api
    restart: unless-stopped
    ports:
      - "8000:8000"
    env_file:
      - /opt/superdeploy/projects/cheapa/data/api/.env
    volumes:
      - /opt/superdeploy/projects/cheapa/data/api:/app/data
      - /opt/superdeploy/projects/cheapa/logs/api:/app/logs
    networks:
      - cheapa-network
    depends_on:
      - postgres-primary
      - postgres-analytics
      - redis-session
      - rabbitmq-main
    labels:
      - "com.superdeploy.app=api"
  
  services:
    image: c100394/services:latest
    container_name: cheapa_services
    restart: unless-stopped
    env_file:
      - /opt/superdeploy/projects/cheapa/data/services/.env
    volumes:
      - /opt/superdeploy/projects/cheapa/data/services:/app/data
      - /opt/superdeploy/projects/cheapa/logs/services:/app/logs
    networks:
      - cheapa-network
    depends_on:
      - postgres-primary
      - rabbitmq-main
    labels:
      - "com.superdeploy.app=services"
  
  storefront:
    image: c100394/storefront:latest
    container_name: cheapa_storefront
    restart: unless-stopped
    ports:
      - "3000:3000"
    env_file:
      - /opt/superdeploy/projects/cheapa/data/storefront/.env
    volumes:
      - /opt/superdeploy/projects/cheapa/data/storefront:/app/data
      - /opt/superdeploy/projects/cheapa/logs/storefront:/app/logs
    networks:
      - cheapa-network
    depends_on:
      - postgres-primary
      - redis-products
    labels:
      - "com.superdeploy.app=storefront"

volumes:
  postgres-primary-data:
  postgres-analytics-data:
  redis-session-data:
  redis-products-data:
  rabbitmq-main-data:

networks:
  cheapa-network:
    external: true
```

---

## 🛠️ Implementation Plan

### Phase 1: Named Addon Instances (2-3 hours)

#### Step 1.1: Update Addon Metadata

```yaml
# addons/postgres/addon.yml
name: postgres
description: PostgreSQL relational database
category: database
multiple_instances: true  # ← NEW: Allow multiple instances

# Define resource plans
plans:
  small:
    memory: 256M
    cpu: 0.25
    disk: 5G
    max_connections: 50
    description: "For development/testing"
    
  standard:
    memory: 512M
    cpu: 0.5
    disk: 10G
    max_connections: 100
    description: "For production workloads"
    
  large:
    memory: 1G
    cpu: 1.0
    disk: 20G
    max_connections: 200
    description: "For high-traffic production"
    
  xlarge:
    memory: 2G
    cpu: 2.0
    disk: 50G
    max_connections: 500
    description: "For enterprise workloads"

# Environment variable template (uses {INSTANCE} placeholder)
env_template:
  - name: "{INSTANCE}_URL"
    description: "Full connection URL"
    format: "postgresql://{USER}:{PASSWORD}@{HOST}:{PORT}/{DATABASE}"
    
  - name: "{INSTANCE}_HOST"
    description: "PostgreSQL hostname"
    
  - name: "{INSTANCE}_PORT"
    description: "PostgreSQL port"
    
  - name: "{INSTANCE}_USER"
    description: "Database username"
    
  - name: "{INSTANCE}_PASSWORD"
    description: "Database password"
    secret: true
    
  - name: "{INSTANCE}_DATABASE"
    description: "Database name"

# Readonly connection (for read replicas / readonly access)
readonly_env_template:
  - name: "{INSTANCE}_READONLY_URL"
    format: "postgresql://{READONLY_USER}:{READONLY_PASSWORD}@{HOST}:{PORT}/{DATABASE}"
  - name: "{INSTANCE}_READONLY_USER"
  - name: "{INSTANCE}_READONLY_PASSWORD"
    secret: true

# Port allocation strategy
port_allocation:
  base_port: 5432
  increment: 1  # Second instance: 5433, Third: 5434

# Health check template
healthcheck:
  command: "pg_isready -U {USER} -d {DATABASE}"
  interval: 10s
  timeout: 5s
  retries: 5
  start_period: 30s
```

#### Step 1.2: Update Config Service

```python
# cli/services/config_service.py

from typing import Dict, List, Optional
from dataclasses import dataclass

@dataclass
class AddonInstance:
    """Represents a single addon instance."""
    category: str      # databases, caches, queues
    name: str          # primary, analytics, session
    type: str          # postgres, redis, rabbitmq
    version: str       # 15-alpine
    plan: str          # small, standard, large
    options: Dict      # Custom options
    
    @property
    def full_name(self) -> str:
        """Full instance name: category.name"""
        return f"{self.category}.{self.name}"
    
    @property
    def container_name(self, project: str) -> str:
        """Docker container name"""
        return f"{project}_{self.type}_{self.name}"


@dataclass
class AddonAttachment:
    """Represents an app → addon attachment."""
    addon: str         # databases.primary
    as_: str          # DATABASE (env var prefix)
    access: str       # readwrite, readonly
    
    @property
    def category(self) -> str:
        return self.addon.split('.')[0]
    
    @property
    def instance(self) -> str:
        return self.addon.split('.')[1]


class ConfigService:
    def parse_addons(self, config: Dict) -> List[AddonInstance]:
        """
        Parse addon instances from config.yml
        
        Input:
            addons:
              databases:
                primary:
                  type: postgres
                  plan: standard
        
        Output:
            [AddonInstance(category='databases', name='primary', type='postgres', ...)]
        """
        instances = []
        
        addons_config = config.get('addons', {})
        
        for category, category_instances in addons_config.items():
            for instance_name, instance_config in category_instances.items():
                instance = AddonInstance(
                    category=category,
                    name=instance_name,
                    type=instance_config['type'],
                    version=instance_config.get('version'),
                    plan=instance_config.get('plan', 'standard'),
                    options=instance_config.get('options', {})
                )
                instances.append(instance)
        
        return instances
    
    def parse_app_attachments(self, app_config: Dict) -> List[AddonAttachment]:
        """
        Parse app's addon attachments
        
        Input:
            addons:
              - addon: databases.primary
                as: DATABASE
                access: readwrite
        
        Output:
            [AddonAttachment(addon='databases.primary', as_='DATABASE', access='readwrite')]
        """
        attachments = []
        
        for attachment_config in app_config.get('addons', []):
            if isinstance(attachment_config, str):
                # Simple format: "databases.primary"
                addon = attachment_config
                as_ = self._default_prefix(addon)
                access = 'readwrite'
            else:
                # Full format with options
                addon = attachment_config['addon']
                as_ = attachment_config.get('as', self._default_prefix(addon))
                access = attachment_config.get('access', 'readwrite')
            
            attachment = AddonAttachment(
                addon=addon,
                as_=as_,
                access=access
            )
            attachments.append(attachment)
        
        return attachments
    
    def _default_prefix(self, addon: str) -> str:
        """
        Get default env var prefix from addon name
        
        databases.primary → DATABASE
        caches.session → CACHE
        queues.main → QUEUE
        """
        category = addon.split('.')[0]
        
        prefix_map = {
            'databases': 'DATABASE',
            'caches': 'CACHE',
            'queues': 'QUEUE',
            'search': 'SEARCH',
            'proxy': 'PROXY',
        }
        
        return prefix_map.get(category, category.upper())
```

#### Step 1.3: Port Allocation Service

> **Note (2025-11):** This service was removed as unused code during CLI refactoring. Port allocation is now handled differently in the actual implementation.

```python
# cli/services/port_allocator.py (REMOVED - Example code only)

from typing import Dict, List
import yaml
from pathlib import Path

class PortAllocator:
    """Manages port allocation for addon instances."""
    
    def __init__(self, project_name: str, state_file: Path):
        self.project_name = project_name
        self.state_file = state_file
        self.state = self._load_state()
    
    def _load_state(self) -> Dict:
        """Load port allocation state."""
        if self.state_file.exists():
            with open(self.state_file) as f:
                return yaml.safe_load(f) or {}
        return {}
    
    def _save_state(self):
        """Save port allocation state."""
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.state_file, 'w') as f:
            yaml.dump(self.state, f, default_flow_style=False)
    
    def allocate_port(self, addon_type: str, instance_name: str) -> int:
        """
        Allocate port for addon instance.
        
        Strategy:
        - postgres: 5432, 5433, 5434, ...
        - redis: 6379, 6380, 6381, ...
        - rabbitmq: 5672, 5673, 5674, ...
        """
        # Base ports for each addon type
        base_ports = {
            'postgres': 5432,
            'redis': 6379,
            'rabbitmq': 5672,
            'elasticsearch': 9200,
            'mongodb': 27017,
        }
        
        if addon_type not in base_ports:
            raise ValueError(f"Unknown addon type: {addon_type}")
        
        # Check if already allocated
        addon_key = f"{addon_type}.{instance_name}"
        if addon_key in self.state.get('ports', {}):
            return self.state['ports'][addon_key]
        
        # Find next available port
        base_port = base_ports[addon_type]
        allocated_ports = [
            port for key, port in self.state.get('ports', {}).items()
            if key.startswith(f"{addon_type}.")
        ]
        
        if not allocated_ports:
            new_port = base_port
        else:
            new_port = max(allocated_ports) + 1
        
        # Save allocation
        if 'ports' not in self.state:
            self.state['ports'] = {}
        self.state['ports'][addon_key] = new_port
        self._save_state()
        
        return new_port
    
    def get_allocated_ports(self, addon_type: str) -> Dict[str, int]:
        """Get all allocated ports for addon type."""
        return {
            instance: port
            for full_key, port in self.state.get('ports', {}).items()
            if full_key.startswith(f"{addon_type}.")
            for instance in [full_key.split('.')[1]]
        }
    
    def deallocate_port(self, addon_type: str, instance_name: str):
        """Deallocate port for removed addon instance."""
        addon_key = f"{addon_type}.{instance_name}"
        if 'ports' in self.state and addon_key in self.state['ports']:
            del self.state['ports'][addon_key]
            self._save_state()
```

---

### Phase 2: Environment Variable Generation (2 hours)

> **Note (2025-11):** This service was removed as unused code during CLI refactoring. Environment variable generation is handled differently in the actual implementation.

```python
# cli/services/env_generator.py (REMOVED - Example code only)

from typing import Dict, List
from cli.services.config_service import AddonInstance, AddonAttachment

class EnvGenerator:
    """Generates environment variables for app attachments."""
    
    def __init__(self, project_name: str):
        self.project_name = project_name
    
    def generate_addon_env_vars(
        self,
        instance: AddonInstance,
        attachment: AddonAttachment,
        credentials: Dict
    ) -> Dict[str, str]:
        """
        Generate environment variables for an addon attachment.
        
        Args:
            instance: AddonInstance (databases.primary)
            attachment: AddonAttachment (as DATABASE, readonly)
            credentials: Dict from secrets.yml
        
        Returns:
            Dict of env vars with attachment prefix
        """
        prefix = attachment.as_
        addon_type = instance.type
        
        # Base env vars (all addon types)
        env_vars = {
            f"{prefix}_HOST": credentials['HOST'],
            f"{prefix}_PORT": str(credentials['PORT']),
        }
        
        # Addon-specific env vars
        if addon_type == 'postgres':
            env_vars.update(self._postgres_env_vars(prefix, credentials, attachment.access))
        
        elif addon_type == 'redis':
            env_vars.update(self._redis_env_vars(prefix, credentials))
        
        elif addon_type == 'rabbitmq':
            env_vars.update(self._rabbitmq_env_vars(prefix, credentials))
        
        elif addon_type == 'elasticsearch':
            env_vars.update(self._elasticsearch_env_vars(prefix, credentials))
        
        return env_vars
    
    def _postgres_env_vars(self, prefix: str, creds: Dict, access: str) -> Dict:
        """Generate PostgreSQL environment variables."""
        if access == 'readonly':
            user = creds.get('READONLY_USER')
            password = creds.get('READONLY_PASSWORD')
            readonly_flag = 'true'
        else:
            user = creds['USER']
            password = creds['PASSWORD']
            readonly_flag = 'false'
        
        database = creds['DATABASE']
        host = creds['HOST']
        port = creds['PORT']
        
        return {
            f"{prefix}_USER": user,
            f"{prefix}_PASSWORD": password,
            f"{prefix}_DATABASE": database,
            f"{prefix}_NAME": database,  # Alias
            f"{prefix}_URL": f"postgresql://{user}:{password}@{host}:{port}/{database}",
            f"{prefix}_READONLY": readonly_flag,
            f"{prefix}_SSL": 'false',
            f"{prefix}_SSLMODE": 'disable',
        }
    
    def _redis_env_vars(self, prefix: str, creds: Dict) -> Dict:
        """Generate Redis environment variables."""
        host = creds['HOST']
        port = creds['PORT']
        password = creds.get('PASSWORD', '')
        
        if password:
            url = f"redis://default:{password}@{host}:{port}"
        else:
            url = f"redis://{host}:{port}"
        
        return {
            f"{prefix}_URL": url,
            f"{prefix}_PASSWORD": password,
        }
    
    def _rabbitmq_env_vars(self, prefix: str, creds: Dict) -> Dict:
        """Generate RabbitMQ environment variables."""
        host = creds['HOST']
        port = creds['PORT']
        user = creds['USER']
        password = creds['PASSWORD']
        vhost = creds.get('VHOST', '/')
        
        return {
            f"{prefix}_USER": user,
            f"{prefix}_USERNAME": user,  # Alias
            f"{prefix}_PASSWORD": password,
            f"{prefix}_VHOST": vhost,
            f"{prefix}_URL": f"amqp://{user}:{password}@{host}:{port}{vhost}",
        }
    
    def _elasticsearch_env_vars(self, prefix: str, creds: Dict) -> Dict:
        """Generate Elasticsearch environment variables."""
        host = creds['HOST']
        port = creds['PORT']
        user = creds.get('USER', 'elastic')
        password = creds.get('PASSWORD', '')
        
        return {
            f"{prefix}_USER": user,
            f"{prefix}_PASSWORD": password,
            f"{prefix}_URL": f"http://{host}:{port}",
        }
```

---

### Phase 3: CLI Commands (2 hours)

#### addons:list

```python
# cli/commands/addons.py

import click
from rich.table import Table
from cli.base import ProjectCommand

class AddonsListCommand(ProjectCommand):
    """List all addon instances for project."""
    
    def execute(self) -> None:
        self.show_header(
            title="Addons",
            project=self.project_name,
            subtitle="Managed addon instances"
        )
        
        # Load config
        config = self.config_service.get_raw_config(self.project_name)
        
        # Parse addon instances
        instances = self.config_service.parse_addons(config)
        
        if not instances:
            self.console.print("[yellow]No addons configured[/yellow]")
            return
        
        # Parse app attachments to show which apps use which addons
        apps_config = config.get('apps', {})
        attachment_map = {}  # addon.full_name → [app1, app2]
        
        for app_name, app_config in apps_config.items():
            attachments = self.config_service.parse_app_attachments(app_config)
            for attachment in attachments:
                if attachment.addon not in attachment_map:
                    attachment_map[attachment.addon] = []
                attachment_map[attachment.addon].append(app_name)
        
        # Create table
        table = Table(
            title=f"Addon Instances - {self.project_name}",
            show_header=True,
            header_style="bold cyan"
        )
        table.add_column("Name", style="cyan", no_wrap=True)
        table.add_column("Type", style="white")
        table.add_column("Version", style="dim")
        table.add_column("Plan", style="yellow")
        table.add_column("Status", style="green")
        table.add_column("Attached To", style="magenta")
        
        # Get status from Docker
        status_map = self._get_addon_status()
        
        for instance in sorted(instances, key=lambda x: (x.category, x.name)):
            full_name = instance.full_name
            attached_apps = ', '.join(attachment_map.get(full_name, ['-']))
            status = status_map.get(full_name, 'unknown')
            
            table.add_row(
                full_name,
                instance.type,
                instance.version,
                instance.plan,
                status,
                attached_apps
            )
        
        self.console.print(table)
        
        # Summary
        self.console.print(f"\n[dim]Total: {len(instances)} addon instances[/dim]")
    
    def _get_addon_status(self) -> Dict[str, str]:
        """Get status of addon containers from Docker."""
        # SSH to VM and check container status
        # Returns: {'databases.primary': 'healthy', 'caches.session': 'running'}
        pass


@click.command(name="addons:list")
@click.option("--verbose", "-v", is_flag=True)
def addons_list(project, verbose):
    """
    List all addon instances
    
    Examples:
        superdeploy cheapa:addons:list
        superdeploy cheapa:addons
    """
    cmd = AddonsListCommand(project, verbose=verbose)
    cmd.run()
```

#### addons:info

```python
class AddonsInfoCommand(ProjectCommand):
    """Show detailed info about addon instance."""
    
    def __init__(self, project_name: str, addon: str, verbose: bool = False):
        super().__init__(project_name, verbose=verbose)
        self.addon = addon  # e.g., "databases.primary"
    
    def execute(self) -> None:
        # Parse addon reference
        if '.' not in self.addon:
            self.console.print("[red]Invalid addon format. Use: category.name[/red]")
            self.console.print("[dim]Example: databases.primary[/dim]")
            return
        
        category, instance_name = self.addon.split('.', 1)
        
        # Load config
        config = self.config_service.get_raw_config(self.project_name)
        
        # Find instance
        instances = self.config_service.parse_addons(config)
        instance = next(
            (i for i in instances if i.category == category and i.name == instance_name),
            None
        )
        
        if not instance:
            self.console.print(f"[red]Addon not found: {self.addon}[/red]")
            return
        
        # Show header
        self.show_header(
            title=f"Addon Info: {self.addon}",
            project=self.project_name
        )
        
        # Basic info
        self.console.print("[bold]Basic Information[/bold]")
        self.console.print(f"  Name: {instance.full_name}")
        self.console.print(f"  Type: {instance.type}")
        self.console.print(f"  Version: {instance.version}")
        self.console.print(f"  Plan: {instance.plan}")
        
        # Credentials (from secrets.yml)
        secrets = self._load_secrets()
        addon_secrets = secrets.get('addons', {}).get(instance.type, {}).get(instance_name, {})
        
        if addon_secrets:
            self.console.print("\n[bold]Connection Details[/bold]")
            self.console.print(f"  Host: {addon_secrets.get('HOST')}")
            self.console.print(f"  Port: {addon_secrets.get('PORT')}")
            
            if instance.type == 'postgres':
                user = addon_secrets.get('USER')
                password = addon_secrets.get('PASSWORD')
                database = addon_secrets.get('DATABASE')
                host = addon_secrets.get('HOST')
                port = addon_secrets.get('PORT')
                
                # Masked password
                masked_password = password[:4] + '***' + password[-4:] if password else '***'
                
                self.console.print(f"  User: {user}")
                self.console.print(f"  Password: {masked_password}")
                self.console.print(f"  Database: {database}")
                self.console.print(f"\n  Connection URL:")
                self.console.print(f"    [dim]postgresql://{user}:{masked_password}@{host}:{port}/{database}[/dim]")
        
        # Attachments
        apps_config = config.get('apps', {})
        attachments = []
        
        for app_name, app_config in apps_config.items():
            app_attachments = self.config_service.parse_app_attachments(app_config)
            for attachment in app_attachments:
                if attachment.addon == self.addon:
                    attachments.append((app_name, attachment))
        
        if attachments:
            self.console.print("\n[bold]Attached To[/bold]")
            for app_name, attachment in attachments:
                self.console.print(f"  • {app_name}")
                self.console.print(f"      As: {attachment.as_}")
                self.console.print(f"      Access: {attachment.access}")
        else:
            self.console.print("\n[yellow]⚠️  Not attached to any apps[/yellow]")
        
        # Container status
        self.console.print("\n[bold]Container Status[/bold]")
        container_status = self._get_container_status(instance)
        self.console.print(f"  Status: {container_status}")


@click.command(name="addons:info")
@click.argument("addon")  # databases.primary
@click.option("--verbose", "-v", is_flag=True)
def addons_info(project, addon, verbose):
    """
    Show detailed information about an addon instance
    
    Examples:
        superdeploy cheapa:addons:info databases.primary
        superdeploy cheapa:addons:info caches.session
    """
    cmd = AddonsInfoCommand(project, addon, verbose=verbose)
    cmd.run()
```

#### addons:add

```python
class AddonsAddCommand(ProjectCommand):
    """Add a new addon instance."""
    
    def __init__(
        self,
        project_name: str,
        addon_type: str,
        name: str,
        plan: str = 'standard',
        category: str = None,
        verbose: bool = False
    ):
        super().__init__(project_name, verbose=verbose)
        self.addon_type = addon_type  # postgres, redis
        self.name = name              # primary, analytics
        self.plan = plan              # small, standard, large
        self.category = category      # databases (auto-detect if None)
    
    def execute(self) -> None:
        self.show_header(
            title=f"Add Addon: {self.addon_type}",
            project=self.project_name,
            details={"Name": self.name, "Plan": self.plan}
        )
        
        # Auto-detect category if not provided
        if not self.category:
            category_map = {
                'postgres': 'databases',
                'mysql': 'databases',
                'mongodb': 'databases',
                'redis': 'caches',
                'memcached': 'caches',
                'rabbitmq': 'queues',
                'elasticsearch': 'search',
                'caddy': 'proxy',
            }
            self.category = category_map.get(self.addon_type)
            
            if not self.category:
                self.console.print(f"[red]Unknown addon type: {self.addon_type}[/red]")
                self.console.print("[dim]Supported: postgres, redis, rabbitmq, elasticsearch[/dim]")
                return
        
        # Load addon metadata
        addon_metadata = self._load_addon_metadata(self.addon_type)
        if not addon_metadata:
            return
        
        # Validate plan
        plans = addon_metadata.get('plans', {})
        if self.plan not in plans:
            self.console.print(f"[red]Invalid plan: {self.plan}[/red]")
            self.console.print(f"[dim]Available plans: {', '.join(plans.keys())}[/dim]")
            return
        
        # 1. Update config.yml
        self._update_config()
        
        # 2. Generate credentials
        self._generate_credentials()
        
        # 3. Allocate port
        port = self._allocate_port()
        
        # 4. Generate compose
        self._generate_compose()
        
        # 5. Deploy
        self._deploy_addon()
        
        self.console.print(f"\n[green]✅ Addon added: {self.category}.{self.name}[/green]")
        self.console.print(f"\n[bold]Next steps:[/bold]")
        self.console.print(f"1. Attach to app:")
        self.console.print(f"   [cyan]superdeploy {self.project_name}:addons:attach {self.category}.{self.name} --app <app-name>[/cyan]")
        self.console.print(f"\n2. View connection details:")
        self.console.print(f"   [cyan]superdeploy {self.project_name}:addons:info {self.category}.{self.name}[/cyan]")


@click.command(name="addons:add")
@click.argument("addon_type")  # postgres, redis
@click.option("--name", "-n", required=True, help="Instance name (e.g., primary, analytics)")
@click.option("--plan", "-p", default="standard", help="Resource plan: small|standard|large")
@click.option("--category", "-c", help="Addon category (auto-detected if not provided)")
@click.option("--verbose", "-v", is_flag=True)
def addons_add(project, addon_type, name, plan, category, verbose):
    """
    Add a new addon instance
    
    Examples:
        # Add PostgreSQL database
        superdeploy cheapa:addons:add postgres --name analytics --plan large
        
        # Add Redis cache
        superdeploy cheapa:addons:add redis --name session --plan small
        
        # Add RabbitMQ queue
        superdeploy cheapa:addons:add rabbitmq --name priority --plan standard
    """
    cmd = AddonsAddCommand(project, addon_type, name, plan, category, verbose)
    cmd.run()
```

#### addons:attach

```python
@click.command(name="addons:attach")
@click.argument("addon")  # databases.primary
@click.option("--app", "-a", required=True, help="App name to attach to")
@click.option("--as", "as_", help="Environment variable prefix (e.g., DATABASE)")
@click.option("--access", default="readwrite", help="Access mode: readwrite|readonly")
@click.option("--verbose", "-v", is_flag=True)
def addons_attach(project, addon, app, as_, access, verbose):
    """
    Attach addon to an application
    
    Automatically generates environment variables for the app.
    
    Examples:
        # Attach primary database to API
        superdeploy cheapa:addons:attach databases.primary --app api
        
        # Attach analytics DB as ANALYTICS with readonly access
        superdeploy cheapa:addons:attach databases.analytics --app api --as ANALYTICS --access readonly
        
        # Attach session cache
        superdeploy cheapa:addons:attach caches.session --app api --as CACHE
    """
    # 1. Update config.yml (add attachment to app.addons)
    # 2. Regenerate app .env file with new env vars
    # 3. Restart app container
    pass
```

---

## 📝 Migration Guide

### Migrating Existing Projects

#### Before (Old System):

```yaml
# config.yml
addons:
  postgres:
    version: 15-alpine
  redis:
    version: 7-alpine

apps:
  api:
    path: /path/to/api
    port: 8000

# secrets.yml (manually edited)
secrets:
  shared:
    POSTGRES_HOST: 10.1.0.3
    POSTGRES_PORT: 5432
    POSTGRES_USER: cheapa_user
    POSTGRES_PASSWORD: xxx
    POSTGRES_DB: cheapa_db
    
    REDIS_HOST: 10.1.0.4
    REDIS_PORT: 6379
    REDIS_PASSWORD: yyy

env_aliases:
  api:
    DB_HOST: POSTGRES_HOST
    DB_PORT: POSTGRES_PORT
```

#### After (New System):

```yaml
# config.yml
addons:
  databases:
    primary:
      type: postgres
      version: 15-alpine
      plan: standard
  
  caches:
    main:
      type: redis
      version: 7-alpine
      plan: small

apps:
  api:
    path: /path/to/api
    port: 8000
    addons:
      - addon: databases.primary
        as: DB
      - addon: caches.main
        as: CACHE

# secrets.yml (AUTO-GENERATED - don't edit)
addons:
  postgres:
    primary:
      HOST: 10.1.0.3
      PORT: 5432
      USER: cheapa_user
      PASSWORD: xxx
      DATABASE: cheapa_db
  
  redis:
    main:
      HOST: 10.1.0.4
      PORT: 6379
      PASSWORD: yyy
```

#### Migration Steps:

```bash
# 1. Backup current config
cp config.yml config.yml.backup
cp secrets.yml secrets.yml.backup

# 2. Run migration command
superdeploy cheapa:migrate:addons

# This will:
# - Convert addons to named instances
# - Create attachment mappings
# - Regenerate secrets.yml
# - Update docker-compose.yml

# 3. Verify changes
superdeploy cheapa:addons:list

# 4. Test deployment
superdeploy cheapa:up --dry-run

# 5. Deploy
superdeploy cheapa:up
```

---

## 🎯 Benefits Summary

| Feature | Old System | New System |
|---------|------------|------------|
| Multiple DB Support | ❌ Impossible | ✅ Unlimited instances |
| Named Instances | ❌ No names | ✅ `databases.primary`, `databases.analytics` |
| Addon Visibility | ❌ Unknown usage | ✅ `addons:info` shows all attachments |
| Auto ENV Generation | ❌ Manual editing | ✅ Auto-generated on attachment |
| Resource Plans | ❌ One size fits all | ✅ Small/Standard/Large/XLarge |
| Port Management | ❌ Manual conflicts | ✅ Auto-allocated (5432, 5433, 5434...) |
| Addon → App Mapping | ❌ Implicit (env_aliases) | ✅ Explicit (app.addons) |
| Credentials | ❌ Hand-typed | ✅ Auto-generated secure passwords |
| Connection URLs | ❌ Build manually | ✅ Auto-generated (DATABASE_URL) |
| Readonly Access | ❌ Not supported | ✅ `access: readonly` with separate user |

---

## 🚀 Example Scenarios

### Scenario 1: E-commerce with Separate Databases

```yaml
addons:
  databases:
    products:
      type: postgres
      plan: large        # High-traffic product catalog
    
    orders:
      type: postgres
      plan: standard     # Order management
    
    analytics:
      type: postgres
      plan: xlarge       # Data warehouse for reporting
  
  caches:
    products:
      type: redis
      plan: large        # Product cache
    
    sessions:
      type: redis
      plan: small        # User sessions

apps:
  api:
    addons:
      - addon: databases.products
        as: PRODUCTS_DB
      - addon: databases.orders
        as: ORDERS_DB
      - addon: caches.products
        as: CACHE
  
  analytics_service:
    addons:
      - addon: databases.products
        as: PRODUCTS_DB
        access: readonly   # Read-only replica
      - addon: databases.orders
        as: ORDERS_DB
        access: readonly
      - addon: databases.analytics
        as: WAREHOUSE_DB
```

### Scenario 2: Microservices with Shared Resources

```yaml
addons:
  databases:
    shared:
      type: postgres
      plan: large
  
  queues:
    tasks:
      type: rabbitmq
      plan: standard
    
    notifications:
      type: rabbitmq
      plan: small

apps:
  user_service:
    addons:
      - databases.shared as DB
      - queues.tasks
  
  order_service:
    addons:
      - databases.shared as DB
      - queues.tasks
  
  notification_service:
    addons:
      - queues.notifications
```

---

## 📚 References

- Heroku Addons: https://devcenter.heroku.com/articles/managing-add-ons
- Heroku Addon Attachments: https://devcenter.heroku.com/articles/managing-add-on-attachments
- Railway Plugin System: https://docs.railway.app/reference/plugins
- Render.com Add-ons: https://render.com/docs/add-ons

---

## 📅 Timeline

- **Phase 1**: Named Addon Instances → 2-3 hours
- **Phase 2**: Environment Variable Generation → 2 hours
- **Phase 3**: CLI Commands → 2 hours
- **Phase 4**: Testing & Documentation → 2 hours

**Total Estimated Time**: 8-10 hours

---

## ✅ Next Steps

1. Review and approve this design
2. Start with Phase 1 (Named Instances)
3. Test with simple scenario (2 postgres DBs)
4. Expand to all addon types
5. Implement CLI commands
6. Write migration guide
7. Update all documentation

