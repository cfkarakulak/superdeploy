# 🎯 SuperDeploy - Gelişmiş Konular

## Secret Encryption (AGE)

SuperDeploy, environment variable'ları GitHub Actions'tan Forgejo runner'a güvenli şekilde transfer etmek için AGE encryption kullanır.

### Nasıl Çalışır

**1. Setup (Tek Seferlik):**
- Ansible, Forgejo runner VM'inde AGE keypair oluşturur
- Private key VM'de kalır (`/opt/forgejo-runner/.age/key.txt`)
- Public key `superdeploy sync` ile GitHub Secrets'a eklenir

**2. Deployment:**
```
GitHub Actions
  ↓
  1. .env dosyası oluşturulur (secrets'tan)
  2. AGE public key ile şifrelenir
  3. Base64 encode edilir
  ↓
Forgejo API
  ↓
Forgejo Runner
  ↓
  4. Base64 decode edilir
  5. AGE private key ile şifresi çözülür
  6. /opt/superdeploy/.env.decrypted yazılır
  ↓
Docker Compose
  ↓
  7. Şifreli .env yüklenir
  8. Services başlatılır
  ↓
Cleanup
  ↓
  9. /opt/superdeploy/.env.decrypted güvenli şekilde silinir (shred -u)
```

### Güvenlik Özellikleri

**Encryption at Rest:**
Private key sadece runner VM'de, disk encrypted olarak saklanır.

**Encryption in Transit:**
Environment variable'lar GitHub → Forgejo transfer'i sırasında şifreli gider.

**No Persistent Storage:**
Şifresi çözülmüş .env dosyası sadece deployment süresince disk'te kalır, sonra `shred` ile güvenli şekilde silinir.

**Access Control:**
Private key'e sadece `superdeploy` user'ı (runner) erişebilir. File permissions: `600`.

## Zero-Downtime Deployment

SuperDeploy, Docker Compose'un update stratejisiyle zero-downtime deployment yapar.

### Deployment Akışı

**1. Health Check:**
Yeni container ayağa kalkar ve health check'leri geçer.

**2. Graceful Shutdown:**
Eski container'a SIGTERM gönderilir. `stop_grace_period` kadar bekler.

**3. Traffic Switch:**
Load balancer (Caddy) yeni container'a yönlendirmeye başlar.

**4. Old Container Cleanup:**
Eski container temizlenir.

### Config (docker-compose.apps.yml)

```yaml
api:
  healthcheck:
    test: ["CMD", "curl", "-fsS", "http://localhost:8000/healthz"]
    interval: 10s
    timeout: 5s
    retries: 12
    start_period: 30s
  stop_grace_period: 30s  # Graceful shutdown
```

**Health Check Parameters:**
- `start_period`: Container başlangıcında bekle (30s)
- `interval`: Her 10 saniyede bir kontrol et
- `retries`: 12 başarısız denemeden sonra unhealthy say
- `timeout`: Her check max 5 saniye

**Graceful Shutdown:**
`stop_grace_period` içinde container şunları yapmalı:
- Yeni request'leri reddet
- Mevcut request'leri tamamla
- Database connection'ları temizle
- Temiz şekilde kapat

### Application Health Endpoint

Uygulamanızda `/health` veya `/healthz` endpoint'i olmalı:

```python
# FastAPI örneği
@app.get("/healthz")
async def health_check():
    try:
        # Database bağlantısını kontrol et
        await db.execute("SELECT 1")
        return {"status": "healthy"}
    except Exception as e:
        raise HTTPException(status_code=503, detail="unhealthy")
```

## Database Migrations

### Otomatik Migration

Deployment sırasında migration çalıştırmak için:

```bash
superdeploy deploy --app api --tag v1.2.3 --migrate
```

Veya GitHub Actions workflow'unda:

```yaml
inputs:
  migrate:
    description: 'Run DB migrations (true/false)'
    required: false
    default: 'false'
```

### Migration Stratejisi

**Backward Compatible Migrations:**
Her zaman backward compatible migration yazın. Böylece rollback sorun çıkarmaz.

