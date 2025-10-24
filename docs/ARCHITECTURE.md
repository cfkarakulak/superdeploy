# SuperDeploy Mimarisi

## 🏗️ Genel Mimari

SuperDeploy, **tam izole edilmiş çoklu proje** mimarisi kullanır. Her proje kendi kaynaklarına sahiptir ve diğer projelerden tamamen bağımsızdır.

## 🖥️ VM Yapısı

### Shared Infrastructure (Tek VM)
```
vm-core-1 (34.44.228.225)
├── Caddy (Reverse Proxy) - TÜM projeler için
├── Prometheus (Monitoring) - TÜM projeler için  
├── Grafana (Dashboard) - TÜM projeler için
├── Alertmanager (Alerts) - TÜM projeler için
└── Project-Specific Services ↓
```

### Her Proje İçin Ayrı Servisler
```
Proje: cheapa
├── Forgejo (Git Server) - SADECE cheapa için
├── PostgreSQL - SADECE cheapa için
├── RabbitMQ - SADECE cheapa için
├── Redis - SADECE cheapa için
├── API Container - SADECE cheapa için
├── Dashboard Container - SADECE cheapa için
└── Services Container - SADECE cheapa için
```

## 🔧 Ansible Yapısı ve Addon Sistemi

### Dinamik Konfigürasyon Mimarisi

SuperDeploy, **tamamen dinamik** bir Ansible yapısı kullanır. Tüm konfigürasyonlar `project.yml` dosyasından okunur ve hiçbir hardcoded değer yoktur.

### Ansible Role Katmanları

```bash
# System Layer (Foundation)
system/base/              # OS-level setup (packages, users, swap)
system/docker/            # Docker installation & configuration
system/security/          # Firewall, SSH hardening
system/monitoring-agent/  # Node exporter, system metrics

# Orchestration Layer (Deployment)
orchestration/addon-deployer/    # Generic addon deployment
orchestration/project-deployer/  # Project-specific deployment
```

### Addon Sistemi: Template vs Instance Mimarisi

**ÖNEMLİ KAVRAM:** SuperDeploy'da addon'lar **template** (şablon) olarak tanımlanır ve her proje için ayrı **instance** (örnek) olarak deploy edilir.

#### Template Yapısı (superdeploy/addons/)

`superdeploy/addons/` dizini **yeniden kullanılabilir şablonlar** içerir. Bu şablonlar hiçbir projeye özel değildir:

```bash
superdeploy/addons/          # ŞABLONLAR (Templates)
├── forgejo/                 # Forgejo şablonu
│   ├── addon.yml           # Metadata (name, version, ports, dependencies)
│   ├── env.yml             # Environment variable tanımları
│   ├── ansible.yml         # Deployment task'ları
│   ├── compose.yml.j2      # Docker compose şablonu
│   ├── tasks/              # Ek setup task'ları
│   │   ├── setup-admin.yml
│   │   ├── setup-runner.yml
│   │   └── setup-secrets.yml
│   └── templates/          # Konfigürasyon şablonları
│       ├── forgejo.env.j2
│       └── runner-config.yml.j2
├── postgres/               # PostgreSQL şablonu
├── redis/                  # Redis şablonu
├── rabbitmq/               # RabbitMQ şablonu
└── mongodb/                # MongoDB şablonu
```

#### Instance Yapısı (projects/[project-name]/)

Her proje için addon şablonları **proje-spesifik instance'lara** dönüştürülür:

```bash
projects/cheapa/            # INSTANCE'LAR (Deployed)
├── project.yml             # Proje konfigürasyonu
├── .passwords.yml          # Otomatik oluşturulan şifreler
└── compose/                # Render edilmiş compose dosyaları
    ├── docker-compose.core.yml    # Addon instance'ları
    │   ├── cheapa-forgejo         # Forgejo instance
    │   ├── cheapa-postgres        # PostgreSQL instance
    │   ├── cheapa-rabbitmq        # RabbitMQ instance
    │   └── cheapa-redis           # Redis instance
    └── docker-compose.apps.yml    # Uygulama container'ları
        ├── cheapa-api
        ├── cheapa-dashboard
        └── cheapa-services
```

#### Forgejo Neden superdeploy/addons/ Dizininde?

**Soru:** Forgejo neden `superdeploy/addons/forgejo/` dizininde? Her projenin kendi Forgejo'su varsa neden proje dizininde değil?

**Cevap:** Forgejo bir **şablon** olarak tanımlanır, **instance** olarak deploy edilir:

