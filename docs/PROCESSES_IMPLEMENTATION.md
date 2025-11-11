# Process-Based Deployment (Heroku Procfile-like)

## 🎯 Overview

SuperDeploy now supports **Heroku Procfile-like process definitions** via the `.superdeploy` marker file. This allows a single codebase to define multiple processes (web, worker, release, etc.) without duplicating app entries in `config.yml`.

---

## 📝 Configuration Format

### **config.yml** - Process Definitions

```yaml
apps:
  api:
    type: python
    path: /path/to/api
    vm: app
    domain: api.cheapa.io
    addons:
      - databases.primary as DB
      - queues.main as RABBITMQ
    
    # Process definitions (Heroku Procfile-like)
    processes:
      web:
        command: gunicorn app:app --bind 0.0.0.0:$PORT --workers 4
        port: 8000
        replicas: 2
      
      worker:
        command: python craft queue:work --tries=3
        replicas: 5
      
      release:
        command: python craft migrate --force
        run_on: deploy  # Runs once on deployment
```

### **Generated .superdeploy Marker**

```yaml
# /path/to/api/.superdeploy (auto-generated)
project: cheapa
app: api
vm: app
managed_by: superdeploy
version: v3

# Process definitions as root-level keys (clean syntax)
web:
  command: gunicorn app:app --bind 0.0.0.0:$PORT --workers 4
  port: 8000
  replicas: 2

worker:
  command: python craft queue:work --tries=3
  replicas: 5

release:
  command: python craft migrate --force
  run_on: deploy
```

---

## 🚀 Usage

### 1. Define Processes in config.yml

```yaml
apps:
  myapp:
    type: python
    path: /path/to/myapp
    processes:
      web:
        command: gunicorn app:app
        port: 8000
        replicas: 2
      worker:
        command: celery worker
        replicas: 5
```

### 2. Generate Marker Files

```bash
superdeploy myproject:generate
```

**Output:**
```
myapp:
  Type: python (explicit)
  ✓ .superdeploy (2 processes)
  Secrets: 10
  ✓ .github/workflows/deploy.yml
```

### 3. Deploy Infrastructure

```bash
superdeploy myproject:up
```

---

## 🔧 Process Types

### **web** - HTTP Server
```yaml
web:
  command: gunicorn app:app --bind 0.0.0.0:$PORT
  port: 8000        # Required for web processes
  replicas: 2       # Optional, default: 1
```

- Exposes HTTP port
- Load balanced by Caddy
- Health checks enabled
- Zero-downtime deployments

### **worker** - Background Jobs
```yaml
worker:
  command: python craft queue:work
  replicas: 5       # Scale independently
```

- No port exposed
- Consumes from job queue
- Scaled independently
- No health checks (exit-based)

### **release** - Deployment Hooks
```yaml
release:
  command: python craft migrate --force
  run_on: deploy    # Runs once per deployment
```

- Runs before web/worker start
- Blocks deployment if fails
- Perfect for migrations
- No replicas (single execution)

### **cron** - Scheduled Tasks (Future)
```yaml
scheduler:
  command: python craft schedule:run
  schedule: "0 * * * *"  # Every hour
```

---

## 📊 Architecture

### **Before** (Duplicate Entries)

```yaml
apps:
  api:
    type: python
    process_type: web
    replicas: 2
    
  api-worker:  # Duplicate!
    type: python
    process_type: worker
    path: /same/path/as/api  # Same codebase!
    replicas: 5
```

**Problems:**
- ❌ Duplicate config for same codebase
- ❌ Hard to maintain
- ❌ Not Heroku-compatible

### **After** (Process-Based)

```yaml
apps:
  api:
    type: python
    path: /path/to/api
    processes:
      web: {command: "...", replicas: 2}
      worker: {command: "...", replicas: 5}
```

**Benefits:**
- ✅ Single app entry
- ✅ Heroku Procfile-like
- ✅ Easy to scale processes independently
- ✅ Clear separation of concerns

---

## 🔄 Scaling

### Scale All Processes
```bash
superdeploy myproject:scale myapp=5
# Scales all processes to 5 replicas
```

### Scale Specific Process
```bash
superdeploy myproject:scale myapp:web=3 myapp:worker=10
# web: 3 replicas, worker: 10 replicas
```

### View Current Scale
```bash
superdeploy myproject:ps
```

**Output:**
```
Process       Replicas  Status
──────────────────────────────
myapp:web     3/3       running
myapp:worker  10/10     running
```

---

## 🐳 Docker Compose Generation

### Auto-Generated Services

From this:
```yaml
processes:
  web: {command: "gunicorn...", port: 8000, replicas: 2}
  worker: {command: "celery...", replicas: 5}
```