**Kötü Örnek:**
```python
# KÖTÜ: Column silme
op.drop_column('users', 'old_field')
```

**İyi Örnek:**
```python
# İYİ: İki aşamalı yaklaşım
# Migration 1: Column'ı nullable yap, kod'da kullanmayı bırak
op.alter_column('users', 'old_field', nullable=True)

# Deployment 1: Yeni kod deploy et (old_field kullanmıyor)

# Migration 2 (sonraki release): Column'ı sil
op.drop_column('users', 'old_field')
```

### Migration Rollback

Migration başarısız olursa deployment durur:

```yaml
- name: 🗄️ Run DB migrations
  run: |
    if docker compose run --rm api alembic upgrade head; then
      echo "✅ Migrations completed"
    else
      echo "❌ MIGRATION FAILED!"
      exit 1
    fi
```

**Manuel Rollback:**

```bash
# Son migration'ı geri al
superdeploy run api "alembic downgrade -1"

# Belirli revision'a geri dön
superdeploy run api "alembic downgrade abc123"

# Mevcut durumu görüntüle
superdeploy run api "alembic current"

# Migration geçmişi
superdeploy run api "alembic history"
```

## Multi-Environment Setup

Staging ve Production ortamları için ayrı konfigürasyon.

### Repository Branch Strategy

```
main (development)
  ↓
staging (pre-production tests)
  ↓
production (live)
```

### Environment-Specific .env

Her environment için ayrı `.env` dosyası:

```
superdeploy/.env.staging
superdeploy/.env.production
```

### GitHub Environments

Her repo için hem `staging` hem `production` environment'ı oluşturun:

```bash
# GitHub UI → Settings → Environments → New environment

# Staging: Auto-deploy on push
# Production: Require review before deploy
```

### Workflow Değişikliği

GitHub Actions'ta environment dinamik olarak seçilir:

```yaml
environment: ${{ github.ref == 'refs/heads/production' && 'production' || 'staging' }}
```

## Custom Domain ve SSL/TLS

### Domain Ayarları

**1. DNS Konfigürasyonu:**
```
A Record:  yourdomain.com        → CORE_EXTERNAL_IP
A Record:  *.yourdomain.com      → CORE_EXTERNAL_IP
CNAME:     api.yourdomain.com    → yourdomain.com
CNAME:     dashboard.yourdomain.com → yourdomain.com
```

**2. Caddy Konfigürasyonu:**

```caddyfile
# /opt/superdeploy/Caddyfile

yourdomain.com {
    reverse_proxy superdeploy-dashboard:3000
    tls admin@yourdomain.com
}

api.yourdomain.com {
    reverse_proxy superdeploy-api:8000
    tls admin@yourdomain.com
}
```

**3. Caddy Restart:**
```bash
ssh -i ~/.ssh/superdeploy_deploy superdeploy@CORE_IP \
  "docker restart superdeploy-caddy"
```

Caddy otomatik olarak Let's Encrypt SSL sertifikası alır.

## Backup ve Restore

### Database Backup

**Otomatik Backup (Cron):**

```bash
# VM'de cron job ekle
ssh -i ~/.ssh/superdeploy_deploy superdeploy@CORE_IP

# Backup scripti oluştur
cat > /opt/superdeploy/backup-db.sh << 'EOF'
#!/bin/bash
DATE=$(date +%Y%m%d-%H%M%S)
BACKUP_DIR=/opt/backups/postgres
mkdir -p $BACKUP_DIR

docker exec superdeploy-postgres pg_dump \
  -U superdeploy superdeploy_db | \
  gzip > $BACKUP_DIR/backup-$DATE.sql.gz

# Son 7 günü tut
find $BACKUP_DIR -name "backup-*.sql.gz" -mtime +7 -delete

echo "✅ Backup completed: backup-$DATE.sql.gz"
EOF

chmod +x /opt/superdeploy/backup-db.sh

# Günlük 3:00'de çalışacak cron
crontab -e
# 0 3 * * * /opt/superdeploy/backup-db.sh >> /var/log/backup.log 2>&1
```

