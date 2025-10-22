# İlk Kurulum Rehberi

Bu döküman, **hiçbir şey yokken başlayıp**, **tam çalışan bir production sistemi** ayağa kaldırmanı anlatır.

---

## 🎯 Kurulum Sonunda Ne Olacak?

✅ GCP'de 1 VM çalışacak (core services + runner)  
✅ GitHub'a her push otomatik deploy olacak  
✅ Her deployment'tan email alacaksın  
✅ `superdeploy` CLI ile sistemi yönetebileceksin  

**Süre:** ~15 dakika

---

## 📋 Ön Gereksinimler

### **1. Yerel Makinende Olması Gerekenler:**

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

### **2. Hesaplar:**

- ✅ **GCP Account** (Billing aktif)
- ✅ **GitHub Account**
- ✅ **Docker Hub Account** (ücretsiz)
- ✅ **Gmail Account** (email notifications için)

---

## 🔧 Adım 1: GCP Projesini Hazırla

### **1.1. Yeni GCP Projesi Oluştur**

```bash
# GCP Console → New Project → "superdeploy-prod"
# Project ID'yi not al (örn: galvanic-camp-475519-d6)

# gcloud'u yeni projeye bağla
gcloud config set project PROJE_ID
```

### **1.2. Gerekli API'leri Aktif Et**

```bash
gcloud services enable compute.googleapis.com
gcloud services enable storage-api.googleapis.com
```

### **1.3. Service Account Oluştur**

```bash
# Service account oluştur
gcloud iam service-accounts create superdeploy-terraform \
  --display-name="SuperDeploy Terraform"

# Gerekli rolleri ver
gcloud projects add-iam-policy-binding PROJE_ID \
  --member="serviceAccount:superdeploy-terraform@PROJE_ID.iam.gserviceaccount.com" \
  --role="roles/compute.admin"

gcloud projects add-iam-policy-binding PROJE_ID \
  --member="serviceAccount:superdeploy-terraform@PROJE_ID.iam.gserviceaccount.com" \
  --role="roles/iam.serviceAccountUser"

# JSON key indir
gcloud iam service-accounts keys create ~/superdeploy-key.json \
  --iam-account=superdeploy-terraform@PROJE_ID.iam.gserviceaccount.com

# Ortam değişkenine ekle
export GOOGLE_APPLICATION_CREDENTIALS=~/superdeploy-key.json
```

---

## 🔑 Adım 2: SSH Key Oluştur (Deploy Key)

SuperDeploy VM'lere bağlanmak için **deploy-only** SSH key kullanır (şifresiz).

```bash
# Yeni SSH key oluştur (passphrase YOK!)
ssh-keygen -t ed25519 -f ~/.ssh/superdeploy_deploy -N "" -C "superdeploy-deploy"

# Public key'i kontrol et
cat ~/.ssh/superdeploy_deploy.pub
```

**Güvenlik:** Bu key sadece deployment için kullanılır, kişisel dosyalarına erişemez.

---

## 🐳 Adım 3: Docker Hub Token Al

```bash
# Docker Hub → Account Settings → Security → New Access Token
# Token adı: "superdeploy"
# Access: Read, Write, Delete

# Token'ı kopyala: dckr_pat_XXXXX...
```

---

## 📧 Adım 4: Gmail App Password Oluştur

Email bildirimleri için Gmail SMTP kullanacağız.

```bash
# 1. Google Account → Security
# 2. 2-Step Verification (aktif olmalı)
# 3. App Passwords → "SuperDeploy" → Generate
# 4. 16 haneli şifreyi kopyala (örn: "abcd efgh ijkl mnop")
```

---

## 📝 Adım 5: .env Dosyasını Hazırla

```bash
cd superdeploy
cp ENV.example .env
nano .env  # veya vim, code, vb.
```

### **Doldurulması Gerekenler:**

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
GITHUB_TOKEN=ghp_XXXXX...  # GitHub Personal Access Token

# Email
ALERT_EMAIL=your-email@gmail.com
SMTP_PASSWORD=your-gmail-app-password

# Forgejo
FORGEJO_ORG=your-org-name
FORGEJO_ADMIN_PASSWORD=$(openssl rand -base64 24)
```

**Not:** 
- `GITHUB_ORG`: GitHub organizasyon adın (örn: `cheapaio`)
- `SMTP_PASSWORD`: Gmail App Password (16 haneli)
- Database/Queue şifreleri `superdeploy init` ile otomatik oluşturulacak

---

## 🚀 Adım 6: SuperDeploy CLI Kur

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

## 🏗️ Adım 7: Proje Oluştur

**İlk önce projeyi initialize et:**

```bash
superdeploy init -p myproject
```

### **Interactive Sorular:**

```
Add services for this project:
  Services: api,dashboard,services

