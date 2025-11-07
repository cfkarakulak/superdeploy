# Günlük Operasyonlar

Bu doküman, sistemi kurduktan sonra **günlük kullanımda** ihtiyaç duyacağın tüm komutları ve senaryoları içerir.

---

## 🎯 Hızlı Referans

```bash
# Orchestrator durumu
superdeploy orchestrator:status

# Orchestrator'a SSH
superdeploy orchestrator:ssh

# Sistem durumu (tüm VM'ler ve servisler)
superdeploy status -p myproject

# Yeni deployment (otomatik)
git push origin production

# Logs (real-time)
superdeploy logs -p myproject -a api --follow

# Secrets yönetimi (GitHub + Forgejo sync)
superdeploy sync -p myproject

# Selective addon deployment (sadece belirli addon)
superdeploy myproject:up --addon postgres

# IP korumalı deployment
superdeploy myproject:up --preserve-ip

# Infrastructure silme
superdeploy myproject:down
```

---

## 📊 Sistem Durumu Kontrolü

### Orchestrator Durumu

```bash
superdeploy orchestrator:status
```

**Çıktı:**
```
✅ Orchestrator is deployed
  IP: 34.72.179.175
  URL: http://34.72.179.175:3001
  Forgejo: https://forgejo.yourdomain.com
  Grafana: https://grafana.yourdomain.com
  Prometheus: https://prometheus.yourdomain.com
```

### Proje Durumu

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
  ✅ Core VM: myproject-core-0 (RUNNING) - 10.1.0.2
  ✅ App VM: myproject-app-0 (RUNNING) - 10.1.0.3

Services (Core VM):
  ✅ PostgreSQL: healthy (5432)
  ✅ RabbitMQ: healthy (5672)

Application Services (App VM):
  ✅ API: healthy (8000) - v45
  ✅ Dashboard: healthy (3000) - v23
  ✅ Services: healthy (8001) - v12
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

# Orchestrator Forgejo logs
superdeploy orchestrator logs -s forgejo --tail 100

# Prometheus logs
superdeploy orchestrator logs -s prometheus --tail 100

# Grafana logs
superdeploy orchestrator logs -s grafana --tail 100
```

### VM'ye SSH ile Bağlanma

```bash
# Orchestrator VM'ye bağlan
superdeploy orchestrator ssh

# Proje VM'ye bağlan (otomatik)
superdeploy ssh -p myproject

# Manuel (belirli VM)
ssh -i ~/.ssh/superdeploy_deploy superdeploy@WEB_VM_IP
ssh -i ~/.ssh/superdeploy_deploy superdeploy@API_VM_IP

# Container'lara bak
docker ps

# API container'ına gir
docker exec -it myproject-api bash

# Logs
docker logs myproject-api --tail 100
```

---

## 🔐 Secrets ve Environment Variables Yönetimi (Heroku-like! 🚀)

### Environment Variable Stratejisi

SuperDeploy, local development ve production ortamlarını ayırmak için iki farklı dosya kullanır:

- **`.env`** - Local development (SuperDeploy ASLA değiştirmez)
- **`.env.superdeploy`** - Production (SuperDeploy otomatik oluşturur)

### ⚡ Hızlı Yöntem: config:set Komutu (Heroku-like!)

**EN KOLAY VE HIZLI YÖNTEM!** Tek komutla env güncelle + sync + deploy:

```bash
# Env variable güncelle
superdeploy config:set API_KEY=xyz123 -p myproject

# Env güncelle + OTOMATIK DEPLOY! 🚀
superdeploy config:set DB_HOST=10.0.0.5 -p myproject --deploy

# Tek bir app için deploy
superdeploy config:set STRIPE_API_KEY=sk_live_xyz -p myproject -a api --deploy

# Env değişkeni sil
superdeploy config:unset OLD_API_KEY -p myproject --deploy
```

**Bu komut şunları yapar:**
1. ✅ `secrets.yml` dosyasını günceller
2. ✅ GitHub ve Forgejo'ya sync eder
3. ✅ `--deploy` flag varsa otomatik git push yapar
4. ✅ Deployment'ı tetikler

**Artık manuel işlem yok! Heroku gibi tek komut!** 🎉

### 📋 Config Yönetimi Komutları

```bash
# Tüm config'leri listele
superdeploy config:list -p myproject

