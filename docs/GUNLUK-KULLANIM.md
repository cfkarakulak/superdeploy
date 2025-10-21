# 📝 SuperDeploy - Günlük Kullanım Kılavuzu

## Deployment Workflow

### Normal Deployment (Otomatik)

Kod değişikliğinizi `production` branch'ine push ettiğinizde her şey otomatik çalışır:

```bash
cd app-repos/api

# Değişiklikleri commit edin
git add .
git commit -m "feat: Add new endpoint"

# Production'a push edin
git push origin production
```

**Ne Olur:**
1. GitHub Actions tetiklenir (2-5 dakika)
2. Docker image build edilir
3. Image Docker Hub'a push edilir
4. Environment variable'lar şifrelenir
5. Forgejo'ya deployment isteği gönderilir
6. Forgejo runner şifreyi açar ve deploy eder
7. Email notification alırsınız

### Manuel Deployment (CLI)

Bazen GitHub Actions'ı atlayıp doğrudan deploy etmek isteyebilirsiniz:

```bash
superdeploy deploy \
  --app api \
  --tag abc1234 \
  --migrate
```

Parametreler:
- `--app`: Hangi servis (api, dashboard, services)
- `--tag`: Docker image tag'i
- `--migrate`: Database migration'ları çalıştır (opsiyonel)

## Log Takibi

### Canlı Log İzleme

Deployment sırasında veya hata ayıklarken logları canlı izleyin:

```bash
# API logları (son 100 satır + canlı takip)
superdeploy logs -a api -f

# Sadece son 50 satır
superdeploy logs -a api -l 50

# Ctrl+C ile durdurun
```

### Tüm Servislerin Logları

```bash
# PostgreSQL
superdeploy logs -a postgres

# RabbitMQ
superdeploy logs -a rabbitmq

# Redis
superdeploy logs -a redis
```

**Log Format:**
Loglar timestamp ile gelir ve renklendirilir. Error'lar kırmızı, warning'ler sarı görünür.

## Status Kontrolü

Sistemin genel durumunu kontrol edin:

```bash
superdeploy status
```

**Çıktı:**
```
SuperDeploy Infrastructure Status
┏━━━━━━━━━━━┳━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Component ┃ Status     ┃ Details                       ┃
┡━━━━━━━━━━━╇━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ Core VM   │ ✅ Running │ 34.61.244.204 (up 41 minutes) │
│ Forgejo   │ ✅ Active  │ v13.0.1                       │
│ Runner    │ ✅ Active  │ core-runner                   │
└───────────┴────────────┴───────────────────────────────┘
```

**Sorun Durumunda:**
- ❌ kırmızı X: Servis çalışmıyor
- ⚠️ sarı ünlem: Warning durumu
- ✅ yeşil tik: Her şey normal

## Release Yönetimi

### Release Geçmişi

Hangi versiyonların ne zaman deploy edildiğini görün:

```bash
superdeploy releases -a api
```

**Çıktı:**
```
Release History - API
┏━━━━━━━━━┳━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━┳━━━━━━━━━━━━┓
┃ Version ┃ Git SHA ┃ Deployed At          ┃ Image   ┃ Status     ┃
┡━━━━━━━━━╇━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━╇━━━━━━━━━━━━┩
│ v42     │ abc1234 │ 2025-10-21 12:34:35Z │ abc1234 │ ✅ RUNNING │
│ v41     │ def5678 │ 2025-10-20 09:11:22Z │ def5678 │            │
│ v40     │ ghi9012 │ 2025-10-19 15:45:10Z │ ghi9012 │            │
└─────────┴─────────┴──────────────────────┴─────────┴────────────┘

💡 To rollback: superdeploy rollback -a api <sha>
```

### Rollback (Geri Alma)

Bir önceki versiyona hızlıca geri dönün:

```bash
# SHA ile rollback
superdeploy rollback -a api def5678

# Confirmation ister:
⚠️  Rollback Warning

App: api
Target: def5678

Continue with rollback? [y/N]: y

🔄 Triggering rollback deployment...
✅ Rollback triggered successfully!
```

**Ne Zaman Kullanılır:**
- Yeni deployment'ta critical bug bulundu
- Performance sorunu oluştu
- Hızlıca eski stabil versiyona dönmek gerekiyor

