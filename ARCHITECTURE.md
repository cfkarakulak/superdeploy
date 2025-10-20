# Architecture

## System Overview

**GitHub** → Build Docker images  
**Forgejo** → Self-hosted CI/CD runner (deployment only)  
**Core VM** → PostgreSQL, RabbitMQ, API, Dashboard, Services, Caddy

## Flow Diagram

```
Developer
   │
   │ git push production
   ▼
GitHub Repo (api/dashboard/services)
   │
   │ GitHub Actions
   │ - Build Docker image
   │ - Tag: SHA (abc123)
   │ - Push to Docker Hub
   │ - HTTP POST to Forgejo API
   ▼
Forgejo (http://VM_IP:3001)
   │
   │ Actions Runner (self-hosted on Core VM)
   │ - Read secrets from Forgejo UI
   │ - Generate .env files
   │ - docker compose pull (selective)
   │ - docker compose up -d (selective)
   │ - Health checks
   │ - Email notification
   ▼
Production (Core VM)
   ├── PostgreSQL (localhost:5432)
   ├── RabbitMQ (localhost:5672)
   ├── API (docker.io/org/api:abc123)
   ├── Dashboard (docker.io/org/dashboard:def456)
   └── Services (docker.io/org/services:ghi789)
```

## Component Responsibilities

### GitHub
- Source code hosting
- Code review & collaboration
- Docker image build
- Registry push (Docker Hub)
- Trigger Forgejo deployment

### Forgejo
- Self-hosted Git (backup only)
- Actions Runner orchestration
- Secrets management (runtime ENV)
- Selective service deployment
- Health checks & notifications

### Terraform
- GCP VMs provisioning
- Network & firewall setup
- Remote state (GCS bucket)

### Ansible
- System packages installation
- Security hardening (UFW, Fail2Ban, SSH)
- Docker installation
- Forgejo + runner setup
- Backup cron jobs

### Docker Compose
**Modular structure:**
- `docker-compose.core.yml` - PostgreSQL, RabbitMQ, Caddy, Forgejo
- `docker-compose.apps.yml` - API, Dashboard, Services
- `docker-compose.apps.staging.yml` - Staging overrides
- `docker-compose.monitoring.yml` - Prometheus, Grafana, Loki, Alertmanager

### Caddy
- Reverse proxy (api/forgejo/app subdomains)
- Auto HTTPS (Let's Encrypt)
- Security headers (HSTS, CSP, nosniff)
- HTTP→HTTPS redirect

## Network Architecture

```
Internet
   │
   ├─→ :80/:443 → Caddy
   │              │
   │              ├─→ api.domain.com → API:8000
   │              ├─→ forgejo.domain.com → Forgejo:3001
   │              └─→ app.domain.com → Dashboard:3000
   │
   └─→ :22 → SSH (UFW rate-limited)

Internal (127.0.0.1 only):
   ├─→ PostgreSQL:5432
   ├─→ RabbitMQ:5672
   └─→ RabbitMQ Management:15672 (UFW blocked from internet)
```

## Security Layers

1. **Network**: UFW firewall, internal-only services
2. **TLS**: Caddy + Let's Encrypt auto
3. **SSH**: Key-only, no root, Fail2Ban
4. **Containers**: Healthchecks, graceful shutdown
5. **Secrets**: Encrypted (GitHub Secrets + Forgejo Secrets)

## Deployment Pipeline

```
1. Code Push (production branch)
   ↓
2. GitHub Actions Build
   - docker build
   - docker push org/service:SHA
   - curl Forgejo API
   ↓
3. Forgejo Workflow Dispatch
   - Read input: {"api":"SHA"}
   - Generate .env from secrets
   ↓
4. Selective Pull
   - python scripts/partial_pull.py "api" '{"api":"SHA"}' "prod"
   ↓
5. Selective Deploy
   - python scripts/partial_up.py "api" "prod"
   - docker compose up -d --no-deps api
   ↓
6. Health Checks
   - Wait 60s, 12 retries
   - curl http://localhost:8000/healthz
   ↓
7. Notification
   - Email: ALERT_EMAIL
   - Status: SUCCESS/FAILED
```

## Rollback Strategy

**SHA-based (deterministic):**
```bash
# Find previous SHA
docker inspect superdeploy-api | jq '.Config.Labels["com.superdeploy.image.tag"]'

# Rollback
make rollback SERVICE=api TAG=previous-sha ENV=prod

# Time: ~30 seconds (pull + restart)
```

## Multi-Environment

**Production:**
- Branch: `production`
- Compose: `core.yml + apps.yml`
- Domain: `api.yourdomain.com`

**Staging:**
- Branch: `staging`
- Compose: `core.yml + apps.yml + apps.staging.yml`
- Domain: `staging.api.yourdomain.com`
- Ports: 8001, 3001 (different from prod)

## Monitoring Flow

```
Services
   │
   │ Metrics (Prometheus format)
   ▼
Prometheus (:9090)
   │
   │ Scrape every 15s
   │ - cAdvisor (containers)
   │ - PostgreSQL
   │ - RabbitMQ
   │ - API /metrics
   ▼
Alertmanager (:9093)
   │
   │ Rules: alerts.yml
   │ - ServiceDown (2 min)
   │ - HighCPU (>80%, 5 min)
   │ - DiskSpace (<15%)
   ▼
Email (ALERT_EMAIL)
```

## Backup Strategy

**PostgreSQL:**
- Daily: 02:00 UTC
- Retention: 7 days local
- Method: `pg_dump`
- GCS: Optional offsite

**Forgejo:**
- Daily: 03:00 UTC
- Retention: 7 days local
- Method: `forgejo dump` (repos + DB)
- GCS: Optional offsite

**Terraform State:**
- GCS backend
- Versioning: 30 versions
- Lifecycle: Auto-delete old versions

## Why Hybrid SCM?

**GitHub:**
- Public collaboration
- Code review
- Issue tracking
- GitHub Actions (free build minutes)

**Forgejo:**
- Self-hosted runner (secrets stay on VM)
- No internet egress for credentials
- Deployment isolation
- Free CI/CD runner

