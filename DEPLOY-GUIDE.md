# 🚀 SuperDeploy - Multi-Repo Production Deployment

## 📋 Architecture Overview

**4 Independent Repositories:**

```
1. cheapa-api/          → API service (FastAPI)
2. cheapa-storefront/   → Frontend/Dashboard (Node.js)
3. cheapa-services/     → Background services (Proxy Registry)
4. superdeploy/         → Deployment orchestration (THIS REPO)
```

**Flow:**
```
Service Repo Push → CI Build Image → Trigger superdeploy → Deploy to VM
```

---

## 🎯 Quick Start (From Scratch)

### 1️⃣ Initial Setup (One-Time)

```bash
cd superdeploy/

# 1. Copy env template
cp ENV.example .env

# 2. Edit .env - ONLY fill these:
nano .env
#   GCP_PROJECT_ID=your-project-id
#   All CHANGE_ME_* passwords

# 3. Deploy everything!
make deploy
```

**That's it!** This will:
- ✅ Create 3 VMs on GCP
- ✅ Install Docker, Forgejo, PostgreSQL, RabbitMQ
- ✅ Setup Forgejo Actions runner
- ✅ Create 4 repos (superdeploy-app + 3 service repos)
- ✅ Push all code automatically

**⏱️ Total time: ~5 minutes**

---

## 🔄 Daily Development Workflow

### Option A: Work on API

```bash
cd cheapa-api/

# Make changes to app.py or Dockerfile
nano app.py

# Commit and push
git add -A
git commit -m "feat: add new endpoint"
git push

# 🎉 That's it! CI automatically:
#   1. Builds Docker image
#   2. Tags with commit SHA
#   3. Triggers deployment
#   4. Updates CORE VM
```

### Option B: Work on Storefront

```bash
cd cheapa-storefront/

# Make changes
nano public/index.html

git add -A && git commit -m "ui: update homepage" && git push

# 🎉 Auto-deployed!
```

### Option C: Work on Services

```bash
cd cheapa-services/

# Update service logic
nano app.py

git add -A && git commit -m "fix: improve error handling" && git push

# 🎉 Auto-deployed!
```

---

## 📦 What Gets Deployed Where

### CORE VM (34.56.43.99)
- **PostgreSQL** (port 5432)
- **RabbitMQ** (port 5672, management: 15672)
- **API** (port 8000) ← from `cheapa-api` repo
- **Storefront** (port 8001) ← from `cheapa-storefront` repo
- **Services** (port 8080) ← from `cheapa-services` repo
- **Caddy** (ports 80/443)
- **Forgejo** (port 3001)

### SCRAPE VM (34.67.236.167)
- Worker services (future)

### PROXY VM (34.173.11.246)
- SOCKS5/HTTP proxies (future)

---

## 🔧 Useful Commands

### Check Service Status
```bash
# On CORE VM
ssh superdeploy@34.56.43.99
cd /opt/superdeploy/deploy/compose/vm1-core
docker compose ps
docker compose logs -f api          # API logs
docker compose logs -f dashboard    # Storefront logs
```

### Manual Deployment Trigger
```bash
# From superdeploy/ directory
cd deploy/compose/vm1-core
ssh superdeploy@34.56.43.99 << 'EOF'
  cd /opt/superdeploy/deploy/compose/vm1-core
  docker compose pull
  docker compose up -d
EOF
```

### View CI/CD Runs
```
http://34.56.43.99:3001/cradexco/cheapa-api/actions
http://34.56.43.99:3001/cradexco/cheapa-storefront/actions
http://34.56.43.99:3001/cradexco/cheapa-services/actions
http://34.56.43.99:3001/cradexco/superdeploy-app/actions
```

---

## 🔄 Rollback

```bash
cd superdeploy/

# Rollback API to previous version
./scripts/rollback.sh core api abc123

# Rollback Storefront
./scripts/rollback.sh core dashboard xyz789
```

---

## 🆘 Troubleshooting

### "Service won't start"
```bash
# Check logs
ssh superdeploy@34.56.43.99
cd /opt/superdeploy/deploy/compose/vm1-core
docker compose logs api

# Restart service
docker compose restart api
```

### "CI workflow stuck"
```bash
# Check runner status
ssh superdeploy@34.56.43.99
sudo systemctl status forgejo-runner
sudo systemctl restart forgejo-runner
```

### "Can't push to service repo"
```bash
# Verify git remote
cd cheapa-api/
git remote -v

# Should be: http://34.56.43.99:3001/cradexco/cheapa-api.git
```

### "Fresh deployment after VM deletion"
```bash
# Just run deploy again - it handles everything!
cd superdeploy/
make deploy
```

---

## 📊 Repository Structure

### cheapa-api/
```
cheapa-api/
├── .forgejo/workflows/ci.yml   # CI pipeline
├── Dockerfile                   # Build instructions
├── app.py                       # FastAPI application
└── requirements.txt             # Python deps (if needed)
```

### cheapa-storefront/
```
cheapa-storefront/
├── .forgejo/workflows/ci.yml
├── Dockerfile
├── package.json
├── server.js
└── public/
    └── index.html
```

### cheapa-services/
```
cheapa-services/
├── .forgejo/workflows/ci.yml
├── Dockerfile
├── app.py
└── requirements.txt
```

### superdeploy/ (THIS REPO)
```
superdeploy/
├── .env                         # 🔐 MAIN CONFIG FILE
├── ENV.example
├── Makefile                     # Deployment commands
├── ARCHITECTURE.md              # Technical design
├── DEPLOY-GUIDE.md              # This file
├── deploy/compose/
│   └── vm1-core/
│       ├── docker-compose.yml   # Service orchestration
│       ├── .env.versions        # Deployed versions
│       └── Caddyfile
├── .forgejo/workflows/
│   └── deploy-core-v2.yml       # Deployment workflow
└── scripts/
    └── rollback.sh              # Rollback tool
```

---

## 🎯 Current Status

✅ **Infrastructure**: 3 VMs on GCP  
✅ **Git Server**: Forgejo + Actions  
✅ **Services**: PostgreSQL, RabbitMQ, Caddy  
✅ **Repos**: 4 independent repositories  
✅ **CI/CD**: Full automation per service  
✅ **Deployment**: Single command (`make deploy`)  

---

## 📝 Next Steps

1. **Add real code** to service repos
2. **Test deployment** by pushing changes
3. **Monitor** via Forgejo Actions UI
4. **Scale** by adding more services

---

## 🌐 Access Points

- **Forgejo**: http://34.56.43.99:3001
- **Admin**: cradexco / SuperSecure123Pass
- **API**: http://34.56.43.99:8000
- **Storefront**: http://34.56.43.99:8001
- **Services**: http://34.56.43.99:8080

---

**🚀 Happy Deploying!**

