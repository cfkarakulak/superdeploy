# 🚀 SIFIRDAN KURULUM - AKILLI YOL

## 📋 ÖN HAZIRLIK (5 dakika)

```bash
# 1. Gerekli araçları kur
brew install terraform ansible gh jq age google-cloud-sdk

# 2. GCP login
gcloud auth login
gcloud auth application-default login
gcloud config set project YOUR_PROJECT_ID

# 3. GitHub login
gh auth login  # Browser'da login olacak

# 4. SSH key oluştur
ssh-keygen -t ed25519 -f ~/.ssh/superdeploy_gcp
gcloud compute os-login ssh-keys add --key-file ~/.ssh/superdeploy_gcp.pub
```

---

## 🎯 SUPERDEPLOY KURULUM (1 dakika)

```bash
# 1. Repo'yu çek
cd ~/Desktop
git clone https://github.com/cfkarakulak/superdeploy.git
cd superdeploy

# 2. .env oluştur (minimum gerekli)
cat > .env << 'ENVEND'
# GCP
GCP_PROJECT_ID=your-project-id
SSH_KEY_PATH=~/.ssh/superdeploy_gcp
SSH_USER=superdeploy

# Forgejo
FORGEJO_ORG=cradexco
FORGEJO_ADMIN_USER=admin
FORGEJO_ADMIN_PASSWORD=$(openssl rand -base64 16)
FORGEJO_ADMIN_EMAIL=admin@example.com
REPO_SUPERDEPLOY=superdeploy-app

# Docker Hub
DOCKER_REGISTRY=docker.io
DOCKER_ORG=your-dockerhub-username
DOCKER_USERNAME=your-dockerhub-username
DOCKER_TOKEN=your-dockerhub-token

# GitHub
GITHUB_TOKEN=ghp_your_github_token

# Forgejo DB
FORGEJO_DB_USER=superdeploy
FORGEJO_DB_PASSWORD=$(openssl rand -base64 16)
FORGEJO_DB_NAME=forgejo

# Feature Toggles
USE_REMOTE_STATE=false
ENABLE_MONITORING=false
ENABLE_HARDENING=false

# Monitoring
ALERT_EMAIL=your-email@example.com

# App Secrets (generate strong passwords)
POSTGRES_USER=superdeploy
POSTGRES_PASSWORD=$(openssl rand -base64 24)
POSTGRES_DB=superdeploy_db
RABBITMQ_USER=superdeploy
RABBITMQ_PASSWORD=$(openssl rand -base64 24)
REDIS_PASSWORD=$(openssl rand -base64 24)
API_SECRET_KEY=$(openssl rand -hex 32)
ENVEND

# 3. .env'i düzenle (sadece gerçek değerleri ekle)
vim .env  # GCP_PROJECT_ID, DOCKER_TOKEN, GITHUB_TOKEN, ALERT_EMAIL
```

---

## 🚀 DEPLOY! (6 dakika)

```bash
# TEK KOMUT - HER ŞEYİ YAPAR!
make deploy
```

**Bu komut:**
1. ✅ Terraform ile 3 VM kurar
2. ✅ IP'leri .env'e yazar
3. ✅ Ansible ile her şeyi kurar (Docker, Forgejo, Runner, AGE)
4. ✅ Code'u GitHub ve Forgejo'ya pushar

---

## 🎯 CLI KURULUM (10 saniye)

```bash
# CLI'yi global yap
make cli-install

# Test et (her yerden çalışır!)
cd ~
superdeploy status
```

---

## 🔥 SECRET SYNC - MAGIC! (30 saniye)

```bash
# HER ŞEYİ OTOMATİK SYNC ET!
superdeploy sync
```

**Bu komut:**
1. ✅ AGE public key'i VM'den çeker
2. ✅ Forgejo PAT oluşturur (yoksa)
3. ✅ GitHub'a 7 repo secret pushar (api, dashboard, services)
4. ✅ GitHub'a 10-15 environment secret pushar
5. ✅ Production environment hazır!

**Süre:** 30 saniye (manual: 20 dakika!)

---

## ✅ TEST DEPLOY

```bash
# API repo'ya test push (opsiyonel)
cd ~/app-repos/api
git push origin production

# Logs izle
superdeploy logs -a api -f
```

---

## 🎉 TAMAM!

Artık çalışan bir sistem var:
- ✅ Infrastructure: 3 VM (GCP)
- ✅ Forgejo: http://CORE_IP:3001
- ✅ CI/CD: Runner active
- ✅ Secrets: Synced to GitHub
- ✅ CLI: Heroku-level power

---

## 📊 TOPLAM SÜRE

- **İlk setup:** 5 dk (brew, gcloud, gh)
- **Deploy:** 6 dk (make deploy)
- **CLI install:** 10 sn
- **Secret sync:** 30 sn

**TOPLAM:** ~12 dakika (manual: 2 saat!)

---

## 🔧 GÜNLÜK KULLANIM

```bash
# Kod değiştir → push
cd ~/app-repos/api
git push origin production  # Otomatik deploy!

# Logs
superdeploy logs -a api -f

# One-off command
superdeploy run api "python manage.py migrate"

# Scale
superdeploy scale api=3

# Status
superdeploy status

# Deploy specific app
superdeploy deploy -a api -e production

# Promote staging to prod
superdeploy promote abc123 -a api
```

---

## 💡 PRO TIPS

### Secret değişti mi?
```bash
vim ~/Desktop/superdeploy/.env  # Değiştir
superdeploy sync                # Sync et
```

### VM'ler yeniden başladı, IP değişti?
```bash
cd ~/Desktop/superdeploy
make update-ips     # IP'leri güncelle
superdeploy sync    # GitHub'a sync et
```

### Yeni app eklemek?
```bash
# Yakında: superdeploy apps:create my-app --template python-fastapi
# Şimdilik: Manual repo oluştur, superdeploy sync çalıştır
```

