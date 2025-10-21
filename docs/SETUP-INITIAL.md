# 🚀 Initial Setup Guide (First Time Only)

This guide is for **first-time setup** on a brand new machine. You only need to do this **once**.

---

## ✅ Prerequisites

### 1. Install Required Tools

```bash
# Terraform
brew install terraform

# Ansible
brew install ansible

# Google Cloud SDK
brew install --cask google-cloud-sdk

# jq (JSON parser)
brew install jq

# age (encryption)
brew install age

# GitHub CLI (optional, for secrets management)
brew install gh
```

### 2. Configure GCP

```bash
# Login to GCP
gcloud auth login

# Set application default credentials
gcloud auth application-default login

# Set your project
gcloud config set project YOUR_PROJECT_ID

# Enable required APIs
gcloud services enable compute.googleapis.com
gcloud services enable storage.googleapis.com
```

### 3. Create SSH Key

```bash
# Generate SSH key for GCP
ssh-keygen -t ed25519 -C "superdeploy@gcp" -f ~/.ssh/superdeploy_gcp

# Add public key to GCP
gcloud compute os-login ssh-keys add \
  --key-file ~/.ssh/superdeploy_gcp.pub

# Or add manually in GCP Console:
# Compute Engine → Metadata → SSH Keys → Add SSH Key
```

### 4. Create GitHub Personal Access Token

1. Go to: `https://github.com/settings/tokens`
2. Click **"Generate new token (classic)"**
3. Select scopes:
   - ✅ `repo` (full control)
   - ✅ `admin:repo_hook`
   - ✅ `workflow`
