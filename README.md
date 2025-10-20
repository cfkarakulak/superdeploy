# 🚀 SuperDeploy - Zero-Config Deployment System

**Tek dosya, sıfır hardcode, tamamen otomatik!**

---

## 🎯 TL;DR (3 Adım)

```bash
# 1. .env'i kopyala ve IP'leri güncelle
cp ENV.example .env
nano .env  # Sadece IP'leri değiştir

# 2. Commit & Push
git add .env
git commit -m "config: initial setup"
git push

# 3. İzle ve tadını çıkar! 🎉
# Forgejo Actions otomatik olarak HER ŞEYİ deploy eder
```

**Hepsi bu kadar!** 

---

## 📁 Dosya Yapısı (ÇOK BASİT!)

```
superdeploy/
├── .env              ← TEK konfigürasyon dosyası (HERŞEYİ buradan yönet)
├── ENV.example       ← Şablon (ilk setup için kopyala)
├── SETUP.md          ← Detaylı dokümantasyon
└── deploy/
    ├── compose/
    │   ├── vm1-core/      ← CORE VM servisleri
    │   ├── vm2-scrape/    ← SCRAPE VM servisleri
    │   └── vm3-proxy/     ← PROXY VM servisleri
    └── .forgejo/workflows/ ← CI/CD (otomatik deployment)
```

---

## ⚙️ TEK .env Dosyası - HERŞEYİ Kontrol Eder

### 🔴 VM Restart Olduysa → SADECE .env'i Güncelle!

```bash
# 1. Yeni IP'leri al
gcloud compute instances list

# 2. .env'deki 6 satırı güncelle
nano .env

# Güncelle:
CORE_EXTERNAL_IP=YENİ_IP
CORE_INTERNAL_IP=YENİ_IP
SCRAPE_EXTERNAL_IP=YENİ_IP
SCRAPE_INTERNAL_IP=YENİ_IP
PROXY_EXTERNAL_IP=YENİ_IP
PROXY_INTERNAL_IP=YENİ_IP

# 3. Push et, bitti!
git add .env
git commit -m "update: VM IPs after restart"
git push

# 4. Forgejo Actions 3 VM'e de otomatik deploy yapar! 🎉
```

### 🔵 Şifre Değiştirmek İstersen → SADECE .env'i Güncelle!

```bash
nano .env

# Değiştir:
POSTGRES_PASSWORD=yeni_sifre
RABBITMQ_DEFAULT_PASS=yeni_sifre

# Push et
git add .env
git commit -m "security: update passwords"
git push

# Otomatik redeploy! 🎉
```

### 🟢 Yeni Servis Eklemek İstersen → SADECE .env'i Güncelle!

```bash
nano .env

# Yeni değişken ekle
REDIS_HOST=10.0.0.8
REDIS_PORT=6379

# Push et, bitti! 🎉
```

---

## 🎬 İlk Kurulum (Sıfırdan)

### Ön Koşul
- Terraform ile VM'ler oluşturulmuş olmalı
- Forgejo çalışıyor olmalı
- Runner kayıtlı olmalı

### 1. Repository'yi Klonla
```bash
git clone http://YOUR_FORGEJO_IP:3001/cradexco/superdeploy-app.git
cd superdeploy-app
```

### 2. .env Oluştur
```bash
cp ENV.example .env
nano .env
```

**ÖNEMLİ: Sadece şunları doldur:**
```env
# VM IP'leri (gcloud'dan al)
CORE_EXTERNAL_IP=34.56.43.99
CORE_INTERNAL_IP=10.0.0.5
SCRAPE_EXTERNAL_IP=34.67.236.167
SCRAPE_INTERNAL_IP=10.0.0.7
PROXY_EXTERNAL_IP=34.173.11.246
PROXY_INTERNAL_IP=10.0.0.6

# Şifreler (GÜVENLİ şifreler kullan!)
POSTGRES_PASSWORD=suPer_sEcurE_p4ss
RABBITMQ_DEFAULT_PASS=r4bbit_sEcurE_p4ss
API_SECRET_KEY=api_secret_min_32_characters_long_random
PROXY_REGISTRY_API_KEY=proxy_registry_api_key_random
PROXY_PASSWORD=proxy_sEcurE_p4ss
```

Geri kalan herşey otomatik! ✨