SuperDeploy generates **separate Docker services** for each process:
```yaml
services:
  myapp-web:
    image: myorg/myapp:latest
    command: gunicorn app:app --bind 0.0.0.0:8000
    ports: ["8000:8000"]
    environment:
      - PROCESS_TYPE=web
    deploy:
      replicas: 2
      update_config:
        order: start-first  # Zero-downtime
        parallelism: 1
        failure_action: rollback
      restart_policy:
        condition: on-failure
  
  myapp-worker:
    image: myorg/myapp:latest
    command: celery worker
    environment:
      - PROCESS_TYPE=worker
    deploy:
      replicas: 5
      restart_policy:
        condition: on-failure
```

**Key Points:**
- ✅ Same Docker image, different commands
- ✅ Each process type = separate service
- ✅ Pattern: `app-process` (e.g., `api-web`, `api-worker`)
- ✅ Independent scaling per process
- ✅ Workflows deploy all processes for an app

---

## 🎨 Migration Path

### Step 1: Update config.yml

**Old Format:**
```yaml
apps:
  api:
    type: web  # Wrong!
    replicas: 1
    port: 8000
```

**New Format:**
```yaml
apps:
  api:
    type: python  # App technology
    processes:
      web:
        command: gunicorn app:app
        port: 8000
        replicas: 1
```

### Step 2: Regenerate

```bash
superdeploy myproject:generate
```

This creates/updates `.superdeploy` with processes.

### Step 3: Deploy

```bash
superdeploy myproject:up
```

Docker Compose will be generated with multiple services.

---

## 🔮 Future Enhancements

### 1. External Procfile Support

```yaml
apps:
  myapp:
    type: python
    path: /path/to/myapp
    procfile: true  # Use app/Procfile instead of config.yml
```

```procfile
# /path/to/myapp/Procfile (Heroku-compatible)
web: gunicorn app:app
worker: celery worker
release: python manage.py migrate
```

### 2. Process-Level Resources

```yaml
processes:
  web:
    command: gunicorn...
    resources:
      memory: 512M
      cpu: 0.5
  
  worker:
    command: celery...
    resources:
      memory: 2G  # More memory for workers
      cpu: 1.0
```

### 3. Process Dependencies

```yaml
processes:
  web:
    command: gunicorn...
    depends_on: [release]  # Wait for migrations
  
  worker:
    command: celery...
    depends_on: [web]  # Start after web is healthy
```

---

## 📚 Examples

### Python App

```yaml
api:
  type: python
  path: ~/code/api
  processes:
    web:
      command: gunicorn app:app --bind 0.0.0.0:$PORT --workers 4
      port: 8000
      replicas: 2
    
    worker:
      command: python craft queue:work --tries=3
      replicas: 5
    
    release:
      command: python craft migrate --force
      run_on: deploy
```

### Next.js App

```yaml
storefront:
  type: nextjs
  path: ~/code/storefront
  processes:
    web:
      command: npm run start
      port: 3000
      replicas: 1
```

### Microservices Architecture

```yaml
user-service:
  type: python
  path: ~/services/users
  processes:
    web: {command: "uvicorn main:app", port: 8001, replicas: 3}
    worker: {command: "celery -A tasks worker", replicas: 2}

order-service:
  type: python
  path: ~/services/orders
  processes:
    web: {command: "uvicorn main:app", port: 8002, replicas: 3}
    worker: {command: "celery -A tasks worker", replicas: 5}
```

---

## ✅ Benefits Summary

| Feature | Old System | New System |
|---------|------------|------------|
| **Multiple Processes** | ❌ Duplicate apps | ✅ Single app with processes |
| **Process Commands** | ❌ Hardcoded | ✅ Configurable |
| **Scaling** | ❌ App-level only | ✅ Process-level granular |
| **Heroku-Compatible** | ❌ No | ✅ Yes (Procfile-like) |
| **Maintenance** | ❌ Complex | ✅ Simple |
| **Migration Hooks** | ❌ Manual | ✅ Built-in (release process) |

---

## 🔧 Implementation Status

### ✅ Completed (v3)
- [x] AppMarker v3 with root-level process keys (clean syntax)
- [x] ProcessDefinition with command, port, replicas
- [x] MarkerManager.create_marker() generates v3 markers
- [x] Config.yml process definitions
- [x] Generate command parses and writes processes
- [x] Docker Compose generation with process-based services (app-process pattern)
- [x] GitHub Actions workflows with multi-process deployment
- [x] Pattern-based service detection (`api-*`, `services-*`)
- [x] Deployment hooks with process-aware service selection

### 🚧 Next Phase
- [ ] Scale command with process-level granularity (`app:web=3 app:worker=10`)
- [ ] PS command shows all processes (`api-web`, `api-worker`)
- [ ] Process-level health checks and status

### 🔮 Future Enhancements
- [ ] External Procfile support (app/Procfile)
- [ ] Process-level resource limits
- [ ] Process dependencies (depends_on)
- [ ] Cron/scheduled processes
- [ ] Release process orchestration (runs before web/worker)

---

**Status:** v3 Complete ✅  
**Date:** 2025-11-11  
**Version:** v3.0  
**Breaking Changes:** Yes - removed backward compatibility, v3-only format

