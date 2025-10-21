# SuperDeploy - Sistem Genel Bakış

## 🎯 Ne İşe Yarar?

SuperDeploy, **application code'unuzu GitHub'dan alıp**, **Docker image'a çevirip**, **GCP VM'lerine deploy eden** tam otomatik bir sistemdir.

Tek komutla sıfırdan tüm infrastructure'ı ayağa kaldırır, GitHub'daki her push otomatik olarak production'a yansır.

---

## 📐 Mimari (Basitleştirilmiş)

```
┌─────────────────────────────────────────────────────────────────┐
│                         DEVELOPER                               │
│                                                                 │
│  1. Code yaz → 2. git push → 3. Email bildirim al → 4. Bitti!  │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                    GITHUB (Code Repos)                          │
│                                                                 │
│  • cheapaio/api          (Backend API)                          │
│  • cheapaio/dashboard    (Frontend)                             │
│  • cheapaio/services     (Background Workers)                   │
│                                                                 │
│  Push gelince → GitHub Actions tetiklenir                       │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                   GITHUB ACTIONS (Build)                        │
│                                                                 │
│  1. Docker image build et                                       │
│  2. Docker Hub'a push et                                        │
│  3. Environment variables'ı şifrele (AGE encryption)            │
│  4. Forgejo'ya deployment trigger gönder                        │
│  5. Email notification gönder (SMTP)                            │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                  GCP VM (Forgejo Runner)                        │
│                                                                 │
│  1. Şifrelenmiş env'leri çöz (AGE private key ile)              │
│  2. Docker image'ı pull et                                      │
│  3. Container'ları restart et (zero-downtime)                   │
│  4. Health check yap                                            │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🏗️ Sistemin 3 Ana Katmanı

### **1. Infrastructure Layer (Terraform + Ansible)**
- **Terraform:** GCP'de VM'leri, network'ü, firewall'ları oluşturur
- **Ansible:** VM'lere Docker, Forgejo, PostgreSQL, RabbitMQ kurulumunu yapar

### **2. CI/CD Layer (GitHub Actions + Forgejo Actions)**
- **GitHub Actions:** Code'u build edip Docker image'a çevirir
- **Forgejo Actions:** Image'ı VM'lere deploy eder

### **3. Application Layer (Docker Compose)**
- **Core Services:** PostgreSQL, RabbitMQ, Redis, Caddy (reverse proxy)
- **App Services:** API, Dashboard, Services (background workers)

---

## 🔑 Önemli Kavramlar

### **AGE Encryption**
Environment variables'ları GitHub Actions'dan Forgejo'ya güvenli şekilde aktarmak için kullanılır.

```
GitHub Actions (Public key) → [Encrypt] → Forgejo Runner (Private key) → [Decrypt]
```

### **SSH Keys**
- **Deploy Key:** GitHub'dan Forgejo VM'sine bağlanmak için
- **Runner Key:** Forgejo Runner'ın Forgejo'ya bağlanması için

### **Forgejo PAT (Personal Access Token)**
GitHub Actions'ın Forgejo API'sine workflow tetiklemesi için gerekli.

---

## 🌊 Tam Deployment Flow (Baştan Sona)

### **Senaryo:** API'ye yeni bir feature ekledin ve production'a çıkartmak istiyorsun.

```
┌─────────────────────────────────────────────────────────────────┐
│ Adım 1: Developer (Sen)                                         │
└─────────────────────────────────────────────────────────────────┘

$ cd app-repos/api
$ git add .
$ git commit -m "feat: add new endpoint"
$ git push origin production

┌─────────────────────────────────────────────────────────────────┐
│ Adım 2: GitHub Actions (Otomatik - ~2 dakika)                  │
└─────────────────────────────────────────────────────────────────┘

✓ Checkout code
✓ Build Docker image (docker.io/c100394/api:abc123)
✓ Push to Docker Hub
✓ Encrypt environment variables (AGE)
✓ Trigger Forgejo workflow (HTTP POST)
✓ Send email notification

┌─────────────────────────────────────────────────────────────────┐
│ Adım 3: Forgejo Actions (Otomatik - ~1 dakika)                 │
└─────────────────────────────────────────────────────────────────┘

