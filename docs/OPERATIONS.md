# SuperDeploy Operations Guide

Operations rehberi - production sistemini yönetmek için daily kullanım kılavuzu.

---

## 🚀 Deployment Operations

### New App Deployment

```bash
# 1. config.yml'e app ekle
# 2. secrets.yml'e app secrets ekle
# 3. Workflow generate et
superdeploy myproject:generate --app newapp

# 4. Secrets sync et
superdeploy myproject:sync

# 5. App repo'ya commit et
cd ~/code/myorg/newapp
git add .superdeploy .github/workflows/deploy.yml
git commit -m "Add SuperDeploy"
git push origin main

# 6. Production'a deploy et
git checkout -b production
git push origin production
```

### Update Existing App

```bash
# Sadece code değişikliği - otomatik deploy
cd ~/code/myorg/api
git add .
git commit -m "Update feature"
git push origin production  # ← GitHub Actions otomatik deploy eder
```

### Rollback

```bash
# GitHub Actions UI'da previous successful run'ı re-run et
# Veya Git üzerinden:
cd ~/code/myorg/api
git revert HEAD
git push origin production
```

---

## 🔧 Infrastructure Operations

### Scale Up VM

```bash
# config.yml'de machine_type değiştir
vms:
  app:
    machine_type: e2-standard-2  # e2-medium'dan upgrade

# Apply changes
superdeploy myproject:up
# Terraform existing VM'i upgrade eder
```

### Add New VM

```bash
# config.yml'e yeni VM ekle
vms:
  worker:
    machine_type: e2-medium
    disk_size: 20
    services: []

# Deploy (runners auto-register)
superdeploy myproject:up
```

### Add Infrastructure Service

```bash
# config.yml'de service ekle
vms:
  core:
    services:
      - postgres
      - rabbitmq
      - redis  # ← yeni

# Deploy
superdeploy myproject:up
# Sadece yeni addon deploy edilir
```

---

## 🔐 Secret Management

### View Secrets

```bash
# Local secrets
cat projects/myproject/secrets.yml

# GitHub repository secrets (web UI)
# https://github.com/myorg/api/settings/secrets/actions

# GitHub environment secrets (web UI)
# https://github.com/myorg/api/settings/environments
```

### Update Secrets

```bash
# 1. secrets.yml'i güncelle
vim projects/myproject/secrets.yml

# 2. GitHub'a sync et
superdeploy myproject:sync

# 3. App'i re-deploy et (secrets ortam değişkenlerinde)
cd ~/code/myorg/api
git commit --allow-empty -m "Reload secrets"
git push origin production
```

### Add New Secret

```bash
# secrets.yml'e ekle
secrets:
  api:
    NEW_SECRET: value

# Sync et
superdeploy myproject:sync

# App code'unda kullan
# Python: os.getenv('NEW_SECRET')
# Node.js: process.env.NEW_SECRET
```

---

## 📊 Monitoring & Debugging

### Check System Status

```bash
# VM ve service durumunu göster
superdeploy myproject:status

# Çıktı:
# ┏━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━┳━━━━━━━━━┓
# ┃ Component     ┃ Status              ┃ Details        ┃ Version ┃
# ┡━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━╇━━━━━━━━━┩
# │ app (app)     │ Running             │ 34.123.45.67   │         │
# │   └─ api      │ Up 5 mins (healthy) │ container      │ 1.2.5   │
# │   └─ frontend │ Up 5 mins (healthy) │ container      │ 0.3.1   │
# │ core (core)   │ Running             │ 34.123.45.68   │         │
# │   └─ postgres │ Up 2 days (healthy) │ container      │ -       │
# │   └─ rabbitmq │ Up 2 days (healthy) │ container      │ -       │
# └───────────────┴─────────────────────┴────────────────┴─────────┘

# Verbose mode (debug için)
superdeploy myproject:status -v
```

### Version Management

SuperDeploy automatically tracks semantic versions for each deployment.

