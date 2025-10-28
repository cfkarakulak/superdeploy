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
superdeploy sync -p myproject

# Infrastructure
superdeploy down -p myproject
```

---

## 📊 Sistem Durumu Kontrolü

### Tüm Servislerin Durumu

```bash
superdeploy status -p myproject
```

**Çıktı:**
```
╭─────────────────────────────────────╮
│ 🚀 SuperDeploy Status               │
╰─────────────────────────────────────╯

Infrastructure Status:
  ✅ GCP Project: my-gcp-project
  ✅ Core VM: myproject-core (RUNNING)
  ✅ External IP: 34.42.105.169

Core Services:
  ✅ PostgreSQL: healthy (5432)
  ✅ RabbitMQ: healthy (5672)
  ✅ Redis: healthy (6379)
  ✅ Forgejo: healthy (3001)

Application Services:
  ✅ API: healthy (8000) - v45
  ✅ Dashboard: healthy (3000) - v23
```

### Belirli Bir Service

```bash
superdeploy status -a api
```

---

## 🚀 Deployment Senaryoları

### Senaryo 1: Normal Feature Deployment

```bash
# 1. Feature branch'inde çalış
git checkout -b feature/new-endpoint
# kod yaz...
git commit -m "feat: add new endpoint"

# 2. PR aç, merge et (GitHub)

# 3. Production'a deploy
git checkout production
git pull origin production
git merge main
git push origin production

# 4. Kontrol et
superdeploy status -a api
```

### Senaryo 2: Hotfix (Acil Düzeltme)

```bash
# 1. Hotfix branch oluştur
git checkout production
git checkout -b hotfix/critical-bug

# 2. Düzeltmeyi yap
git commit -m "fix: critical security issue"

# 3. Direkt production'a push
git checkout production
git merge hotfix/critical-bug
git push origin production

# 4. Deployment izle
superdeploy logs -p myproject -a api --follow
```

### Senaryo 3: Rollback (Geri Alma)

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
```

---

## 🔍 Logs ve Debugging

### Real-time Logs

```bash
# Son 100 satır
superdeploy logs -p myproject -a api --tail 100

# Real-time takip
superdeploy logs -p myproject -a api --follow

# Belirli bir zaman aralığı
superdeploy logs -p myproject -a api --since "30m"

# Error logları filtrele
superdeploy logs -p myproject -a api --tail 500 | grep ERROR
```

### Database Logs

```bash
# PostgreSQL logs
superdeploy logs -p myproject -s postgres --tail 100

# RabbitMQ logs
superdeploy logs -p myproject -s rabbitmq --tail 100
```

### VM'ye SSH ile Bağlanma

```bash
# Otomatik
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

### Environment Variable Stratejisi

SuperDeploy, local development ve production ortamlarını ayırmak için iki farklı dosya kullanır:

- **`.env`** - Local development (SuperDeploy ASLA değiştirmez)
- **`.env.superdeploy`** - Production (SuperDeploy otomatik oluşturur)

### Sync Komutu Nasıl Çalışır?

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
   - `projects/[project]/.passwords.yml` (otomatik şifreler)
   - `--env-file` ile belirtilen dosyalar

2. **Merge eder (öncelik sırası):**
   - En yüksek: `--env-file` dosyaları
   - Orta: `.passwords.yml`
   - En düşük: `superdeploy/.env`

3. **Dağıtır:**
   - GitHub Repository Secrets
   - GitHub Environment Secrets
   - Forgejo Repository Secrets

### Production Secret'larını Güncelleme

```bash
# Senaryo: PostgreSQL şifresini değiştirmek istiyorsun

# 1. Sadece production şifresini güncelle
nano projects/myproject/.passwords.yml
# POSTGRES_PASSWORD: yeni_sifre

# 2. GitHub ve Forgejo'ya sync et
superdeploy sync -p myproject

# 3. PostgreSQL container'ını restart et
ssh superdeploy@CORE_IP
cd /opt/superdeploy/projects/myproject/compose
docker compose -f docker-compose.core.yml restart postgres

# 4. Uygulamaları restart et
superdeploy restart -p myproject --all

# NOT: Local .env dosyan hiç değişmedi!
```

### Yeni Bir Secret Ekleme

```bash
# Senaryo: Yeni bir API key eklemek istiyorsun

# 1. Uygulama .env dosyasına ekle (local için)
echo "STRIPE_API_KEY=sk_test_..." >> app-repos/api/.env

# 2. Production için .passwords.yml'e ekle
echo "STRIPE_API_KEY=sk_live_..." >> projects/myproject/.passwords.yml

# 3. GitHub ve Forgejo'ya sync et
superdeploy sync -p myproject -e app-repos/api/.env

# 4. Uygulamayı redeploy et
cd app-repos/api
git commit --allow-empty -m "chore: update secrets"
git push origin production
```

### Secrets'ları Görüntüleme

```bash
# Maskelenmiş halde (güvenli)
superdeploy env show

# Çıktı:
# POSTGRES_PASSWORD=***************
# API_SECRET_KEY=***************
```

### Environment Variable Dosyaları Nerede?

```
superdeploy/
├── .env                              # Infrastructure secrets
└── projects/myproject/
    ├── .passwords.yml                # Otomatik oluşturulan şifreler
    └── secrets.env                   # (Opsiyonel) Custom secrets

