# 🏗️ Multi-Project Architecture

## Genel Bakış

SuperDeploy artık **multi-project** destekliyor. Her proje tamamen izole:
- Ayrı Docker network'ler
- Ayrı database'ler (PostgreSQL, Redis, RabbitMQ)
- Ayrı volume'ler (veri persistence)
- Ayrı resource limit'ler
- Birbirlerini görmezler, erişemezler

## Neden Multi-Project?

### Senaryo 1: Farklı Müşteriler
```
Cheapa Project → E-ticaret platformu
  ├─ PostgreSQL (müşteri verileri)
  ├─ RabbitMQ (sipariş kuyruğu)
  └─ Redis (session cache)

ProjectB → Blog platformu
  ├─ PostgreSQL (yazılar, yorumlar)
  └─ Redis (cache)

❌ Cheapa'nın verileri ProjectB'ye karışmaz
✅ Tamamen izole ortamlar
```

### Senaryo 2: Staging vs Production
```
Cheapa-Production → 34.61.244.204
  └─ Gerçek müşteri verileri

Cheapa-Staging → 35.192.123.45
  └─ Test verileri

✅ Staging'de test yap, production'a hiç dokunma
```

## Proje Yapısı

```
superdeploy/
  ├─ projects/
  │   │
  │   ├─ cheapa/                    # Proje 1
  │   │   ├─ compose/
  │   │   │   ├─ docker-compose.core.yml
  │   │   │   └─ docker-compose.apps.yml
  │   │   ├─ ansible/
  │   │   │   └─ vars/
  │   │   │       └─ cheapa.yml     # Cheapa-specific config
  │   │   └─ terraform/
  │   │       └─ cheapa.tfvars
  │   │
  │   ├─ projectb/                  # Proje 2
  │   │   ├─ compose/
  │   │   ├─ ansible/
  │   │   └─ terraform/
  │   │
  │   └─ _template/                 # Yeni proje için template
  │       ├─ compose/
  │       ├─ ansible/
  │       └─ README.md
  │
  └─ .env                           # PROJECT=cheapa
```

## Yeni Proje Ekleme

### Adım 1: Template'i Kopyala

```bash
cd superdeploy/projects
cp -r _template my-new-project
cd my-new-project
```

### Adım 2: Konfigürasyonu Güncelle

**ansible/vars/my-new-project.yml:**
```yaml
project_name: my-new-project
project_id: my-new-project-id
project_domain: mynewproject.com

# ÖNEMLİ: Her proje için farklı subnet!
subnet_cidr: "10.30.0.0/24"  # Cheapa: 10.10.x.x, ProjectB: 10.20.x.x

core_services:
  postgres:
    container_name: "mynewproject-postgres"
    # ... (template'de mevcut)
```

### Adım 3: Compose Dosyalarını Güncelle

**compose/docker-compose.core.yml:**

Find & Replace:
- `cheapa` → `mynewproject`
- `cheapa-network` → `mynewproject-network`
- `cheapa-postgres-data` → `mynewproject-postgres-data`

**Örnek:**
```yaml
networks:
  mynewproject-network:        # ✅ Unique
    name: mynewproject-network

volumes:
  mynewproject-postgres-data:  # ✅ Unique

services:
  postgres:
    container_name: mynewproject-postgres  # ✅ Unique
    networks:
      - mynewproject-network               # ✅ Isolated
```

### Adım 4: Deploy Et

```bash
# Root .env dosyasında PROJECT değişkenini set et
echo "PROJECT=mynewproject" > .env

# Veya environment variable olarak
export PROJECT=mynewproject

# Deploy
superdeploy up
```

## Izolasyon Nasıl Çalışır?

### Docker Network Isolation

```
Host Machine (VM)
  │
  ├─ Docker Network: cheapa-network (10.10.0.0/24)
  │   ├─ cheapa-postgres (10.10.0.2)
  │   ├─ cheapa-api (10.10.0.3)
  │   └─ cheapa-dashboard (10.10.0.4)
  │
  └─ Docker Network: projectb-network (10.20.0.0/24)
      ├─ projectb-postgres (10.20.0.2)
      ├─ projectb-api (10.20.0.3)
      └─ projectb-dashboard (10.20.0.4)

❌ cheapa-api, projectb-postgres'e erişemez (farklı network)
✅ cheapa-api, cheapa-postgres'e erişir (aynı network)
```

### Container Naming

Her container benzersiz isim taşır:
```
cheapa-postgres       # Proje 1'in DB'si
projectb-postgres     # Proje 2'nin DB'si
mynewproject-postgres # Proje 3'ün DB'si
```

Docker'da isim충돌 olmaz, her proje kendi container'larını yönetir.

### Volume Isolation