```bash
# Version'lar otomatik artırılır:
# - Normal commit: patch bump (0.0.1 → 0.0.2)
# - feat: veya [minor]: minor bump (0.0.2 → 0.1.0)  
# - breaking: veya [major]: major bump (0.1.0 → 1.0.0)

# Örnek commit'ler:
git commit -m "Fix bug in API"                    # → 0.0.1 → 0.0.2
git commit -m "feat: add new endpoint"            # → 0.0.2 → 0.1.0
git commit -m "[minor] improve performance"       # → 0.1.0 → 0.2.0
git commit -m "breaking: change database schema"  # → 0.2.0 → 1.0.0

# Version bilgileri VM'de saklanır:
# /opt/superdeploy/projects/myproject/versions.json
# {
#   "api": {
#     "version": "1.2.5",
#     "deployed_at": "2025-11-10T12:30:00Z",
#     "git_sha": "abc1234...",
#     "deployed_by": "user",
#     "branch": "production"
#   }
# }
```

### SSH to VM

```bash
# config.yml'den IP al veya:
superdeploy myproject:status

# SSH
ssh superdeploy@34.123.45.67
```

### Check Docker Containers

```bash
# SSH to VM
ssh superdeploy@<VM_IP>

# List containers
docker ps

# Check logs
docker logs myproject_api --tail 100 -f

# Check specific app
cd /opt/superdeploy/projects/myproject/compose
docker compose logs api -f
```

### Check GitHub Runner

```bash
# SSH to VM
ssh superdeploy@<VM_IP>

# Runner status
sudo systemctl status github-runner

# Runner logs
sudo journalctl -u github-runner -f

# Check registration
cat /opt/superdeploy/.project
# Output: myproject
```

### Check Deployment Logs

```bash
# GitHub Actions UI:
# https://github.com/myorg/api/actions

# Veya gh CLI ile:
gh run list -R myorg/api --limit 10
gh run view <run-id> -R myorg/api --log
```

---

## 🔄 Maintenance Operations

### Update Infrastructure Packages

```bash
# SSH to VM
ssh superdeploy@<VM_IP>

# Update system
sudo apt update && sudo apt upgrade -y

# Restart if needed
sudo reboot

# GitHub runner otomatik başlar (systemd service)
```

### Restart Container

```bash
# SSH to VM
ssh superdeploy@<VM_IP>

# Restart specific app
cd /opt/superdeploy/projects/myproject/compose
docker compose restart api

# Or recreate
docker compose up -d --force-recreate api
```

### Clean Docker Resources

```bash
# SSH to VM
ssh superdeploy@<VM_IP>

# Remove unused images
docker image prune -af

# Remove unused volumes
docker volume prune -f

# Remove unused networks
docker network prune -f
```

### Backup Database

```bash
# SSH to core VM
ssh superdeploy@<CORE_VM_IP>

# Postgres backup
docker exec myproject_postgres pg_dump -U postgres mydb > backup.sql

# Copy to local
scp superdeploy@<CORE_VM_IP>:~/backup.sql ./backup.sql
```

### Restore Database

```bash
# Copy backup to VM
scp backup.sql superdeploy@<CORE_VM_IP>:~/

# SSH to VM
ssh superdeploy@<CORE_VM_IP>

# Restore
docker exec -i myproject_postgres psql -U postgres mydb < backup.sql
```

---

## 🌐 DNS & Domain Operations

### Setup Custom Domain

```bash
# 1. Get VM IPs
superdeploy myproject:status

# 2. Add DNS A records:
# api.myproject.com → <APP_VM_IP>
# storefront.myproject.com → <APP_VM_IP>

# 3. Wait for DNS propagation (5-30 min)
dig api.myproject.com

# 4. Update secrets.yml with domain
secrets:
  storefront:
    NEXT_PUBLIC_API_URL: https://api.myproject.com

# 5. Sync and redeploy
superdeploy myproject:sync
```

### Setup SSL with Caddy

