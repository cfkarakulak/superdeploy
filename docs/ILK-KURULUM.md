# 🚀 SuperDeploy - İlk Kurulum Kılavuzu

## Ön Hazırlık

### Gereksinimler

**Yerel Bilgisayarınızda:**
- Python 3.9+
- Git
- Terraform
- Ansible
- Google Cloud SDK (gcloud)
- GitHub CLI (gh)

**Cloud Tarafı:**
- Google Cloud Platform hesabı ve aktif project
- GitHub hesabı
- Docker Hub hesabı (veya GitHub Container Registry)

### Kurulum Komutları (macOS)

```bash
brew install python git terraform ansible google-cloud-sdk gh
```

## Adım 1: Repository'leri Klonlayın

```bash
# SuperDeploy (orchestration)
git clone https://github.com/cfkarakulak/superdeploy.git
cd superdeploy

# Uygulama repository'leri (örnek)
cd ../
git clone https://github.com/cheapaio/api.git app-repos/api
git clone https://github.com/cheapaio/dashboard.git app-repos/dashboard
git clone https://github.com/cheapaio/services.git app-repos/services
```

## Adım 2: SuperDeploy CLI Kurulumu

```bash
cd superdeploy

# Python virtual environment
python3 -m venv venv
source venv/bin/activate

# CLI'yı yükle
pip install -e .

# Test et
superdeploy --version
```

Başarılı olursa `SuperDeploy CLI v1.0.0` gibi bir çıktı göreceksiniz.

## Adım 3: GCP Ayarları

### Project Seçimi ve Yetkilendirme

```bash
# Google Cloud'a giriş
gcloud auth login
gcloud auth application-default login

# Project seçimi
gcloud config set project YOUR_PROJECT_ID

# Gerekli API'leri etkinleştir
gcloud services enable compute.googleapis.com
gcloud services enable storage-api.googleapis.com
```

### Service Account (Opsiyonel, Önerilen)

Production kullanımda kişisel account yerine service account kullanın:

```bash
gcloud iam service-accounts create superdeploy-sa \
    --description="SuperDeploy deployment account" \
    --display-name="SuperDeploy"

gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
    --member="serviceAccount:superdeploy-sa@YOUR_PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/compute.admin"

gcloud iam service-accounts keys create ~/superdeploy-key.json \
    --iam-account superdeploy-sa@YOUR_PROJECT_ID.iam.gserviceaccount.com

export GOOGLE_APPLICATION_CREDENTIALS=~/superdeploy-key.json
```

## Adım 4: GitHub Ayarları

### Personal Access Token Oluşturma

1. GitHub → Settings → Developer settings → Personal access tokens → Tokens (classic)
2. "Generate new token (classic)"
3. Scope seçimleri:
   - `repo` (full control)
   - `workflow` (update workflows)
   - `admin:org` → `read:org` (eğer organization kullanıyorsanız)
4. Token'ı kopyalayın (bir daha göremezsiniz!)

### GitHub CLI Giriş

```bash
gh auth login
# GitHub.com seçin
# HTTPS seçin
# Paste your authentication token
```

## Adım 5: Docker Hub Ayarları

```bash
# Docker Hub'a giriş yapın ve Access Token oluşturun
# https://hub.docker.com/settings/security

# Token'ı not edin, aşağıda kullanacağız
```

## Adım 6: İnteraktif Setup

SuperDeploy CLI, tüm gerekli ayarları interaktif olarak yapmanızı sağlar:

```bash
superdeploy init
```

Bu komut şunları yapar:

### 6.1. GCP Project Detection
Otomatik olarak mevcut project'inizi bulur ve onayınızı ister.

### 6.2. SSH Key Oluşturma
Deployment için passphrase-free bir SSH key oluşturur (`~/.ssh/superdeploy_deploy`).

### 6.3. Password Generation
PostgreSQL, RabbitMQ, Redis ve API için güvenli, rastgele passwordler oluşturur.

### 6.4. Forgejo Admin Kurulumu
Forgejo için admin kullanıcı adı ve email ayarlar.

