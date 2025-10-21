# 📱 Per-App Setup Guide (For Each Application)

This guide shows how to configure **each application** (API, Dashboard, Services) for deployment.

You need to do this **once per application**.

---

## 📋 Overview

For each app, you'll:
1. Configure GitHub repository secrets
2. Set up GitHub Environment (production/staging)
3. Add environment-specific secrets
4. Test deployment

---

## 🔧 Step 1: Repository Secrets (GitHub)

Go to: `https://github.com/YOUR_ORG/YOUR_APP/settings/secrets/actions`

### Add Repository Secrets (same for all environments):

| Secret Name | Value | Where to Get |
|-------------|-------|--------------|
| `AGE_PUBLIC_KEY` | `age1xxxx...` | From Ansible deployment output |
| `FORGEJO_BASE_URL` | `http://CORE_IP:3001` | From `superdeploy/.env` |
| `FORGEJO_ORG` | `cradexco` | From `superdeploy/.env` |
| `FORGEJO_PAT` | `a8b552e...` | From `superdeploy/.env` (created earlier) |
| `DOCKER_USERNAME` | Your Docker Hub username | Docker Hub account |
| `DOCKER_TOKEN` | `dckr_pat_xxx...` | Docker Hub access token |
| `DOCKER_ORG` | Your Docker Hub org | Same as username (usually) |

**How to add:**
1. Click **"New repository secret"**
2. Enter **Name** and **Value**
3. Click **"Add secret"**

---

## 🌍 Step 2: Create GitHub Environment

Go to: `https://github.com/YOUR_ORG/YOUR_APP/settings/environments`

1. Click **"New environment"**
2. Name: **`production`**
3. Click **"Configure environment"**
4. (Optional) Add protection rules:
   - ✅ Required reviewers
   - ✅ Deployment branches: `production` only

Repeat for **`staging`** environment if needed.

---

## 🔐 Step 3: Environment Secrets (Production)

Go to: `https://github.com/YOUR_ORG/YOUR_APP/settings/environments`

Select **`production`** → **Environment secrets** → **Add secret**

### For API Service:

```bash
# Database
POSTGRES_HOST=postgres
POSTGRES_USER=superdeploy
POSTGRES_PASSWORD=SuperDBPass123!     # ✏️ Strong password
POSTGRES_DB=superdeploy_db
POSTGRES_PORT=5432

# Message Queue
RABBITMQ_HOST=rabbitmq
RABBITMQ_USER=superdeploy
RABBITMQ_PASSWORD=SuperQueuePass123!  # ✏️ Strong password
RABBITMQ_PORT=5672

# Cache
REDIS_HOST=redis
REDIS_PASSWORD=RedisPass123!          # ✏️ Strong password

# API Configuration
API_SECRET_KEY=your-32-char-secret-key-here-change-this
API_DEBUG=false
API_BASE_URL=http://CORE_IP:8000      # ✏️ Get from superdeploy/.env
PUBLIC_URL=http://CORE_IP             # ✏️ Get from superdeploy/.env

# Optional
SENTRY_DSN=                           # Leave empty for now
```

### For Dashboard Service:

```bash
# API Connection
DASHBOARD_API_URL=http://CORE_IP:8000       # ✏️ Get from superdeploy/.env
DASHBOARD_PUBLIC_URL=http://CORE_IP         # ✏️ Get from superdeploy/.env

# Optional
DASHBOARD_PORT=3000
NEXT_PUBLIC_API_URL=http://CORE_IP:8000     # For Next.js
```

### For Services (Background Workers):

```bash
# Database (same as API)
POSTGRES_HOST=postgres
POSTGRES_USER=superdeploy
POSTGRES_PASSWORD=SuperDBPass123!     # ✏️ Same as API
POSTGRES_DB=superdeploy_db

# Message Queue (same as API)
RABBITMQ_HOST=rabbitmq
RABBITMQ_USER=superdeploy
RABBITMQ_PASSWORD=SuperQueuePass123!  # ✏️ Same as API

# Worker Configuration
SERVICES_WORKER_COUNT=4
SERVICES_LOG_LEVEL=info

# Optional
SENTRY_DSN=
```