1. **Şablon Tanımı:** `superdeploy/addons/forgejo/` dizini Forgejo'nun nasıl kurulacağını tanımlar (hangi portlar, hangi konfigürasyonlar, hangi task'lar)

2. **Instance Oluşturma:** Her proje için bu şablon kullanılarak **proje-spesifik instance** oluşturulur:
   - `cheapa` projesi → `cheapa-forgejo` container'ı (port 3001)
   - `myapp` projesi → `myapp-forgejo` container'ı (port 3002)
   - Her instance tamamen izole, kendi veritabanı ve konfigürasyonu var

3. **Avantajlar:**
   - ✅ **DRY Prensibi:** Forgejo kurulum mantığı bir kez tanımlanır
   - ✅ **Tutarlılık:** Tüm projeler aynı Forgejo yapısını kullanır
   - ✅ **Bakım Kolaylığı:** Forgejo güncellemesi tek yerden yapılır
   - ✅ **Ölçeklenebilirlik:** Yeni proje eklemek için kod değişikliği gerekmez

#### Addon Instance Oluşturma Süreci

```bash
# 1. Kullanıcı project.yml'de addon'ları tanımlar
infrastructure:
  forgejo:
    version: "1.21"
    port: 3001
    admin_user: "admin"

# 2. addon-deployer role şablonu okur
- superdeploy/addons/forgejo/addon.yml
- superdeploy/addons/forgejo/env.yml
- superdeploy/addons/forgejo/compose.yml.j2

# 3. Project.yml değerleri ile şablon render edilir
- Container adı: cheapa-forgejo
- Port: 3001
- Admin user: admin
- Network: cheapa-network

# 4. Render edilmiş dosya projects/cheapa/compose/ dizinine yazılır
projects/cheapa/compose/docker-compose.core.yml

# 5. Docker Compose ile instance deploy edilir
docker compose -f projects/cheapa/compose/docker-compose.core.yml up -d

# Sonuç: cheapa-forgejo container'ı çalışıyor
```

**Addon Deployment Akışı:**
1. `addon-deployer` role addon.yml'i okur
2. `env.yml` tanımlarını project.yml ile merge eder
3. `compose.yml.j2` template'ini proje değerleri ile render eder
4. Render edilmiş dosyayı `projects/[project]/compose/` dizinine yazar
5. `ansible.yml` deployment task'larını çalıştırır
6. Health check ile servisin sağlıklı olduğunu doğrular

### Project Configuration (project.yml)

Tüm proje konfigürasyonu tek bir dosyada:

```yaml
project: "cheapa"

# Infrastructure addons (required)
infrastructure:
  forgejo:
    version: "1.21"
    port: 3001
    admin_user: "admin"
    org: "cheapaio"
    repo: "superdeploy"
    ssh_port: 2222

# Service addons (optional)
addons:
  postgres:
    version: "15-alpine"
    port: 5432
    user: "cheapa_user"
    database: "cheapa_db"
  redis:
    version: "7-alpine"
    port: 6379
  monitoring:
    enabled: true
    prometheus_port: 9090
    grafana_port: 3000

# Application services
apps:
  api:
    path: "/path/to/api"
    port: 8000
    vm: "core"
  dashboard:
    path: "/path/to/dashboard"
    port: 8010
    vm: "core"
```

**Avantajlar:**
- ✅ Port değişikliği → Sadece project.yml'i düzenle
- ✅ Yeni addon → project.yml'e ekle, redeploy
- ✅ Hiçbir kod değişikliği gerektirmez
- ✅ Tüm konfigürasyon tek yerde

## 🔄 Forgejo Yapısı

### Tek Forgejo Instance - Org-Based İzolasyon

**ÖNEMLI:** Tek Forgejo instance tüm projeleri yönetir!

```bash
# Tek Forgejo Instance (SADECE DEPLOYMENT)
http://34.44.228.225:3001
└── Organization: cradexco
    └── superdeploy (parametreli deployment workflow)
        └── .forgejo/workflows/deploy.yml

# GitHub (SOURCE OF TRUTH - APP CODE)
├── Organization: cheapaio
│   ├── api (app code + secrets + GitHub Actions)
│   ├── dashboard (app code + secrets + GitHub Actions)
│   └── services (app code + secrets + GitHub Actions)
└── Organization: myorg
    ├── api (app code + secrets + GitHub Actions)
    └── frontend (app code + secrets + GitHub Actions)
```