**Manuel Backup:**

```bash
superdeploy run postgres "pg_dump -U superdeploy superdeploy_db" > backup.sql
```

### Database Restore

```bash
# Backup'ı VM'e kopyala
scp -i ~/.ssh/superdeploy_deploy backup.sql superdeploy@CORE_IP:/tmp/

# Restore
ssh -i ~/.ssh/superdeploy_deploy superdeploy@CORE_IP \
  "docker exec -i superdeploy-postgres psql -U superdeploy superdeploy_db < /tmp/backup.sql"
```

### GCS Backup (Önerilen)

Google Cloud Storage'a otomatik backup:

```bash
# GCS bucket oluştur
gsutil mb -p YOUR_PROJECT_ID gs://superdeploy-backups

# Backup scripti güncelle
cat > /opt/superdeploy/backup-db.sh << 'EOF'
#!/bin/bash
DATE=$(date +%Y%m%d-%H%M%S)
BACKUP_FILE=backup-$DATE.sql.gz

docker exec superdeploy-postgres pg_dump \
  -U superdeploy superdeploy_db | \
  gzip > /tmp/$BACKUP_FILE

# GCS'e yükle
gsutil cp /tmp/$BACKUP_FILE gs://superdeploy-backups/

# Local'i temizle
rm /tmp/$BACKUP_FILE

echo "✅ Backup uploaded to GCS: $BACKUP_FILE"
EOF
```

## Performance Optimization

### 1. Docker Build Caching

Multi-stage build kullanarak dependency layer'ını cache'leyin:

```dockerfile
# Stage 1: Dependencies
FROM python:3.11-slim as dependencies
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Stage 2: Application
FROM python:3.11-slim
WORKDIR /app
COPY --from=dependencies /usr/local /usr/local
COPY . .
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0"]
```

### 2. Database Connection Pooling

Her request'te yeni connection açmak yerine pool kullanın:

```python
# SQLAlchemy
engine = create_engine(
    DATABASE_URL,
    pool_size=20,           # Connection pool boyutu
    max_overflow=10,        # Pool doluysa max ek connection
    pool_pre_ping=True,     # Dead connection'ları tespit et
    pool_recycle=3600       # 1 saatte bir connection'ları yenile
)
```

### 3. Redis Caching

Sık erişilen data için Redis cache:

```python
@app.get("/api/users/{user_id}")
async def get_user(user_id: int):
    # Önce cache'e bak
    cached = await redis.get(f"user:{user_id}")
    if cached:
        return json.loads(cached)
    
    # Cache miss: DB'den çek
    user = await db.get_user(user_id)
    
    # Cache'e yaz (TTL: 5 dakika)
    await redis.setex(f"user:{user_id}", 300, json.dumps(user))
    
    return user
```

### 4. Horizontal Scaling

Traffic artışında API replica sayısını artırın:

```bash
# Normal trafik: 2 replica
superdeploy scale api=2

# Yoğun saatler: 5 replica
superdeploy scale api=5

# Gece düşük trafik: 1 replica
superdeploy scale api=1
```

## Security Hardening

### 1. Firewall Rules

Sadece gerekli portları açık tutun:

```hcl
# terraform/main.tf
resource "google_compute_firewall" "allow_http" {
  name    = "allow-http"
  network = "default"
  
  allow {
    protocol = "tcp"
    ports    = ["80", "443"]  # Sadece HTTP/HTTPS
  }
  
  source_ranges = ["0.0.0.0/0"]  # Herkese açık
}

resource "google_compute_firewall" "allow_ssh" {
  name    = "allow-ssh"
  network = "default"
  
  allow {
    protocol = "tcp"
    ports    = ["22"]
  }
  
  source_ranges = ["YOUR_OFFICE_IP/32"]  # Sadece ofis IP'si
}
```

### 2. Container Security

Non-root user kullanın:

```dockerfile
FROM python:3.11-slim

# User oluştur
RUN useradd -m -u 1000 appuser

WORKDIR /app
COPY . .

# Ownership değiştir
RUN chown -R appuser:appuser /app

# Non-root user'a geç
USER appuser

CMD ["uvicorn", "app.main:app"]
```