**Important:**
- ✅ Use **same passwords** for shared resources (DB, RabbitMQ, Redis)
- ✅ Different apps can have different `API_SECRET_KEY`
- ✅ `CORE_IP` = value of `CORE_EXTERNAL_IP` from `superdeploy/.env`

---

## 📝 Step 4: Verify Workflow File

Make sure your app has `.github/workflows/deploy.yml`:

```yaml
name: Build and Deploy

on:
  push:
    branches: [production]
  workflow_dispatch:

# ... (rest of workflow - should already exist in your app repo)
```

If missing, copy from:
```bash
cp ~/Desktop/cheapa.io/hero/app-repos/api/.github/workflows/deploy.yml \
   ~/YOUR_APP/.github/workflows/
```

---

## 🚀 Step 5: Create Production Branch

```bash
cd ~/YOUR_APP

# Create production branch
git checkout -b production

# Push to GitHub
git push origin production
```

---

## 🧪 Step 6: Test Deployment

```bash
# Make a small change
echo "# Test deployment" >> README.md
git add .
git commit -m "Test: trigger first deployment"
git push origin production
```

### Monitor Deployment:

1. **GitHub Actions:**
   ```
   https://github.com/YOUR_ORG/YOUR_APP/actions
   ```
   - ✅ Build & push Docker image
   - ✅ Encrypt environment variables
   - ✅ Trigger Forgejo deployment

2. **Forgejo Actions:**
   ```
   http://CORE_IP:3001/cradexco/superdeploy-app/actions
   ```
   - ✅ Decrypt environment
   - ✅ Pull images
   - ✅ Deploy services

3. **Logs (via CLI):**
   ```bash
   superdeploy logs -a api -f
   ```

---

## ✅ Verification

```bash
# Check service status
superdeploy status

# Check specific app
superdeploy info -a api

# Test API endpoint
curl http://CORE_IP:8000/health

# Run migrations (if needed)
superdeploy run api "python manage.py migrate"
```

**Expected:**
- ✅ GitHub Actions: All steps green
- ✅ Forgejo Actions: Deployment successful
- ✅ Service responding: `200 OK`

---

## 🔄 Staging Environment (Optional)

Repeat steps 2-6 for **`staging`** environment:

1. Create GitHub Environment: **`staging`**
2. Add staging-specific secrets (can use different passwords)
3. Create branch: `staging`
4. Push to trigger deployment

---

## 📊 Quick Reference

### Get CORE_IP:
```bash
cd ~/Desktop/superdeploy
grep CORE_EXTERNAL_IP .env | cut -d'=' -f2
```

### Get Forgejo PAT:
```bash
cd ~/Desktop/superdeploy
grep FORGEJO_PAT .env | cut -d'=' -f2
```

### Get AGE Public Key:
```bash
ssh -i ~/.ssh/superdeploy_gcp superdeploy@CORE_IP \
  "cat /opt/forgejo-runner/.age/public_key.txt"
```

---

## 🔧 Troubleshooting

### GitHub Actions stuck at "Trigger Forgejo"

**Check:**
```bash
# Is Forgejo reachable?
curl http://CORE_IP:3001/api/v1/version

# Is PAT valid?
curl -H "Authorization: token $FORGEJO_PAT" \
  http://CORE_IP:3001/api/v1/user
```

### Forgejo workflow fails to decrypt env

**Check:**
```bash
# Is AGE_PUBLIC_KEY correct?
ssh -i ~/.ssh/superdeploy_gcp superdeploy@CORE_IP \
  "cat /opt/forgejo-runner/.age/public_key.txt"

# Compare with GitHub secret
```

### Service won't start (missing env vars)

**Check:**
```bash
# View decrypted env (during deployment)
superdeploy logs -a api | grep "Loading decrypted"

# Run manually to test
superdeploy run api env | grep POSTGRES
```

---

## 🎉 Per-App Setup Complete!

You've configured:
- ✅ GitHub repository secrets
- ✅ GitHub Environment (production)
- ✅ Environment-specific secrets
- ✅ Successful test deployment

**Next:** Learn daily workflows → `DEPLOYMENT-GUIDE.md`

---

## 📚 Related Docs

- Initial setup: `SETUP-INITIAL.md`
- Daily workflows: `DEPLOYMENT-GUIDE.md`
- CLI reference: `CLI-REFERENCE.md`
- Production: `PRODUCTION-CHECKLIST.md`