### 6.5. .env Dosyası Oluşturma
Tüm ayarları `.env` dosyasına kaydeder.

**Örnek Çıktı:**

```
╔══════════════════════════════════════╗
║ 🚀 SuperDeploy Setup Wizard          ║
╚══════════════════════════════════════╝

1. GCP Project ID
Detected: galvanic-camp-475519-d6
✅ Using detected project

2. SSH User
Enter SSH username for VMs [superdeploy]: 

3. Generate Passwords
Generating strong, random passwords...
✅ Passwords generated!

4. Forgejo Admin Email
Enter Forgejo Admin Email [admin@example.com]: admin@superdeploy.io

5. SSH Key Pair
Generating new SSH key pair at ~/.ssh/superdeploy_deploy...
✅ SSH key pair generated!

6. Finalizing .env
Writing all configurations to .env...
✅ .env file created successfully!

Next steps:
  1. Review your .env file for any adjustments.
  2. Run: superdeploy up to deploy your infrastructure.
  3. Run: superdeploy sync to push secrets to GitHub.
```

## Adım 7: .env Dosyasını Kontrol Edin

```bash
cat .env
```

Önemli değerleri kontrol edin:
- `GCP_PROJECT_ID`: Doğru project
- `GCP_REGION`: İstediğiniz region (varsayılan: us-central1)
- `GITHUB_TOKEN`: Kopyaladığınız token
- `DOCKER_USERNAME` ve `DOCKER_TOKEN`: Docker Hub bilgileri
- Passwordler: Güçlü ve unique olmalı

**Eksik olan değerleri manuel ekleyin:**

```bash
# .env dosyasını düzenle
nano .env

# Ekle:
GITHUB_TOKEN=ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
DOCKER_USERNAME=your-dockerhub-username
DOCKER_TOKEN=dckr_pat_xxxxxxxxxxxxxxxxxxxxxxxx
```

## Adım 8: Infrastructure Deployment

Şimdi GCP'de VM'leri oluşturup konfigüre edin:

```bash
superdeploy up
```

Bu komut yaklaşık 10-15 dakika sürer ve şunları yapar:

### 8.1. Terraform Provisioning (~3 dakika)
- VM'leri oluşturur (Core, Scrape, Proxy)
- Network ayarlarını yapar
- Firewall kurallarını ekler
- IP adreslerini `.env` dosyasına kaydeder

### 8.2. Ansible Configuration (~5-7 dakika)
- Docker ve bağımlılıkları kurar
- Forgejo ve runner'ı kurar
- PostgreSQL, RabbitMQ, Redis container'larını başlatır
- System güvenlik ayarlarını yapar

### 8.3. Git Push (~1 dakika)
- SuperDeploy kodunu hem GitHub'a hem Forgejo'ya push eder
- Forgejo repository'si hazır hale gelir

**Başarılı Deployment Çıktısı:**

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🎉 Infrastructure Deployed!
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🌐 Forgejo:    http://34.61.244.204:3001
👤 Login:      admin / SuperSecurePass123!

Next step: superdeploy sync
```

## Adım 9: Secret Synchronization

GitHub repository'lerinize otomatik olarak tüm secret'ları push edin:

```bash
superdeploy sync
```

Bu komut şunları yapar:

### 9.1. AGE Public Key Fetch
Forgejo runner'daki encryption key'ini alır.

### 9.2. Forgejo PAT Creation
Forgejo API için Personal Access Token oluşturur ve `.env`'e kaydeder.

### 9.3. GitHub Secrets Push
Her uygulama repository'sine (api, dashboard, services) şunları ekler:

**Repository Secrets:**
- `AGE_PUBLIC_KEY`: Environment şifrelemesi için
- `FORGEJO_BASE_URL`: Deployment endpoint
- `FORGEJO_ORG`: Organization adı
- `FORGEJO_PAT`: API authentication
- `DOCKER_USERNAME`, `DOCKER_TOKEN`: Image push için

**Environment Secrets (production):**
- `POSTGRES_*`: Database bağlantı bilgileri
- `RABBITMQ_*`: Message queue ayarları
- `REDIS_*`: Cache ayarları
- `API_SECRET_KEY`: JWT signing key
- `PUBLIC_URL`: Frontend URL

**Başarılı Sync Çıktısı:**

```
━━━ API (cheapaio/api) ━━━
  ✓ AGE_PUBLIC_KEY
  ✓ FORGEJO_BASE_URL
  ✓ FORGEJO_PAT
  ...

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🎉 Sync Complete!
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Next steps:
  1. Push to GitHub: git push origin production
  2. Deployment will auto-trigger!
