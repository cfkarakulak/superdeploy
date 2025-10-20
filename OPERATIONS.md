# Operations Guide

## Monitoring

### Access

```
Prometheus:    http://VM_IP:9090
Grafana:       http://VM_IP:3002  (admin/GRAFANA_ADMIN_PASSWORD)
Alertmanager:  http://VM_IP:9093
```

### Setup

```bash
cd superdeploy/compose

# Add to .env
ALERT_EMAIL=your@email.com
GRAFANA_ADMIN_USER=admin
GRAFANA_ADMIN_PASSWORD=change-me

# Deploy
docker compose -f docker-compose.core.yml \
               -f docker-compose.monitoring.yml up -d
```

### Grafana Dashboards

**Import:**
1. http://VM_IP:3002 → Dashboards → Import
2. ID: `14282` (Docker Container Metrics)
3. Datasource: Prometheus

**Pre-configured metrics:**
- Container CPU/Memory
- Network I/O
- Disk usage
- Service health

### Alerts

**Active alerts:**
- ServiceDown (2 min)
- HighCPU (>80%, 5 min)
- HighMemory (>85%, 5 min)
- DiskSpaceLow (<15%)
- DiskSpaceCritical (<5%)
- ContainerDown (2 min)
- ContainerRestarting
- PostgreSQLDown
- RabbitMQDown

**Configure:**
```bash
vim superdeploy/compose/monitoring/alerts.yml
docker compose -f docker-compose.monitoring.yml restart prometheus
```

**Test alert:**
```bash
# Trigger high CPU
ssh superdeploy@VM_IP "stress --cpu 4 --timeout 300"

# Check Alertmanager
curl http://VM_IP:9093/api/v1/alerts
```

### Logs (Loki)

```bash
# View in Grafana
# Explore → Datasource: Loki → Query: {container_name="superdeploy-api"}

# Or CLI
curl -G -s "http://VM_IP:3100/loki/api/v1/query_range" \
  --data-urlencode 'query={container_name="superdeploy-api"}' \
  --data-urlencode 'limit=100'
```

---

## Backup

### Automatic

**Cron jobs (already configured):**

```bash
# PostgreSQL: Daily 02:00 UTC
# /opt/superdeploy/scripts/backup/postgres-backup.sh

# Forgejo: Daily 03:00 UTC
# /opt/superdeploy/scripts/backup/forgejo-backup.sh
```

**Check status:**
```bash
ssh superdeploy@VM_IP "ls -lh /opt/backups/postgres/"
ssh superdeploy@VM_IP "ls -lh /opt/backups/forgejo/"
```

### Manual Backup

**PostgreSQL:**
```bash
ssh superdeploy@VM_IP "bash /opt/superdeploy/scripts/backup/postgres-backup.sh"
```

**Forgejo:**
```bash
ssh superdeploy@VM_IP "bash /opt/superdeploy/scripts/backup/forgejo-backup.sh"
```

**Download to local:**
```bash
scp superdeploy@VM_IP:/opt/backups/postgres/postgres_backup_*.sql.gz ./
scp superdeploy@VM_IP:/opt/backups/forgejo/forgejo_backup_*.tar.gz ./
```

### Restore

**PostgreSQL:**
```bash
# Upload backup
scp backup.sql.gz superdeploy@VM_IP:/tmp/

# Restore
ssh superdeploy@VM_IP
cd /opt/superdeploy/compose

# Stop services
docker compose -f docker-compose.core.yml -f docker-compose.apps.yml down api dashboard services

# Drop & recreate DB
docker exec -it superdeploy-postgres psql -U superdeploy -c "DROP DATABASE superdeploy_db;"
docker exec -it superdeploy-postgres psql -U superdeploy -c "CREATE DATABASE superdeploy_db;"

# Restore
gunzip -c /tmp/backup.sql.gz | docker exec -i superdeploy-postgres psql -U superdeploy superdeploy_db

# Start services
docker compose -f docker-compose.core.yml -f docker-compose.apps.yml up -d
```

**Forgejo:**
```bash
# Upload backup
scp backup.tar.gz superdeploy@VM_IP:/tmp/

# Restore
ssh superdeploy@VM_IP
cd /opt/superdeploy/compose

# Stop Forgejo
docker compose -f docker-compose.core.yml down forgejo

# Extract
tar -xzf /tmp/backup.tar.gz -C /opt/

# Start Forgejo
docker compose -f docker-compose.core.yml up -d forgejo
```

### Offsite (GCS)

**Optional setup:**
```bash
# Install gsutil
ssh superdeploy@VM_IP "curl https://sdk.cloud.google.com | bash"

# Authenticate
ssh superdeploy@VM_IP "gcloud auth login"

# Modify backup scripts
vim superdeploy/scripts/backup/postgres-backup.sh
# Add: gsutil cp $BACKUP_FILE gs://your-bucket/backups/postgres/
```

---

## Maintenance

