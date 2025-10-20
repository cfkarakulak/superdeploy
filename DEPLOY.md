# Deployment Guide

## Quick Commands

```bash
# Single service
make deploy-service SERVICE=api TAG=abc123 ENV=prod

# All services
make deploy-all API_TAG=abc DASH_TAG=def SVC_TAG=ghi ENV=prod

# Rollback
make rollback SERVICE=api TAG=previous-sha ENV=prod

# Database migration
make migrate-db ENV=prod

# Staging
make deploy-service SERVICE=api TAG=test ENV=staging
```

---

## Manual Deployment (API Calls)

### Get Forgejo API Token

```bash
# From .env
source superdeploy/.env
echo $FORGEJO_PAT
```

### Trigger Deploy Workflow

```bash
FORGEJO_URL="http://$CORE_EXTERNAL_IP:3001"
ORG="yourorg"
REPO="superdeploy-app"

# Single service
curl -X POST \
  -H "Authorization: token $FORGEJO_PAT" \
  -H "Content-Type: application/json" \
  "$FORGEJO_URL/api/v1/repos/$ORG/$REPO/actions/workflows/deploy.yml/dispatches" \
  -d '{
    "ref": "master",
    "inputs": {
      "environment": "prod",
      "services": "api",
      "image_tags": "{\"api\":\"abc123\"}",
      "migrate": "false"
    }
  }'

# All services
curl -X POST \
  -H "Authorization: token $FORGEJO_PAT" \
  -H "Content-Type: application/json" \
  "$FORGEJO_URL/api/v1/repos/$ORG/$REPO/actions/workflows/deploy.yml/dispatches" \
  -d '{
    "ref": "master",
    "inputs": {
      "environment": "prod",
      "services": "api,dashboard,services",
      "image_tags": "{\"api\":\"abc123\",\"dashboard\":\"def456\",\"services\":\"ghi789\"}",
      "migrate": "false"
    }
  }'
```

---

## GitHub Actions Trigger

**Automatic** (on push to `production` branch):

```yaml
# app-repos/api/.github/workflows/deploy.yml
on:
  push:
    branches: [production]
```

**Manual** (GitHub UI):
1. Actions → Build and Deploy API → Run workflow
2. Select branch: `production`
3. Run

---

## Deployment Flow

```
1. GitHub Actions Build
   - docker build
   - docker tag org/service:SHA
   - docker push
   - curl Forgejo API

2. Forgejo Workflow Start
   - git pull superdeploy code
   - Generate .env from secrets
   - Prepare compose files

3. Migration (if migrate=true)
   - docker compose run api alembic upgrade head
   - Verify: alembic current
   - Timeout: 10 min
   - On fail: STOP deployment

4. Selective Pull
   - python scripts/partial_pull.py
   - Pull only changed services

5. Selective Deploy
   - python scripts/partial_up.py
   - docker compose up -d --no-deps SERVICE
   - No restart of dependencies

6. Health Checks
   - 12 retries, 5s interval
   - Timeout: 60s
   - curl http://localhost:8000/healthz

7. Notification
   - Email to ALERT_EMAIL
   - Status: SUCCESS/FAILED
   - Image tags, timestamp
```

---

## Rollback

### Option 1: Makefile

```bash
# Find previous SHA
docker inspect superdeploy-api | jq -r '.Config.Labels["com.superdeploy.image.tag"]'

# Rollback
make rollback SERVICE=api TAG=def456 ENV=prod
```

### Option 2: Manual Docker

```bash
ssh superdeploy@VM_IP

cd /opt/superdeploy/compose
export API_IMAGE_TAG=def456  # Previous SHA
docker compose -f docker-compose.core.yml -f docker-compose.apps.yml pull api
docker compose -f docker-compose.core.yml -f docker-compose.apps.yml up -d api

# Verify
docker ps | grep api
docker logs -f superdeploy-api
```

### Option 3: Forgejo UI

1. http://VM_IP:3001/org/superdeploy-app/actions
2. Re-run previous successful workflow
3. Or trigger new with old SHA

**Time: ~30 seconds** (pull + restart)

---

## Multi-Environment

### Production

**Branch:** `production`

```bash
git checkout production
git push origin production
```

Compose: `core.yml + apps.yml`

### Staging

**Branch:** `staging`

```bash
git checkout staging
git push origin staging
```

Compose: `core.yml + apps.yml + apps.staging.yml`