```bash
# 1. config.yml'e caddy ekle
vms:
  app:
    services:
      - caddy

# 2. Deploy
superdeploy myproject:up

# Caddy otomatik Let's Encrypt SSL alır
# https://api.myproject.com otomatik çalışır
```

---

## 🚨 Disaster Recovery

### Full Infrastructure Restore

```bash
# 1. superdeploy repo'yu clone et
git clone https://github.com/cfkarakulak/superdeploy.git

# 2. GCP credentials setup
export GOOGLE_APPLICATION_CREDENTIALS=~/superdeploy-key.json

# 3. Full deploy (runners auto-register with REPOSITORY_TOKEN)
superdeploy myproject:up

# 4. Secrets sync
superdeploy myproject:sync

# 5. Database restore (if needed)
# ... backup restore steps ...
```

### Destroy Everything

```bash
# ⚠️ DESTRUCTIVE - Will delete all VMs and data!
superdeploy myproject:down

# Confirmation required
# Enter: yes
```

---

## 📈 Scaling Operations

### Horizontal Scaling (Multiple Instances)

```yaml
# config.yml - Multiple app VMs
vms:
  app-1:
    machine_type: e2-medium
    services: []
  app-2:
    machine_type: e2-medium
    services: []

# Load balancer gerekir (Caddy veya GCP Load Balancer)
```

### Vertical Scaling

```yaml
# config.yml - Bigger machines
vms:
  app:
    machine_type: e2-standard-4  # More CPU/RAM
    disk_size: 50  # More disk
```

---

## 🧪 Testing Operations

### Test Runner Connection

```bash
# GitHub'da manuel workflow trigger et
# https://github.com/myorg/api/actions

# "Run workflow" → "production" branch
# Deployment başlamalı ve succeed etmeli
```

### Test Secret Access

```bash
# App container içinde
ssh superdeploy@<VM_IP>
docker exec -it myproject_api env | grep DATABASE_URL
```

### Test Health Checks

```bash
# Health endpoint test et
curl http://<VM_IP>:8000/health

# Expected: 200 OK
```

---

## 📝 Best Practices

### Regular Operations

1. **Weekly:** Check GitHub Actions runs - başarısız deploymentları investigate et
2. **Weekly:** Check disk usage: `df -h`
3. **Monthly:** Update system packages
4. **Monthly:** Review and rotate secrets
5. **Quarterly:** Review and optimize VM sizes

### Security

1. **Secrets:** Asla Git'e commit etme
2. **SSH Keys:** Passphrase kullan (production için)
3. **Tokens:** 90 günde bir rotate et
4. **Firewall:** Sadece gerekli portları aç
5. **Updates:** Security patch'leri hemen uygula

### Cost Optimization

1. **VM Sizes:** Oversized VM'leri downsize et
2. **Disk:** Unused disk'leri sil
3. **Images:** Old Docker images'ı temizle
4. **Resources:** Unused services'leri kaldır
5. **Scheduling:** Dev environment'ları gece kapat

---

## 🆘 Common Issues

### "Runner not found"

```bash
# GitHub runner offline - restart et
ssh superdeploy@<VM_IP>
sudo systemctl restart github-runner
```

### "Docker image pull failed"

```bash
# Docker Hub credentials yanlış
# secrets.yml'i kontrol et
# Tekrar sync et
superdeploy myproject:sync
```

### "Container unhealthy"

```bash
# Container logs kontrol et
docker logs myproject_api --tail 100

# Restart container
docker compose restart api
```

### "Wrong project" error in deployment

```bash
# .project file yanlış
ssh superdeploy@<VM_IP>
cat /opt/superdeploy/.project  # Doğru project name'i göstermeli

# Fix:
echo "myproject" | sudo tee /opt/superdeploy/.project
```

---

## 📞 Support

### Get Help

```bash
# Detailed status
superdeploy myproject:status --verbose

# Validate configuration
superdeploy myproject:config validate

# Check logs
tail -f projects/myproject/logs/*.log
```

### Report Issues

GitHub Issues: https://github.com/cfkarakulak/superdeploy/issues