**ÖNEMLİ:** 
- Forgejo'da **sadece 1 repo**: `cradexco/superdeploy`
- Uygulama kodu YOK! Sadece deployment workflow var
- Tüm projeler aynı workflow'u kullanır (parametreli)

### Forgejo Runner - Project-Specific

**Her proje için ayrı runner (aynı Forgejo instance'ı kullanır):**

```bash
# Cheapa runner
cheapa-runner → Sadece cheapa org'u için çalışır
├── Labels: [self-hosted, cheapa, linux, docker]
├── Çalıştırır: cheapa-api, cheapa-dashboard, cheapa-services
├── Erişir: cheapa-postgres, cheapa-rabbitmq, cheapa-redis
└── Workflow filter: runs-on: [self-hosted, cheapa]

# MyApp runner  
myapp-runner → Sadece myapp org'u için çalışır
├── Labels: [self-hosted, myapp, linux, docker]
├── Çalıştırır: myapp-api, myapp-frontend
├── Erişir: myapp-postgres, myapp-redis
└── Workflow filter: runs-on: [self-hosted, myapp]
```

### Avantajlar

✅ **Tek bakım noktası:** Tek Forgejo instance  
✅ **Org-level izolasyon:** Her proje kendi organization'ı  
✅ **Runner-level izolasyon:** Label filtering ile deployment ayrımı  
✅ **Daha az resource:** Tek DB, tek web server  
✅ **Merkezi yönetim:** Tüm projeler tek arayüzden

## 📊 Network İzolasyonu

### Docker Networks
```bash
# Shared network (monitoring only)
superdeploy-infrastructure
├── Caddy
├── Prometheus  
├── Grafana
└── Alertmanager

# Project-specific networks
cheapa-network (172.20.0.0/24)
├── cheapa-forgejo
├── cheapa-postgres
├── cheapa-rabbitmq
├── cheapa-redis
├── cheapa-api
├── cheapa-dashboard
└── cheapa-services

myapp-network (172.21.0.0/24)  
├── myapp-forgejo
├── myapp-postgres
├── myapp-redis
├── myapp-api
└── myapp-frontend
```

## 🔐 Secrets Yönetimi

### Infrastructure Secrets (Shared)
```bash
# GitHub'da tüm app repos için
FORGEJO_BASE_URL=http://34.44.228.225:3001
FORGEJO_PAT=forgejo_pat_xxx
AGE_PUBLIC_KEY=age1ym7237snvf...
CORE_EXTERNAL_IP=34.44.228.225
DOCKER_USERNAME=myuser
DOCKER_TOKEN=dckr_pat_xxx
```

### App-Specific Secrets (Per Project)
```bash
# GitHub cheapaio/api için
POSTGRES_PASSWORD=secure_cheapa_pg_pass
RABBITMQ_PASSWORD=secure_cheapa_mq_pass  
REDIS_PASSWORD=secure_cheapa_redis_pass
API_SECRET_KEY=cheapa_api_secret
SENTRY_DSN=https://sentry.io/cheapa-api

# GitHub myorg/api için
POSTGRES_PASSWORD=secure_myapp_pg_pass
REDIS_PASSWORD=secure_myapp_redis_pass
API_SECRET_KEY=myapp_api_secret
```

## 🔧 Environment Variable Yönetim Stratejisi

### .env vs .env.superdeploy Ayrımı

SuperDeploy, **local development** ve **production deployment** ortamlarını ayırmak için iki ayrı dosya kullanır:

#### Dosya Yapısı

```bash
app-repos/api/
├── .env                    # Local development (GELİŞTİRİCİ TARAFINDAN YÖNETİLİR)
├── .env.superdeploy        # Production overrides (SUPERDEPLOY TARAFINDAN OLUŞTURULUR)
├── .env.example            # Template dosya
└── .github/workflows/
    └── deploy.yml          # İki dosyayı merge eder
```

#### .env (Local Development)

**Amaç:** Geliştiricinin local ortamında kullandığı değerler

**Özellikler:**
- ✅ Geliştirici tarafından manuel olarak düzenlenir
- ✅ Local veritabanı, local servisler için değerler içerir
- ✅ **SuperDeploy tarafından ASLA değiştirilmez**
- ✅ Git'e commit edilmez (.gitignore'da)

**Örnek içerik:**
```bash
# Local development environment
DEBUG=True
DATABASE_URL=postgresql://localhost:5432/myapp_dev
REDIS_URL=redis://localhost:6379
API_KEY=test_key_for_local_dev
```