**Nasıl Çalışır:**
Rollback, eski image tag'i ile yeni bir deployment tetikler. Zero-downtime olarak eski versiyona döner. Database migration'ları geri alınmaz (dikkatli olun!).

## One-off Commands (Tek Seferlik Komutlar)

Container içinde komut çalıştırmak için:

```bash
# Database migration
superdeploy run api "alembic upgrade head"

# Django shell
superdeploy run api "python manage.py shell"

# Celery task'i manuel çalıştır
superdeploy run services "celery -A app.celery call app.tasks.cleanup"

# Interactive bash
superdeploy run api "bash"
```

**Kullanım Örnekleri:**

### Database Seed
```bash
superdeploy run api "python manage.py seed_database"
```

### Cache Temizleme
```bash
superdeploy run api "python -c 'from app import redis_client; redis_client.flushall()'"
```

### User Oluşturma
```bash
superdeploy run api "python scripts/create_admin.py admin@example.com"
```

## Service Restart

Bir servisi yeniden başlatmak için:

```bash
superdeploy restart -a api
```

**Ne Zaman Kullanılır:**
- Config değişikliği yaptınız ama deployment yapmak istemiyorsunuz
- Servis hang olmuş, manual restart gerekiyor
- Memory leak şüphesi var, temiz başlatmak istiyorsunuz

**Downtime:** Kısa süre (5-10 saniye) downtime olur. Zero-downtime restart için full deployment yapın.

## Scaling (Ölçeklendirme)

Servis replikalarını artırın:

```bash
# API'yi 3 instance'a çıkar
superdeploy scale api=3

# Dashboard'u 2 instance yap
superdeploy scale dashboard=2

# Workers'ı 5'e çıkar
superdeploy scale services=5
```

**Load Balancing:**
Caddy (reverse proxy) otomatik olarak istekleri tüm instance'lara dağıtır. Horizontal scaling sayesinde yük artışlarına kolayca karşılık verebilirsiniz.

**Dikkat:**
- Database ve Queue'yu scale etmeyin (tek instance olmalı)
- Her instance ayrı container olarak çalışır
- Memory ve CPU kullanımı artacaktır

## Environment Variable Yönetimi

### Güvenli Görüntüleme

Environment variable'ları güvenli şekilde görüntüleyin:

```bash
# Masked view (default)
superdeploy env show

# Çıktı:
Environment Variables
┏━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━┓
┃ Key                  ┃ Value          ┃
┡━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━┩
│ POSTGRES_PASSWORD    │ Supe...Pass    │
│ RABBITMQ_PASSWORD    │ Supe...Pass    │
└──────────────────────┴────────────────┘
```

### Full Values (Şifre Gerektirir)

```bash
superdeploy env show --no-mask

# GITHUB_TOKEN sorar:
Token: ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# Full values gösterir
POSTGRES_PASSWORD    SuperSecurePass123!
```

**Güvenlik:**
- Default olarak passwordler maskelenir
- `--no-mask` için `.env` dosyasındaki `GITHUB_TOKEN` gerekir
- Shell history'e password yazılmaz (getpass kullanılır)

### Health Check

Environment konfigürasyonunun sağlığını kontrol edin:

```bash
superdeploy env check
```

**Çıktı:**
```
🔍 Environment Health Check

Issues found:
  ❌ API_SECRET_KEY: Not set
  ❌ POSTGRES_PASSWORD: Short password (< 16 chars)

Warnings:
  ⚠️  SENTRY_DSN: Not configured (optional)

Summary:
  Total vars: 34
  Issues: 2
  Warnings: 1
```

## Config Değişiklikleri

Environment variable değiştirdiğinizde yapmanız gerekenler:

### Senaryo 1: IP Değişti (VM Restart)

```bash
# Terraform yeniden çalıştır
cd superdeploy
superdeploy up --skip-ansible

# .env otomatik güncellenir

# GitHub secrets'ı güncelle
superdeploy sync
```

### Senaryo 2: Password Değiştirme

```bash
# .env dosyasını düzenle
nano .env
# POSTGRES_PASSWORD=YeniGuvenliPassword

# GitHub'a sync et
superdeploy sync

# Servisleri restart et (yeni password'ü alsınlar)
superdeploy restart -a api
superdeploy restart -a dashboard
superdeploy restart -a services
```

### Senaryo 3: Yeni Secret Ekleme

