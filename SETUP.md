# Setup Guide

## Prerequisites

### Local Tools

```bash
# macOS
brew install terraform ansible jq gh

# Linux
sudo apt install terraform ansible jq gh
```

### GCP Setup

```bash
# Install gcloud
curl https://sdk.cloud.google.com | bash
exec -l $SHELL

# Login
gcloud auth login
gcloud auth application-default login
gcloud config set project YOUR_PROJECT_ID
```

### SSH Key (Deploy-Only)

```bash
ssh-keygen -t ed25519 -f ~/.ssh/superdeploy_deploy -N ""
```

### GitHub CLI

```bash
gh auth login
```

### Docker Hub Token

1. hub.docker.com → Account Settings → Security → New Access Token
2. Save for `.env`

---

## Installation

### Step 1: Clone & Configure

```bash
git clone <repo>
cd superdeploy

cp ENV.example .env
vim .env
```

**Minimum required:**
```bash
GCP_PROJECT_ID=your-project-id
GCP_REGION=us-central1
GCP_ZONE=us-central1-a

SSH_USER=superdeploy
SSH_KEY_PATH=~/.ssh/superdeploy_deploy

FORGEJO_ADMIN_USER=admin
FORGEJO_ADMIN_PASSWORD=StrongPassword123
FORGEJO_ADMIN_EMAIL=admin@yourdomain.com
FORGEJO_ORG=yourorg

DOCKER_REGISTRY=docker.io
DOCKER_ORG=your-dockerhub-username
DOCKER_USERNAME=your-dockerhub-username
DOCKER_TOKEN=dckr_pat_xxxxx

GITHUB_TOKEN=ghp_xxxxx

FORGEJO_DB_USER=superdeploy
FORGEJO_DB_PASSWORD=DBPassword123
FORGEJO_DB_NAME=forgejo
```

### Step 2: Remote State Setup (First Time Only)

```bash
make setup-remote-state
```

### Step 3: Full Deployment

```bash
make deploy
```

**What happens:**
1. Terraform creates VMs (2 min)
2. Extracts IPs, updates `.env`
3. Generates Ansible inventory
4. Waits for VMs ready (120s)
5. Ansible deploys:
   - Packages (Docker, tools)
   - Security (UFW, Fail2Ban, SSH hardening)
   - Forgejo + Runner
   - Backup cron jobs
6. Pushes code to Forgejo

**Total: ~6 minutes**

### Step 4: Forgejo PAT

```bash
make forgejo-pat-create
```

Or manual:
1. http://VM_IP:3001 → Settings → Applications
2. Generate Token (scopes: `write:repository`, `write:activitypub`)
3. Add to `.env`: `FORGEJO_PAT=...`

### Step 5: Configure Secrets

#### GitHub Secrets (Build)

```bash
# Automatic
make github-secrets-setup

# Or manual: https://github.com/org/repo/settings/secrets/actions
```

Secrets needed:
- `DOCKER_ORG`, `DOCKER_USERNAME`, `DOCKER_TOKEN`
- `FORGEJO_BASE_URL` (http://VM_IP:3001)
- `FORGEJO_ORG`, `FORGEJO_PAT`

#### Forgejo Secrets (Runtime)

**Forgejo UI → superdeploy-app → Settings → Actions → Secrets**

Add:
```
POSTGRES_USER=superdeploy
POSTGRES_PASSWORD=YourDBPass
POSTGRES_DB=superdeploy_db

RABBITMQ_USER=superdeploy
RABBITMQ_PASSWORD=YourQueuePass

API_SECRET_KEY=your-32-char-secret
SENTRY_DSN=https://... (optional)

PUBLIC_URL=http://VM_IP
API_BASE_URL=http://VM_IP:8000
```

### Step 6: First Deployment

```bash
cd ../app-repos/api
git checkout -b production
git push origin production

# GitHub Actions builds → triggers Forgejo → deploys
```

Check: http://VM_IP:3001/yourorg/superdeploy-app/actions

---

## HTTPS Setup (Optional)

### DNS

```
api.yourdomain.com      A  VM_IP
forgejo.yourdomain.com  A  VM_IP
app.yourdomain.com      A  VM_IP
```

### Configure

```bash
# .env
DOMAIN_API=api.yourdomain.com
DOMAIN_FORGEJO=forgejo.yourdomain.com
DOMAIN_APP=app.yourdomain.com
ACME_EMAIL=admin@yourdomain.com
```

### Deploy Caddy

```bash
cd superdeploy/compose
docker compose -f docker-compose.core.yml up -d caddy

# Caddy auto:
# - Gets Let's Encrypt cert
# - HTTP→HTTPS redirect
# - Renews every 90 days
```

Access: https://api.yourdomain.com

---

## Monitoring Setup (Optional)

```bash
cd superdeploy/compose

# Add ALERT_EMAIL to .env
echo "ALERT_EMAIL=your@email.com" >> /opt/superdeploy/.env

docker compose -f docker-compose.core.yml \
               -f docker-compose.monitoring.yml up -d
```

Services:
- Prometheus: http://VM_IP:9090
- Grafana: http://VM_IP:3002 (admin/admin)
- Alertmanager: http://VM_IP:9093

Alerts sent to `ALERT_EMAIL`.

---

## Verification

```bash
# Services status
ssh superdeploy@VM_IP "cd /opt/superdeploy/compose && docker compose ps"

# Health checks
curl http://VM_IP:8000/healthz
curl http://VM_IP:15672  # Should fail (internal only)

# Logs
ssh superdeploy@VM_IP "docker logs -f superdeploy-api"

# Backups
ssh superdeploy@VM_IP "ls -lh /opt/backups/postgres/"
```

---

## Troubleshooting

### VMs not ready

```bash
# Wait longer
sleep 120
make ansible-deploy
```

### Terraform state issues

```bash
# Migrate to remote state
terraform init -migrate-state
```

### Forgejo not accessible

```bash
# Check firewall
ssh superdeploy@VM_IP "sudo ufw status"

# Check service
ssh superdeploy@VM_IP "docker ps | grep forgejo"
```

### Runner not working

```bash
# Check status
ssh superdeploy@VM_IP "systemctl status forgejo-runner"

# View logs
ssh superdeploy@VM_IP "journalctl -u forgejo-runner -f"

# Restart
ssh superdeploy@VM_IP "sudo systemctl restart forgejo-runner"
```

### Deployment failed

Check Forgejo Actions logs:  
http://VM_IP:3001/yourorg/superdeploy-app/actions

---

## Cleanup

```bash
# Destroy everything
make destroy

# Clean local state
make clean
```

