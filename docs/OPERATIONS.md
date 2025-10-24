# Günlük Operasyonlar

Bu döküman, sistemi kurduktan sonra **günlük kullanımda** ihtiyaç duyacağın tüm komutları ve senaryoları içerir.

---

## 🎯 Hızlı Referans

```bash
# Sistem durumu
superdeploy status -p myproject

# Yeni deployment
git push origin production

# Rollback
superdeploy rollback -a api v42

# Logs
superdeploy logs -p myproject -a api --tail 100

# Secrets yönetimi
superdeploy env show
superdeploy sync -p myproject

# Infrastructure
superdeploy down -p myproject
```

---

## 📊 Sistem Durumu Kontrolü

### **Tüm Servislerin Durumu**

```bash
superdeploy status -p myproject
```

**Çıktı:**
```
╭─────────────────────────────────────╮
│ 🚀 SuperDeploy Status               │
╰─────────────────────────────────────╯

Infrastructure Status:
  ✅ GCP Project: galvanic-camp-475519-d6
  ✅ Core VM: myproject-core (RUNNING)
  ✅ External IP: 34.42.105.169
  ✅ Internal IP: 10.0.0.5

Core Services (Project: myproject):
  ✅ PostgreSQL: healthy (5432)
  ✅ RabbitMQ: healthy (5672)
  ✅ Redis: healthy (6379)
  ✅ Forgejo: healthy (3001)
  ✅ Caddy: healthy (80,443)

Application Services:
  ✅ API: healthy (8000) - v45
  ✅ Dashboard: healthy (3000) - v23
  ❌ Services: degraded (worker issues)

Last Deployment:
  Service: api
  Time: 2025-10-21 17:30:00 UTC
  Status: SUCCESS
  Image: docker.io/c100394/api:abc123
```

### **Belirli Bir Service**

```bash
superdeploy status -a api
```

---

## 🚀 Deployment Senaryoları

### **Senaryo 1: Normal Feature Deployment**

```bash
# 1. Feature branch'inde çalış
git checkout -b feature/new-endpoint
# kod yaz...
git commit -m "feat: add new endpoint"

# 2. PR aç, merge et (GitHub)
# (Otomatik testler çalışır)

# 3. Main'e merge olduktan sonra production'a deploy
git checkout production
git pull origin production
git merge main
git push origin production

# 4. Email bekle (~3 dakika)
# 5. Kontrol et
superdeploy status -a api
```

### **Senaryo 2: Hotfix (Acil Düzeltme)**

```bash
# 1. Hotfix branch oluştur
git checkout production
git checkout -b hotfix/critical-bug

# 2. Düzeltmeyi yap
# ... kod düzeltmesi ...
git commit -m "fix: critical security issue"

# 3. Direkt production'a push (PR atlamadan)
git checkout production
git merge hotfix/critical-bug
git push origin production

# 4. Deployment izle
# GitHub Actions: https://github.com/myprojectio/api/actions
# Forgejo: http://CORE_IP:3001/cradexco/superdeploy/actions

# 5. Sonra main'e de merge et
git checkout main
git merge hotfix/critical-bug
git push origin main
```

### **Senaryo 3: Rollback (Geri Alma)**

```bash
# 1. Hangi versiyonlar var?
superdeploy releases -p myproject -a api

# Çıktı:
# v45  2025-10-21 17:30  abc123  CURRENT
# v44  2025-10-21 15:20  def456  SUCCESS
# v43  2025-10-21 12:10  ghi789  SUCCESS

# 2. Bir önceki versiyona dön
superdeploy rollback -a api v44

# 3. Kontrol et
superdeploy status -a api
curl http://34.42.105.169:8000/health

# 4. Eğer sorun devam ederse bir daha geri al
superdeploy rollback -a api v43
```

---

## 🔍 Logs ve Debugging

### **Real-time Logs**

```bash
# Son 100 satır
superdeploy logs -p myproject -a api --tail 100

# Real-time takip (Ctrl+C ile çık)
superdeploy logs -p myproject -a api --follow

# Belirli bir zaman aralığı
superdeploy logs -p myproject -a api --since "30m"

# Error logları filtrele
superdeploy logs -p myproject -a api --tail 500 | grep ERROR
```

### **Database Logs**

```bash
# PostgreSQL logs
superdeploy logs -p myproject -s postgres --tail 100

# RabbitMQ logs
superdeploy logs -p myproject -s rabbitmq --tail 100
```