#### .env.superdeploy (Production Overrides)

**Amaç:** Production deployment için SuperDeploy tarafından oluşturulan değerler

**Özellikler:**
- ✅ SuperDeploy tarafından otomatik oluşturulur
- ✅ Production servis bağlantıları içerir (DB, Redis, RabbitMQ)
- ✅ `superdeploy sync:repos` komutu ile güncellenir
- ✅ Git'e commit edilmez (.gitignore'da)
- ✅ **Manuel düzenlenmemelidir** (her sync'te yeniden oluşturulur)

**Örnek içerik:**
```bash
# SuperDeploy generated production overrides
# DO NOT EDIT MANUALLY - Generated by superdeploy sync:repos

# Database connection (from cheapa-postgres)
POSTGRES_HOST=${POSTGRES_HOST}
POSTGRES_PORT=${POSTGRES_PORT}
POSTGRES_USER=${POSTGRES_USER}
POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
POSTGRES_DB=${POSTGRES_DB}

# Redis connection (from cheapa-redis)
REDIS_HOST=${REDIS_HOST}
REDIS_PORT=${REDIS_PORT}
REDIS_PASSWORD=${REDIS_PASSWORD}

# RabbitMQ connection (from cheapa-rabbitmq)
RABBITMQ_HOST=${RABBITMQ_HOST}
RABBITMQ_PORT=${RABBITMQ_PORT}
RABBITMQ_USER=${RABBITMQ_USER}
RABBITMQ_PASSWORD=${RABBITMQ_PASSWORD}
```

#### Merge Stratejisi (Deployment Sırasında)

GitHub Actions deployment workflow'u iki dosyayı merge eder:

```bash
# .github/workflows/deploy.yml içinde
- name: Merge environment files
  run: |
    cat .env > merged.env
    cat .env.superdeploy >> merged.env
    # .env.superdeploy değerleri .env değerlerini override eder
```

**Merge Önceliği:**
1. `.env` dosyası önce okunur (base values)
2. `.env.superdeploy` dosyası üzerine yazılır (overrides)
3. Aynı değişken her iki dosyada varsa `.env.superdeploy` kazanır

**Örnek Merge:**
```bash
# .env
DEBUG=True
DATABASE_URL=postgresql://localhost:5432/myapp_dev
API_KEY=local_test_key

# .env.superdeploy
DATABASE_URL=postgresql://cheapa-postgres:5432/cheapa_db
POSTGRES_PASSWORD=secure_production_pass

# Merged result (deployment'ta kullanılan)
DEBUG=True                                                    # .env'den
DATABASE_URL=postgresql://cheapa-postgres:5432/cheapa_db     # .env.superdeploy override
API_KEY=local_test_key                                       # .env'den
POSTGRES_PASSWORD=secure_production_pass                     # .env.superdeploy'dan
```

#### Kullanım Senaryoları

**Senaryo 1: Local Development**
```bash
# Geliştirici sadece .env dosyasını düzenler
vim app-repos/api/.env

# Local'de çalıştır
cd app-repos/api
python app.py  # Sadece .env kullanılır
```

**Senaryo 2: Production Deployment**
```bash
# SuperDeploy ile secrets sync
superdeploy sync:repos -e ~/app-repos/api/.env:cheapaio/api

# .env.superdeploy otomatik oluşturulur
# GitHub'a push edildiğinde her iki dosya merge edilir
git push origin production
```

**Senaryo 3: Production Secret Güncelleme**
```bash
# Sadece production secrets'ı güncelle
superdeploy sync:repos -c ~/superdeploy/projects/cheapa/.passwords.yml

# .env.superdeploy yeniden oluşturulur
# Local .env dosyası değişmez
```

#### Avantajlar

✅ **Local Ortam Korunur:** Geliştirici local .env'ini özgürce düzenleyebilir  
✅ **Production Güvenliği:** Production secrets local'de saklanmaz  
✅ **Otomatik Senkronizasyon:** SuperDeploy production değerleri otomatik yönetir  
✅ **Açık Ayrım:** Hangi değerlerin nereden geldiği açıkça belli  
✅ **Kolay Rollback:** .env.superdeploy silinip yeniden oluşturulabilir

## 🚀 Deployment Akışı

### 1. GitHub → Build & Push
```bash
# GitHub Actions (cheapaio/api)
1. Checkout code
2. Build Docker image
3. Push to GHCR (ghcr.io/cheapaio/api:sha-abc123)
4. Get image digest (immutable)
5. Encrypt environment variables (AGE)
```

### 2. GitHub → Trigger Forgejo
```bash
# GitHub Actions continues...
6. POST http://34.44.228.225:3001/api/v1/repos/cradexco/superdeploy/dispatches
   {
     "event_type": "deploy",
     "client_payload": {
       "project": "cheapa",
       "service": "api",
       "image": "ghcr.io/cheapaio/api@sha256:abc123",
       "env_bundle": "AGE_ENCRYPTED_BASE64",
       "git_sha": "abc123",
       "git_ref": "production"
     }
   }
```

### 3. Forgejo Workflow Execution
```bash
# Forgejo Runner (cheapa-runner)
# runs-on: [self-hosted, cheapa]
1. Receive parameters from GitHub
2. Decrypt environment bundle (AGE)
3. Generate docker-compose-api.yml
4. Pull image: docker pull ghcr.io/cheapaio/api@sha256:abc123
5. Deploy: docker compose up -d --wait
6. Health check: wait for container healthy
7. Cleanup: remove decrypted env
8. Send notification email
```

### 3. Service Discovery
```bash
# Caddy routes (auto-generated)
api.cheapa.com → cheapa-api:8000
dashboard.cheapa.com → cheapa-dashboard:3000

# Prometheus targets (auto-generated)  
- cheapa-api:8000/metrics
- cheapa-dashboard:3000/metrics
- cheapa-services:8080/metrics
```

## 📁 Dosya Yapısı

### SuperDeploy Repository (Template ve Instance Ayrımı)

```
superdeploy/
├── shared/                    # Shared infrastructure
│   ├── terraform/            # VM provisioning
│   ├── ansible/              # Configuration management
│   │   ├── playbooks/
│   │   │   └── site.yml      # Main orchestration playbook
│   │   ├── roles/
│   │   │   ├── system/       # Foundation layer (OS-level)
│   │   │   │   ├── base/     # System packages, users, directories
│   │   │   │   ├── docker/   # Docker installation & configuration
│   │   │   │   ├── security/ # Firewall, hardening, SSH
│   │   │   │   └── monitoring-agent/ # Node exporter, log forwarding
│   │   │   └── orchestration/ # Deployment layer
│   │   │       ├── addon-deployer/    # Generic addon deployment orchestrator
│   │   │       └── project-deployer/  # Project-specific deployment orchestrator
│   │   └── inventories/
│   │       └── dev.ini
│   └── compose/              # Shared services (Caddy, Prometheus)
│
├── addons/                   # 🎨 TEMPLATE LAYER (Yeniden kullanılabilir şablonlar)
│   ├── forgejo/              # Forgejo şablonu
│   │   ├── addon.yml         # Metadata (name, version, category)
│   │   ├── ansible.yml       # Deployment tasks
│   │   ├── compose.yml.j2    # Docker compose ŞABLONU
│   │   ├── env.yml           # Environment variable tanımları
│   │   ├── tasks/            # Setup tasks (admin, runner, secrets)
│   │   └── templates/        # Configuration şablonları
│   ├── postgres/             # PostgreSQL şablonu
│   ├── redis/                # Redis şablonu
│   ├── rabbitmq/             # RabbitMQ şablonu
│   ├── mongodb/              # MongoDB şablonu
│   ├── caddy/                # Reverse proxy şablonu
│   └── monitoring/           # Prometheus + Grafana şablonu
│
├── projects/                 # 🚀 INSTANCE LAYER (Deploy edilmiş örnekler)
│   ├── cheapa/               # Cheapa projesi instance'ları
│   │   ├── project.yml       # Proje konfigürasyonu (addon parametreleri)
│   │   ├── .passwords.yml    # Otomatik oluşturulan secrets
│   │   └── compose/          # Render edilmiş compose dosyaları
│   │       ├── docker-compose.core.yml    # Addon instance'ları
│   │       │   # İçerik: cheapa-forgejo, cheapa-postgres, cheapa-redis, cheapa-rabbitmq
│   │       └── docker-compose.apps.yml    # Uygulama container'ları
│   │           # İçerik: cheapa-api, cheapa-dashboard, cheapa-services
│   │
│   └── myapp/                # MyApp projesi instance'ları
│       ├── project.yml       # MyApp konfigürasyonu
│       ├── .passwords.yml    # MyApp secrets
│       └── compose/          # MyApp compose dosyaları
│           ├── docker-compose.core.yml    # myapp-forgejo, myapp-postgres, myapp-redis
│           └── docker-compose.apps.yml    # myapp-api, myapp-frontend
│
└── cli/                      # SuperDeploy CLI
    ├── commands/             # CLI commands
    └── core/                 # Core functionality (addon loader, validator)
```

**Template → Instance Dönüşümü:**

```bash
# TEMPLATE (addons/forgejo/compose.yml.j2)
services:
  {{ project_name }}-forgejo:
    image: codeberg.org/forgejo/forgejo:{{ forgejo_version }}
    ports:
      - "{{ forgejo_port }}:3000"
    networks:
      - {{ project_name }}-network

# INSTANCE (projects/cheapa/compose/docker-compose.core.yml)
services:
  cheapa-forgejo:
    image: codeberg.org/forgejo/forgejo:1.21
    ports:
      - "3001:3000"
    networks:
      - cheapa-network
```

### App Repositories (GitHub) - Environment File Yapısı

```
cheapaio/api/
├── .env                      # 🔧 LOCAL DEVELOPMENT (geliştirici yönetir)
│                             # Örnek: DEBUG=True, DATABASE_URL=localhost
├── .env.superdeploy          # 🚀 PRODUCTION OVERRIDES (SuperDeploy oluşturur)
│                             # Örnek: POSTGRES_HOST=cheapa-postgres
├── .env.example              # 📝 Template dosya
├── Dockerfile
├── src/
└── .github/workflows/
    └── deploy.yml            # .env + .env.superdeploy merge eder

cheapaio/dashboard/  
├── .env                      # 🔧 LOCAL DEVELOPMENT
├── .env.superdeploy          # 🚀 PRODUCTION OVERRIDES
├── .env.example              # 📝 Template
├── Dockerfile
├── src/
└── .github/workflows/
    └── deploy.yml            # .env + .env.superdeploy merge eder
```

**Dosya Rolleri:**
- **addons/**: Şablonlar (template) - Hiçbir projeye özel değil, yeniden kullanılabilir
- **projects/[name]/**: Instance'lar (deployed) - Proje-spesifik, render edilmiş, çalışan
- **.env**: Local development - Geliştirici tarafından yönetilir
- **.env.superdeploy**: Production overrides - SuperDeploy tarafından oluşturulur

## 🔄 Scaling Yeni Proje

### Yeni Proje Ekleme
```bash
# 1. Proje oluştur
superdeploy init -p myapp --services api,frontend

# 2. Infrastructure deploy
superdeploy up -p myapp

# 3. Secrets sync
superdeploy sync:infra -p myapp
superdeploy sync:repos -e ~/myapp-api/.env:myorg/api -c ~/superdeploy/projects/myapp/.passwords.yml

# 4. Deploy
cd ~/myapp-api && git push origin production
```

### Otomatik Oluşturulan Kaynaklar
```bash
# Docker networks
myapp-network (172.21.0.0/24)

# Services  
myapp-forgejo:3002
myapp-postgres:5432
myapp-redis:6379
myapp-api:8000
myapp-frontend:3000

# Caddy routes
api.myapp.com → myapp-api:8000
myapp.com → myapp-frontend:3000

# Prometheus targets
myapp-api:8000/metrics
myapp-frontend:3000/metrics
```

## 🎯 Avantajlar

### ✅ Tam İzolasyon
- Her proje kendi DB/MQ/Redis'ine sahip
- Network seviyesinde izolasyon
- Secrets izolasyonu
- Deployment izolasyonu

### ✅ Ölçeklenebilirlik  
- Yeni proje = 5 dakika setup
- Shared monitoring tüm projeleri izler
- Shared proxy tüm projeleri serve eder

### ✅ Güvenlik
- Projeler birbirini göremez
- Encrypted secret transfer (AGE)
- Network policies ile izolasyon

### ✅ Operasyonel Kolaylık
- Tek CLI ile tüm operasyonlar
- Otomatik secret sync
- Otomatik service discovery
- Merkezi monitoring

## 🚨 Önemli Notlar

1. **Her proje izole:** Hiçbir shared state yok
2. **Forgejo per-project:** Her proje kendi Git server'ına sahip  
3. **Network separation:** Docker networks ile tam izolasyon
4. **Secret management:** GitHub → AGE → Forgejo → Docker
5. **Monitoring centralized:** Tüm projeler tek Grafana'da
