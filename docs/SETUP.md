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

### **Init Komutu Ne Yapar?**

`init` komutu, yeni bir proje için gerekli tüm konfigürasyon dosyalarını ve yapılandırmayı oluşturur:

**1. Proje Yapısı Oluşturulur:**
```bash
projects/myproject/
├── project.yml              # Proje konfigürasyonu
├── .passwords.yml           # Otomatik oluşturulan güvenli şifreler
└── compose/                 # Docker Compose dosyaları (up sonrası)
```

**2. Güvenli Şifreler Oluşturulur:**
- Her servis için benzersiz, 32 karakterlik güvenli şifreler
- Kriptografik olarak güvenli rastgele üretim
- `projects/myproject/.passwords.yml` dosyasına kaydedilir

**3. Proje Konfigürasyonu (project.yml):**
- VM konfigürasyonu (core services)
- Addon tanımları (Forgejo, PostgreSQL, Redis, RabbitMQ, vb.)
- Uygulama servisleri (api, dashboard, services)
- Network ayarları
- Monitoring konfigürasyonu

**4. .env.superdeploy Dosyaları Oluşturulur:**
- Her uygulama repository'si için ayrı dosya
- Infrastructure bağlantı bilgileri (DB, Queue, Cache)
- Otomatik oluşturulan şifreler dahil edilir
- Yerel `.env` dosyaları **ASLA değiştirilmez**

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

✅ `projects/myproject/` klasörü oluşturuldu  
✅ `project.yml` konfigürasyon dosyası hazırlandı  
✅ Güvenli şifreler oluşturuldu (`.passwords.yml`)  
✅ `.env.superdeploy` dosyaları her uygulama için oluşturuldu  
✅ Sistem deployment için hazır

**Önemli:** `init` komutu sadece konfigürasyon dosyalarını oluşturur. Infrastructure'ı deploy etmek için `superdeploy up` komutunu kullanmalısın.

---

## 🔐 Adım 8: .env.superdeploy Dosyalarını Oluştur

`superdeploy init` komutu, her uygulama repository'si için `.env.superdeploy` dosyalarını otomatik olarak oluşturur.

### **Ne Oluşturulur?**

```bash
app-repos/
├── api/.env.superdeploy           # API servisi için production config
├── dashboard/.env.superdeploy     # Dashboard için production config
└── services/.env.superdeploy      # Services için production config
```

### **Dosya İçeriği:**

Her `.env.superdeploy` dosyası, o servisin ihtiyaç duyduğu infrastructure bağlantı bilgilerini içerir:

```bash
# PostgreSQL
POSTGRES_HOST=postgres
POSTGRES_PORT=5432
POSTGRES_USER=myproject_user
POSTGRES_PASSWORD=<otomatik-oluşturulan-şifre>
POSTGRES_DB=myproject_db

# RabbitMQ
RABBITMQ_HOST=rabbitmq
RABBITMQ_PORT=5672
RABBITMQ_USER=myproject_user
RABBITMQ_PASSWORD=<otomatik-oluşturulan-şifre>

# Redis
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_PASSWORD=<otomatik-oluşturulan-şifre>
```

### **Önemli Notlar:**

⚠️ **Yerel .env Dosyaları Korunur:**
- Mevcut `.env` dosyaları **ASLA değiştirilmez**
- Developer'ların yerel geliştirme ortamları etkilenmez
- `.env.superdeploy` sadece production deployment için kullanılır