app-repos/
├── api/
│   ├── .env                         # Local development
│   └── .env.superdeploy             # Production overrides
├── dashboard/
│   ├── .env
│   └── .env.superdeploy
```

### Hangi Dosyayı Ne Zaman Düzenlemeli?

| Senaryo | Düzenlenecek Dosya | Komut |
|---------|-------------------|-------|
| Local development | `app-repos/[app]/.env` | Manuel edit |
| Production secret | `projects/[project]/.passwords.yml` | `superdeploy sync` |
| Infrastructure | `superdeploy/.env` | `superdeploy sync` |
| Yeni secret | Her ikisi de | `superdeploy sync -e` |

---

## 🗄️ Database İşlemleri

### Database Migration

```bash
# Otomatik (deployment sırasında)
# .github/workflows/deploy.yml içinde migrate: "true"

# Manuel
ssh superdeploy@34.42.105.169
cd /opt/superdeploy/projects/myproject/compose
docker compose run --rm api alembic upgrade head
```

### Database Backup

```bash
# PostgreSQL dump al
ssh superdeploy@34.42.105.169
docker exec myproject-postgres pg_dump -U superdeploy superdeploy_db > backup_$(date +%Y%m%d).sql

# Local'e indir
scp -i ~/.ssh/superdeploy_deploy superdeploy@34.42.105.169:backup_*.sql ./
```

### Database Restore

```bash
# Backup dosyasını VM'ye yükle
scp -i ~/.ssh/superdeploy_deploy backup_20251021.sql superdeploy@34.42.105.169:~/

# Restore et
ssh superdeploy@34.42.105.169
cat backup_20251021.sql | docker exec -i myproject-postgres psql -U superdeploy superdeploy_db
```

---

## 📦 Container Yönetimi

### Container'ları Restart Etme

```bash
# Tek bir service
superdeploy restart -p myproject -a api

# Tüm app services
superdeploy restart -p myproject --all

# Core services
ssh superdeploy@34.42.105.169
cd /opt/superdeploy/projects/myproject/compose
docker compose -f docker-compose.core.yml restart postgres
```

### Container Scaling

```bash
# Birden fazla worker instance
ssh superdeploy@34.42.105.169
cd /opt/superdeploy/projects/myproject/compose
docker compose -f docker-compose.apps.yml up -d --scale services=3
```

### Container Temizliği

```bash
# Kullanılmayan image'ları temizle
ssh superdeploy@34.42.105.169
docker image prune -a -f

# Kullanılmayan volume'ları temizle (DİKKATLİ!)
docker volume prune -f
```

---

## 🌐 IP Değişimi Senaryosu

### VM restart edildi ve IP değişti, ne yapmalı?

```bash
# 1. superdeploy up komutu otomatik günceller
superdeploy up -p myproject

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

### "gh CLI not found" Hatası

```bash
# Çözüm: gh CLI'yi kur
brew install gh

# GitHub'a login ol
gh auth login
```

### "Failed to fetch AGE public key" Hatası

```bash
# Çözüm 1: up komutunu tekrar çalıştır
superdeploy up -p myproject

# Çözüm 2: Manuel kontrol et
ssh superdeploy@CORE_IP
cat /opt/forgejo-runner/.age/key.txt
```

### "PAT creation failed" Hatası

```bash
# Çözüm 1: Forgejo'nun çalıştığını kontrol et
curl http://CORE_IP:3001/api/healthz

# Çözüm 2: Admin şifresini kontrol et
cat projects/myproject/.passwords.yml | grep FORGEJO_ADMIN_PASSWORD
```

### Sync Sonrası Secret'lar Yüklenmiyor

```bash
# Sebep: Container'lar restart edilmemiş

# Çözüm: Tüm uygulamaları restart et
superdeploy restart -p myproject --all
```

---

## 🆘 Acil Durum Senaryoları

### Tüm Servisler Çöktü

```bash
# 1. VM'ye bağlan
ssh superdeploy@34.42.105.169

# 2. Container durumunu kontrol et
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

### PostgreSQL Şifresi Unutuldu

```bash
# 1. .env dosyasından kontrol et
cat superdeploy/.env | grep POSTGRES_PASSWORD

# 2. Veya superdeploy CLI ile
superdeploy env show
```

### Disk Doldu

```bash
# 1. Disk kullanımını kontrol et
ssh superdeploy@34.42.105.169
df -h

# 2. Docker temizliği
docker system prune -a --volumes -f

# 3. Log rotation
sudo journalctl --vacuum-time=7d
```

---

## 📊 Monitoring

### Manuel Health Check

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

---

## 🔧 Maintenance

### Sistem Güncelleme

```bash
# VM packages güncelle
ssh superdeploy@34.42.105.169
sudo apt update && sudo apt upgrade -y

# Docker güncelle
sudo apt install docker-ce docker-ce-cli containerd.io -y
```

---

## 🗑️ Silme İşlemleri

### Tüm Infrastructure'ı Sil

```bash
superdeploy destroy -p myproject
# Confirm? (y/n): y

# Bu komut:
# - GCP VM'leri siler
# - Terraform state temizler
# - .env'deki IP'leri temizler
```

### Sadece Bir Service'i Kaldır

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
- **FLOW.md:** İş akışı ve parametre akışı

---

**Yardıma mı ihtiyacın var?** 
- GitHub Issues: https://github.com/cfkarakulak/superdeploy/issues
