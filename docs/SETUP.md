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
GCP_PROJECT=galvanic-camp-475519-d6
GCP_REGION=us-central1
GCP_ZONE=us-central1-a

# SSH
SSH_KEY_PATH=~/.ssh/superdeploy_deploy
SSH_PUBLIC_KEY_PATH=~/.ssh/superdeploy_deploy.pub

# Docker Hub
DOCKER_USERNAME=c100394
DOCKER_TOKEN=dckr_pat_XXXXX...

# GitHub (kendi repolarını yaz)
GITHUB_REPO_API=cheapaio/api
GITHUB_REPO_DASHBOARD=cheapaio/dashboard
GITHUB_REPO_SERVICES=cheapaio/services
GITHUB_TOKEN=ghp_XXXXX...  # GitHub Personal Access Token

# Database & Queue
POSTGRES_PASSWORD=$(openssl rand -base64 32)
RABBITMQ_PASSWORD=$(openssl rand -base64 32)
REDIS_PASSWORD=$(openssl rand -base64 32)
API_SECRET_KEY=$(openssl rand -hex 32)

# Email
ALERT_EMAIL=cradexco@gmail.com

# Forgejo
FORGEJO_ORG=cradexco
FORGEJO_ADMIN_PASSWORD=$(openssl rand -base64 24)
```

**Not:** `openssl rand` komutları random şifreler üretir. Manuel de girebilirsin.

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

## 🏗️ Adım 7: Infrastructure'ı Ayağa Kaldır

**Tek komutla tüm sistem ayağa kalkacak!**

```bash
superdeploy up
```

### **Bu Komut Ne Yapar?**

```
[1/8] ⚙️  Terraform init & apply (VM'leri oluşturur)
[2/8] 📝 IP adreslerini .env'e yazar
[3/8] 🔧 Ansible inventory hazırlar
[4/8] 🧹 SSH known_hosts temizler
[5/8] 🚀 Ansible playbook çalıştırır (Docker, Forgejo, Postgres, RabbitMQ kurulur)
[6/8] 🔐 Forgejo PAT oluşturur
[7/8] 🔄 GitHub secrets'ları sync eder
[8/8] ✅ Tamamlandı!
```

**Süre:** ~10 dakika

---

## 📧 Adım 8: SMTP Secrets Ekle (GitHub)

Email bildirimleri için SMTP credentials eklemen gerekiyor:

```bash
# API repo
gh secret set SMTP_USERNAME --repo cheapaio/api --body "cradexco@gmail.com"
gh secret set SMTP_PASSWORD --repo cheapaio/api --body "ajjb ydtw ptpr rflw"

# Dashboard repo
gh secret set SMTP_USERNAME --repo cheapaio/dashboard --body "cradexco@gmail.com"
gh secret set SMTP_PASSWORD --repo cheapaio/dashboard --body "ajjb ydtw ptpr rflw"

# Services repo
gh secret set SMTP_USERNAME --repo cheapaio/services --body "cradexco@gmail.com"
gh secret set SMTP_PASSWORD --repo cheapaio/services --body "ajjb ydtw ptpr rflw"
```

**Not:** `superdeploy up` sonrası otomatik yapılmıyor çünkü Gmail şifresi `.env` dosyasında değil.

---

## ✅ Adım 9: İlk Deployment'ı Test Et

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
superdeploy status

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

