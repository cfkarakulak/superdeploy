# İlk Kurulum Rehberi

Bu döküman, **hiçbir şey yokken başlayıp**, **tam çalışan bir production sistemi** ayağa kaldırmanı anlatır.

---

## 🎯 Kurulum Sonunda Ne Olacak?

✅ Orchestrator VM çalışacak (Forgejo + Monitoring + Caddy)  
✅ Proje VM'leri çalışacak  
✅ GitHub'a her push otomatik deploy olacak  
✅ Subdomain'ler ile SSL'li erişim (forgejo.domain.com, grafana.domain.com)  
✅ `superdeploy` CLI ile sistemi yönetebileceksin  

**Süre:** ~20 dakika

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

# GitHub CLI
gh --version
```

### Hesaplar

- ✅ **GCP Account** (Billing aktif)
- ✅ **GitHub Account**
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

## 🐳 Adım 3: Docker Hub Token Al

```bash
# Docker Hub → Account Settings → Security → New Access Token
# Token adı: "superdeploy"
# Access: Read, Write, Delete

# Token'ı kopyala: dckr_pat_XXXXX...
```

---

## 📝 Adım 4: .env Dosyasını Hazırla

```bash
cd superdeploy
cp ENV.example .env
nano .env
```

### Doldurulması Gerekenler

```bash
# GCP
GCP_PROJECT=your-gcp-project-id
GCP_REGION=us-central1
GCP_ZONE=us-central1-a

# SSH
SSH_KEY_PATH=~/.ssh/superdeploy_deploy
SSH_PUBLIC_KEY_PATH=~/.ssh/superdeploy_deploy.pub

# Docker Hub
DOCKER_USERNAME=your-dockerhub-username
DOCKER_TOKEN=dckr_pat_XXXXX...

# GitHub
GITHUB_ORG=your-github-org
GITHUB_TOKEN=ghp_XXXXX...

# Forgejo
FORGEJO_ORG=your-org-name
FORGEJO_ADMIN_PASSWORD=$(openssl rand -base64 24)
```

---

## 🚀 Adım 5: SuperDeploy CLI Kur

```bash
cd superdeploy

# Virtual environment oluştur
python3 -m venv venv
source venv/bin/activate

# Bağımlılıkları yükle
pip install -e .

# CLI test et
superdeploy --version
```

---

## 🏗️ Adım 6: Orchestrator Kurulumu

### 6.1. Orchestrator Projesi Oluştur

```bash
superdeploy init -p orchestrator
```

### 6.2. Orchestrator project.yml Düzenle

```yaml
project: orchestrator
description: Global Forgejo orchestrator for all projects

cloud:
  gcp:
    project_id: "your-gcp-project"
    region: "us-central1"
    zone: "us-central1-a"

vms:
  orchestrator:
    count: 1
    machine_type: e2-medium
    disk_size: 50
    preserve_ip: true
    services:
      - forgejo
      - monitoring
      - caddy

addons:
  forgejo:
    version: "1.21.0"
    port: 3001
    ssh_port: 2222
    admin_user: "admin"
    admin_email: "admin@yourdomain.com"
    org: "myorg"
    repo: "superdeploy"
  
  monitoring:
    prometheus_port: 9090
    grafana_port: 3000
  
  caddy:
    domain: "yourdomain.com"
    email: "admin@yourdomain.com"
    subdomains:
      forgejo: "forgejo"
      grafana: "grafana"
      prometheus: "prometheus"