# Sadece POSTGRES değişkenlerini göster
superdeploy config:list -p myproject --filter POSTGRES

# Tek bir değişkeni oku
superdeploy config:get POSTGRES_PASSWORD -p myproject

# Detaylı config görüntüle (servis gruplarıyla)
superdeploy config:show -p myproject
superdeploy config:show -p myproject --mask  # Şifreleri maskele
```

### Sync Komutu Nasıl Çalışır? (Advanced)

**Not:** Artık `config:set --deploy` kullanabilirsin, ama manuel control istiyorsan:

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
   - `projects/[project]/secrets.yml` (otomatik şifreler)
   - `--env-file` ile belirtilen dosyalar

2. **Merge eder (öncelik sırası):**
   - En yüksek: `--env-file` dosyaları
   - Orta: `secrets.yml`
   - En düşük: `superdeploy/.env`

3. **Dağıtır:**
   - GitHub Repository Secrets
   - GitHub Environment Secrets
   - Forgejo Repository Secrets

### 🎯 Gerçek Dünya Senaryoları

#### Senaryo 1: PostgreSQL Şifresini Değiştir (Heroku Yöntemi)

```bash
# Tek komut! 🚀
superdeploy config:set POSTGRES_PASSWORD=yeni_sifre -p myproject --deploy

# Deployment loglarını izle
superdeploy logs -p myproject --follow
```

**Bu kadar!** Heroku gibi basit!

#### Senaryo 2: Yeni API Key Ekle (Heroku Yöntemi)

```bash
# Stripe API key ekle + deploy
superdeploy config:set STRIPE_API_KEY=sk_live_xyz -p myproject --deploy

# Sadece api servisi için deploy
superdeploy config:set STRIPE_API_KEY=sk_live_xyz -p myproject -a api --deploy
```

#### Senaryo 3: Eski Secret'ı Sil (Heroku Yöntemi)

```bash
# Eski API key'i sil + deploy
superdeploy config:unset OLD_API_KEY -p myproject --deploy
```

#### Senaryo 4: Manuel Kontrol İstiyorsan (Eski Yöntem)

```bash
# 1. Manuel edit
nano projects/myproject/secrets.yml

# 2. Sync (deployment tetikleme)
superdeploy sync -p myproject

# 3. Manuel deployment
cd app-repos/api
git commit --allow-empty -m "config: update secrets"
git push origin production
```

### Production Secret'larını Güncelleme (Eski Yöntem)

**Artık `config:set --deploy` kullan, ama manuel istiyorsan:**

```bash
# 1. Sadece production şifresini güncelle
nano projects/myproject/secrets.yml
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
    ├── secrets.yml                # Otomatik oluşturulan şifreler
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
| Production secret | `projects/[project]/secrets.yml` | `superdeploy sync` |
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

**Not:** IP preservation aktif olduğu için VM restart'ta IP korunur. Ancak VM silinip yeniden oluşturulursa:

```bash
# 1. superdeploy up komutu otomatik günceller
superdeploy myproject:up

# 2. Yeni IP'yi kontrol et
superdeploy status -p myproject

# 3. GitHub secrets güncellenmiş mi kontrol et
gh secret list --repo myprojectio/api | grep FORGEJO_BASE_URL

# 4. Test deployment
cd app-repos/api
git commit --allow-empty -m "test: verify new IP"
git push origin production
```

### Orchestrator IP Değişimi

Orchestrator IP değişirse tüm projeler etkilenir:

```bash
# 1. Orchestrator'ı yeniden deploy et
superdeploy orchestrator up

# 2. Tüm projelerin project.yml'ini güncelle
# orchestrator.host: "YENİ_IP"

# 3. Her projeyi yeniden deploy et
superdeploy myproject:up

# 4. Runner'ları yeniden register et
superdeploy myproject:up --tags runner
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
superdeploy myproject:up

# Çözüm 2: Manuel kontrol et (project VM'de)
ssh superdeploy@PROJECT_VM_IP
cat /opt/forgejo-runner/.age/key.txt

# Çözüm 3: Orchestrator'da kontrol et
superdeploy orchestrator ssh
cat /opt/forgejo-runner/.age/key.txt
```

