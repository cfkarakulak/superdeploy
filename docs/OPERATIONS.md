# Günlük Operasyonlar

Bu döküman, sistemi kurduktan sonra **günlük kullanımda** ihtiyaç duyacağın tüm komutları ve senaryoları içerir.

---

## 🎯 Hızlı Referans

```bash
# Sistem durumu
superdeploy status -p cheapa

# Yeni deployment
git push origin production

# Rollback
superdeploy rollback -a api v42

# Logs
superdeploy logs -p cheapa -a api --tail 100

# Secrets yönetimi
superdeploy env show
superdeploy sync -p cheapa

# Infrastructure
superdeploy destroy -p cheapa
```

---

## 📊 Sistem Durumu Kontrolü

### **Tüm Servislerin Durumu**

```bash
superdeploy status -p cheapa
```

**Çıktı:**
```
╭─────────────────────────────────────╮
│ 🚀 SuperDeploy Status               │
╰─────────────────────────────────────╯

Infrastructure Status:
  ✅ GCP Project: galvanic-camp-475519-d6
  ✅ Core VM: cheapa-core (RUNNING)
  ✅ External IP: 34.42.105.169
  ✅ Internal IP: 10.0.0.5

Core Services (Project: cheapa):
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
# GitHub Actions: https://github.com/cheapaio/api/actions
# Forgejo: http://34.42.105.169:3001/cradexco/superdeploy-app/actions

# 5. Sonra main'e de merge et
git checkout main
git merge hotfix/critical-bug
git push origin main
```

### **Senaryo 3: Rollback (Geri Alma)**

```bash
# 1. Hangi versiyonlar var?
superdeploy releases -p cheapa -a api

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
superdeploy logs -p cheapa -a api --tail 100

# Real-time takip (Ctrl+C ile çık)
superdeploy logs -p cheapa -a api --follow

# Belirli bir zaman aralığı
superdeploy logs -p cheapa -a api --since "30m"

# Error logları filtrele
superdeploy logs -p cheapa -a api --tail 500 | grep ERROR
```

### **Database Logs**

```bash
# PostgreSQL logs
superdeploy logs -p cheapa -s postgres --tail 100

# RabbitMQ logs
superdeploy logs -p cheapa -s rabbitmq --tail 100
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
docker exec -it cheapa-api bash

# Logs
docker logs cheapa-api --tail 100
```

---

## 🔐 Secrets ve Environment Variables

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

### **Secrets Değiştirme**

```bash
# 1. .env dosyasını düzenle
nano superdeploy/.env

# 2. Yeni değerleri GitHub'a sync et
superdeploy sync -p cheapa

# 3. Servisleri restart et (yeni env'ler yüklensin)
superdeploy restart -p cheapa -a api
```

### **Yeni Bir Secret Ekleme**

```bash
# 1. .env'e ekle
echo "NEW_API_KEY=abc123xyz" >> superdeploy/.env

# 2. Sync et
superdeploy sync -p cheapa

# 3. docker-compose.apps.yml'e ekle (eğer container'da kullanılacaksa)
# environment:
#   NEW_API_KEY: ${NEW_API_KEY}

# 4. Redeploy (git push veya manuel)
superdeploy restart -p cheapa -a api
```

---

## 🗄️ Database İşlemleri

### **Database Migration**

```bash
# Otomatik (deployment sırasında)
# .github/workflows/deploy.yml içinde migrate: "true" ayarla

# Manuel
ssh superdeploy@34.42.105.169
cd /opt/superdeploy/projects/cheapa/compose
docker compose run --rm api alembic upgrade head
```

### **Database Backup**

```bash
# PostgreSQL dump al
ssh superdeploy@34.42.105.169
docker exec cheapa-postgres pg_dump -U superdeploy superdeploy_db > backup_$(date +%Y%m%d).sql

# Local'e indir
scp -i ~/.ssh/superdeploy_deploy superdeploy@34.42.105.169:backup_*.sql ./
```

### **Database Restore**

```bash
# Backup dosyasını VM'ye yükle
scp -i ~/.ssh/superdeploy_deploy backup_20251021.sql superdeploy@34.42.105.169:~/

# Restore et
ssh superdeploy@34.42.105.169
cat backup_20251021.sql | docker exec -i cheapa-postgres psql -U superdeploy superdeploy_db
```

---

## 📦 Container Yönetimi

### **Container'ları Restart Etme**

```bash
# Tek bir service
superdeploy restart -p cheapa -a api

# Tüm app services
superdeploy restart -p cheapa --all

# Core services (PostgreSQL, RabbitMQ, vb.)
ssh superdeploy@34.42.105.169
cd /opt/superdeploy/projects/cheapa/compose
docker compose -f docker-compose.core.yml restart postgres
```

### **Container Scaling**

```bash
# Birden fazla worker instance çalıştır
ssh superdeploy@34.42.105.169
cd /opt/superdeploy/projects/cheapa/compose
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
superdeploy up -p cheapa

# Veya sadece sync:
superdeploy sync -p cheapa

# 2. Yeni IP'yi kontrol et
superdeploy status -p cheapa

# 3. GitHub secrets güncellenmiş mi kontrol et
gh secret list --repo cheapaio/api | grep FORGEJO_BASE_URL

# 4. Test deployment
cd app-repos/api
git commit --allow-empty -m "test: verify new IP"
git push origin production
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
cd /opt/superdeploy/projects/cheapa/compose
docker compose -f docker-compose.core.yml up -d

# 4. App services'i başlat
docker compose -f docker-compose.apps.yml up -d

# 5. Logs kontrol et
docker logs cheapa-postgres --tail 100
docker logs cheapa-api --tail 100
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
docker exec cheapa-postgres pg_isready -U superdeploy

# RabbitMQ
docker exec cheapa-rabbitmq rabbitmq-diagnostics ping

# Redis
docker exec cheapa-redis redis-cli ping
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
superdeploy destroy -p cheapa
# Confirm? (y/n): y

# Bu komut:
# - GCP VM'leri siler
# - Terraform state temizler
# - .env'deki IP'leri temizler
```

### **Sadece Bir Service'i Kaldır**

```bash
ssh superdeploy@34.42.105.169
cd /opt/superdeploy/projects/cheapa/compose
docker compose -f docker-compose.apps.yml stop services
docker compose -f docker-compose.apps.yml rm -f services
```

---

## 📚 Daha Fazla Bilgi

- **OVERVIEW.md:** Genel mimari ve kavramlar
- **SETUP.md:** İlk kurulum
- **DEPLOYMENT.md:** Deployment flow detayları

---

**Yardıma mı ihtiyacın var?** 
- GitHub Issues: https://github.com/cfkarakulak/superdeploy/issues
- Email: cradexco@gmail.com