### **VM'ye SSH ile Bağlanma**

```bash
# Otomatik (superdeploy CLI)
superdeploy ssh

# Manuel
ssh -i ~/.ssh/superdeploy_deploy superdeploy@34.42.105.169

# Container'lara bak
docker ps

# API container'ına gir
docker exec -it myproject-api bash

# Logs
docker logs myproject-api --tail 100
```

---

## 🔐 Secrets ve Environment Variables Yönetimi

### **Environment Variable Stratejisi**

SuperDeploy, local development ve production ortamlarını ayırmak için iki farklı dosya kullanır:

- **`.env`** - Local development için (SuperDeploy tarafından ASLA değiştirilmez)
- **`.env.superdeploy`** - Production deployment için (SuperDeploy tarafından otomatik oluşturulur)

**Önemli:** SuperDeploy, uygulama repository'lerindeki `.env` dosyalarına ASLA dokunmaz. Bu sayede local development ortamınız güvende kalır.

### **Sync Komutu Nasıl Çalışır?**

`sync` komutu, local dosyalardan secret'ları toplayıp GitHub ve Forgejo'ya dağıtır:

```bash
# Temel kullanım
superdeploy sync -p myproject

# Uygulama-specific .env dosyalarını dahil et
superdeploy sync -p myproject -e ../app-repos/api/.env

# Birden fazla .env dosyası
superdeploy sync -p myproject -e ../app-repos/api/.env -e ../app-repos/dashboard/.env

# Sadece Forgejo'yu atla
superdeploy sync -p myproject --skip-forgejo

# Sadece GitHub'ı atla
superdeploy sync -p myproject --skip-github
```

**Sync komutu ne yapar?**

1. **Kaynaklardan toplar:**
   - `superdeploy/.env` (infrastructure secrets)
   - `projects/[project]/.passwords.yml` (otomatik oluşturulan şifreler)
   - `--env-file` ile belirtilen dosyalar (uygulama secrets)

2. **Merge eder (öncelik sırası):**
   - En yüksek: `--env-file` ile verilen dosyalar
   - Orta: `.passwords.yml` (project-specific)
   - En düşük: `superdeploy/.env` (infrastructure)

3. **Dağıtır:**
   - **GitHub Repository Secrets:** Build-time secrets (FORGEJO_PAT, AGE_PUBLIC_KEY, DOCKER_TOKEN)
   - **GitHub Environment Secrets:** Runtime secrets (POSTGRES_PASSWORD, REDIS_PASSWORD)
   - **Forgejo Repository Secrets:** Deployment için gerekli secrets

### **Production Secret'larını Güncelleme (Local'e Dokunmadan)**

```bash
# Senaryo: PostgreSQL şifresini değiştirmek istiyorsun

# 1. Sadece production şifresini güncelle
nano projects/myproject/.passwords.yml
# POSTGRES_PASSWORD: yeni_sifre_buraya

# 2. GitHub ve Forgejo'ya sync et
superdeploy sync -p myproject

# 3. PostgreSQL container'ını yeni şifre ile restart et
ssh superdeploy@CORE_IP
cd /opt/superdeploy/projects/myproject/compose
docker compose -f docker-compose.core.yml down postgres
docker compose -f docker-compose.core.yml up -d postgres

# 4. Uygulamaları restart et (yeni şifreyi alsınlar)
superdeploy restart -p myproject --all

# NOT: Local .env dosyan hiç değişmedi!
```

### **Yeni Bir Secret Ekleme**

```bash
# Senaryo: Yeni bir API key eklemek istiyorsun

# 1. Uygulama .env dosyasına ekle (local development için)
echo "STRIPE_API_KEY=sk_test_..." >> app-repos/api/.env

# 2. Production için .passwords.yml'e ekle
echo "STRIPE_API_KEY=sk_live_..." >> projects/myproject/.passwords.yml

# 3. GitHub ve Forgejo'ya sync et
superdeploy sync -p myproject -e app-repos/api/.env

# 4. Uygulamayı redeploy et
cd app-repos/api
git commit --allow-empty -m "chore: update secrets"
git push origin production

# NOT: Local'de sk_test_, production'da sk_live_ kullanılacak
```

### **Secrets'ları Görüntüleme**

