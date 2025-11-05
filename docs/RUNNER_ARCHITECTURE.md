# Forgejo Runner Architecture

## Overview

SuperDeploy implements a **hybrid runner architecture** that supports multiple projects with a single Forgejo instance while maintaining proper isolation and flexibility.

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│  Orchestrator VM (Fixed)                                        │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │  Forgejo Server                                           │  │
│  │  - Git repositories (all projects)                        │  │
│  │  - CI/CD workflows                                        │  │
│  │  - Runner management                                      │  │
│  └───────────────────────────────────────────────────────────┘  │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │  Orchestrator Runner                                      │  │
│  │  Name: orchestrator-runner                                │  │
│  │  Labels: [orchestrator, linux, docker, ubuntu-latest]    │  │
│  │  Purpose: Infrastructure tasks, multi-project workflows   │  │
│  └───────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                            │
                            │ Manages
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│  Project: cheapa                                                │
│  ┌─────────────────────┐  ┌─────────────────────┐              │
│  │  VM: web            │  │  VM: api            │              │
│  │  ┌───────────────┐  │  │  ┌───────────────┐  │              │
│  │  │  Runner       │  │  │  │  Runner       │  │              │
│  │  │  cheapa-web-0 │  │  │  │  cheapa-api-0 │  │              │
│  │  │  Labels:      │  │  │  │  Labels:      │  │              │
│  │  │  - cheapa     │  │  │  │  - cheapa     │  │              │
│  │  │  - web        │  │  │  │  - api        │  │              │
│  │  │  - linux      │  │  │  │  - linux      │  │              │
│  │  │  - docker     │  │  │  │  - docker     │  │              │
│  │  └───────────────┘  │  │  └───────────────┘  │              │
│  └─────────────────────┘  └─────────────────────┘              │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│  Project: myapp                                                 │
│  ┌─────────────────────┐  ┌─────────────────────┐              │
│  │  VM: app            │  │  VM: worker         │              │
│  │  ┌───────────────┐  │  │  ┌───────────────┐  │              │
│  │  │  Runner       │  │  │  │  Runner       │  │              │
│  │  │  myapp-app-0  │  │  │  │  myapp-work-0 │  │              │
│  │  │  Labels:      │  │  │  │  Labels:      │  │              │
│  │  │  - myapp      │  │  │  │  - myapp      │  │              │
│  │  │  - app        │  │  │  │  - worker     │  │              │
│  │  │  - linux      │  │  │  │  - linux      │  │              │
│  │  │  - docker     │  │  │  │  - docker     │  │              │
│  │  └───────────────┘  │  │  └───────────────┘  │              │
│  └─────────────────────┘  └─────────────────────┘              │
└─────────────────────────────────────────────────────────────────┘
```

## Runner Types

### 1. Orchestrator Runner

**Purpose:** Handles infrastructure-level tasks and workflows that need to run on the Forgejo VM.

**Characteristics:**
- **Fixed name:** `orchestrator-runner`
- **Location:** Orchestrator VM (where Forgejo runs)
- **Labels:** `[self-hosted, orchestrator, linux, docker, ubuntu-latest]`
- **Scope:** Multi-project (serves all projects)
- **Use cases:**
  - Infrastructure provisioning
  - Cross-project workflows
  - Forgejo maintenance tasks
  - Backup operations

**Configuration:**
```yaml
# Deployed by: addons/forgejo/tasks/setup-runner.yml
Name: orchestrator-runner
Labels: 
  - ubuntu-latest:docker://node:20-bookworm
  - orchestrator:docker://node:20-bookworm
  - linux:docker://node:20-bookworm
  - docker:docker://node:20-bookworm
```

### 2. Project-Specific Runners

**Purpose:** Handles project-specific deployments on their respective VMs.

**Characteristics:**
- **Dynamic name:** `{project}-{vm_role}-{hostname}`
- **Location:** Each project VM (web, api, worker, etc.)
- **Labels:** `[self-hosted, {project}, {vm_role}, linux, docker, ubuntu-latest]`
- **Scope:** Project-specific (isolated per project)
- **Use cases:**
  - Application deployments
  - Service restarts
  - Database migrations
  - Project-specific tasks

**Configuration:**
```yaml
# Deployed by: roles/system/forgejo-runner/tasks/main.yml
Name: {hostname} (e.g., cheapa-core-0)
Labels:
  - self-hosted:docker://node:20-bookworm
  - project-runner:docker://node:20-bookworm
  - ubuntu-latest:docker://node:20-bookworm
  - {project}:docker://node:20-bookworm
  - {vm_role}:docker://node:20-bookworm
  - linux:docker://node:20-bookworm
  - docker:docker://node:20-bookworm