✅ **Otomatik Yönetim:**
- Bu dosyalar SuperDeploy tarafından yönetilir
- Manuel düzenleme yapma (her sync'te yeniden oluşturulur)
- Şifreler `projects/myproject/.passwords.yml` dosyasından gelir

📝 **Git İgnore:**
- `.env.superdeploy` dosyaları `.gitignore`'a eklenmelidir
- Production secrets asla Git'e commit edilmemelidir

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

## 🔄 Adım 10: Secrets'ları Senkronize Et

Infrastructure deploy edildikten sonra, tüm secrets'ları GitHub ve Forgejo'ya otomatik olarak senkronize etmek için `sync` komutunu kullan.

```bash
superdeploy sync -p myproject
```

### **Sync Komutu Ne Yapar?**

`sync` komutu, yerel konfigürasyon dosyalarındaki secrets'ları GitHub ve Forgejo repository'lerine dağıtır:

**Kaynak Dosyalar (Öncelik Sırasına Göre):**
1. **Kullanıcı .env dosyaları** (--env-file ile belirtilen)
2. **Proje secrets** (`projects/myproject/.passwords.yml`)
3. **Infrastructure secrets** (`superdeploy/.env`)

**Hedef Konumlar:**
- **GitHub Repository Secrets:** Infrastructure seviyesi secrets (FORGEJO_PAT, AGE_PUBLIC_KEY, DOCKER_TOKEN)
- **GitHub Environment Secrets:** Runtime application secrets (POSTGRES_PASSWORD, REDIS_PASSWORD, vb.)
- **Forgejo Repository Secrets:** GitHub Environment Secrets ile aynı (deployment workflow için)

### **Merge Önceliği:**

Aynı secret birden fazla kaynakta varsa, **en yüksek öncelikli kaynak kazanır**:
- Kullanıcı tarafından sağlanan .env dosyaları (en yüksek öncelik)
- Otomatik oluşturulan proje secrets (.passwords.yml)
- Infrastructure secrets (en düşük öncelik)

### **Örnek Kullanım:**

```bash
# Tüm secrets'ları sync et
superdeploy sync -p myproject

# Belirli bir .env dosyası ile sync et (bu değerler öncelikli olur)
superdeploy sync -p myproject --env-file app-repos/api/.env

# Sadece belirli bir repository için sync et
superdeploy sync -p myproject --repo api
```

**Not:** Sync komutu mevcut secrets'ları günceller, silmez. Boş değerler atlanır.

---

## 📝 .env.superdeploy Dosyaları Hakkında

SuperDeploy, uygulama repository'lerinde **iki ayrı .env dosyası** kullanır:

### **1. .env (Yerel Geliştirme)**
- Developer'ın yerel ortamı için
- **SuperDeploy tarafından ASLA değiştirilmez**
- Güvenle düzenleyebilirsin
- Git'e commit edilmez (.gitignore'da)

