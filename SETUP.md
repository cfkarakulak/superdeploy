# 🚀 SuperDeploy - Complete Setup Guide

**Production-ready multi-repository deployment system with automatic CI/CD**

---

## 📦 What Is This?

A deployment system with **4 independent repositories**:

```
cheapa-api/         → Your API code (FastAPI)
cheapa-storefront/  → Your frontend code (Node.js)
cheapa-services/    → Your background services
superdeploy/        → THIS REPO (deployment config)
```

**Magic:** Push to any service repo → Automatically builds & deploys in 60 seconds!

---

## 🎯 Quick Start (Complete Setup)

### Step 1: Initial Configuration (2 minutes)

```bash
cd superdeploy/

# Copy environment template
cp ENV.example .env

# Edit ONLY these values:
nano .env
```

**Required changes in `.env`:**
```bash
# Line 23: Your GCP project
GCP_PROJECT_ID=your-project-id-here

# Lines 44-54: Change ALL passwords (use: openssl rand -base64 32)
FORGEJO_ADMIN_PASSWORD=YourStrongPassword123
POSTGRES_PASSWORD=YourPostgresPassword456
RABBITMQ_DEFAULT_PASS=YourRabbitPassword789
# ... etc (change all CHANGE_ME_* values)
```

### Step 2: Deploy Everything (5 minutes)

```bash
make deploy
```

**This single command:**
- ✅ Creates 3 VMs on Google Cloud
- ✅ Installs Docker, PostgreSQL, RabbitMQ
- ✅ Sets up Forgejo Git server + CI/CD runner
- ✅ Creates 4 repositories (superdeploy-app + 3 service repos)
- ✅ Pushes all code automatically
- ✅ Everything ready to use!

**That's it! ⏱️ Total time: ~7 minutes**

---

## 🌐 Access Your System

After deployment completes:

| Service | URL | Credentials |
|---------|-----|-------------|
| **Forgejo** (Git + CI/CD) | http://34.56.43.99:3001 | cradexco / (your password) |
| **API** | http://34.56.43.99:8000 | - |
| **Storefront** | http://34.56.43.99:8001 | - |
| **Services** | http://34.56.43.99:8080 | - |

*(IPs shown are examples - check your `.env` for actual IPs)*

---

## 🔄 Daily Workflow: How to Deploy Changes

### Scenario 1: Update API

```bash
# 1. Go to your local cheapa-api repo
cd ../cheapa-api/

# 2. Make changes
nano app.py

# 3. Commit and push
git add -A
git commit -m "feat: add new endpoint"
git push

# 4. Done! Watch it deploy automatically:
# http://34.56.43.99:3001/cradexco/cheapa-api/actions
```

**What happens automatically:**
1. Forgejo CI builds Docker image
2. Tags it with commit SHA
3. Triggers deployment workflow
4. Updates running service
5. ⏱️ Total: ~60 seconds

### Scenario 2: Update Storefront

```bash
cd ../cheapa-storefront/
nano public/index.html
git add -A && git commit -m "ui: update homepage" && git push
# 🎉 Auto-deployed!
```

### Scenario 3: Update Services

```bash
cd ../cheapa-services/
nano app.py
git add -A && git commit -m "fix: improve logic" && git push
# 🎉 Auto-deployed!
```

---

## 📊 Repository Structure