Veri kalıcılığı için her proje kendi volume'lerini kullanır:
```bash
# Cheapa'nın volume'leri
cheapa-postgres-data       → /var/lib/docker/volumes/cheapa-postgres-data
cheapa-rabbitmq-data       → /var/lib/docker/volumes/cheapa-rabbitmq-data

# ProjectB'nin volume'leri
projectb-postgres-data     → /var/lib/docker/volumes/projectb-postgres-data
projectb-redis-data        → /var/lib/docker/volumes/projectb-redis-data
```

Bir projeyi sildiğinde sadece o projenin volume'leri silinir, diğerleri etkilenmez.

## Deployment Modelleri

### Model 1: Her Proje Ayrı VM'de (Önerilen)

```
VM-Cheapa (34.61.244.204)
  └─ Cheapa tüm servisleri
     ├─ PostgreSQL
     ├─ RabbitMQ
     ├─ Redis
     ├─ API
     └─ Dashboard

VM-ProjectB (35.192.123.45)
  └─ ProjectB tüm servisleri
     ├─ PostgreSQL
     ├─ Redis
     ├─ API
     └─ Dashboard
```

**Avantajlar:**
- ✅ Tam izolasyon (network, CPU, memory, disk)
- ✅ Bir VM crash olsa diğeri etkilenmez
- ✅ Scaling per-project (VM boyutu, replica sayısı)
- ✅ Güvenlik (farklı SSH key'ler, firewall rules)

**Deployment:**
```bash
# Cheapa deploy
export PROJECT=cheapa
export GCP_PROJECT_ID=cheapa-prod-123
superdeploy up

# ProjectB deploy
export PROJECT=projectb
export GCP_PROJECT_ID=projectb-prod-456
superdeploy up
```

### Model 2: Aynı VM, Farklı Network'ler

```
VM-Shared (34.61.244.204)
  ├─ Cheapa Network (10.10.0.0/24)
  │   └─ Cheapa servisleri
  │
  └─ ProjectB Network (10.20.0.0/24)
      └─ ProjectB servisleri
```

**Avantajlar:**
- ✅ Maliyet düşük (tek VM)
- ✅ Yine de network isolation

**Dezavantajlar:**
- ❌ CPU/Memory/Disk paylaşımlı
- ❌ Bir proje tüm kaynakları tüketirse diğeri etkilenir
- ❌ Downtime riski (VM restart → her şey aynı anda düşer)

**Ne Zaman Kullanılır:**
- Development/Staging ortamları
- Küçük projeler (düşük trafik)
- Maliyet kısıtlaması

### Model 3: Mikro-servis Tarzı (İleri Seviye)

```
VM-Cheapa-DB (dedicated database VM)
  └─ cheapa-postgres
     (High IOPS disk, lots of RAM)

VM-Cheapa-Queue (dedicated queue VM)
  └─ cheapa-rabbitmq
     (Optimized for message processing)

VM-Cheapa-App (application VM)
  ├─ cheapa-api (scaled to 5 replicas)
  └─ cheapa-dashboard

VM-Cheapa-Workers (worker VM)
  └─ cheapa-services (scaled to 10 replicas)
```

**Avantajlar:**
- ✅ Her servis için optimize edilmiş kaynak
- ✅ Independent scaling (API'yi scale et, DB dokunma)
- ✅ High availability (bir VM düşse diğerleri çalışır)

**Dezavantajlar:**
- ❌ Karmaşık network routing
- ❌ Yüksek maliyet
- ❌ Yönetim zorluğu

**Ne Zaman Kullanılır:**
- Production, high-traffic uygulamalar
- Her servisin farklı resource ihtiyacı var
- %99.9+ uptime gereksinimi

## Resource Management

Her proje için resource limit tanımla:

**ansible/vars/cheapa.yml:**
```yaml
resource_limits:
  postgres:
    memory: "2G"
    cpus: "1.0"
  rabbitmq:
    memory: "1G"
    cpus: "0.5"
  api:
    memory: "1G"
    cpus: "0.5"
```

**Neden Önemli:**
- Bir proje tüm RAM'i tüketip diğerlerini etkilemesin
- OOM (Out of Memory) durumlarında sadece o servis restart olsun
- Kaynak kullanımı tahmin edilebilir

## Backup & Recovery

### Per-Project Backup

```bash
# Cheapa backup
docker exec cheapa-postgres pg_dump -U cheapa_user cheapa_db > cheapa-backup-$(date +%Y%m%d).sql

# ProjectB backup
docker exec projectb-postgres pg_dump -U projectb_user projectb_db > projectb-backup-$(date +%Y%m%d).sql
```

### Volume Backup

```bash
# Cheapa volume'lerini backup'la
docker run --rm -v cheapa-postgres-data:/data -v $(pwd):/backup alpine tar czf /backup/cheapa-postgres.tar.gz /data

# ProjectB volume'lerini backup'la
docker run --rm -v projectb-postgres-data:/data -v $(pwd):/backup alpine tar czf /backup/projectb-postgres.tar.gz /data
```

### GCS Bucket Separation

Her proje için ayrı bucket:
```
gs://cheapa-backups/
  ├─ postgres/
  ├─ rabbitmq/
  └─ volumes/

gs://projectb-backups/
  ├─ postgres/
  └─ volumes/
```

Restore ederken karışma riski yok.

## Monitoring

### Prometheus Labels

Her container project label'ı taşır:
```yaml
labels:
  - "com.superdeploy.project=cheapa"
  - "com.superdeploy.service=postgres"
```

Prometheus'ta project bazlı query:
```promql
# Cheapa'nın toplam CPU kullanımı
sum(rate(container_cpu_usage_seconds_total{project="cheapa"}[5m]))

# ProjectB'nin memory kullanımı
sum(container_memory_usage_bytes{project="projectb"})
```

### Grafana Dashboards

Her proje için ayrı dashboard veya tek dashboard'da filter:
```
Dashboard: "All Projects Overview"
  - Filter by: project=cheapa
  - Filter by: project=projectb
```

## Security & Access Control

### SSH Keys

Her proje için farklı SSH key kullan:
```bash
# Cheapa için
ssh-keygen -t rsa -b 4096 -f ~/.ssh/cheapa_deploy

# ProjectB için
ssh-keygen -t rsa -b 4096 -f ~/.ssh/projectb_deploy
```

### Firewall Rules

Project-based firewall:
```hcl
# Cheapa firewall
resource "google_compute_firewall" "cheapa_allow_http" {
  name    = "cheapa-allow-http"
  network = google_compute_network.cheapa.name
  
  allow {
    protocol = "tcp"
    ports    = ["80", "443"]
  }
  
  source_ranges = ["0.0.0.0/0"]
  target_tags   = ["cheapa-vm"]
}

# ProjectB firewall
resource "google_compute_firewall" "projectb_allow_http" {
  name    = "projectb-allow-http"
  network = google_compute_network.projectb.name
  
  allow {
    protocol = "tcp"
    ports    = ["80", "443"]
  }
  
  source_ranges = ["0.0.0.0/0"]
  target_tags   = ["projectb-vm"]
}
```

## Migration Path

### Mevcut Single-Project'ten Multi-Project'e Geçiş

**Adım 1: Backup Al**
```bash
# Tüm data'yı backup'la
./scripts/backup-all.sh
```

**Adım 2: Projects Yapısını Oluştur**
```bash
mkdir -p projects/cheapa
mv compose projects/cheapa/
mv ansible/vars/core.yml projects/cheapa/ansible/vars/cheapa.yml
```

**Adım 3: Container İsimlerini Güncelle**
```yaml
# Önce:
container_name: superdeploy-postgres

# Sonra:
container_name: cheapa-postgres
```

**Adım 4: Yeniden Deploy**
```bash
export PROJECT=cheapa
superdeploy up
```

**Adım 5: Data Restore**
```bash
# Backup'tan restore et
docker exec -i cheapa-postgres psql -U cheapa_user cheapa_db < backup.sql
```

## Best Practices

1. **Naming Convention:**
   - Container: `{project}-{service}`
   - Network: `{project}-network`
   - Volume: `{project}-{service}-data`

2. **Subnet Planning:**
   - Project A: 10.10.0.0/24
   - Project B: 10.20.0.0/24
   - Project C: 10.30.0.0/24
   - Her yeni proje için +10 subnet

3. **Resource Limits:**
   - Her zaman limit tanımla
   - Production için cömert (2x expected)
   - Staging için kısıtlı (cost optimization)

4. **Secrets:**
   - Asla password paylaşma
   - Her proje için unique strong password
   - Rotate periodically

5. **Backups:**
   - Günlük otomatik backup
   - 7 gün retention
   - Farklı GCS bucket'lar

6. **Monitoring:**
   - Project label'ları ekle
   - Alerting per-project
   - Dedicated Slack channels

7. **Documentation:**
   - Her projede README.md
   - Architecture diagram
   - Runbook for incidents

---

**Sonuç:**

Multi-project architecture sayesinde artık:
- ✅ Birden fazla müşteriyi aynı infrastructure'da host edebilirsin
- ✅ Her proje tamamen izole
- ✅ Bir projede sorun olsa diğerleri etkilenmez
- ✅ Per-project scaling ve optimization
- ✅ Temiz, organize kod yapısı