### 3. Secret Rotation

Düzenli olarak passwordleri değiştirin:

```bash
# Yeni password oluştur
NEW_PASSWORD=$(openssl rand -base64 32)

# .env'de güncelle
sed -i "s/POSTGRES_PASSWORD=.*/POSTGRES_PASSWORD=$NEW_PASSWORD/" .env

# GitHub'a sync et
superdeploy sync

# PostgreSQL'de de değiştir
superdeploy run postgres "psql -U postgres -c \"ALTER USER superdeploy WITH PASSWORD '$NEW_PASSWORD';\""

# Servisleri restart et
superdeploy restart -a api
```

### 4. HTTPS Only

Caddy'de HTTP'yi HTTPS'e yönlendir:

```caddyfile
http://yourdomain.com {
    redir https://yourdomain.com{uri}
}

https://yourdomain.com {
    reverse_proxy superdeploy-dashboard:3000
    
    # Security headers
    header {
        Strict-Transport-Security "max-age=31536000;"
        X-Content-Type-Options "nosniff"
        X-Frame-Options "DENY"
        X-XSS-Protection "1; mode=block"
    }
}
```

## Monitoring ve Alerting

### Prometheus + Grafana Setup

**1. docker-compose.monitoring.yml ekleyin:**

```yaml
services:
  prometheus:
    image: prom/prometheus:latest
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
      - prometheus_data:/prometheus
    ports:
      - "9090:9090"
  
  grafana:
    image: grafana/grafana:latest
    ports:
      - "3000:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=${GRAFANA_PASSWORD}
    volumes:
      - grafana_data:/var/lib/grafana
```

**2. prometheus.yml:**

```yaml
scrape_configs:
  - job_name: 'api'
    static_configs:
      - targets: ['superdeploy-api:8000']
  
  - job_name: 'postgres'
    static_configs:
      - targets: ['postgres-exporter:9187']
```

### Email Alerting

Deployment notification'lar zaten email olarak geliyor. Critical error'lar için de ekleyin:

```python
# Application code
import smtplib

def send_alert(subject, message):
    smtp = smtplib.SMTP('smtp.gmail.com', 587)
    smtp.starttls()
    smtp.login(ALERT_EMAIL, ALERT_PASSWORD)
    smtp.sendmail(ALERT_EMAIL, ALERT_EMAIL, f"Subject: {subject}\n\n{message}")
    smtp.quit()

# Kullanım
try:
    critical_operation()
except Exception as e:
    send_alert("🚨 Critical Error", str(e))
    raise
```

## Troubleshooting Recipes

### Out of Memory (OOM)

Container memory limiti yetersiz:

```yaml
# docker-compose.apps.yml
api:
  deploy:
    resources:
      limits:
        memory: 2G      # 1G'den 2G'ye çıkar
      reservations:
        memory: 512M
```

### Slow Database Queries

PostgreSQL slow query log'u aktif edin:

```bash
superdeploy run postgres "psql -U postgres -c \"ALTER SYSTEM SET log_min_duration_statement = 1000;\""
superdeploy restart -a postgres

# Logları izle
superdeploy logs -a postgres | grep "duration:"
```

### Connection Pool Exhaustion

Pool size'ı artırın:

```python
# config.py
DATABASE_POOL_SIZE = 50  # 20'den 50'ye çıkar
DATABASE_MAX_OVERFLOW = 20
```

### High CPU Usage

Profiling yapın:

```bash
# cProfile ile profil çıkar
superdeploy run api "python -m cProfile -o profile.stats app/main.py"

# py-spy ile canlı profiling
pip install py-spy
py-spy top --pid $(docker inspect -f '{{.State.Pid}}' superdeploy-api)
```

---

**Sonuç:**

Bu gelişmiş konular, SuperDeploy'u production-ready hale getirir. Güvenlik, performans, monitoring ve disaster recovery stratejileri sayesinde kurumsal düzeyde kullanıma hazırsınız.