Note: All labels use the same Docker executor (node:20-bookworm) for consistency
```

## Label Strategy

### Standard Labels (All Runners)

- `ubuntu-latest` - Compatibility with GitHub Actions syntax
- `linux` - OS identifier  
- `docker` - Indicates Docker support
- `self-hosted` - Indicates self-hosted runner
- `project-runner` - Indicates project-specific runner (not on orchestrator runners)

**Important:** All labels use the format `label:docker://node:20-bookworm` to ensure:
- Consistent execution environment across all runners
- Node.js 20 availability for deployment scripts
- Debian bookworm base for compatibility

### Custom Labels

#### Orchestrator Runner
- `orchestrator` - Identifies the fixed infrastructure runner

#### Project Runners
- `{project}` - Project name (e.g., `cheapa`, `myapp`)
- `{vm_role}` - VM role (e.g., `web`, `api`, `worker`)

## Workflow Usage

### Target Project VMs (Most Common)

```yaml
# .forgejo/workflows/deploy.yml
jobs:
  deploy:
    # Runs on ANY runner with the project label
    runs-on: [self-hosted, cheapa]
```

This will run on any VM in the `cheapa` project (web, api, worker, etc.).

### Target Specific VM Role

```yaml
jobs:
  deploy-api:
    # Runs specifically on the API VM
    runs-on: [self-hosted, cheapa, api]
  
  deploy-web:
    # Runs specifically on the web VM
    runs-on: [self-hosted, cheapa, web]
```

### Target Orchestrator

```yaml
jobs:
  infrastructure:
    # Runs on the Forgejo VM itself
    runs-on: [self-hosted, orchestrator]
```

Use this for:
- Infrastructure provisioning
- Forgejo configuration
- Cross-project operations

### Multi-Project Workflows

```yaml
jobs:
  deploy-cheapa:
    runs-on: [self-hosted, cheapa]
    steps:
      - name: Deploy cheapa
        run: echo "Deploying cheapa"
  
  deploy-myapp:
    runs-on: [self-hosted, myapp]
    steps:
      - name: Deploy myapp
        run: echo "Deploying myapp"
```

## Runner Registration

### Orchestrator Runner

**When:** During Forgejo addon deployment  
**Where:** `addons/forgejo/tasks/setup-runner.yml`  
**How:**

```bash
forgejo-runner register \
  --no-interactive \
  --instance "http://forgejo:3000" \
  --token "REGISTRATION_TOKEN" \
  --name "orchestrator-runner" \
  --labels "ubuntu-latest:docker://node:20-bookworm,orchestrator:docker://node:20-bookworm,linux:docker://node:20-bookworm,docker:docker://node:20-bookworm,self-hosted:docker://node:20-bookworm"
```

**Note:** Self-hosted label is now explicitly added for consistency.

### Project Runners

**When:** During VM provisioning (`superdeploy up`)  
**Where:** `roles/system/forgejo-runner/tasks/main.yml`  
**How:**

```bash
forgejo-runner register \
  --no-interactive \
  --instance "http://ORCHESTRATOR_IP:3001" \
  --token "REGISTRATION_TOKEN" \
  --name "HOSTNAME" \
  --labels "self-hosted:docker://node:20-bookworm,project-runner:docker://node:20-bookworm,ubuntu-latest:docker://node:20-bookworm,{project}:docker://node:20-bookworm,{vm_role}:docker://node:20-bookworm,linux:docker://node:20-bookworm,docker:docker://node:20-bookworm"
```

**Key Points:**
- Token is generated on orchestrator VM via `docker exec orchestrator-forgejo forgejo actions generate-runner-token`
- Registration happens from project VM but connects to orchestrator Forgejo instance
- All labels use Docker executor for consistent environment
- Label format: `label:docker://node:20-bookworm`