```
hero/
├── superdeploy/              # Deployment orchestration (THIS REPO)
│   ├── .env                  # 🔐 MAIN CONFIG (all IPs, passwords)
│   ├── ENV.example           # Template
│   ├── Makefile              # Commands (deploy, destroy, etc.)
│   ├── SETUP.md              # This file
│   ├── deploy/compose/
│   │   ├── vm1-core/
│   │   │   ├── docker-compose.yml    # Core services
│   │   │   └── Caddyfile             # Reverse proxy config
│   │   ├── vm2-scrape/
│   │   └── vm3-proxy/
│   ├── .forgejo/workflows/
│   │   └── deploy-core-v2.yml        # Deployment workflow
│   └── scripts/
│       └── rollback.sh               # Rollback tool
│
├── superdeploy-infra/        # Infrastructure code (Terraform + Ansible)
│   ├── main.tf               # GCP resources
│   ├── terraform-wrapper.sh # Auto-generates tfvars from .env
│   └── ansible/
│       └── playbooks/
│           └── site.yml      # System setup
│
├── cheapa-api/               # API service repo
│   ├── app.py
│   ├── Dockerfile
│   └── .forgejo/workflows/
│       └── ci.yml            # Auto-build & deploy
│
├── cheapa-storefront/        # Frontend repo
│   ├── server.js
│   ├── Dockerfile
│   └── .forgejo/workflows/
│       └── ci.yml
│
└── cheapa-services/          # Background services repo
    ├── app.py
    ├── Dockerfile
    └── .forgejo/workflows/
        └── ci.yml
```

---

## 🛠️ Available Commands

```bash
cd superdeploy/

make deploy         # Full deployment (Terraform + Ansible + Git push)
make update-ips     # Extract new IPs after VM restart
make test           # Test all services
make destroy        # Delete all infrastructure (asks confirmation)
make clean          # Clean temporary files
```

---

## 🔧 Configuration Management

### Single Source of Truth: `.env`

**Everything** is controlled by `superdeploy/.env`:
- VM IPs
- Database passwords
- Service ports
- Docker image versions
- Everything!

**When VMs restart and IPs change:**
```bash
cd superdeploy/
make update-ips     # Extracts new IPs from Terraform
git add .env && git commit -m "config: update IPs" && git push
# Services automatically redeploy with new config!
```

---

## 🧪 Testing & Monitoring

### Check Service Status
```bash
ssh superdeploy@34.56.43.99
cd /opt/superdeploy/deploy/compose/vm1-core
docker compose ps                    # All services
docker compose logs -f api           # API logs
docker compose logs -f dashboard     # Storefront logs
```

### View CI/CD Status
- http://34.56.43.99:3001/cradexco/cheapa-api/actions
- http://34.56.43.99:3001/cradexco/cheapa-storefront/actions
- http://34.56.43.99:3001/cradexco/cheapa-services/actions
- http://34.56.43.99:3001/cradexco/superdeploy-app/actions

### Health Checks
```bash
curl http://34.56.43.99:8000/health    # API
curl http://34.56.43.99:8001           # Storefront
curl http://34.56.43.99:8080/health    # Services
```

---

## 🔄 Rollback

If a deployment breaks something:

```bash
cd superdeploy/

# Rollback API to previous version
./scripts/rollback.sh core api abc123

# Rollback Storefront
./scripts/rollback.sh core dashboard xyz789

# Find previous version tags in git history or Forgejo UI
```

---

## 🆘 Troubleshooting

### "make deploy fails"
```bash
# Check .env is configured
cat .env | grep CHANGE_ME
# Should return nothing (all CHANGE_ME_* replaced)

# Verify GCP credentials
gcloud auth list
```

### "Service won't start after push"
```bash
# Check CI logs
# http://34.56.43.99:3001/cradexco/cheapa-api/actions

# Check service logs on VM
ssh superdeploy@34.56.43.99
cd /opt/superdeploy/deploy/compose/vm1-core
docker compose logs api

# Restart service
docker compose restart api
```

### "CI workflow stuck"
```bash
# Restart Forgejo runner
ssh superdeploy@34.56.43.99
sudo systemctl restart forgejo-runner
sudo systemctl status forgejo-runner
```

### "Can't access Forgejo"
```bash
# Check if Forgejo is running
ssh superdeploy@34.56.43.99
cd /opt/forgejo
docker compose ps

# Restart Forgejo
docker compose restart forgejo
```

---

## 🔐 Security Notes

- ✅ `.env` contains passwords - **NEVER commit to public repos**
- ✅ Change all default passwords in `.env`
- ✅ Use strong passwords (32+ chars): `openssl rand -base64 32`
- ✅ Firewall rules auto-configured by Terraform
- ✅ SSH key-based authentication only

---

## 📝 What Each VM Does