### 3. Push ve İzle
```bash
git add .env
git commit -m "config: initial deployment"
git push

# Forgejo Actions'a git ve izle:
open http://YOUR_IP:3001/cradexco/superdeploy-app/actions
```

**3 workflow paralel çalışır:**
- 🚀 Deploy CORE VM   (PostgreSQL, RabbitMQ, API, Proxy Registry, Dashboard)
- 🔍 Deploy SCRAPE VM (Scraping Workers, Playwright)
- 🌐 Deploy PROXY VM  (SOCKS5, HTTP Proxy, IP Monitor)

---

## 🧪 Deployment'ı Test Et

```bash
# API Health
curl http://${CORE_EXTERNAL_IP}:8000/health

# Proxy Registry Health
curl http://${CORE_EXTERNAL_IP}:8080/health

# Dashboard
open http://${CORE_EXTERNAL_IP}:8001

# RabbitMQ Management
open http://${CORE_EXTERNAL_IP}:15672
# User: superdeploy
# Pass: (RABBITMQ_DEFAULT_PASS from .env)
```

**Hepsi "healthy" gösteriyorsa → ✅ BAŞARILI!**

---

## 🔧 Günlük Kullanım

### Tek Bir Şey Hatırla:

```
.env değiş → push et → otomatik deploy!
```

### Örnekler:

#### VM Restart Oldu
```bash
nano .env     # IP'leri güncelle
git push      # Deploy!
```

#### Config Değişikliği
```bash
nano .env     # İstediğin değişkeni değiştir
git push      # Deploy!
```

#### Manuel Deployment
```bash
# Forgejo'da workflow'u manuel tetikle
http://YOUR_IP:3001/cradexco/superdeploy-app/actions
# "Run workflow" butonuna tıkla
```

---

## 🚨 Sorun Giderme

### 1. Workflow Çalışmıyor
```bash
# Runner'ı kontrol et
ssh superdeploy@${CORE_EXTERNAL_IP}
systemctl status forgejo-runner

# Restart
sudo systemctl restart forgejo-runner
```

### 2. Servisler Başlamıyor
```bash
# Herhangi bir VM'de
ssh superdeploy@${VM_IP}
cd /opt/superdeploy/compose
docker compose logs
```

### 3. RabbitMQ Authentication Hatası
```bash
# .env'deki şifrelerde özel karakter (!, $, vb.) kullanma
# Basit şifreler kullan: SuperSecurePass123
```

### 4. Database Connection Hatası
```bash
# Postgres'in healthy olduğundan emin ol
docker compose ps postgres

# Volume'u temizle ve yeniden başlat
docker compose down
docker volume rm superdeploy_postgres_data
docker compose up -d
```

---

## 📊 Mimari

```
┌─────────────────────────────────────────────────────────┐
│  .env (Tek Kaynak)                                       │
│  - VM IPs                                                │
│  - Passwords                                             │
│  - Configuration                                         │
└────────────────┬────────────────────────────────────────┘
                 │
                 ├─> Forgejo Actions (CI/CD)
                 │
       ┌─────────┼─────────┬────────────┐
       │         │         │            │
       v         v         v            v
   CORE VM   SCRAPE VM  PROXY VM   (Future VMs)
   
   HERŞEYİ .env kontrol eder!
```

---

## 🎓 Best Practices

1. **Asla** production şifrelerini commit etme (geliştirme için OK)
2. **Her zaman** .env'i güncel tut
3. **Workflow loglarını** izle: `http://YOUR_IP:3001/.../actions`
4. **Backup al**: .env dosyasını güvenli bir yerde sakla
5. **Test et**: Değişiklik yaptıktan sonra health check'leri kontrol et

---

## 🎉 Başarı Kriterleri

✅ Tek `.env` dosyası var  
✅ Hiç hardcoded IP/şifre yok  
✅ `git push` → otomatik deployment  
✅ Tüm servisler "healthy"  
✅ VM restart → sadece .env güncelle → push → çalışır  

---

## 📚 Daha Fazla Bilgi

- **Detaylı Setup**: `SETUP.md`
- **Env Variables**: `ENV.example` (tüm değişkenlerin açıklaması)
- **Forgejo Actions**: http://YOUR_IP:3001/cradexco/superdeploy-app/actions

---

**🚀 Kolay deployment'ların tadını çıkar!**

_Yapımcı: Sıfır hardcode felsefesi ile ❤️_

