# İlk Kurulum Rehberi

Bu döküman, **hiçbir şey yokken başlayıp**, **tam çalışan bir production sistemi** ayağa kaldırmanı anlatır.

---

## 🎯 Kurulum Sonunda Ne Olacak?

✅ Proje VM'leri çalışacak (apps + infrastructure)  
✅ GitHub Actions ile otomatik deployment  
✅ Self-hosted GitHub runners her VM'de  
✅ `superdeploy` CLI ile sistemi yönetebileceksin  

**Süre:** ~15 dakika

---

## 📋 Ön Gereksinimler

### Yerel Makinende Olması Gerekenler

```bash
# Python 3.9+
python3 --version

# Terraform
terraform --version

# Ansible
ansible --version

# Google Cloud SDK
gcloud --version

# GitHub CLI (authenticated!)
gh --version
gh auth status
```

### Hesaplar

- ✅ **GCP Account** (Billing aktif)
- ✅ **GitHub Account** (authenticated with `gh`)
- ✅ **Docker Hub Account** (ücretsiz)

---

## 🔧 Adım 1: GCP Projesini Hazırla

### 1.1. Yeni GCP Projesi Oluştur

```bash
# GCP Console → New Project
# Project ID'yi not al

# gcloud'u yeni projeye bağla
gcloud config set project PROJE_ID
```

### 1.2. Gerekli API'leri Aktif Et

```bash
gcloud services enable compute.googleapis.com
gcloud services enable storage-api.googleapis.com
```

### 1.3. Service Account Oluştur

```bash
# Service account oluştur
gcloud iam service-accounts create superdeploy-terraform \
  --display-name="SuperDeploy Terraform"

# Gerekli rolleri ver
gcloud projects add-iam-policy-binding PROJE_ID \
  --member="serviceAccount:superdeploy-terraform@PROJE_ID.iam.gserviceaccount.com" \
  --role="roles/compute.admin"

# JSON key indir
gcloud iam service-accounts keys create ~/superdeploy-key.json \
  --iam-account=superdeploy-terraform@PROJE_ID.iam.gserviceaccount.com

# Ortam değişkenine ekle
export GOOGLE_APPLICATION_CREDENTIALS=~/superdeploy-key.json
```

---

## 🔑 Adım 2: SSH Key Oluştur

```bash
# Yeni SSH key oluştur (passphrase YOK!)
ssh-keygen -t ed25519 -f ~/.ssh/superdeploy_deploy -N "" -C "superdeploy-deploy"

# Public key'i kontrol et
cat ~/.ssh/superdeploy_deploy.pub
```

---

## 📦 Adım 3: SuperDeploy CLI Kur

```bash
# Repo'yu clone et
git clone https://github.com/cfkarakulak/superdeploy.git
cd superdeploy

# Virtual environment oluştur
python3 -m venv venv
source venv/bin/activate

# Kurulum yap
pip install -e .

# Test et
superdeploy --version
```

---

## 🎯 Adım 4: İlk Projeyi Oluştur

### 4.1. Proje Dizinini Oluştur

```bash
cd superdeploy
mkdir -p projects/myproject
```

### 4.2. config.yml Oluştur

```yaml
# projects/myproject/config.yml

project: myproject
description: "My production project"
region: us-central1

# GitHub configuration
github:
  organization: myorg  # GitHub organization or username

# Cloud provider
cloud:
  gcp:
    project_id: "your-gcp-project-id"
    region: "us-central1"
    zone: "us-central1-a"

# Virtual machines
vms:
  core:
    machine_type: e2-medium
    disk_size: 20
    services:
      - postgres
      - rabbitmq
  
  app:
    machine_type: e2-medium
    disk_size: 30
    services: []  # No infrastructure services, only apps

# Applications
apps:
  api:
    path: "~/code/myorg/api"
    vm: app
  
  storefront:
    path: "~/code/myorg/storefront"
    vm: app

# Network configuration
network:
  docker_subnet: "172.30.0.0/24"
```

### 4.3. secrets.yml Oluştur

```yaml
# projects/myproject/secrets.yml

secrets:
  shared:
    # Docker Hub credentials
    DOCKER_REGISTRY: docker.io
    DOCKER_ORG: myorg
    DOCKER_USERNAME: myusername
    DOCKER_TOKEN: dckr_pat_xxx  # Docker Hub access token
    
    # Infrastructure passwords (auto-generated ile de değiştirebilirsin)
    POSTGRES_PASSWORD: secure_password_here
    RABBITMQ_PASSWORD: secure_password_here
    
    # GCP
    GCP_PROJECT_ID: your-gcp-project-id
    GCP_REGION: us-central1
    
    # SSH
    SSH_KEY_PATH: ~/.ssh/superdeploy_deploy
    SSH_USER: superdeploy
  
  api:
    # API-specific secrets
    DATABASE_URL: postgres://user:pass@core-internal-ip:5432/mydb
    REDIS_URL: redis://core-internal-ip:6379
    SECRET_KEY: your-secret-key
  
  storefront:
    # Storefront-specific secrets
    NEXT_PUBLIC_API_URL: https://api.myproject.com
```

---

## 🚀 Adım 5: GitHub Runner Token Al

GitHub self-hosted runner token gerekli:

```bash
# Organization-level token (önerilen):
# https://github.com/organizations/myorg/settings/actions/runners/new

# Veya repository-level token:
# https://github.com/myorg/myrepo/settings/actions/runners/new

# Token'ı kopyala (48 saat geçerli)
# Örnek: A1B2C3D4E5F6G7H8I9J0...
```

---

## 🏗️ Adım 6: Infrastructure Deploy Et