### VM1 - CORE (e2-medium, 20GB)
- PostgreSQL database
- RabbitMQ message queue
- API service
- Storefront (dashboard)
- Background services (proxy registry)
- Caddy reverse proxy
- Forgejo Git + CI/CD runner

### VM2 - SCRAPE (e2-standard-4, 100GB)
- Future: Scraping workers with Playwright

### VM3 - PROXY (e2-small, 20GB)
- Future: SOCKS5 and HTTP proxies

---

## 🎓 Understanding the Flow

### First-Time Deployment
```
make deploy
  ↓
Terraform creates VMs
  ↓
Ansible installs software (Docker, Forgejo, etc.)
  ↓
Ansible sets up Forgejo runner
  ↓
Git pushes superdeploy code to Forgejo
  ↓
✅ System ready!
```

### Daily Development
```
Edit cheapa-api/app.py
  ↓
git push to Forgejo
  ↓
Forgejo CI workflow triggers (.forgejo/workflows/ci.yml)
  ↓
Docker builds new image (tagged with commit SHA)
  ↓
CI calls superdeploy-app deploy workflow
  ↓
Deploy workflow pulls new image
  ↓
docker compose up -d (rolling update)
  ↓
✅ API updated! (old version still ran during deploy)
```

---

## 🚨 Starting from Scratch

If you deleted all VMs:

```bash
cd superdeploy/

# Make sure .env is configured
cat .env | head -30

# Deploy everything again
make deploy

# That's it! Takes ~7 minutes
```

---

## 💡 Tips & Best Practices

1. **Always use `.env` for config** - Never hardcode IPs or passwords
2. **Commit .env to superdeploy repo** - It's needed for CI/CD
3. **Tag releases** - Use git tags for versioning: `git tag v1.2.3`
4. **Monitor CI/CD** - Watch Forgejo Actions UI for deployment status
5. **Test locally first** - Use `docker compose` locally before pushing
6. **Small commits** - Easier to rollback if needed
7. **Check logs** - Always check `docker compose logs` if something fails

---

## 📚 Advanced Topics

### Adding a New Service

1. Create new repo in Forgejo
2. Add `.forgejo/workflows/ci.yml` (copy from existing service)
3. Add service to `deploy/compose/vm1-core/docker-compose.yml`
4. Update CI workflow to trigger deployment
5. Push and watch it deploy!

### Using External Docker Registry

Edit service CI workflows:
```yaml
env:
  REGISTRY: ghcr.io  # or docker.io
  ORG: yourorg
```

Add registry credentials to Forgejo secrets.

### Scaling Workers

Edit `superdeploy-infra/envs/dev/gcp.auto.tfvars`:
```hcl
vm_counts = {
  core   = 1
  scrape = 3  # Scale to 3 workers
  proxy  = 2
}
```

Run: `cd superdeploy-infra && terraform apply`

---

## ✅ Checklist: Ready to Deploy?

- [ ] GCP project created
- [ ] `gcloud auth login` done
- [ ] SSH key generated: `~/.ssh/cfk_gcp`
- [ ] `superdeploy/.env` configured (all CHANGE_ME_* replaced)
- [ ] Passwords are strong (32+ chars)
- [ ] GCP_PROJECT_ID set correctly

**If all checked:**
```bash
cd superdeploy/
make deploy
```

**Watch the magic happen! 🎉**

---

## 🎯 Summary

**What you have:**
- ✅ Production-ready infrastructure
- ✅ Automatic CI/CD for all services
- ✅ 4 independent repositories
- ✅ One-command deployment
- ✅ Instant rollback capability
- ✅ Complete isolation between services

**What you do:**
- ✅ Edit code in service repos
- ✅ Push to Forgejo
- ✅ Watch automatic deployment
- ✅ That's it!

**No more:**
- ❌ Manual deployments
- ❌ SSH into servers
- ❌ Docker build commands
- ❌ Complex deployment scripts

---

**Questions?** Check Forgejo Actions logs or service logs via SSH.

**Ready to deploy your own code?** Just replace demo files in service repos!

🚀 **Happy Deploying!**