**Differences:**
- Ports: 8001 (API), 3001 (Dashboard)
- Image tags: `-staging` suffix
- Separate secrets

---

## Database Migrations

### Automatic (with deployment)

```bash
make deploy-service SERVICE=api TAG=abc123 ENV=prod MIGRATE=true

# Or API call
curl -X POST ... -d '{"inputs": {"migrate": "true"}}'
```

### Manual

```bash
ssh superdeploy@VM_IP

cd /opt/superdeploy/compose
docker compose -f docker-compose.core.yml -f docker-compose.apps.yml \
  run --rm api alembic upgrade head

# Verify
docker compose run --rm api alembic current

# Rollback migration
docker compose run --rm api alembic downgrade -1
```

---

## Selective Deployment

**Only changed service:**

```bash
# Scenario: API code changed, Dashboard unchanged
make deploy-service SERVICE=api TAG=new-sha ENV=prod

# Result:
# - API restarted with new image
# - Dashboard unchanged
# - PostgreSQL unchanged
# - Zero downtime for Dashboard
```

**Multiple services:**

```bash
make deploy-all API_TAG=sha1 DASH_TAG=sha2 SVC_TAG=latest ENV=prod
```

---

## Health Checks

**Built into workflow:**

```yaml
- name: Wait for health
  run: |
    for i in {1..12}; do
      if curl -f http://localhost:8000/healthz; then
        echo "✅ Healthy"
        exit 0
      fi
      sleep 5
    done
    echo "❌ Health check failed"
    exit 1
```

**Manual check:**

```bash
curl -f http://VM_IP:8000/healthz
curl -f http://VM_IP/healthz  # Dashboard
```

---

## Logs

```bash
# Real-time
ssh superdeploy@VM_IP "docker logs -f superdeploy-api"

# Last 100 lines
ssh superdeploy@VM_IP "docker logs --tail 100 superdeploy-api"

# All services
ssh superdeploy@VM_IP "cd /opt/superdeploy/compose && docker compose logs -f"

# Specific time range
ssh superdeploy@VM_IP "docker logs --since 30m superdeploy-api"
```

---

## Monitoring Deployment

**Forgejo Actions UI:**
```
http://VM_IP:3001/org/superdeploy-app/actions
```

**Prometheus:**
```bash
# Container restarts
curl -s http://VM_IP:9090/api/v1/query?query=rate(container_restarts_total[5m])

# API health
curl -s http://VM_IP:9090/api/v1/query?query=up{job="api"}
```

**Grafana:**
```
http://VM_IP:3002
Dashboard: Docker Container Metrics
```

---

## Common Issues

### Image not found

```bash
# Check Docker Hub
docker pull docker.io/org/api:abc123

# Check credentials
ssh superdeploy@VM_IP "docker login"
```

### Health check timeout

```bash
# Check service status
ssh superdeploy@VM_IP "docker ps | grep api"

# Check logs for errors
ssh superdeploy@VM_IP "docker logs superdeploy-api"

# Increase retries (workflow edit)
```

### Migration failed

```bash
# Check DB connection
ssh superdeploy@VM_IP "docker exec superdeploy-postgres psql -U superdeploy -c '\l'"

# Manual migration
ssh superdeploy@VM_IP
cd /opt/superdeploy/compose
docker compose run --rm api alembic upgrade head

# Rollback if needed
docker compose run --rm api alembic downgrade -1
```

### Secrets not loaded

Verify in Forgejo UI:
```
http://VM_IP:3001/org/superdeploy-app/settings/actions/secrets
```

Must have:
- POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_DB
- RABBITMQ_USER, RABBITMQ_PASSWORD
- API_SECRET_KEY

---

## Performance

**Typical deployment times:**

| Operation | Time |
|-----------|------|
| Pull image (new) | 10-30s |
| Pull image (cached layers) | 2-5s |
| Container restart | 5-10s |
| Health check wait | 15-60s |
| **Total (single service)** | **30-90s** |
| **Total (all services)** | **2-3 min** |

**Rollback: ~30 seconds**

---

## Blue-Green (Future)

**Not implemented yet**, but architecture supports:

```yaml
# docker-compose.blue-green.yml
api-blue:
  image: org/api:abc123
  ports: ["8000:8000"]

api-green:
  image: org/api:def456
  ports: ["8001:8000"]

# Caddy switches upstream
api.domain.com → api-green:8000
```

Switch via env var: `ACTIVE_ENV=green`

