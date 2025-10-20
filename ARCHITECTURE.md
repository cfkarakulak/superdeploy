# 🏗️ SuperDeploy - Advanced Multi-Repo CI/CD Architecture

## 📋 Overview

**Production-ready** image-based deployment system with **independent service repositories**, **version control**, and **instant rollback**.

```
Service Repo (api/storefront/services)
    ↓ push code
    ↓ CI builds Docker image
    ↓ pushes to registry (tag: version/sha)
    ↓ triggers superdeploy-app workflow
    ↓
superdeploy-app (this repo)
    ↓ receives image tag
    ↓ updates docker-compose
    ↓ pulls new image
    ↓ deploys to target VM
    ↓
    ✅ Service updated!
```

---

## 🎯 Core Principles

1. **Service Isolation**: Each service has its own repo
2. **Immutable Images**: Built once, deployed everywhere
3. **Version Control**: Every deployment is tagged and traceable
4. **Atomic Updates**: Only changed services are redeployed
5. **Instant Rollback**: Redeploy previous tag in seconds

---

## 📦 Repository Structure

### Service Repositories (Independent)

```
cheapa-api/              # API service
├── Dockerfile          # How to build
├── src/                # Application code
└── .forgejo/
    └── workflows/
        └── ci.yml      # Build → Push → Trigger Deploy

cheapa-storefront/       # Frontend/Dashboard
├── Dockerfile
├── src/
└── .forgejo/workflows/ci.yml

cheapa-services/         # Background workers
├── Dockerfile
├── src/
└── .forgejo/workflows/ci.yml
```

### superdeploy-app (Orchestration)

```
superdeploy-app/         # THIS REPO
├── deploy/compose/
│   ├── vm1-core/
│   │   ├── docker-compose.yml    # Uses registry images
│   │   └── .env.versions         # Current versions
│   ├── vm2-scrape/
│   └── vm3-proxy/
└── .forgejo/workflows/
    ├── deploy-core.yml           # API + Storefront
    ├── deploy-scrape.yml         # Workers
    └── deploy-proxy.yml          # Proxies
```

---

## 🔧 Image Registry

### Registry Options

1. **Docker Hub**: `docker.io/cheapa/api:v1.0.0`
2. **GHCR**: `ghcr.io/cheapa/api:v1.0.0`
3. **Private Registry**: `registry.cheapa.io/api:v1.0.0`
4. **Forgejo Registry**: `forgejo:3000/cheapa/api:v1.0.0` (built-in!)

### Image Naming Convention

```
<registry>/<org>/<service>:<tag>

Examples:
  docker.io/cheapa/api:v1.2.3
  docker.io/cheapa/api:abc123d
  docker.io/cheapa/storefront:v2.0.0
  docker.io/cheapa/worker:latest
```

---

## 🔄 Deployment Flow

### 1. Service Repository CI (Build & Trigger)

```yaml
# cheapa-api/.forgejo/workflows/ci.yml

name: Build & Deploy API

on:
  push:
    branches: [main, master]
    tags: ['v*']

jobs:
  build-and-deploy:
    runs-on: self-hosted
    steps:
      - name: Checkout
        run: git clone $REPO .
      
      - name: Generate tag
        run: |
          if [ "${{ github.ref_type }}" = "tag" ]; then
            echo "TAG=${{ github.ref_name }}" >> $GITHUB_ENV
          else
            echo "TAG=$(git rev-parse --short HEAD)" >> $GITHUB_ENV
          fi
      
      - name: Build image
        run: |
          docker build -t cheapa/api:${{ env.TAG }} .
          docker tag cheapa/api:${{ env.TAG }} cheapa/api:latest
      
      - name: Push to registry
        run: |
          docker push cheapa/api:${{ env.TAG }}
          docker push cheapa/api:latest
      
      - name: Trigger deployment
        run: |
          curl -X POST \
            -H "Authorization: Bearer ${{ secrets.FORGEJO_PAT }}" \
            -H "Content-Type: application/json" \
            http://forgejo:3001/api/v1/repos/cheapa/superdeploy-app/actions/workflows/deploy-core.yml/dispatches \
            -d '{
              "ref": "master",
              "inputs": {
                "api_image_tag": "${{ env.TAG }}",
                "dashboard_image_tag": ""
              }
            }'
```

### 2. superdeploy-app Workflow (Pull & Deploy)

```yaml
# superdeploy-app/.forgejo/workflows/deploy-core.yml

name: Deploy CORE VM

on:
  workflow_dispatch:
    inputs:
      api_image_tag:
        description: 'API image tag (leave empty to skip)'
        required: false
      dashboard_image_tag:
        description: 'Dashboard image tag (leave empty to skip)'
        required: false

jobs:
  deploy:
    runs-on: self-hosted
    steps:
      - name: Update versions file
        run: |
          if [ -n "${{ inputs.api_image_tag }}" ]; then
            sed -i "s/^API_IMAGE_TAG=.*/API_IMAGE_TAG=${{ inputs.api_image_tag }}/" \
              deploy/compose/vm1-core/.env.versions
          fi
          if [ -n "${{ inputs.dashboard_image_tag }}" ]; then
            sed -i "s/^DASHBOARD_IMAGE_TAG=.*/DASHBOARD_IMAGE_TAG=${{ inputs.dashboard_image_tag }}/" \
              deploy/compose/vm1-core/.env.versions
          fi
      
      - name: Deploy to CORE VM
        run: |
          ssh superdeploy@$CORE_IP << 'EOF'
            cd /opt/superdeploy/deploy/compose/vm1-core
            docker compose pull
            docker compose up -d
            docker image prune -f
          EOF
      
      - name: Health check
        run: |
          sleep 5
          curl -f http://$CORE_IP:8000/health || exit 1
```

