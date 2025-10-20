# SuperDeploy - Zero-Hardcoded Setup Guide

## 🎯 Philosophy

**EVERYTHING is configured via `.env` file. NO hardcoded IPs, passwords, or configuration.**

When VMs restart and IPs change, you only need to:
1. Update `.env` file
2. Push to git
3. Done!

---

## 🚀 Quick Start (From Scratch)

### 1. Clone Repository
```bash
git clone http://YOUR_FORGEJO_IP:3001/cradexco/superdeploy-app.git
cd superdeploy-app
```

### 2. Configure Environment
```bash
# Copy example to .env
cp ENV.example .env

# Edit .env with your actual values
nano .env

# CRITICAL: Update these when VMs restart!
# - CORE_EXTERNAL_IP
# - CORE_INTERNAL_IP  
# - SCRAPE_EXTERNAL_IP
# - SCRAPE_INTERNAL_IP
# - PROXY_EXTERNAL_IP
# - PROXY_INTERNAL_IP
```

### 3. Configure Forgejo (One-time)
```bash
# Go to Forgejo
open http://YOUR_FORGEJO_IP:3001

# Register runner (one-time setup)
# Already done if you see "self-hosted" runner active
```

### 4. Deploy!
```bash
# Commit .env (yes, we commit it for this project)
git add .env
git commit -m "config: update environment"
git push

# Workflows automatically trigger:
# - deploy-core.yml   → Deploys to CORE VM
# - deploy-scrape.yml → Deploys to SCRAPE VM  
# - deploy-proxy.yml  → Deploys to PROXY VM
```

---

## 📋 What Gets Deployed

### CORE VM (10.0.0.5 / 34.56.43.99)
- **PostgreSQL** - Database
- **RabbitMQ** - Message Queue
- **API** - FastAPI Backend
- **Proxy Registry** - Proxy Management
- **Dashboard** - Web UI
- **Caddy** - Reverse Proxy
- **Forgejo** - Git Server + Actions Runner

### SCRAPE VM (10.0.0.7 / 34.67.236.167)
- **Scrape Workers** - Scraping jobs
- **Playwright** - Browser automation

### PROXY VM (10.0.0.6 / 34.173.11.246)
- **Dante SOCKS5** - Proxy server
- **Tinyproxy HTTP** - HTTP proxy
- **IP Monitor** - IP change detection

---

## 🔧 Common Tasks

### Update Configuration (e.g., After VM Restart)
```bash
# 1. Get new IPs
gcloud compute instances list

# 2. Update .env
nano .env
# Update CORE_EXTERNAL_IP, CORE_INTERNAL_IP, etc.

# 3. Push changes
git add .env
git commit -m "config: update IPs after restart"
git push

# 4. Workflows auto-deploy everywhere!
```

### Manual Deployment
```bash
# Trigger workflows manually in Forgejo UI:
# http://YOUR_IP:3001/cradexco/superdeploy-app/actions

# Or trigger specific VM:
cd superdeploy-app
echo "# trigger" >> deploy/compose/vm1-core/TEST.txt
git commit -am "trigger: manual deploy"
git push
```

### Check Deployment Status
```bash
# Core VM
ssh superdeploy@${CORE_EXTERNAL_IP}
docker compose -f /opt/superdeploy/compose/docker-compose.yml ps

# Scrape VM
ssh superdeploy@${SCRAPE_EXTERNAL_IP}
docker compose -f /opt/superdeploy/compose/docker-compose.yml ps

# Proxy VM
ssh superdeploy@${PROXY_EXTERNAL_IP}
docker compose -f /opt/superdeploy/compose/docker-compose.yml ps
```

### View Logs
```bash
# On any VM
docker compose logs -f [service_name]

# Examples:
docker compose logs -f api
docker compose logs -f postgres
docker compose logs -f rabbitmq
```

---

## 🔐 Security Notes

### .env File Handling
- ✅ **Development**: `.env` is committed to git for convenience
- ⚠️ **Production**: Use secrets management or encrypted files
- 🔒 **Never** share `.env` publicly

### Passwords in .env
All sensitive values are in `.env`:
- `POSTGRES_PASSWORD`
- `RABBITMQ_DEFAULT_PASS`
- `API_SECRET_KEY`
- `PROXY_PASSWORD`
- etc.

**Change all default passwords before production use!**

---

## 🛠️ Troubleshooting

### Workflow Stuck in "Waiting"
```bash
# Check runner status
ssh superdeploy@${CORE_EXTERNAL_IP}
systemctl status forgejo-runner

# Restart runner if needed
sudo systemctl restart forgejo-runner
```

### Services Not Starting
```bash
# Check .env is loaded
docker compose config

# Check logs
docker compose logs
```

### IP Changed But Services Can't Connect
```bash
# 1. Update .env in repository
# 2. Push changes
# 3. Workflows will redeploy with new IPs automatically
```

### RabbitMQ Unhealthy
```bash
# Check logs
docker logs superdeploy-rabbitmq

# Restart
docker compose restart rabbitmq
```

---

## 📚 Architecture

### Single Source of Truth: `.env`
```
.env  →  Forgejo Workflows  →  Docker Compose  →  Services
```

### No Hardcoded Values
- ❌ No IPs in code
- ❌ No passwords in compose files
- ❌ No configuration in workflows
- ✅ Everything from `.env`

### VM Restart Flow
```
1. VMs restart → IPs change
2. Update .env → Push to git
3. Workflows run → Services redeploy
4. Done!
```

---

## 🎓 Best Practices

1. **Always update .env first** before manual changes
2. **Test locally** with `docker compose config` before pushing
3. **Monitor workflows** at http://YOUR_IP:3001/cradexco/superdeploy-app/actions
4. **Keep backups** of working `.env` configurations
5. **Document changes** in git commit messages

---

## 📞 Support

### Check Workflow Logs
http://YOUR_IP:3001/cradexco/superdeploy-app/actions

### Check Service Health
```bash
curl http://${CORE_EXTERNAL_IP}:8000/health        # API
curl http://${CORE_EXTERNAL_IP}:8080/health        # Proxy Registry
curl http://${CORE_EXTERNAL_IP}/                   # Dashboard
```

### Full System Check
```bash
# Run on CORE VM
cd /opt/superdeploy/compose
docker compose ps
docker compose logs --tail=50
```

---

## 🎉 Success Criteria

You know it's working when:
- ✅ All workflows show green checkmarks
- ✅ `docker compose ps` shows all services "healthy"
- ✅ API responds: `curl http://localhost:8000/health`
- ✅ Dashboard loads in browser
- ✅ No hardcoded IPs anywhere!

---

**Made with ❤️ for zero-configuration deployments**

