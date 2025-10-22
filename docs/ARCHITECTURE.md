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

## 🔄 Forgejo Yapısı

### Tek Forgejo Instance - Org-Based İzolasyon

**ÖNEMLI:** Tek Forgejo instance tüm projeleri yönetir!

```bash
# Tek Forgejo Instance
http://34.44.228.225:3001
├── Organization: cradexco (shared infrastructure)
│   └── superdeploy-app (deployment workflows)
├── Organization: cheapa (cheapa project)
│   ├── api (app code - GitHub mirror)
│   ├── dashboard (app code - GitHub mirror)
│   └── services (app code - GitHub mirror)
└── Organization: myapp (myapp project)
    ├── api (app code - GitHub mirror)
    └── frontend (app code - GitHub mirror)
```

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

## 🚀 Deployment Akışı

### 1. GitHub → Forgejo Trigger
```bash
# GitHub Actions (cheapaio/api)
1. Build Docker image
2. Push to registry  
3. Encrypt environment variables (AGE)
4. Trigger Forgejo workflow
   POST http://34.44.228.225:3001/api/v1/repos/cradexco/superdeploy-app/dispatches
```

### 2. Forgejo Workflow Execution
```bash
# Forgejo Runner (cheapa-runner)
1. Receive encrypted payload from GitHub
2. Decrypt environment variables (AGE)
3. Generate docker-compose.yml for cheapa
4. Deploy: docker compose up cheapa-api
5. Health check: curl cheapa-api:8000/health
6. Send notification email
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

### SuperDeploy Repository
```
superdeploy/
├── shared/                    # Shared infrastructure
│   ├── terraform/            # VM provisioning
│   ├── ansible/              # Configuration management
│   └── compose/              # Shared services (Caddy, Prometheus)
├── projects/                 # Project-specific configs
│   └── cheapa/
│       ├── config.yml        # Project metadata
│       ├── .passwords.yml    # Generated secrets
│       └── compose/          # Project services
│           ├── docker-compose.core.yml    # DB, MQ, Redis
│           ├── docker-compose.apps.yml    # API, Dashboard
│           └── docker-compose.git.yml     # Forgejo
└── cli/                      # SuperDeploy CLI
```

### App Repositories (GitHub)
```
cheapaio/api/
├── .env                      # App-specific environment
├── Dockerfile
├── src/
└── .github/workflows/
    └── deploy.yml           # Build → Push → Trigger Forgejo

cheapaio/dashboard/  
├── .env                     # App-specific environment
├── Dockerfile
├── src/
└── .github/workflows/
    └── deploy.yml          # Build → Push → Trigger Forgejo
```

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