### **2. .env.superdeploy (Production Override)**
- SuperDeploy tarafından otomatik oluşturulur
- Production deployment için gerekli değerleri içerir
- Infrastructure bağlantı bilgileri (DB, Queue, Cache)
- **Manuel olarak düzenlenmemelidir** (her sync'te yeniden oluşturulur)

### **Deployment Sırasında Ne Olur?**

GitHub Actions deployment workflow'u sırasında:

1. Her iki dosya da okunur (.env ve .env.superdeploy)
2. Değerler birleştirilir
3. **.env.superdeploy değerleri önceliklidir** (production değerleri kazanır)
4. Birleştirilmiş değerler şifrelenir ve Forgejo'ya gönderilir
5. Forgejo runner şifreyi çözer ve container'ları başlatır

### **Dosya Konumları:**

```
app-repos/
└── api/
    ├── .env                    # Yerel dev (ASLA değiştirilmez)
    ├── .env.superdeploy        # Production (otomatik oluşturulur)
    └── .github/workflows/
        └── deploy.yml          # Her iki dosyayı birleştirir
```

### **Örnek İçerik:**

**.env (Yerel Geliştirme):**
```bash
# Developer'ın yerel PostgreSQL'i
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_USER=dev_user
POSTGRES_PASSWORD=dev_password
POSTGRES_DB=myapp_dev

# Yerel Redis
REDIS_HOST=localhost
REDIS_PORT=6379
```

**.env.superdeploy (Production):**
```bash
# Production PostgreSQL (SuperDeploy tarafından yönetilir)
POSTGRES_HOST=postgres
POSTGRES_PORT=5432
POSTGRES_USER=myproject_user
POSTGRES_PASSWORD=<otomatik-oluşturulan-güvenli-şifre>
POSTGRES_DB=myproject_db

# Production Redis
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_PASSWORD=<otomatik-oluşturulan-güvenli-şifre>
```

**Deployment'ta Kullanılan Değerler:**
- `POSTGRES_HOST`: `postgres` (production değeri kazanır)
- `POSTGRES_PASSWORD`: Güvenli şifre (production değeri kazanır)
- Diğer tüm production değerleri .env.superdeploy'dan gelir

### **Neden Bu Yaklaşım?**

✅ **Güvenlik:** Yerel .env'e production secrets karışmaz  
✅ **Esneklik:** Developer yerel ortamını özgürce yapılandırabilir  
✅ **Otomatizasyon:** Production config otomatik yönetilir  
✅ **Hata Önleme:** Yanlışlıkla production secrets commit edilmez

---

## 🔐 Otomatik Oluşturulan Şifreler

`superdeploy init` komutu çalıştırıldığında, tüm servisler için **güvenli, rastgele şifreler** otomatik olarak oluşturulur.

### **Şifrelerin Saklandığı Yer:**

```bash
projects/myproject/.passwords.yml
```

### **Örnek İçerik:**

```yaml
passwords:
  POSTGRES_PASSWORD: "xK9mP2nQ7vL4wR8sT3yU6zB1cD5eF0gH"
  RABBITMQ_PASSWORD: "aB2cD3eF4gH5iJ6kL7mN8oP9qR0sT1uV"
  REDIS_PASSWORD: "wX2yZ3aB4cD5eF6gH7iJ8kL9mN0oP1qR"
  MONGODB_PASSWORD: "sT2uV3wX4yZ5aB6cD7eF8gH9iJ0kL1mN"
  FORGEJO_ADMIN_PASSWORD: "oP2qR3sT4uV5wX6yZ7aB8cD9eF0gH1iJ"
```

### **Şifre Özellikleri:**

- **Uzunluk:** 32 karakter
- **Karakter Seti:** Büyük/küçük harf, rakam
- **Güvenlik:** Kriptografik olarak güvenli rastgele üretim
- **Benzersizlik:** Her servis için farklı şifre

### **Şifreler Nereye Dağıtılır?**

`superdeploy sync` komutu çalıştırıldığında:

1. **GitHub Repository Secrets** → Infrastructure secrets (FORGEJO_PAT, AGE_KEY)
2. **GitHub Environment Secrets** → Application secrets (DB, Queue, Cache şifreleri)
3. **Forgejo Repository Secrets** → Deployment için gerekli secrets
4. **.env.superdeploy dosyaları** → Her uygulama repository'sinde

### **Şifreleri Manuel Değiştirme:**

Eğer bir şifreyi değiştirmek istersen:

```bash
# 1. .passwords.yml dosyasını düzenle
nano projects/myproject/.passwords.yml

# 2. Yeni şifreyi ekle veya mevcut şifreyi değiştir
# POSTGRES_PASSWORD: "yeni-güvenli-şifre"

# 3. Secrets'ları yeniden sync et
superdeploy sync -p myproject

# 4. Servisleri yeniden başlat (yeni şifre ile)
superdeploy restart -p myproject
```

**Önemli:** Şifre değiştirirken, hem GitHub/Forgejo secrets'larını hem de çalışan container'ları güncellemelisin.

### **Şifre Güvenliği:**

⚠️ **Dikkat Edilmesi Gerekenler:**
- `.passwords.yml` dosyasını **asla Git'e commit etme**
- Dosya izinlerini kontrol et: `chmod 600 projects/myproject/.passwords.yml`
- Düzenli olarak şifreleri rotate et (özellikle production'da)
- Backup'larını güvenli bir yerde sakla (şifreli)

✅ **SuperDeploy Güvenlik Önlemleri:**
- Şifreler GitHub/Forgejo'da encrypted secrets olarak saklanır
- Deployment sırasında AGE encryption kullanılır
- Container'lar arası iletişimde environment variable'lar kullanılır
- Log dosyalarında şifreler maskelenir

---

## ✅ Adım 11: İlk Deployment'ı Test Et

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