**Troubleshooting Token Generation:**

If runner registration fails with "token not available":

```bash
  --instance "http://ORCHESTRATOR_IP:3001" \
  --token "REGISTRATION_TOKEN" \
  --name "cheapa-web-cheapa-web-0" \
  --labels "ubuntu-latest:docker://node:20-bookworm,cheapa:docker://node:20-bookworm,web:docker://node:20-bookworm,linux:docker://node:20-bookworm,docker:docker://node:20-bookworm"
```

## Configuration Files

### Orchestrator Runner Service

**Location:** `/etc/systemd/system/forgejo-runner.service`  
**Working Directory:** `/var/lib/superdeploy/{project}/addons/forgejo/runner`  
**User:** `superdeploy`

```ini
[Unit]
Description=Forgejo Actions Runner
After=docker.service
Requires=docker.service

[Service]
Type=simple
User=superdeploy
WorkingDirectory=/var/lib/superdeploy/{project}/addons/forgejo/runner
ExecStart=/usr/local/bin/forgejo-runner daemon
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### Project Runner Service

**Location:** `/etc/systemd/system/forgejo-runner.service`  
**Working Directory:** `/opt/forgejo-runner`  
**User:** `superdeploy`

```ini
[Unit]
Description=Forgejo Actions Runner
After=docker.service network-online.target
Wants=network-online.target
Requires=docker.service

[Service]
Type=simple
User=superdeploy
WorkingDirectory=/opt/forgejo-runner
ExecStart=/usr/local/bin/forgejo-runner daemon
Restart=always
RestartSec=10
Environment="HOME=/opt/forgejo-runner"

[Install]
WantedBy=multi-user.target
```

## Example: cheapa Project

### project.yml

```yaml
project: cheapa

vms:
  web:
    count: 1
    machine_type: e2-small
    services: []
  
  api:
    count: 1
    machine_type: e2-small
    services: []
  
  worker:
    count: 2
    machine_type: e2-medium
    services: []
```

### Runners Created

1. **Orchestrator Runner** (on Forgejo VM)
   - Name: `orchestrator-runner`
   - Labels: `[orchestrator, linux, docker, ubuntu-latest]`

2. **Web Runner** (on web-0 VM)
   - Name: `cheapa-web-cheapa-web-0`
   - Labels: `[cheapa, web, linux, docker, ubuntu-latest]`

3. **API Runner** (on api-0 VM)
   - Name: `cheapa-api-cheapa-api-0`
   - Labels: `[cheapa, api, linux, docker, ubuntu-latest]`

4. **Worker Runners** (on worker-0 and worker-1 VMs)
   - Name: `cheapa-worker-cheapa-worker-0`
   - Labels: `[cheapa, worker, linux, docker, ubuntu-latest]`
   - Name: `cheapa-worker-cheapa-worker-1`
   - Labels: `[cheapa, worker, linux, docker, ubuntu-latest]`

### Workflow Examples

```yaml
# Deploy API to api VM
name: Deploy API
on: [push]
jobs:
  deploy:
    runs-on: [self-hosted, cheapa, api]
    steps:
      - name: Deploy
        run: docker compose up -d api

# Deploy web to web VM
name: Deploy Web
on: [push]
jobs:
  deploy:
    runs-on: [self-hosted, cheapa, web]
    steps:
      - name: Deploy
        run: docker compose up -d web

# Run worker tasks on any worker VM
name: Process Jobs
on: [push]
jobs:
  process:
    runs-on: [self-hosted, cheapa, worker]
    steps:
      - name: Process
        run: python process_jobs.py

# Infrastructure task on orchestrator
name: Backup
on: [schedule]
jobs:
  backup:
    runs-on: [self-hosted, orchestrator]
    steps:
      - name: Backup databases
        run: ./backup.sh
```

## Troubleshooting

### Check Runner Status

```bash
# On orchestrator VM
sudo systemctl status forgejo-runner

# On project VMs
sudo systemctl status forgejo-runner
```

### View Runner Logs

```bash
# On orchestrator VM
sudo journalctl -u forgejo-runner -f

# On project VMs
sudo journalctl -u forgejo-runner -f
```

### List Registered Runners

```bash
# Via Forgejo CLI (on orchestrator VM)
docker exec -u 1000:1000 {project}-forgejo forgejo actions list-runners