Network subnet:
  Use auto-assigned subnet? [Y/n]: Y

GitHub organization:
  GitHub org name [myprojectio]: myprojectio

Database configuration:
  Generate secure passwords? [Y/n]: Y

Enable monitoring? [Y/n]: Y

Domain (optional):
  Domain [myproject.example.com]: 
```

### **Sonuç:**

✅ `/opt/apps/myproject/` klasörü oluşturuldu  
✅ Docker Compose dosyaları generate edildi  
✅ Güvenli şifreler oluşturuldu (`.passwords.yml`)  
✅ GitHub secret komutları gösterildi

---

## 🔐 Adım 8: GitHub Secrets Ekle

`superdeploy init` sonunda gösterilen komutları çalıştır:

```bash
# Her servis için (örnek: api)
gh secret set POSTGRES_USER -b "myproject_user" -R myprojectio/api
gh secret set POSTGRES_PASSWORD -b "GENERATED_PASSWORD" -R myprojectio/api
gh secret set POSTGRES_DB -b "myproject_db" -R myprojectio/api
gh secret set POSTGRES_HOST -b "postgres" -R myprojectio/api
gh secret set POSTGRES_PORT -b "5432" -R myprojectio/api

gh secret set RABBITMQ_USER -b "myproject_user" -R myprojectio/api
gh secret set RABBITMQ_PASSWORD -b "GENERATED_PASSWORD" -R myprojectio/api
gh secret set RABBITMQ_HOST -b "rabbitmq" -R myprojectio/api
gh secret set RABBITMQ_PORT -b "5672" -R myprojectio/api

gh secret set REDIS_PASSWORD -b "GENERATED_PASSWORD" -R myprojectio/api
gh secret set REDIS_HOST -b "redis" -R myprojectio/api
gh secret set REDIS_PORT -b "6379" -R myprojectio/api

# Dashboard ve services için de tekrarla
```

**Not:** Şifreler `/opt/apps/myproject/.passwords.yml` dosyasında

---

## 🚀 Adım 9: Infrastructure'ı Deploy Et

**Tek komutla tüm sistem ayağa kalkacak!**

```bash
superdeploy up -p myproject
```

### **Bu Komut Ne Yapar?**

```
[1/8] ⚙️  Terraform init & apply (VM'leri oluşturur)
[2/8] 📝 IP adreslerini .env'e yazar
[3/8] 🔧 Ansible inventory hazırlar
[4/8] 🧹 SSH known_hosts temizler
[5/8] 🚀 Ansible playbook çalıştırır (Docker, Forgejo, monitoring kurulur)
[6/8] 🔐 Forgejo PAT oluşturur
[7/8] 🔄 GitHub secrets'ları sync eder
[8/8] ✅ Tamamlandı!
```

**Süre:** ~10 dakika

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

### **Beklenen Sonuç:**

1. **GitHub Actions:** Build başlayacak (~2 dakika)
2. **Forgejo Actions:** Deploy başlayacak (~1 dakika)
3. **Email:** `cradexco@gmail.com` adresine bildirim gelecek

```
📧 Subject: [SuperDeploy] ✅ api - test: first deployment

Status: ✅ SUCCESS
Service: api
Commit: abc123
...
```

---

## 🎉 Kurulum Tamamlandı!

Artık sistemi kullanmaya hazırsın. Günlük kullanım için `OPERATIONS.md` dosyasına bak.

---

## 🔍 Kurulum Sonrası Kontroller

```bash
# VM'lerin durumunu kontrol et
gcloud compute instances list

# Servislerin durumunu kontrol et
superdeploy status -p cheapa

# Forgejo'ya web browser'dan bağlan
# http://[CORE_EXTERNAL_IP]:3001
# Username: cradexco
# Password: .env dosyasındaki FORGEJO_ADMIN_PASSWORD

# GitHub secrets kontrol et
gh secret list --repo cheapaio/api
```

---

## 🆘 Sorun Giderme

### **"Terraform apply failed"**
- GCP API'leri aktif mi kontrol et
- Service account rollerini kontrol et
- Billing aktif mi kontrol et

### **"SSH connection failed"**
- `~/.ssh/known_hosts` dosyasını temizle: `ssh-keygen -R [IP]`
- SSH key path'i doğru mu kontrol et

### **"Forgejo PAT creation failed"**
- VM çalışıyor mu: `gcloud compute instances list`
- Forgejo container ayakta mı: `ssh superdeploy@[IP] docker ps`

### **"Email gelmiyor"**
- SMTP secrets eklenmiş mi: `gh secret list --repo cheapaio/api`
- Gmail App Password doğru mu
- GitHub Actions log'larını kontrol et

---

**Sonraki adım:** `DEPLOYMENT.md` - Deployment flow detayları