apps: {}
```

### 6.3. Orchestrator'ı Deploy Et

```bash
superdeploy orchestrator up
```

**Bu komut ne yapar?**
- Orchestrator VM oluşturur
- Forgejo + PostgreSQL kurar
- Prometheus + Grafana kurar
- Caddy reverse proxy kurar (SSL sertifikaları ile)
- Orchestrator runner kurar

**Süre:** ~8 dakika

### 6.4. Orchestrator IP'sini Not Al

```bash
cat projects/orchestrator/.env | grep ORCHESTRATOR_EXTERNAL_IP
# Örnek: 34.72.179.175
```

### 6.5. DNS Kayıtlarını Ekle

Orchestrator IP'si için A kayıtları ekle:

```
forgejo.yourdomain.com    A    34.72.179.175
grafana.yourdomain.com    A    34.72.179.175
prometheus.yourdomain.com A    34.72.179.175
```

**Not:** DNS propagation ~5-10 dakika sürebilir.

---

## 🚀 Adım 7: Proje Oluştur

```bash
superdeploy init -p myproject
```

### Init Komutu Ne Yapar?

**1. Proje Yapısı Oluşturulur:**
```bash
projects/myproject/
├── project.yml              # Proje konfigürasyonu
├── .passwords.yml           # Otomatik oluşturulan güvenli şifreler
└── compose/                 # Docker Compose dosyaları
```

**2. Güvenli Şifreler Oluşturulur:**
- Her servis için benzersiz, 32 karakterlik güvenli şifreler
- Kriptografik olarak güvenli rastgele üretim

**3. Proje Konfigürasyonu (project.yml):**
- VM konfigürasyonu
- Addon tanımları (Forgejo, PostgreSQL, Redis, RabbitMQ)
- Uygulama servisleri
- Network ayarları

### Interactive Sorular

```
Add services for this project:
  Services: api,dashboard

VM configuration:
  VM roles: web,api

Services per VM:
  web VM services: postgres,redis
  api VM services: (none)

Orchestrator IP:
  Orchestrator IP: 34.72.179.175

Network subnet:
  Use auto-assigned subnet? [Y/n]: Y

GitHub organization:
  GitHub org name: myprojectio