✓ Decrypt environment variables
✓ Pull Docker image (docker.io/c100394/api:abc123)
✓ Run DB migrations (optional)
✓ Deploy services (docker compose up -d)
✓ Health checks (PostgreSQL, RabbitMQ, API)

┌─────────────────────────────────────────────────────────────────┐
│ Adım 4: Email Notification                                     │
└─────────────────────────────────────────────────────────────────┘

📧 Subject: [SuperDeploy] ✅ api - feat: add new endpoint

SuperDeploy Deployment Notification
════════════════════════════════════

Status: ✅ SUCCESS
Service: api
Commit: abc123
Image: abc123
Deployed at: 2025-10-21T17:30:00Z

→ Done! Yeni feature production'da!
```

---

## 📁 Repository Yapısı

```
superdeploy/                    # Ana orkestrasyon repo (GitHub)
├── .env                        # Tüm secrets ve config
├── superdeploy_cli/            # Python CLI tool (superdeploy up/sync/destroy)
├── projects/
│   └── cheapa/
│       ├── compose/            # Docker Compose files
│       ├── ansible/            # Ansible playbooks
│       └── terraform/          # Terraform configs
└── docs/                       # Bu dökümanlar

app-repos/api/                  # API service repo (GitHub)
├── .github/workflows/deploy.yml
└── app.py                      # FastAPI application

app-repos/dashboard/            # Dashboard repo (GitHub)
├── .github/workflows/deploy.yml
└── server.js                   # Next.js application

app-repos/services/             # Background workers repo (GitHub)
├── .github/workflows/deploy.yml
└── worker.py                   # Celery workers
```

---

## 🔐 Security Model

### **Secrets'ların Yolculuğu:**

1. **Developer:** `.env` dosyasına şifreleri yazar (local)
2. **`superdeploy sync`:** GitHub secrets'a push eder
3. **GitHub Actions:** Secrets'ları alır, AGE ile şifreler
4. **Forgejo Runner:** AGE private key ile şifre çözer
5. **Docker Containers:** Environment variables olarak alır

### **Hiçbir Zaman:**
- ❌ Plain text secrets Git'e commitlenmez
- ❌ Secrets log'lara yazılmaz
- ❌ Şifrelenmiş env'ler disk'te kalıcı tutulmaz (deployment sonrası silinir)

---

## 🚀 Hızlı Başlangıç

```bash
# 1. .env dosyasını hazırla
cp ENV.example .env
# (Şifreleri doldur)

# 2. Tek komutla tüm infrastructure'ı ayağa kaldır
superdeploy up -p cheapa

# 3. GitHub'a push yap
cd ../app-repos/api
git push origin production

# 4. Email bekle (1-2 dakika)
```

Detaylar için: `SETUP.md` ve `DEPLOYMENT.md`

---

## 📊 Sistem Durumu Kontrolü

```bash
# Tüm servislerin durumunu gör
superdeploy status -p cheapa

# Hangi image'ların deploy olduğunu gör
superdeploy releases -p cheapa -a api

# Bir önceki versiona geri dön
superdeploy rollback -a api v42

# Environment variables'ı gör (masked)
superdeploy env show

# Logs
superdeploy logs -p cheapa -a api --tail 100
```

---

## 🆘 Sık Sorulan Sorular

**Q: VM'lerin IP'si değişirse ne olur?**  
A: `superdeploy up` komutu yeni IP'leri otomatik `.env`'e yazar ve `superdeploy sync` ile GitHub secrets'ları günceller.

**Q: Hangi portlar açık?**  
A: Sadece `80`, `443`, `3001` (Forgejo), `8000` (API) dışarıya açık. PostgreSQL/RabbitMQ sadece internal.

**Q: Email gelmezse?**  
A: `SMTP_USERNAME` ve `SMTP_PASSWORD` secrets'larını kontrol et (Gmail App Password).

**Q: Deployment sırasında hata olursa?**  
A: Önceki container çalışmaya devam eder (zero-downtime). Forgejo log'larını kontrol et.

---

**Detaylı dökümanlar:** `SETUP.md`, `DEPLOYMENT.md`, `OPERATIONS.md`