```bash
# Maskelenmiş halde (güvenli)
superdeploy env show

# Çıktı:
# POSTGRES_PASSWORD=***************
# API_SECRET_KEY=***************
# RABBITMQ_PASSWORD=***************

# Şifresiz tam değerler (DİKKATLİ!)
superdeploy env show --no-mask
# Password: ****
# (ENV_MASTER_PASSWORD gir)
```

### **Environment Variable Dosyaları Nerede?**

```
superdeploy/
├── .env                              # Infrastructure secrets (CORE_IP, DOCKER_TOKEN, vb.)
└── projects/myproject/
    ├── .passwords.yml                # Otomatik oluşturulan şifreler (POSTGRES_PASSWORD, vb.)
    └── secrets.env                   # (Opsiyonel) Custom secrets

app-repos/
├── api/
│   ├── .env                         # Local development (ASLA değiştirilmez)
│   └── .env.superdeploy             # Production overrides (otomatik oluşturulur)
├── dashboard/
│   ├── .env
│   └── .env.superdeploy
└── services/
    ├── .env
    └── .env.superdeploy
```

### **Hangi Dosyayı Ne Zaman Düzenlemeli?**

| Senaryo | Düzenlenecek Dosya | Komut |
|---------|-------------------|-------|
| Local development değişkeni | `app-repos/[app]/.env` | Yok (manuel edit) |
| Production secret güncelleme | `projects/[project]/.passwords.yml` | `superdeploy sync -p [project]` |
| Infrastructure değişkeni | `superdeploy/.env` | `superdeploy sync -p [project]` |
| Yeni secret ekleme | Her ikisi de | `superdeploy sync -p [project] -e app-repos/[app]/.env` |

---

## 🗄️ Database İşlemleri

### **Database Migration**

```bash
# Otomatik (deployment sırasında)
# .github/workflows/deploy.yml içinde migrate: "true" ayarla

# Manuel
ssh superdeploy@34.42.105.169
cd /opt/superdeploy/projects/myproject/compose
docker compose run --rm api alembic upgrade head
```

### **Database Backup**

```bash
# PostgreSQL dump al
ssh superdeploy@34.42.105.169
docker exec myproject-postgres pg_dump -U superdeploy superdeploy_db > backup_$(date +%Y%m%d).sql

# Local'e indir
scp -i ~/.ssh/superdeploy_deploy superdeploy@34.42.105.169:backup_*.sql ./
```

### **Database Restore**

```bash
# Backup dosyasını VM'ye yükle
scp -i ~/.ssh/superdeploy_deploy backup_20251021.sql superdeploy@34.42.105.169:~/

# Restore et
ssh superdeploy@34.42.105.169
cat backup_20251021.sql | docker exec -i myproject-postgres psql -U superdeploy superdeploy_db
```

---

## 📦 Container Yönetimi

### **Container'ları Restart Etme**

```bash
# Tek bir service
superdeploy restart -p myproject -a api

# Tüm app services
superdeploy restart -p myproject --all

# Core services (PostgreSQL, RabbitMQ, vb.)
ssh superdeploy@34.42.105.169
cd /opt/superdeploy/projects/myproject/compose
docker compose -f docker-compose.core.yml restart postgres
```

### **Container Scaling**

```bash
# Birden fazla worker instance çalıştır
ssh superdeploy@34.42.105.169
cd /opt/superdeploy/projects/myproject/compose
docker compose -f docker-compose.apps.yml up -d --scale services=3
```

### **Container Temizliği**

```bash
# Kullanılmayan image'ları temizle
ssh superdeploy@34.42.105.169
docker image prune -a -f

# Kullanılmayan volume'ları temizle (DİKKATLİ!)
docker volume prune -f
```

---

## 🌐 IP Değişimi Senaryosu

### **VM restart edildi ve IP değişti, ne yapmalı?**

```bash
# 1. superdeploy up komutu otomatik günceller
superdeploy up -p myproject

# Veya sadece sync:
superdeploy sync -p myproject

# 2. Yeni IP'yi kontrol et
superdeploy status -p myproject

# 3. GitHub secrets güncellenmiş mi kontrol et
gh secret list --repo myprojectio/api | grep FORGEJO_BASE_URL

# 4. Test deployment
cd app-repos/api
git commit --allow-empty -m "test: verify new IP"
git push origin production
```

---

## 🔧 Sync Sorunları ve Çözümleri

### **"gh CLI not found" Hatası**