### Update System Packages

```bash
ssh superdeploy@VM_IP

# Unattended upgrades (automatic security patches)
sudo systemctl status unattended-upgrades

# Manual update
sudo apt update && sudo apt upgrade -y
```

### Update Docker Images

```bash
# Pull latest
ssh superdeploy@VM_IP "cd /opt/superdeploy/compose && docker compose pull"

# Restart with new images
ssh superdeploy@VM_IP "cd /opt/superdeploy/compose && docker compose up -d"
```

### Restart Services

```bash
# Single service
ssh superdeploy@VM_IP "docker restart superdeploy-api"

# All services
ssh superdeploy@VM_IP "cd /opt/superdeploy/compose && docker compose restart"

# Core services only
ssh superdeploy@VM_IP "cd /opt/superdeploy/compose && docker compose -f docker-compose.core.yml restart"
```

### Clean Docker

```bash
ssh superdeploy@VM_IP

# Remove unused images
docker image prune -a --filter "until=168h"  # 7 days

# Remove stopped containers
docker container prune

# Remove unused volumes
docker volume prune

# Full cleanup (careful!)
docker system prune -a --volumes
```

---

## Security

### SSH Access

**Key-only, no password, no root:**
```bash
ssh -i ~/.ssh/superdeploy_deploy superdeploy@VM_IP
```

**Add new key:**
```bash
ssh superdeploy@VM_IP
echo "ssh-ed25519 AAAA..." >> ~/.ssh/authorized_keys
```

### Firewall Status

```bash
ssh superdeploy@VM_IP "sudo ufw status verbose"
```

**Expected:**
```
Status: active
To                         Action      From
--                         ------      ----
22/tcp                     LIMIT       Anywhere
80/tcp                     ALLOW       Anywhere
443/tcp                    ALLOW       Anywhere
3001/tcp                   ALLOW       Anywhere  # Forgejo
8000/tcp                   ALLOW       Anywhere  # API
```

### Fail2Ban Status

```bash
ssh superdeploy@VM_IP "sudo fail2ban-client status sshd"
```

### Check for Intrusions

```bash
# Failed SSH attempts
ssh superdeploy@VM_IP "sudo grep 'Failed password' /var/log/auth.log | tail -20"

# Fail2Ban bans
ssh superdeploy@VM_IP "sudo fail2ban-client status sshd"

# Active connections
ssh superdeploy@VM_IP "sudo ss -tuln | grep :22"
```

### Update Secrets

**GitHub:**
```
https://github.com/org/repo/settings/secrets/actions
```

**Forgejo:**
```
http://VM_IP:3001/org/superdeploy-app/settings/actions/secrets
```

After update: Re-run deployment to apply.

---

## Troubleshooting

### Service Not Responding

```bash
# Check container status
ssh superdeploy@VM_IP "docker ps -a | grep superdeploy"

# Check logs
ssh superdeploy@VM_IP "docker logs --tail 100 superdeploy-api"

# Check health
ssh superdeploy@VM_IP "docker inspect superdeploy-api | jq '.[0].State.Health'"

# Restart
ssh superdeploy@VM_IP "docker restart superdeploy-api"
```

### Database Connection Failed

```bash
# Check PostgreSQL
ssh superdeploy@VM_IP "docker exec superdeploy-postgres pg_isready -U superdeploy"

# Check credentials
ssh superdeploy@VM_IP "cat /opt/app-repos/api/.env | grep DATABASE_URL"

# Manual connection test
ssh superdeploy@VM_IP "docker exec -it superdeploy-postgres psql -U superdeploy"
```

### RabbitMQ Issues

```bash
# Check status
ssh superdeploy@VM_IP "docker exec superdeploy-rabbitmq rabbitmq-diagnostics ping"

# Check queues
ssh superdeploy@VM_IP "docker exec superdeploy-rabbitmq rabbitmqctl list_queues"

# Reset (careful!)
ssh superdeploy@VM_IP "docker restart superdeploy-rabbitmq"
```

### Disk Full

```bash
# Check usage
ssh superdeploy@VM_IP "df -h"

# Clean Docker
ssh superdeploy@VM_IP "docker system prune -a --volumes -f"

# Clean logs
ssh superdeploy@VM_IP "sudo journalctl --vacuum-time=7d"

# Clean old backups
ssh superdeploy@VM_IP "find /opt/backups -mtime +7 -delete"
```

### High CPU/Memory

```bash
# Check resource usage
ssh superdeploy@VM_IP "docker stats --no-stream"

# Top processes
ssh superdeploy@VM_IP "top -b -n 1 | head -20"

# Restart problematic service
ssh superdeploy@VM_IP "docker restart superdeploy-services"
```

### Deployment Stuck

**Check Forgejo Actions:**
```
http://VM_IP:3001/org/superdeploy-app/actions
```