```

## Adım 10: İlk Deployment

Her uygulama için `production` branch'ine push yaptığınızda otomatik deployment başlar:

```bash
cd ../app-repos/api
git checkout -b production
git push origin production
```

GitHub Actions şunları yapar:
1. Docker image build eder
2. Docker Hub'a push eder
3. Environment variable'ları şifreler
4. Forgejo'yu tetikler

Forgejo Actions şunları yapar:
1. Şifreyi açar
2. Image'ı VM'e çeker
3. `docker compose up -d` ile deploy eder
4. Health check yapar
5. Email notification gönderir

## Adım 11: Doğrulama

Sistem durumunu kontrol edin:

```bash
superdeploy status
```

**Başarılı Çıktı:**

```
SuperDeploy Infrastructure Status
┏━━━━━━━━━━━┳━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Component ┃ Status     ┃ Details                       ┃
┡━━━━━━━━━━━╇━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ Core VM   │ ✅ Running │ 34.61.244.204 (up 41 minutes) │
│ Forgejo   │ ✅ Active  │ v13.0.1                       │
│ Runner    │ ✅ Active  │ core-runner                   │
└───────────┴────────────┴───────────────────────────────┘

🌐 Access URLs:
  Forgejo:    http://34.61.244.204:3001
  API:        http://34.61.244.204:8000
  Dashboard:  http://34.61.244.204
```

Uygulamanızı test edin:

```bash
curl http://34.61.244.204:8000/health
# {"status": "healthy", "timestamp": "2025-10-21T12:34:56Z"}
```

## Sorun Giderme

### "Permission denied (publickey)" Hatası

SSH key'iniz GCP'ye eklenmemiş:

```bash
cat ~/.ssh/superdeploy_deploy.pub
# Bu key'i GCP Console → Compute Engine → Metadata → SSH Keys'e ekleyin
```

### "Failed to connect to Forgejo" Hatası

Firewall port 3001'i açık değil:

```bash
# Terraform yeniden çalıştırın
cd superdeploy/terraform
./terraform-wrapper.sh apply
```

### "Docker image not found" Hatası

Docker Hub credential'ları hatalı:

```bash
# Docker Hub'da login test edin
docker login -u YOUR_USERNAME

# Token'ı .env'de güncelleyin
nano .env
# DOCKER_TOKEN=dckr_pat_xxxxx

# Sync'i yeniden çalıştırın
superdeploy sync
```

### "Deployment timeout" Hatası

Forgejo runner çalışmıyor olabilir:

```bash
# Runner durumunu kontrol edin
ssh -i ~/.ssh/superdeploy_deploy superdeploy@CORE_IP \
  "docker ps | grep runner"

# Runner loglarını inceleyin
ssh -i ~/.ssh/superdeploy_deploy superdeploy@CORE_IP \
  "docker logs forgejo-runner"
```

## Sonraki Adımlar

✅ Infrastructure hazır
✅ Secrets konfigüre edildi
✅ İlk deployment yapıldı

Şimdi günlük kullanım için [GUNLUK-KULLANIM.md](./GUNLUK-KULLANIM.md) dökümanına geçin.

---

**Önemli Notlar:**

1. `.env` dosyanızı **asla Git'e commit etmeyin!** Bu dosya tüm secret'larınızı içerir.
2. `.env` dosyasının yedeğini güvenli bir yerde saklayın (1Password, LastPass, encrypted backup).
3. IP adresleri değiştiğinde (VM restart vs.) `superdeploy sync` çalıştırarak GitHub secrets'ı güncelleyin.
4. Production environment'ta her zaman `production` branch'ini kullanın.