```bash
# Hata: GitHub CLI (gh) not installed

# Çözüm: gh CLI'yi kur
brew install gh

# GitHub'a login ol
gh auth login
# → GitHub.com seç
# → HTTPS seç
# → Browser'da authenticate et
```

### **"Failed to fetch AGE public key" Hatası**

```bash
# Hata: Could not find public key in AGE key file

# Sebep: Forgejo runner henüz kurulmamış veya AGE key oluşturulmamış

# Çözüm 1: up komutunu tekrar çalıştır
superdeploy up -p myproject

# Çözüm 2: Manuel kontrol et
ssh superdeploy@CORE_IP
cat /opt/forgejo-runner/.age/key.txt
# "public key: age1..." satırını görmelisin

# Eğer dosya yoksa, Ansible playbook'u tekrar çalıştır
cd superdeploy/shared/ansible
ansible-playbook -i inventories/dev.ini playbooks/site.yml
```

### **"PAT creation failed" Hatası**

```bash
# Hata: Forgejo PAT creation failed: 401 Unauthorized

# Sebep: Forgejo admin şifresi yanlış veya Forgejo henüz hazır değil

# Çözüm 1: Forgejo'nun çalıştığını kontrol et
curl http://CORE_IP:3001/api/healthz

# Çözüm 2: Admin şifresini kontrol et
cat projects/myproject/.passwords.yml | grep FORGEJO_ADMIN_PASSWORD

# Çözüm 3: Manuel PAT oluştur
# 1. Forgejo'ya browser'dan gir: http://CORE_IP:3001
# 2. Settings → Applications → Generate New Token
# 3. Scopes: read:user, write:repository, write:misc, write:organization
# 4. Token'ı kopyala ve superdeploy/.env'e ekle:
echo "FORGEJO_PAT=your_token_here" >> superdeploy/.env

# 5. Sync'i tekrar çalıştır (--skip-forgejo ile)
superdeploy sync -p myproject --skip-forgejo
```

### **"Secret set failed" Hatası (GitHub)**

```bash
# Hata: Failed to set secret API_KEY: Resource not accessible by integration

# Sebep 1: Repository'ye erişim yok
# Çözüm: gh auth refresh -s admin:org,repo

# Sebep 2: Repository adı yanlış
# Çözüm: projects/myproject/project.yml dosyasını kontrol et
cat projects/myproject/project.yml | grep repositories

# Sebep 3: Repository private ve erişim yok
# Çözüm: Repository settings → Manage access → Kendini ekle
```

### **"Empty secret skipped" Uyarısı**

```bash
# Uyarı: ⊘ SENTRY_DSN (empty, skipped)

# Bu normal! Boş secret'lar otomatik atlanır.
# Eğer bu secret'ı kullanmak istiyorsan:

# 1. Değeri ekle
echo "SENTRY_DSN=https://..." >> projects/myproject/.passwords.yml

# 2. Sync'i tekrar çalıştır
superdeploy sync -p myproject
```

### **Sync Sonrası Secret'lar Yüklenmiyor**

```bash
# Sorun: Sync başarılı ama container'lar yeni secret'ları görmüyor

# Sebep: Container'lar restart edilmemiş

# Çözüm 1: Tüm uygulamaları restart et
superdeploy restart -p myproject --all

# Çözüm 2: Sadece bir uygulamayı restart et
superdeploy restart -p myproject -a api

# Çözüm 3: Manuel restart
ssh superdeploy@CORE_IP
cd /opt/superdeploy/projects/myproject/compose
docker compose -f docker-compose.apps.yml restart api
```

### **Sync Çok Yavaş (Timeout)**

```bash
# Sorun: Environment secret sync'i 30 saniyede timeout oluyor

# Sebep: GitHub API rate limit veya network sorunu

# Çözüm 1: Birkaç dakika bekle ve tekrar dene
sleep 300
superdeploy sync -p myproject

# Çözüm 2: Sadece Forgejo'ya sync et (GitHub'ı atla)
superdeploy sync -p myproject --skip-github

# Çözüm 3: Rate limit'i kontrol et
gh api rate_limit
```

### **Merge Priority Sorunları**