**Check runner:**
```bash
ssh superdeploy@VM_IP "systemctl status forgejo-runner"
ssh superdeploy@VM_IP "journalctl -u forgejo-runner -f"
```

**Cancel job:**
```
Forgejo UI → Actions → Running job → Cancel
```

### Network Issues

```bash
# Check connectivity
ssh superdeploy@VM_IP "ping -c 3 8.8.8.8"
ssh superdeploy@VM_IP "curl -I https://docker.io"

# Check DNS
ssh superdeploy@VM_IP "dig api.yourdomain.com"

# Check ports
ssh superdeploy@VM_IP "sudo netstat -tulpn | grep LISTEN"
```

---

## Performance Tuning

### PostgreSQL

```bash
# Connection limit
docker exec superdeploy-postgres psql -U superdeploy -c "SHOW max_connections;"

# Increase (if needed)
# Edit docker-compose.core.yml:
# command: postgres -c max_connections=200
```

### RabbitMQ

```bash
# Memory limit
docker exec superdeploy-rabbitmq rabbitmqctl environment | grep memory

# Set limit
docker exec superdeploy-rabbitmq rabbitmqctl set_vm_memory_high_watermark 0.6
```

### Docker

```bash
# Log rotation
ssh superdeploy@VM_IP
sudo vim /etc/docker/daemon.json
```

```json
{
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "10m",
    "max-file": "3"
  }
}
```

```bash
sudo systemctl restart docker
```

---

## Health Checks

### Manual Health Check

```bash
# API
curl -f http://VM_IP:8000/healthz || echo "FAILED"

# Dashboard
curl -f http://VM_IP/ || echo "FAILED"

# Forgejo
curl -f http://VM_IP:3001/api/v1/healthz || echo "FAILED"

# PostgreSQL
docker exec superdeploy-postgres pg_isready -U superdeploy

# RabbitMQ
docker exec superdeploy-rabbitmq rabbitmq-diagnostics ping
```

### Automated Check Script

```bash
ssh superdeploy@VM_IP "bash /opt/superdeploy/scripts/health-check.sh"
```

---

## Notifications

**Email (already configured):**
- Deployment: SUCCESS/FAILED → `ALERT_EMAIL`
- Alerts: ServiceDown, CPU, Memory → `ALERT_EMAIL`

**Test email:**
```bash
ssh superdeploy@VM_IP
echo "Test" | mail -s "Test SuperDeploy" $ALERT_EMAIL
```

**Configure SMTP (if needed):**
```bash
# Install Postfix
ssh superdeploy@VM_IP "sudo apt install postfix mailutils -y"

# Configure relay
sudo vim /etc/postfix/main.cf
# relayhost = smtp.gmail.com:587
# smtp_sasl_auth_enable = yes
# smtp_sasl_password_maps = hash:/etc/postfix/sasl_passwd
# smtp_sasl_security_options = noanonymous
# smtp_tls_security_level = encrypt

# Credentials
echo "smtp.gmail.com:587 user@gmail.com:password" | sudo tee /etc/postfix/sasl_passwd
sudo postmap /etc/postfix/sasl_passwd
sudo systemctl restart postfix
```

---

## Capacity Planning

**Current setup:**
- 1 VM (Core): 4 vCPU, 8GB RAM
- Services: PostgreSQL, RabbitMQ, API, Dashboard, Services, Forgejo, Caddy

**When to scale:**
- CPU >70% sustained
- Memory >80% sustained
- Disk >85% used
- Response time >500ms

**Scaling options:**
1. Vertical: Increase VM size
2. Horizontal: Separate DBs to own VM
3. Multi-region: Add VMs in other regions

---

## Disaster Recovery

### Full System Loss

**Prerequisites:**
- Latest backup downloaded
- `.env` file backed up
- SSH key available

**Steps:**
```bash
# 1. Recreate infrastructure
cd superdeploy
make deploy

# 2. Restore databases
scp backup.sql.gz superdeploy@NEW_VM_IP:/tmp/
ssh superdeploy@NEW_VM_IP
# Follow restore procedure above

# 3. Redeploy applications
cd app-repos/api
git push origin production --force
```

**RTO: ~15 minutes**  
**RPO: Last backup (max 24h)**

---

## Migration (VM IP Change)

```bash
# 1. Note current data
ssh superdeploy@OLD_IP "cd /opt/superdeploy && docker compose down"
ssh superdeploy@OLD_IP "tar czf /tmp/data.tar.gz /opt"
scp superdeploy@OLD_IP:/tmp/data.tar.gz ./

# 2. Create new VMs
cd superdeploy
make destroy
make deploy  # New IPs

# 3. Restore data
scp data.tar.gz superdeploy@NEW_IP:/tmp/
ssh superdeploy@NEW_IP "tar xzf /tmp/data.tar.gz -C /"

# 4. Update DNS (if using HTTPS)
# 5. Start services
ssh superdeploy@NEW_IP "cd /opt/superdeploy/compose && docker compose up -d"
```