# Via Forgejo Web UI
http://ORCHESTRATOR_IP:3001/admin/actions/runners
```

### Re-register Runner

```bash
# Stop service
sudo systemctl stop forgejo-runner

# Remove registration
rm -f /opt/forgejo-runner/.runner

# Re-run Ansible
superdeploy up -p {project} --tags runner

# Or manually register
cd /opt/forgejo-runner
forgejo-runner register \
  --no-interactive \
  --instance "http://ORCHESTRATOR_IP:3001" \
  --token "TOKEN" \
  --name "PROJECT-ROLE-HOSTNAME" \
  --labels "ubuntu-latest:docker://node:20-bookworm,PROJECT:docker://node:20-bookworm,ROLE:docker://node:20-bookworm"

# Start service
sudo systemctl start forgejo-runner
```

### Runner Not Picking Up Jobs

**Check labels match:**
```yaml
# Workflow
runs-on: [self-hosted, cheapa]

# Runner must have label: cheapa
```

**Check runner is online:**
```bash
# Via Forgejo Web UI
http://ORCHESTRATOR_IP:3001/admin/actions/runners

# Should show "Online" status
```

**Check runner logs:**
```bash
sudo journalctl -u forgejo-runner -f
```

## Security Considerations

### AGE Encryption

Each runner has its own AGE key pair for secret decryption:

**Orchestrator Runner:**
- Private key: `/opt/forgejo-runner/.age/key.txt`
- Public key: Stored in GitHub Secrets as `AGE_PUBLIC_KEY`

**Project Runners:**
- Private key: `/opt/forgejo-runner/.age/key.txt`
- Public key: Stored in GitHub Secrets as `AGE_PUBLIC_KEY_{PROJECT}_{VM_ROLE}`

### Docker Socket Access

Runners have access to Docker socket for container management:
- User `superdeploy` is in `docker` group
- Can start/stop containers
- Can pull images
- Can execute commands in containers

### Network Access

**Orchestrator Runner:**
- Can access Forgejo container directly
- Can access all project VMs (for orchestration)

**Project Runners:**
- Can access Forgejo via external IP
- Can access other VMs in same project (via internal network)
- Cannot access other projects' VMs

## Best Practices

### 1. Use Project Labels for Isolation

```yaml
# ✅ Good - Isolated to project
runs-on: [self-hosted, cheapa]

# ❌ Bad - Could run on any project
runs-on: [self-hosted]
```

### 2. Use VM Role Labels for Targeting

```yaml
# ✅ Good - Runs on specific VM type
runs-on: [self-hosted, cheapa, api]

# ⚠️  OK - Runs on any VM in project
runs-on: [self-hosted, cheapa]
```

### 3. Use Orchestrator for Infrastructure

```yaml
# ✅ Good - Infrastructure task
jobs:
  provision:
    runs-on: [self-hosted, orchestrator]

# ❌ Bad - Should not run on project VM
jobs:
  provision:
    runs-on: [self-hosted, cheapa]
```

### 4. Keep Runner Names Descriptive

```bash
# ✅ Good
cheapa-api-cheapa-api-0

# ❌ Bad
runner-1
```

### 5. Monitor Runner Health

```bash
# Add to monitoring
systemctl status forgejo-runner
journalctl -u forgejo-runner --since "1 hour ago"
```

## Migration Guide

### From Old Architecture

**Old (Hardcoded):**
```yaml
runs-on: ubuntu-latest  # Runs on GitHub
```

**New (Self-Hosted):**
```yaml
runs-on: [self-hosted, cheapa]  # Runs on project VM
```

### Update Workflows

1. Replace `runs-on: ubuntu-latest` with `runs-on: [self-hosted, {project}]`
2. Add project-specific labels
3. Test workflow execution
4. Monitor runner logs

## See Also

- [Forgejo Actions Documentation](https://forgejo.org/docs/latest/user/actions/)
- [SuperDeploy Architecture](./ARCHITECTURE.md)
- [Orchestrator Setup](./ORCHESTRATOR_SETUP.md)
- [Operations Guide](./OPERATIONS.md)
- [Setup Guide](./SETUP.md)