```bash
# Deploy başlat (GitHub runners otomatik register olacak REPOSITORY_TOKEN ile)
superdeploy myproject:up

# Ne olacak:
# ✓ Terraform: GCP'de VM'ler oluşturulacak
# ✓ Ansible: Docker, Node.js kurulacak
# ✓ GitHub runner kurulacak ve otomatik register edilecek
#   - REPOSITORY_TOKEN ile GitHub API'den registration token alınacak
#   - Labels: [self-hosted, superdeploy, myproject, app/core]
# ✓ Infrastructure addons deploy edilecek (postgres, rabbitmq)
# ✓ .project file oluşturulacak (runner validation için)

# Süre: ~10 dakika
# NOT: GITHUB_RUNNER_TOKEN'a gerek yok, REPOSITORY_TOKEN yeterli!
```

---

## 🔐 Adım 7: Secrets'ları GitHub'a Sync Et

```bash
# GitHub'a secrets'ları gönder
superdeploy myproject:sync

# Ne olacak:
# ✓ Repository secrets set edilecek (Docker credentials)
# ✓ Environment secrets set edilecek (app configuration)
# ✓ Her app için production environment oluşturulacak
```

---

## 📝 Adım 8: App Repo'larını Hazırla

### 8.1. Deployment Workflow'ları Generate Et

```bash
# Tüm app'ler için workflow'ları oluştur
superdeploy myproject:generate

# Ne olacak:
# ✓ Her app repo'sunda .superdeploy marker file oluşturulacak
# ✓ Her app repo'sunda .github/workflows/deploy.yml oluşturulacak
# ✓ App type'a göre (Python, Next.js) optimize edilmiş workflow
```

### 8.2. App Repo'larına Commit Et

```bash
# API repo
cd ~/code/myorg/api
git add .superdeploy .github/workflows/deploy.yml
git commit -m "Add SuperDeploy deployment"
git push origin main

# Storefront repo
cd ~/code/myorg/storefront
git add .superdeploy .github/workflows/deploy.yml
git commit -m "Add SuperDeploy deployment"
git push origin main
```

---

## 🎉 Adım 9: İlk Deployment!

```bash
# Production branch'e push et
cd ~/code/myorg/api
git checkout -b production
git push origin production

# GitHub Actions başlayacak:
# 1. Build job: Docker image build + push
# 2. Deploy job: Self-hosted runner'da deployment

# GitHub'da izle:
# https://github.com/myorg/api/actions
```

---

## ✅ Doğrulama

### Infrastructure'ı Kontrol Et

```bash
# VM'lerin durumunu kontrol et
superdeploy myproject:status

# VM'lere SSH ile bağlan
ssh superdeploy@<VM_EXTERNAL_IP>

# Docker container'ları kontrol et
docker ps

# GitHub runner durumunu kontrol et
sudo systemctl status github-runner
```

### GitHub Runner'ları Kontrol Et

GitHub Settings → Actions → Runners'da runner'ları göreceksin:

```
✅ myproject-app-0 (Idle)
   Labels: self-hosted, superdeploy, myproject, app

✅ myproject-core-0 (Idle)
   Labels: self-hosted, superdeploy, myproject, core
```

### Deployment'ı Test Et

```bash
# API'ye request at
curl http://<APP_VM_EXTERNAL_IP>:8000/health

# Veya domain üzerinden (eğer DNS set ettiysen)
curl https://api.myproject.com/health
```

---

## 🔧 Troubleshooting

### Runner Kayıt Olmuyor

```bash
# REPOSITORY_TOKEN'ı kontrol et:
# 1. secrets.yml'de REPOSITORY_TOKEN var mı?
# 2. Token scope'ları doğru mu? (admin:org gerekli)
# 3. Token expire olmamış mı?

# Token'ı yenile ve tekrar dene:
# - GitHub Settings → Developer settings → Personal access tokens
# - Required scopes: repo, workflow, packages, admin:org (manage_runners)
superdeploy myproject:up
```

### Deployment Başarısız

```bash
# VM'ye SSH ile bağlan
ssh superdeploy@<VM_IP>

# Runner logs'u kontrol et
sudo journalctl -u github-runner -f

# Docker logs'u kontrol et
cd /opt/superdeploy/projects/myproject/compose
docker compose logs -f
```

### Secret'lar Görünmüyor

```bash
# GitHub CLI authenticated mi kontrol et
gh auth status

# Tekrar sync dene
superdeploy myproject:sync
```

---

## 📚 Sonraki Adımlar

### DNS Konfigürasyonu

```bash
# VM IP'lerini al
superdeploy myproject:status

# DNS record'larını ekle:
# api.myproject.com → <APP_VM_IP>
# storefront.myproject.com → <APP_VM_IP>
```

### SSL Sertifikaları

Caddy addon ekleyerek otomatik SSL:

```yaml
# config.yml
vms:
  app:
    services:
      - caddy  # Otomatik Let's Encrypt SSL
```

### Monitoring Ekle

```yaml
# config.yml
vms:
  monitoring:
    machine_type: e2-small
    disk_size: 20
    services:
      - prometheus
      - grafana
```

---

## 🎊 Tebrikler!

Artık tam çalışan bir production deployment sisteminiz var!

**Ne kazandınız:**
- ✅ GitHub Actions ile otomatik deployment
- ✅ Self-hosted runner'lar ile direkt VM deployment
- ✅ Label-based routing ile guaranteed project isolation
- ✅ Secret management
- ✅ Infrastructure as Code
- ✅ Zero-downtime deployments

**Şimdi ne yapabilirsiniz:**
- `git push` ile deploy edin
- Yeni app'ler ekleyin
- Yeni projeler oluşturun
- Infrastructure'ı ölçeklendirin