Generate secure passwords? [Y/n]: Y
```

### Sonuç

✅ `projects/myproject/` klasörü oluşturuldu  
✅ `project.yml` konfigürasyon dosyası hazırlandı  
✅ Güvenli şifreler oluşturuldu (`.passwords.yml`)  
✅ Sistem deployment için hazır

---

## 🚀 Adım 8: Infrastructure'ı Deploy Et

```bash
superdeploy up -p myproject
```

### Bu Komut Ne Yapar?

```
[1/8] ⚙️  Terraform init & apply (VM'leri oluşturur)
[2/8] 📝 IP adreslerini .env'e yazar
[3/8] 🔧 Ansible inventory hazırlar
[4/8] 🧹 SSH known_hosts temizler
[5/8] 🚀 Ansible playbook çalıştırır
      ├── VM-specific addon filtering
      ├── Container deployment
      └── Forgejo runner kurulumu (orchestrator'a register)
[6/8] 🔐 Orchestrator Forgejo PAT oluşturur
[7/8] 🔄 GitHub secrets'ları sync eder
[8/8] ✅ Tamamlandı!
```

**Süre:** ~8 dakika

---

## 🔄 Adım 9: Secrets'ları Senkronize Et

```bash
superdeploy sync -p myproject
```

### Sync Komutu Ne Yapar?

**Kaynak Dosyalar:**
1. Kullanıcı .env dosyaları (--env-file ile belirtilen)
2. Proje secrets (`projects/myproject/.passwords.yml`)
3. Infrastructure secrets (`superdeploy/.env`)

**Hedef Konumlar:**
- **GitHub Repository Secrets:** Infrastructure secrets
- **GitHub Environment Secrets:** Runtime secrets
- **Forgejo Repository Secrets:** Deployment secrets

### Örnek Kullanım

```bash
# Tüm secrets'ları sync et
superdeploy sync -p myproject

# Belirli bir .env dosyası ile
superdeploy sync -p myproject --env-file app-repos/api/.env
```

---

## 📝 .env.superdeploy Dosyaları Hakkında

SuperDeploy, uygulama repository'lerinde **iki ayrı .env dosyası** kullanır:

### 1. .env (Yerel Geliştirme)
- Developer'ın yerel ortamı için
- **SuperDeploy tarafından ASLA değiştirilmez**
- Git'e commit edilmez

### 2. .env.superdeploy (Production Override)
- SuperDeploy tarafından otomatik oluşturulur
- Production deployment için gerekli değerleri içerir
- **Manuel olarak düzenlenmemelidir**

### Deployment Sırasında Ne Olur?

1. Her iki dosya da okunur
2. Değerler birleştirilir
3. **.env.superdeploy değerleri önceliklidir**
4. Birleştirilmiş değerler şifrelenir
5. Forgejo runner şifreyi çözer

### Örnek İçerik

**.env (Yerel):**
```bash
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_USER=dev_user
```

**.env.superdeploy (Production):**
```bash
POSTGRES_HOST=postgres
POSTGRES_PORT=5432
POSTGRES_USER=myproject_user
POSTGRES_PASSWORD=<güvenli-şifre>
```

---

## 🔐 Otomatik Oluşturulan Şifreler

`superdeploy init` komutu tüm servisler için **güvenli, rastgele şifreler** oluşturur.

### Şifrelerin Saklandığı Yer

```bash
projects/myproject/.passwords.yml
```

### Örnek İçerik

```yaml
passwords:
  POSTGRES_PASSWORD: "xK9mP2nQ7vL4wR8sT3yU6zB1cD5eF0gH"
  RABBITMQ_PASSWORD: "aB2cD3eF4gH5iJ6kL7mN8oP9qR0sT1uV"
  REDIS_PASSWORD: "wX2yZ3aB4cD5eF6gH7iJ8kL9mN0oP1qR"
  FORGEJO_ADMIN_PASSWORD: "oP2qR3sT4uV5wX6yZ7aB8cD9eF0gH1iJ"
```

### Şifre Özellikleri

- **Uzunluk:** 32 karakter
- **Karakter Seti:** Büyük/küçük harf, rakam
- **Güvenlik:** Kriptografik olarak güvenli
- **Benzersizlik:** Her servis için farklı

### Şifreler Nereye Dağıtılır?

1. **GitHub Repository Secrets**
2. **GitHub Environment Secrets**
3. **Orchestrator Forgejo Repository Secrets**
4. **.env.superdeploy dosyaları**

### Şifreleri Manuel Değiştirme

```bash
# 1. .passwords.yml dosyasını düzenle
nano projects/myproject/.passwords.yml

# 2. Secrets'ları yeniden sync et
superdeploy sync -p myproject

# 3. Servisleri yeniden başlat
superdeploy restart -p myproject
```

---

## ✅ Adım 10: İlk Deployment'ı Test Et

```bash
cd ../app-repos/api

# Küçük bir değişiklik yap
echo "# Test deployment" >> README.md

# Production'a push et
git add README.md
git commit -m "test: first deployment"
git push origin production
```

### Beklenen Sonuç

1. **GitHub Actions:** Build başlayacak (~2 dakika)
2. **Orchestrator Forgejo:** Workflow'u alacak
3. **Project VM Runner:** Deploy başlayacak (~1 dakika)
4. Container çalışacak

---

## 🎉 Kurulum Tamamlandı!

Artık sistemi kullanmaya hazırsın.

---

## 🔍 Kurulum Sonrası Kontroller

```bash
# VM'lerin durumunu kontrol et
gcloud compute instances list

# Orchestrator durumunu kontrol et
superdeploy orchestrator status

# Proje durumunu kontrol et
superdeploy status -p myproject

# Forgejo'ya web browser'dan bağlan (subdomain ile)
# https://forgejo.yourdomain.com

# Grafana'ya bağlan
# https://grafana.yourdomain.com

# GitHub secrets kontrol et
gh secret list --repo myprojectio/api

# Runner'ları kontrol et (Forgejo UI'da)
# https://forgejo.yourdomain.com/admin/actions/runners
```

---

## 🆘 Sorun Giderme

### "Terraform apply failed"
- GCP API'leri aktif mi kontrol et
- Service account rollerini kontrol et
- Billing aktif mi kontrol et

### "SSH connection failed"
- `~/.ssh/known_hosts` dosyasını temizle
- SSH key path'i doğru mu kontrol et

### "Forgejo PAT creation failed"
- Orchestrator VM çalışıyor mu kontrol et
- Orchestrator Forgejo container ayakta mı kontrol et
- `superdeploy orchestrator status` ile kontrol et

---

**Sonraki adım:** `OPERATIONS.md` - Günlük operasyonlar