4. Click **"Generate token"**
5. **Copy and save** the token (you won't see it again!)

### 5. Create Docker Hub Token

1. Go to: `https://hub.docker.com/settings/security`
2. Click **"New Access Token"**
3. Name: `superdeploy-ci`
4. Access permissions: **"Read, Write, Delete"**
5. Click **"Generate"**
6. **Copy and save** the token

---

## 📦 Clone Repository

```bash
cd ~/Desktop
git clone https://github.com/cfkarakulak/superdeploy.git
cd superdeploy
```

---

## ⚙️ Configure Environment

```bash
# Copy example config
cp ENV.example .env

# Edit configuration
vim .env  # or: code .env, nano .env
```

### Required Configuration (`.env`)

Fill in these values:

```bash
# =============================================================================
# GCP Infrastructure
# =============================================================================
GCP_PROJECT_ID=your-gcp-project-id          # ✏️ Your GCP project ID
SSH_KEY_PATH=~/.ssh/superdeploy_gcp         # ✏️ Path to SSH key
SSH_USER=superdeploy
VM_MACHINE_TYPE=e2-medium
VM_DISK_SIZE=20
VM_IMAGE=debian-cloud/debian-11

# IP addresses (leave empty - Terraform will fill these)
CORE_EXTERNAL_IP=
CORE_INTERNAL_IP=
SCRAPE_EXTERNAL_IP=
SCRAPE_INTERNAL_IP=
PROXY_EXTERNAL_IP=
PROXY_INTERNAL_IP=

# =============================================================================
# Forgejo Git Server
# =============================================================================
FORGEJO_ORG=cradexco                        # ✏️ Your organization name
FORGEJO_ADMIN_USER=admin
FORGEJO_ADMIN_PASSWORD=ChangeThisPassword!  # ✏️ Strong password!
FORGEJO_ADMIN_EMAIL=admin@example.com       # ✏️ Your email

REPO_SUPERDEPLOY=superdeploy-app

# =============================================================================
# Docker Registry
# =============================================================================
DOCKER_REGISTRY=docker.io
DOCKER_ORG=your-dockerhub-username          # ✏️ Docker Hub username
DOCKER_USERNAME=your-dockerhub-username     # ✏️ Same as above
DOCKER_TOKEN=dckr_pat_xxxxxxxxxxxxx         # ✏️ Docker Hub token

# =============================================================================
# GitHub Token
# =============================================================================
GITHUB_TOKEN=ghp_xxxxxxxxxxxxxxxxxxxx       # ✏️ GitHub PAT

# =============================================================================
# Forgejo Database
# =============================================================================
FORGEJO_DB_USER=superdeploy
FORGEJO_DB_PASSWORD=ForgejoDBPass123!       # ✏️ Strong password!
FORGEJO_DB_NAME=forgejo

# =============================================================================
# Feature Toggles
# =============================================================================
USE_REMOTE_STATE=false      # Set to 'true' for GCS backend (production)
ENABLE_MONITORING=false     # Set to 'true' to enable Prometheus/Grafana
ENABLE_HARDENING=false      # Set to 'true' to enable UFW/Fail2Ban
EXPOSE_RABBITMQ_MGMT=true   # Set to 'false' in production

# =============================================================================
# Monitoring
# =============================================================================
GRAFANA_ADMIN_USER=admin
GRAFANA_ADMIN_PASSWORD=GrafanaPass123!      # ✏️ Strong password!
ALERT_EMAIL=your-email@example.com          # ✏️ Your email
```

**Important:**
- ✅ Use **strong passwords** (min 12 chars, mixed case, numbers, symbols)
- ✅ Keep `.env` file **secret** (never commit to Git)
- ✅ IP addresses will be auto-filled by Terraform

---

## 🚀 Deploy Infrastructure

```bash
cd ~/Desktop/superdeploy

# Deploy everything (Terraform + Ansible + Git push)
make deploy
```

### What happens:

1. **Terraform** provisions 3 VMs on GCP:
   - `vm-core-1` (Forgejo, API, Dashboard, PostgreSQL, RabbitMQ)
   - `vm-scrape-1` (Scraping workers)
   - `vm-proxy-1` (Proxy servers)

2. **IP addresses** are automatically written to `.env`

3. **Ansible** configures all VMs:
   - Installs Docker
   - Deploys Forgejo (with auto-created admin & repo)
   - Registers Forgejo runner
   - Generates AGE encryption keypair
   - Sets up systemd services

4. **Code is pushed** to GitHub and Forgejo

**Duration:** ~6-8 minutes

---

## 🔑 Copy AGE Public Key

At the end of deployment, you'll see:

```
╔══════════════════════════════════════════════════════════════════╗
║  🔐 AGE PUBLIC KEY (Add to GitHub Secrets)                       ║
╚══════════════════════════════════════════════════════════════════╝

In GitHub repo secrets, add:
AGE_PUBLIC_KEY=age1xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

**📋 Copy this key!** You'll need it for GitHub configuration.

---

## 🔐 Create Forgejo PAT

Generate a Personal Access Token for Forgejo API access:

```bash
cd ~/Desktop/superdeploy

# Get values from .env
CORE_IP=$(grep "^CORE_EXTERNAL_IP=" .env | cut -d'=' -f2)
FORGEJO_USER=$(grep "^FORGEJO_ADMIN_USER=" .env | cut -d'=' -f2)
FORGEJO_PASS=$(grep "^FORGEJO_ADMIN_PASSWORD=" .env | cut -d'=' -f2)

# Create PAT
PAT=$(curl -sS -X POST "http://$CORE_IP:3001/api/v1/users/$FORGEJO_USER/tokens" \
  -u "$FORGEJO_USER:$FORGEJO_PASS" \
  -H "Content-Type: application/json" \
  -d '{"name":"github-actions","scopes":["write:repository","write:activitypub"]}' | jq -r '.sha1')

echo ""
echo "✅ Forgejo PAT created!"
echo "FORGEJO_PAT=$PAT"
echo ""
echo "📋 Copy this token - you'll need it for GitHub secrets"

# Save to .env
echo "FORGEJO_PAT=$PAT" >> .env
```

**📋 Copy the PAT** - you'll add it to GitHub secrets next.

---

## 🛠️ Install CLI Tool

```bash
cd ~/Desktop/superdeploy

# Install superdeploy CLI
make cli-install

# Verify installation
superdeploy --help

# Test from any directory
cd ~
superdeploy status  # Works from anywhere!
```

Now you can use commands like:
- `superdeploy status`
- `superdeploy logs -a api -f`
- `superdeploy run api "python manage.py migrate"`
- `superdeploy sync` - **🔥 Auto-sync ALL secrets!**

---

## ✅ Verification

```bash
# Check infrastructure status
superdeploy status

# Access Forgejo
open "http://$(grep CORE_EXTERNAL_IP .env | cut -d'=' -f2):3001"
```

**Expected output:**
- ✅ All VMs running
- ✅ Forgejo accessible
- ✅ Runner registered and active

---

## 🎉 Initial Setup Complete!

You've successfully:
- ✅ Provisioned infrastructure on GCP
- ✅ Deployed Forgejo Git server
- ✅ Registered CI/CD runner
- ✅ Generated encryption keys
- ✅ Installed CLI tool

**Next:** Configure your application repositories (see `SETUP-PER-APP.md`)

---

## 🔧 Troubleshooting

### Terraform fails

```bash
# Check GCP credentials
gcloud auth list
gcloud auth application-default print-access-token

# Check project
gcloud config get-value project

# Re-run
make destroy
make deploy
```

### Ansible fails

```bash
# Check SSH key
ssh -i ~/.ssh/superdeploy_gcp superdeploy@CORE_EXTERNAL_IP

# Check .env file
cat .env | grep -E "CORE_EXTERNAL_IP|SSH_KEY_PATH"

# Re-run Ansible only
cd ansible
ansible-playbook playbooks/site.yml -i inventories/dev.ini
```

### Can't access Forgejo

```bash
# Check firewall rules
gcloud compute firewall-rules list

# SSH to VM and check Docker
ssh -i ~/.ssh/superdeploy_gcp superdeploy@CORE_EXTERNAL_IP
cd /opt/forgejo
docker compose ps
docker compose logs forgejo
```

---

## 📚 Next Steps

1. **Configure application repositories** → `SETUP-PER-APP.md`
2. **Deploy your first app** → `DEPLOYMENT-GUIDE.md`
3. **Production hardening** → `PRODUCTION-CHECKLIST.md`

