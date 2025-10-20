# 🚀 SuperDeploy - Sıfırdan Kurulum

## ⚡ 2 Komut, 6 Dakika, Tam Sistem!

```bash
# 1. .env'i hazırla
make init
nano superdeploy/.env  # GCP_PROJECT_ID + şifreleri doldur

# 2. Deploy!
make deploy

# 🎉 DONE!
```

---

## 📋 Detaylı Kurulum

### Ön Gereksinimler

```bash
# GCP CLI
gcloud auth login
gcloud config set project YOUR_PROJECT_ID

# SSH Key
ssh-keygen -t rsa -b 4096 -f ~/.ssh/cfk_gcp

# Dependencies
brew install terraform ansible jq  # macOS
```

### 1️⃣ .env Oluştur

```bash
make init
```

Bu komut `superdeploy/ENV.example`'ı `superdeploy/.env`'e kopyalar.

### 2️⃣ .env'i Doldur

```bash
nano superdeploy/.env
```

**SADECE BUNLARI DOLDUR:**

```env
# GCP Project (ZORUNLU)
GCP_PROJECT_ID=your-gcp-project-id-here  # gcloud projects list

# Passwords (ZORUNLU - openssl rand -base64 32)
POSTGRES_PASSWORD=CHANGE_ME_RANDOM_32_CHARS
RABBITMQ_DEFAULT_PASS=CHANGE_ME_RANDOM_32_CHARS
API_SECRET_KEY=CHANGE_ME_RANDOM_64_CHARS
PROXY_REGISTRY_PASS=CHANGE_ME_RANDOM_32_CHARS
PROXY_REGISTRY_API_KEY=CHANGE_ME_RANDOM_64_CHARS
PROXY_PASSWORD=CHANGE_ME_RANDOM_32_CHARS
SECRET_KEY=CHANGE_ME_RANDOM_64_CHARS
JWT_SECRET=CHANGE_ME_RANDOM_64_CHARS
FORGEJO_ADMIN_PASSWORD=CHANGE_ME_RANDOM_32_CHARS
FORGEJO_DB_PASSWORD=CHANGE_ME_RANDOM_32_CHARS

# SSH Key Path (değiştir eğer farklıysa)
SSH_KEY_PATH=~/.ssh/cfk_gcp
```

**💡 Şifre Oluştur:**

```bash
# Terminal'de çalıştır:
openssl rand -base64 32  # 32 karakter
openssl rand -base64 64  # 64 karakter
```

### 3️⃣ Deploy!

```bash
make deploy
```

**Bu tek komut şunları yapar:**

1. ✅ .env'i kontrol eder
2. ✅ Terraform ile 3 VM oluşturur (CORE, SCRAPE, PROXY)
3. ✅ IP'leri otomatik çeker ve .env'e yazar
4. ✅ SSH known_hosts temizler
5. ✅ VM'lerin hazır olmasını bekler (90s)
6. ✅ Ansible ile full-auto deployment:
   - Docker kurar
   - Firewall yapılandırır
   - Forgejo kurar (NO WIZARD!)
   - Admin user oluşturur
   - Repository oluşturur
   - Runner register eder
7. ✅ Kodu Forgejo'ya pushar
8. ✅ Workflow'lar otomatik başlar

**Süre: ~6 dakika**

---

## 🎯 Access Points

Deployment bittikten sonra:

```bash
# Forgejo UI
http://CORE_EXTERNAL_IP:3001

# Workflows
http://CORE_EXTERNAL_IP:3001/cradexco/superdeploy-app/actions

# Services (2-3 dakika sonra hazır)
curl http://CORE_EXTERNAL_IP:8000/health    # API
curl http://CORE_EXTERNAL_IP:8080/health    # Proxy Registry
open http://CORE_EXTERNAL_IP:8001           # Dashboard
open http://CORE_EXTERNAL_IP:15672          # RabbitMQ
```

**Credentials:**
- Admin: `cradexco` / `<FORGEJO_ADMIN_PASSWORD from .env>`

---

## 🔄 VM Restart Sonrası

VM'ler restart olursa sadece IP'leri güncelle:

```bash
# 1. Yeni IP'leri al ve .env'i güncelle
make update-ips

# 2. Push et
cd superdeploy
git add .env
git commit -m "config: update IPs after restart"
git push

# 3. Otomatik deploy! ✨
```

---

## 🧪 Test

```bash
make test
```

Tüm servisleri test eder (API, Proxy Registry, Dashboard).

---

## 📚 Makefile Komutları

```bash
make help          # Tüm komutları listele
make init          # .env oluştur
make check-env     # .env'i kontrol et
make deploy        # Tam deployment (tek komut!)
make update-ips    # Terraform'dan IP'leri çek
make ansible-deploy # Sadece Ansible deploy
make git-push      # Kodu Forgejo'ya push et
make test          # Servisleri test et
make destroy       # Tüm infrastructure'ı yok et
make clean         # Temp dosyaları temizle
```

---

## 🆘 Sorun Giderme

### .env hatası

```bash
# Eksik değer var mı?
make check-env

# Yeniden başlat
make init
nano superdeploy/.env
```

### Terraform hatası

```bash
# GCP credentials kontrol
gcloud auth list
gcloud config list

# SSH key kontrol
ls -la ~/.ssh/cfk_gcp*
```

### Ansible "dpkg lock" hatası

```bash
# 30 saniye bekle ve tekrar dene
sleep 30
make ansible-deploy
```

### Runner çalışmıyor

```bash
# SSH ile gir
ssh superdeploy@CORE_EXTERNAL_IP

# Status kontrol
sudo systemctl status forgejo-runner

# Restart
sudo systemctl restart forgejo-runner

# Logs
sudo journalctl -u forgejo-runner -f
```

### Workflow başlamıyor

```bash
# Browser'da kontrol et
open http://CORE_EXTERNAL_IP:3001/cradexco/superdeploy-app/actions

# Manuel tetikle
cd superdeploy
git commit --allow-empty -m "trigger: manual workflow"
git push
```

---

## 🎨 Workflow

```
.env hazırla → make deploy → kahve iç → sistem hazır!
     ↓              ↓
  2 dakika      6 dakika
```

---

## 📁 Dosya Yapısı

```
.
├── Makefile                    # ⭐ Ana komutlar
├── superdeploy/
│   ├── ENV.example            # Template
│   ├── .env                   # ⭐ TEK config dosyası
│   ├── deploy/                # Docker Compose files
│   └── .forgejo/              # CI/CD workflows
├── superdeploy-infra/
│   ├── terraform-wrapper.sh  # .env → Terraform
│   ├── main.tf               # Terraform config
│   └── ansible/              # Ansible roles
└── SETUP.md                  # ⭐ Bu dosya
```

---

## 🎯 Özet

| Ne | Komut | Süre |
|----|-------|------|
| Setup | `make init` + `nano .env` | 2 dakika |
| Deploy | `make deploy` | 6 dakika |
| **TOPLAM** | **2 komut** | **8 dakika** |

---

**🚀 Tek .env + Tek komut = Tam sistem!**