```bash
# Sorun: Local .env'deki değer production'a gidiyor (istemiyorum)

# Sebep: --env-file ile local .env'i sync'e dahil etmişsin

# Çözüm: --env-file kullanma, sadece .passwords.yml'i düzenle
nano projects/myproject/.passwords.yml
superdeploy sync -p myproject

# NOT: Merge önceliği:
# 1. --env-file (en yüksek)
# 2. .passwords.yml
# 3. superdeploy/.env (en düşük)
```

---

## 🆘 Acil Durum Senaryoları

### **Tüm Servisler Çöktü**

```bash
# 1. VM'ye bağlan
ssh superdeploy@34.42.105.169

# 2. Tüm container durumunu kontrol et
docker ps -a

# 3. Core services'i başlat
cd /opt/superdeploy/projects/myproject/compose
docker compose -f docker-compose.core.yml up -d

# 4. App services'i başlat
docker compose -f docker-compose.apps.yml up -d

# 5. Logs kontrol et
docker logs myproject-postgres --tail 100
docker logs myproject-api --tail 100
```

### **PostgreSQL Şifresi Unutuldu**

```bash
# 1. .env dosyasından kontrol et
cat superdeploy/.env | grep POSTGRES_PASSWORD

# 2. Veya superdeploy CLI ile
superdeploy env show --no-mask

# 3. Şifreyi değiştir
# .env'de güncelle → superdeploy sync → container restart
```

### **Forgejo Runner Çalışmıyor**

```bash
# 1. Systemd service durumunu kontrol et
ssh superdeploy@34.42.105.169
sudo systemctl status forgejo-runner

# 2. Restart et
sudo systemctl restart forgejo-runner

# 3. Logs kontrol et
sudo journalctl -u forgejo-runner -f

# 4. Container kontrol et
docker ps | grep forgejo-runner
docker logs forgejo-runner --tail 100
```

### **Disk Doldu**

```bash
# 1. Disk kullanımını kontrol et
ssh superdeploy@34.42.105.169
df -h

# 2. Docker temizliği
docker system prune -a --volumes -f

# 3. Log rotation kontrol et
sudo journalctl --vacuum-time=7d

# 4. Eski PostgreSQL backup'ları temizle
rm ~/backup_*.sql
```

---

## 📊 Monitoring ve Alerts

### **Manuel Health Check**

```bash
# API
curl http://34.42.105.169:8000/health

# PostgreSQL
ssh superdeploy@34.42.105.169
docker exec myproject-postgres pg_isready -U superdeploy

# RabbitMQ
docker exec myproject-rabbitmq rabbitmq-diagnostics ping

# Redis
docker exec myproject-redis redis-cli ping
```

### **Email Notification Test**

```bash
# Test deployment yap
cd app-repos/api
git commit --allow-empty -m "test: email notification"
git push origin production

# Email geldi mi kontrol et: cradexco@gmail.com
```

---

## 🔧 Maintenance

### **Sistem Güncelleme**

```bash
# VM packages güncelle
ssh superdeploy@34.42.105.169
sudo apt update && sudo apt upgrade -y

# Docker güncelle
sudo apt install docker-ce docker-ce-cli containerd.io -y

# Forgejo güncelle (manual)
# Docker image version'ını docker-compose.core.yml'de değiştir
```

### **SSL Certificate (Caddy otomatik)**

```bash
# Domain ekle
# Caddyfile'a domain adını ekle
# Caddy otomatik Let's Encrypt sertifikası alır

# Test
curl https://yourdomain.com/health
```

---

## 🗑️ Silme İşlemleri

### **Tüm Infrastructure'ı Sil**

```bash
superdeploy destroy -p myproject
# Confirm? (y/n): y

# Bu komut:
# - GCP VM'leri siler
# - Terraform state temizler
# - .env'deki IP'leri temizler
```

### **Sadece Bir Service'i Kaldır**

```bash
ssh superdeploy@34.42.105.169
cd /opt/superdeploy/projects/myproject/compose
docker compose -f docker-compose.apps.yml stop services
docker compose -f docker-compose.apps.yml rm -f services
```

---

## 📚 Daha Fazla Bilgi

- **ARCHITECTURE.md:** Genel mimari ve kavramlar
- **SETUP.md:** İlk kurulum
- **DEPLOYMENT.md:** Deployment flow detayları
- **FLOW.md:** İş akışı ve parametre akışı

---

**Yardıma mı ihtiyacın var?** 
- GitHub Issues: https://github.com/cfkarakulak/superdeploy/issues
- Email: cradexco@gmail.com

