# SuperDeploy - Production-Ready Self-Hosted CI/CD

**Tek komutla tam otomatik deployment.**

```bash
cd superdeploy && make deploy
```

---

## 📋 Dokümantasyon

- **[ARCHITECTURE.md](ARCHITECTURE.md)** - Sistem mimarisi, akış diyagramı
- **[SETUP.md](SETUP.md)** - Kurulum adımları (sıfırdan production)
- **[DEPLOY.md](DEPLOY.md)** - Deployment komutları, rollback, staging
- **[OPERATIONS.md](OPERATIONS.md)** - Monitoring, backup, troubleshooting

---

## ⚡ Hızlı Başlangıç

```bash
# 1. Environment setup
cd superdeploy
cp ENV.example .env
vim .env  # GCP_PROJECT_ID, SSH_KEY_PATH, DOCKER_* doldur

# 2. Deploy everything
make deploy  # 6 dakika

# 3. HTTPS setup (optional)
# DNS A kayıtları ekle, .env'de DOMAIN_* güncelle
docker compose -f compose/docker-compose.core.yml up -d caddy

# 4. Monitoring (optional)
docker compose -f compose/docker-compose.core.yml \
               -f compose/docker-compose.monitoring.yml up -d
```

---

## ✨ Özellikler

### Deployment
- ✅ Single-command deployment (`make deploy`)
- ✅ Multi-environment (prod + staging)
- ✅ Selective deployment (sadece değişen servis)
- ✅ SHA-based rollback (`make rollback SERVICE=api TAG=sha`)
- ✅ DB migrations (optional toggle)
- ✅ Health checks (12 retries, 60s timeout)

### Security
- ✅ HTTPS/TLS (Caddy + Let's Encrypt auto)
- ✅ UFW firewall + Fail2Ban
- ✅ SSH hardening (no root, no password)
- ✅ Internal-only services (PostgreSQL, RabbitMQ)
- ✅ Secrets encryption (GitHub + Forgejo)

### Infrastructure
- ✅ Terraform (GCP VMs, network, firewall)
- ✅ Remote state (GCS backend, 30 versions)
- ✅ Ansible (packages, security, services)
- ✅ Docker Compose (modular: core + apps + staging + monitoring)

### Monitoring & Backup
- ✅ Prometheus + Grafana + Loki + Alertmanager
- ✅ 10+ alerts (ServiceDown, CPU, Memory, Disk)
- ✅ PostgreSQL backup (daily 02:00 UTC, 7-day retention)
- ✅ Forgejo backup (daily 03:00 UTC, repos + DB)
- ✅ Email notifications (deployment + alerts)

---

## 🚀 Deployment Komutları

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

## 📊 Erişim

**Production:**
```
Dashboard:  http://YOUR_VM_IP
API:        http://YOUR_VM_IP:8000
Forgejo:    http://YOUR_VM_IP:3001
```

**With HTTPS:**
```
https://app.yourdomain.com
https://api.yourdomain.com
https://forgejo.yourdomain.com
```

**Monitoring:**
```
Prometheus:    http://YOUR_VM_IP:9090
Grafana:       http://YOUR_VM_IP:3002
Alertmanager:  http://YOUR_VM_IP:9093
```

---

## 🛠️ Maintenance

```bash
# Check services
ssh superdeploy@VM_IP "cd /opt/superdeploy/compose && docker compose ps"

# View logs
ssh superdeploy@VM_IP "docker logs -f superdeploy-api"

# Backup manually
ssh superdeploy@VM_IP "bash /opt/superdeploy/scripts/backup/postgres-backup.sh"

# Restore
gunzip -c backup.sql.gz | docker exec -i superdeploy-postgres psql -U superdeploy
```

---

## 🔥 Destroy

```bash
make destroy  # Delete all VMs
make clean    # Clean Terraform state
```

---

**License:** MIT  
**Contact:** cradexco@gmail.com