---

## 🎨 docker-compose.yml Changes

### Before (build locally):
```yaml
services:
  api:
    build: ./api
    image: superdeploy-api:local
```

### After (use registry):
```yaml
services:
  api:
    image: cheapa/api:${API_IMAGE_TAG:-latest}
    pull_policy: always
    restart: unless-stopped
    environment:
      - DATABASE_URL=${DATABASE_URL}
```

---

## 🔑 Secrets Management

### Service Repository Secrets

```
DOCKER_USERNAME       # Registry login
DOCKER_PASSWORD       # Registry token
FORGEJO_PAT          # To trigger superdeploy-app workflows
```

### superdeploy-app Secrets

```
POSTGRES_PASSWORD
RABBITMQ_PASSWORD
API_SECRET_KEY
... (all runtime secrets)
```

**Rule**: Service repos only have **build & trigger** secrets, not runtime secrets!

---

## 📊 Version Tracking

### .env.versions file

```env
# deploy/compose/vm1-core/.env.versions
API_IMAGE_TAG=abc123d
DASHBOARD_IMAGE_TAG=v1.2.3
PROXY_REGISTRY_IMAGE_TAG=v1.0.0

# Last deployed
LAST_DEPLOY_DATE=2025-10-20T16:30:00Z
LAST_DEPLOY_BY=workflow
```

### Rollback Process

```bash
# 1. Check history
git log deploy/compose/vm1-core/.env.versions

# 2. Find previous working version
API_IMAGE_TAG=xyz789  # previous commit

# 3. Trigger deploy with old tag
curl -X POST ... -d '{"inputs": {"api_image_tag": "xyz789"}}'

# ✅ Instant rollback in ~30 seconds!
```

---

## 🚀 Migration Plan

### Phase 1: Setup Registry ✅

- [ ] Choose registry (Docker Hub recommended)
- [ ] Create organization: `cheapa`
- [ ] Setup authentication tokens

### Phase 2: Prepare superdeploy-app ✅

- [ ] Add `.env.versions` files
- [ ] Update docker-compose files to use registry images
- [ ] Modify deploy workflows to accept image tags
- [ ] Add version tracking

### Phase 3: Create Service Repos ✅

- [ ] Extract `api/` → `cheapa-api` repo
- [ ] Extract `dashboard/` → `cheapa-storefront` repo
- [ ] Extract `worker/` → `cheapa-services` repo
- [ ] Add CI workflows to each

### Phase 4: Test & Verify ✅

- [ ] Build image from service repo
- [ ] Trigger deployment workflow
- [ ] Verify service updates correctly
- [ ] Test rollback procedure

### Phase 5: Production ✅

- [ ] Deploy all services
- [ ] Monitor for issues
- [ ] Document for team

---

## 💡 Benefits

### Development

- ✅ **Independent Teams**: Each service team works independently
- ✅ **Fast Feedback**: CI runs only for changed service
- ✅ **Easy Testing**: Pull any version locally

### Operations

- ✅ **Atomic Deployments**: Only changed services redeploy
- ✅ **Instant Rollback**: 30-second rollback to any version
- ✅ **Version History**: Complete audit trail
- ✅ **Blue-Green**: Deploy new version alongside old

### Security

- ✅ **Image Scanning**: Scan once in CI
- ✅ **Signed Images**: Verify image authenticity
- ✅ **Secret Isolation**: Service repos don't see runtime secrets

---

## 📝 Workflow Examples

### Deploy Specific Service

```bash
# Deploy only API
curl -X POST .../deploy-core.yml/dispatches \
  -d '{"inputs": {"api_image_tag": "v1.2.3"}}'

# Deploy only Dashboard
curl -X POST .../deploy-core.yml/dispatches \
  -d '{"inputs": {"dashboard_image_tag": "v2.0.0"}}'

# Deploy both
curl -X POST .../deploy-core.yml/dispatches \
  -d '{"inputs": {"api_image_tag": "v1.2.3", "dashboard_image_tag": "v2.0.0"}}'
```

### Rollback

```bash
# Rollback API to previous version
curl -X POST .../deploy-core.yml/dispatches \
  -d '{"inputs": {"api_image_tag": "abc123"}}'
```

---

## 🎯 Next Steps

1. **Choose Registry**: Docker Hub or Forgejo built-in?
2. **Create PAT**: Forgejo settings → Applications → New Token
3. **Update Workflows**: Implement new architecture
4. **Test Cycle**: Build → Deploy → Rollback
5. **Go Live**: Migrate real services

---

**🚀 Ready to build production-grade CI/CD!**