```bash
# .env'e ekle
echo "NEW_API_KEY=xxx" >> .env

# GitHub'a sync et
superdeploy sync

# Yeni deployment (secret'ı kullanacak)
git push origin production
```

## Monitoring

### Container Health

Tüm container'ların health durumunu kontrol edin:

```bash
ssh -i ~/.ssh/superdeploy_deploy superdeploy@YOUR_CORE_IP \
  "docker ps --format 'table {{.Names}}\t{{.Status}}'"
```

### Resource Usage

CPU ve memory kullanımını görün:

```bash
ssh -i ~/.ssh/superdeploy_deploy superdeploy@YOUR_CORE_IP \
  "docker stats --no-stream"
```

### Disk Kullanımı

```bash
ssh -i ~/.ssh/superdeploy_deploy superdeploy@YOUR_CORE_IP \
  "df -h"
```

## Troubleshooting (Hata Ayıklama)

### Deployment Başarısız

1. **GitHub Actions loglarını kontrol edin:**
```bash
cd app-repos/api
gh run view --log
```

2. **Forgejo Actions loglarını kontrol edin:**
Forgejo UI → Actions sekmesi → Son workflow → Loglar

3. **Container loglarını kontrol edin:**
```bash
superdeploy logs -a api -l 200
```

### Servis Çalışmıyor

```bash
# Container durumu
superdeploy status

# Container restart
superdeploy restart -a api

# Container logları
superdeploy logs -a api -f
```

### Database Bağlantı Hatası

```bash
# PostgreSQL durumu
ssh -i ~/.ssh/superdeploy_deploy superdeploy@CORE_IP \
  "docker exec superdeploy-postgres pg_isready"

# PostgreSQL logları
ssh -i ~/.ssh/superdeploy_deploy superdeploy@CORE_IP \
  "docker logs superdeploy-postgres --tail 100"
```

### Network Sorunları

```bash
# Container'lar arasında network testi
ssh -i ~/.ssh/superdeploy_deploy superdeploy@CORE_IP \
  "docker exec superdeploy-api ping -c 3 superdeploy-postgres"

# Port listening kontrolü
ssh -i ~/.ssh/superdeploy_deploy superdeploy@CORE_IP \
  "netstat -tlnp | grep 8000"
```

## Best Practices

### 1. Her Zaman Production Branch Kullanın
```bash
git checkout production
git merge develop
git push origin production
```

### 2. Migration'ları Test Edin
```bash
# Staging'de test edin
superdeploy run api "alembic upgrade head --sql"

# Production'da dikkatli çalıştırın
superdeploy deploy --app api --tag v1.2.3 --migrate
```

### 3. Rollback Planı Hazırlayın
Her critical deployment öncesi:
- Mevcut version'ı not edin: `superdeploy releases -a api`
- Database backup alın
- Rollback komutunu hazırlayın: `superdeploy rollback -a api <old-sha>`

### 4. Log Monitoring
Critical deployment'larda logları takip edin:
```bash
superdeploy logs -a api -f | tee deployment-$(date +%Y%m%d-%H%M).log
```

### 5. Health Check Sonrası Doğrulama
Deployment sonrası manuel smoke test yapın:
```bash
curl http://YOUR_IP:8000/health
curl http://YOUR_IP:8000/api/users/me
```

## Hızlı Referans

```bash
# Deployment
git push origin production                    # Otomatik deployment
superdeploy deploy --app api --tag v1.2.3    # Manuel deployment

# Monitoring
superdeploy status                            # Genel durum
superdeploy logs -a api -f                    # Canlı loglar
superdeploy releases -a api                   # Release geçmişi

# Operations
superdeploy restart -a api                    # Restart
superdeploy rollback -a api abc1234           # Rollback
superdeploy run api "python manage.py shell" # One-off command
superdeploy scale api=3                       # Scaling

# Config
superdeploy env show                          # Environment vars (masked)
superdeploy env check                         # Health check
superdeploy sync                              # GitHub secrets sync
```

---

**İpucu:** Sık kullandığınız komutlar için bash alias tanımlayın:

```bash
# ~/.bashrc veya ~/.zshrc
alias sd='superdeploy'
alias sdlogs='superdeploy logs -a api -f'
alias sdstatus='superdeploy status'
alias sddeploy='superdeploy deploy --app api'
```

Artık `sd status` yazarak hızlıca durum kontrol edebilirsiniz!