### "PAT creation failed" Hatası

```bash
# Çözüm 1: Orchestrator Forgejo'nun çalıştığını kontrol et
curl http://ORCHESTRATOR_IP:3001/api/healthz

# Çözüm 2: Admin şifresini kontrol et
cat projects/orchestrator/secrets.yml | grep FORGEJO_ADMIN_PASSWORD

# Çözüm 3: Orchestrator durumunu kontrol et
superdeploy orchestrator status
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
# 1. Orchestrator'ı kontrol et
superdeploy orchestrator status
superdeploy orchestrator ssh

# 2. Orchestrator container'ları kontrol et
docker ps -a
docker compose -f /var/lib/superdeploy/orchestrator/compose/docker-compose.yml up -d

# 3. Proje VM'ye bağlan
ssh superdeploy@PROJECT_VM_IP

# 4. Container durumunu kontrol et
docker ps -a

# 5. Services'i başlat
cd /opt/superdeploy/projects/myproject/compose
docker compose -f docker-compose.core.yml up -d
docker compose -f docker-compose.apps.yml up -d

# 6. Logs kontrol et
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
# Orchestrator Services
curl http://ORCHESTRATOR_IP:3001/api/healthz  # Forgejo
curl http://ORCHESTRATOR_IP:9090/-/healthy    # Prometheus
curl http://ORCHESTRATOR_IP:3000/api/health   # Grafana

# API
curl http://API_VM_IP:8000/health

# PostgreSQL
ssh superdeploy@WEB_VM_IP
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
# Orchestrator VM güncelle
superdeploy orchestrator ssh
sudo apt update && sudo apt upgrade -y

# Proje VM'leri güncelle
ssh superdeploy@PROJECT_VM_IP
sudo apt update && sudo apt upgrade -y

# Docker güncelle
sudo apt install docker-ce docker-ce-cli containerd.io -y

# Caddy güncelle (orchestrator'da)
superdeploy orchestrator up --addon caddy
```

---

## 🗑️ Silme İşlemleri

### Tüm Infrastructure'ı Sil

```bash
# Proje infrastructure'ını sil
superdeploy destroy -p myproject
# Confirm? (y/n): y

# Bu komut:
# - GCP VM'leri siler
# - Terraform state temizler
# - .env'deki IP'leri temizler

# Orchestrator'ı sil (DİKKATLİ! Tüm projeleri etkiler)
superdeploy orchestrator destroy
# Confirm? (y/n): y
```

### Sadece Bir Service'i Kaldır

```bash
ssh superdeploy@34.42.105.169
cd /opt/superdeploy/projects/myproject/compose
docker compose -f docker-compose.apps.yml stop services
docker compose -f docker-compose.apps.yml rm -f services
```

---

## 🎯 Yeni Özellikler

### Selective Addon Deployment

Sadece belirli bir addon'ı deploy et:

```bash
# Sadece postgres'i deploy et
superdeploy myproject:up --addon postgres

# Sadece caddy'yi güncelle (orchestrator'da)
superdeploy orchestrator up --addon caddy

# Sadece monitoring'i güncelle
superdeploy orchestrator up --addon monitoring
```

### Monitoring Erişimi

```bash
# Grafana (subdomain ile)
https://grafana.yourdomain.com

# Prometheus (subdomain ile)
https://prometheus.yourdomain.com

# Forgejo (subdomain ile)
https://forgejo.yourdomain.com

# Direkt IP ile
http://ORCHESTRATOR_IP:3000  # Grafana
http://ORCHESTRATOR_IP:9090  # Prometheus
http://ORCHESTRATOR_IP:3001  # Forgejo
```

## 📚 Daha Fazla Bilgi

- **ARCHITECTURE.md:** Genel mimari ve kavramlar
- **SETUP.md:** İlk kurulum
- **FLOW.md:** İş akışı ve parametre akışı
- **ORCHESTRATOR_SETUP.md:** Orchestrator kurulum rehberi
- **RUNNER_ARCHITECTURE.md:** Runner mimarisi

---

**Yardıma mı ihtiyacın var?** 
- GitHub Issues: https://github.com/cfkarakulak/superdeploy/issues
