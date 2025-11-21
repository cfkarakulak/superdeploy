# SuperDeploy Mimarisi

## Genel Bakış

SuperDeploy, kendi altyapınızda **Heroku benzeri deployment deneyimi** sunan **self-hosted PaaS platformudur**. GitHub Actions ile direkt entegre çalışan, **self-hosted runner'lar** ve **addon-tabanlı mimari** kullanır.

## Temel Prensipler

1. **GitHub-First Architecture**: Merkezi CI/CD için GitHub Actions
2. **Self-Hosted Runners**: Project VMs'de direkt deployment için GitHub runners
3. **Addon-Tabanlı Mimari**: Tüm servisler (veritabanları, kuyruklar, proxy'ler) addon olarak tanımlanır
4. **Dinamik Konfigürasyon**: Hardcoded servis isimleri veya mantık yok - her şey `config.yml` ile yönetilir
5. **Proje İzolasyonu**: Her proje kendi izole kaynaklarına ve network'üne sahiptir
6. **Template → Instance Pattern**: Addon'lar template'dir, deployment'lar instance'dır
7. **Label-Based Routing**: Runner labels ile guaranteed project-specific routing
8. **IP Preservation**: VM restart'ta statik IP adresleri korunur

---

## Sistem Bileşenleri

### 1. CLI Katmanı (`cli/`)

Tüm operasyonları orkestra eden komut satırı arayüzü:

```
cli/
├── main.py                    # Giriş noktası, komut kaydı
├── base/                      # Base command classes
│   ├── base_command.py       # BaseCommand (console, verbose, etc.)
│   └── project_command.py    # ProjectCommand (extends BaseCommand)
├── commands/                  # Komut implementasyonları
│   ├── init.py               # Proje başlatma
│   ├── up.py                 # Altyapı deployment
│   ├── sync.py               # Secret senkronizasyonu (GitHub)
│   ├── generate.py           # GitHub workflow generation (type-aware)
│   ├── deploy.py             # Uygulama deployment
│   ├── status.py             # Sistem durumu (version tracking dahil)
│   ├── down.py               # Infrastructure teardown
│   └── orchestrator/         # Orchestrator subcommands
│       ├── init.py           # Orchestrator initialization
│       ├── up.py             # Orchestrator deployment
│       ├── down.py           # Orchestrator teardown
│       └── status.py         # Orchestrator status
├── core/                      # Temel fonksiyonellik
│   ├── addon.py              # Addon veri modeli
│   ├── addon_loader.py       # Dinamik addon keşfi
│   ├── app_type_registry.py  # App type plugin system (Python, Next.js)
│   ├── config_loader.py      # Proje konfigürasyonu
│   └── validator.py          # Konfigürasyon validasyonu
├── models/                    # Type-safe dataclasses
│   ├── deployment.py         # DeploymentState, VMState, etc.
│   ├── results.py            # CommandResult, ValidationResult
│   ├── secrets.py            # SecretConfig, AppSecrets
│   └── ssh.py                # SSHConfig, SSHConnection
├── services/                  # Business logic layer
│   ├── config_service.py     # Configuration management
│   ├── state_service.py      # State management
│   ├── secret_service.py     # Secret operations
│   ├── ssh_service.py        # SSH operations
│   └── vm_service.py         # VM operations
└── stubs/                     # Template dosyaları
    ├── workflows/            # GitHub Actions workflow templates
    └── configs/              # Config generator scripts
```

**Temel Özellikler:**
- Progress bar'lı zengin terminal UI
- Kurulum için interaktif wizard'lar
- Kapsamlı hata yönetimi
- Mümkün olduğunda paralel operasyonlar
- **Heroku-like app scaling** - Docker Compose replicas ile horizontal scaling

### 2. Process-Based Architecture (Heroku Procfile-like)

**Multi-Process Support:**

SuperDeploy, Heroku Procfile-like process definitions ile tek bir codebase'den birden fazla process type çalıştırır:

```yaml
apps:
  api:
    type: python       # App technology (not process type!)
    path: /path/to/api
    vm: app
    domain: api.cheapa.io
    processes:
      web:
        command: python craft serve --host 0.0.0.0 --port 8000
        port: 8000
        replicas: 2    # 2 web containers (load balanced)
      worker:
        command: python craft queue:work --tries=3
        replicas: 5    # 5 worker containers (background jobs)
      release:
        command: python craft migrate --force
        run_on: deploy # Runs once on deployment
```

**Özellikler:**
- ✅ **Heroku Procfile-like** - Tek codebase, birden fazla process type
- ✅ **Process-level scaling** - Her process type bağımsız scale edilir
- ✅ **Command override** - Dockerfile CMD yerine marker'dan command kullanılır
- ✅ **Zero-downtime deployments** - `start-first` stratejisi ile yeni container önce başlar
- ✅ **Automatic load balancing** - Caddy ve Docker Compose service discovery
- ✅ **Fast scaling** - 10-30 saniye (VM scaling: 5-10 dakika)
- ✅ **Cost-effective** - VM eklemeden horizontal scaling

**Docker Compose Implementation:**
```yaml
# Generated docker-compose.yml
services:
  api-web:           # Process: web
    image: org/api:latest
    command: python craft serve --host 0.0.0.0 --port 8000
    ports: ["8000:8000"]
    environment:
      - PROCESS_TYPE=web
    deploy:
      replicas: 2
      update_config:
        order: start-first
  
  api-worker:        # Process: worker
    image: org/api:latest
    command: python craft queue:work --tries=3
    environment:
      - PROCESS_TYPE=worker
    deploy:
      replicas: 5
```

**Key Design Decisions:**
- ✅ **Pattern**: `app-process` service naming (e.g., `api-web`, `api-worker`)
- ✅ **Same image**, different commands per process
- ✅ **NO `container_name`** - Docker auto-names replicas
- ✅ **ALL processes** use `deploy.replicas` format
- ✅ **Workflows deploy** all processes for an app automatically

**Caddy Load Balancing:**
- Service name routing (e.g., `api-web:8000`) instead of container names
- Docker Compose service discovery automatically load balances
- Round-robin policy with health checks
- Transparent to application code

**Benefits:**
- **Heroku-compatible** - Familiar Procfile-like workflow
- **Single codebase** - No duplicate app configs
- **Independent scaling** - web vs worker scaled separately
- **10x faster** than VM scaling (30 seconds vs 5-10 minutes)
- **10x cheaper** - No new VMs needed, just more containers
- **High availability** - Replica redundancy provides automatic failover
- **Gradual rollouts** - Rolling updates with automatic rollback on failure

### 3. Addon Sistemi (`addons/`)

Her proje için deploy edilebilen yeniden kullanılabilir servis template'leri:

```
addons/
├── postgres/                  # PostgreSQL addon
│   ├── addon.yml             # Metadata (isim, versiyon, kategori)
│   ├── env.yml               # Environment variable tanımları
│   ├── compose.yml.j2        # Docker Compose template
│   └── ansible.yml           # Deployment görevleri
├── redis/                     # Redis addon
├── rabbitmq/                  # RabbitMQ addon
├── caddy/                     # Reverse proxy + SSL
└── monitoring/                # Prometheus + Grafana (optional)
```

**Addon Yapısı:**

Her addon şunları içerir:
- **addon.yml**: Metadata (isim, açıklama, versiyon, kategori, bağımlılıklar)
- **env.yml**: Default'lar ve tipler ile environment variable şeması
- **compose.yml.j2**: Docker Compose servis tanımı için Jinja2 template
- **ansible.yml**: Deployment görevleri (kurulum, konfigürasyon, health check'ler)

**Örnek addon.yml:**
```yaml
name: postgres
description: PostgreSQL ilişkisel veritabanı
version: "15-alpine"
category: database

env_vars:
  - name: POSTGRES_HOST
    default: "${CORE_INTERNAL_IP}"
    required: true
    secret: false
  - name: POSTGRES_PASSWORD
    required: true
    secret: true
    generate: true

requires: []
conflicts: []
```

### 3. Proje Konfigürasyonu (`projects/`)

Her projenin kendi izole konfigürasyonu ve kaynakları vardır:

```
projects/
└── myproject/
    ├── config.yml           # Proje konfigürasyonu
    ├── secrets.yml           # Encrypted secrets
    └── state.yml             # Deployment state
```

**config.yml Yapısı:**
```yaml
project: myproject
description: Harika projem

# Cloud provider konfigürasyonu
cloud:
  gcp:
    project_id: "my-gcp-project"
    region: "us-central1"
    zone: "us-central1-a"

# VM konfigürasyonu
vms:
  app:
    machine_type: e2-medium
    disk_size: 30
    services: []
  
  core:
    machine_type: e2-medium
    disk_size: 20
    services:
      - postgres
      - rabbitmq

# GitHub configuration
github:
  organization: myorg

# Uygulama servisleri
apps:
  api:
    type: python              # App type (python, nextjs) - optional, auto-detected
    path: "~/code/myorg/api"
    vm: app
  
  storefront:
    type: nextjs              # App type (python, nextjs) - optional, auto-detected
    path: "~/code/myorg/storefront"
    vm: app

# Network konfigürasyonu
network:
  docker_subnet: "172.30.0.0/24"
```

### 4. Altyapı Katmanı (`shared/`)

Altyapı provisioning için Terraform ve Ansible konfigürasyonları:

```
shared/
├── terraform/                 # VM provisioning
│   ├── main.tf               # Ana konfigürasyon
│   ├── modules/
│   │   ├── network/          # VPC, subnet'ler, firewall
│   │   └── instance/         # VM instance'ları
│   └── variables.tf          # Input variable'ları
└── ansible/                   # Konfigürasyon yönetimi
    ├── playbooks/
    │   └── config.yml        # Ana orkestrasyon playbook
    └── roles/
        ├── system/            # Foundation katmanı
        │   ├── base/          # OS paketleri, kullanıcılar, swap
        │   ├── docker/        # Docker kurulumu
        │   ├── github-runner/ # GitHub self-hosted runner
        │   └── security/      # Firewall, SSH hardening
        └── orchestration/     # Deployment katmanı
            ├── addon-deployer/      # Generic addon deployment
            └── project-deployer/    # Proje deployment
```

---

## Deployment Mimarisi

### GitHub-Only Architecture

SuperDeploy, **GitHub Actions** ve **self-hosted runners** kullanan basit ve güçlü bir mimari kullanır:

```
App Repo (GitHub)
    ↓
GitHub Actions (Build)
    ├── Docker build & push
    └── Outputs: project, app, vm_role
    ↓
GitHub Self-Hosted Runner (Project VM)
    ├── Label matching: [self-hosted, superdeploy, {project}, {vm_role}]
    ├── Validate runner project
    ├── Pull Docker image
    ├── docker compose up -d
    └── Health check
    ↓
Running Container
```

### Runner Label Strategy

Her runner **unique label combination** alır:

```bash
# Project: cheapa
cheapa-app-0:  [self-hosted, superdeploy, cheapa, app]
cheapa-core-0: [self-hosted, superdeploy, cheapa, core]

# Project: blogapp
blogapp-app-0:  [self-hosted, superdeploy, blogapp, app]
blogapp-core-0: [self-hosted, superdeploy, blogapp, core]
```

**Workflow Routing:**

```yaml
# In app repo: .github/workflows/deploy.yml
jobs:
  deploy:
    runs-on: 
      - self-hosted  # Self-hosted runner
      - superdeploy  # SuperDeploy runner
      - cheapa       # Project name
      - app          # VM role
```

GitHub **otomatik olarak** TÜM label'ları eşleşen runner'a job'ı yönlendirir. ✅ **Guaranteed routing!**

### Template → Instance Pattern

SuperDeploy, addon'ların bir kez tanımlanıp her proje için instance'lanması prensibine dayanan **template-tabanlı mimari** kullanır:

```
TEMPLATE (addons/postgres/)
    ↓
config.yml konfigürasyonu
    ↓
Jinja2 rendering
    ↓
INSTANCE (myproject-postgres container)
```

**Örnek:**

Template (`addons/postgres/compose.yml.j2`):
```yaml
services:
  {{ project_name }}-postgres:
    image: postgres:{{ postgres_version }}
    environment:
      POSTGRES_USER: {{ postgres_user }}
      POSTGRES_PASSWORD: {{ postgres_password }}
      POSTGRES_DB: {{ postgres_database }}
    networks:
      - {{ project_name }}-network
```

Render Edilmiş Instance:
```yaml
services:
  myproject-postgres:
    image: postgres:15-alpine
    environment:
      POSTGRES_USER: myproject_user
      POSTGRES_PASSWORD: secure_generated_password
      POSTGRES_DB: myproject_db
    networks:
      - myproject-network
```

### Network İzolasyonu

Her proje tam izolasyon için kendi Docker network'üne sahiptir:

```
Project VM (myproject):
├── myproject-network (172.30.0.0/24)
│   ├── myproject-postgres
│   ├── myproject-redis
│   ├── myproject-api
│   └── myproject-storefront

Project VM (blogapp):
└── blogapp-network (172.31.0.0/24)
    ├── blogapp-postgres
    ├── blogapp-redis
    └── blogapp-api
```

**Avantajlar:**
- Projeler arası tam izolasyon
- Port çakışması yok
- Bağımsız ölçeklendirme
- Ayrı secret yönetimi

---

## Deployment Akışı

### 1. Proje Başlatma (`superdeploy init`)

```
Kullanıcı Girişi
    ↓
config.yml oluştur
    ↓
Güvenli şifreler oluştur (secrets.yml)
    ↓
Konfigürasyonu valide et
    ↓
Proje yapısını oluştur
```

### 2. Deployment File Generation (`superdeploy myproject:generate`)

```
App Type Resolution
    ├── Priority 1: Explicit type in config.yml (recommended)
    ├── Priority 2: Auto-detection from app path
    └── Priority 3: Default fallback (python)
    ↓
Create superdeploy marker (project, app, vm_role)
    ↓
Generate GitHub workflow (type-specific template)
    ├── Build job (GitHub-hosted runner)
    └── Deploy job (Self-hosted runner)
    ↓
Files created in app repos
```

### 3. Infrastructure Deployment (`superdeploy myproject:up`)

```
Terraform Phase:
    ├── Create VMs with static IPs
    ├── Configure networking
    └── Output: IPs → state.yml
    
Ansible Phase:
    ├── Install base system (Docker, Node.js)
    ├── Setup GitHub runner with labels
    ├── Create .project file (runner validation)
    ├── Deploy infrastructure addons
    └── Health checks
```

**GitHub Runner Setup:**
1. Download GitHub Actions runner binary
2. Get registration token from GitHub API using `REPOSITORY_TOKEN`
3. Register with labels: `[self-hosted, superdeploy, {project}, {vm_role}]`
4. Create systemd service
5. Start runner daemon

**Note:** No manual `GITHUB_RUNNER_TOKEN` needed - Ansible automatically fetches registration token via GitHub API.

### 4. Secret Sync (`superdeploy myproject:sync`)

```
secrets.yml
    ↓
GitHub CLI (gh)
    ├── Repository secrets (Docker credentials)
    └── Environment secrets (app configuration)
    ↓
Available in GitHub Actions workflows
```

### 5. Application Deployment (`git push production`)

```
Developer Push
    ↓
GitHub Actions Workflow
    ├── Build Job (ubuntu-latest):
    │   ├── Read superdeploy marker
    │   ├── Build Docker image
    │   ├── Push to registry
    │   └── Output: project, app, vm_role
    │
    └── Deploy Job (self-hosted runner):
        ├── Validate runner project (.project file)
        ├── Check if app exists on this VM
        ├── Pull Docker image
        ├── docker compose up -d {app}
        ├── Health check
        ├── Track version (semantic versioning)
        │   ├── Read current version from versions.json
        │   ├── Determine bump type (commit message)
        │   ├── Increment version (major/minor/patch)
        │   └── Save to versions.json
        ├── Cleanup old images
        └── Run deployment hooks (optional)
    ↓
Production Container Running (with version tracked)
```

**Semantic Versioning:**

Version'lar commit message'a göre otomatik artırılır:

```bash
# Patch bump (default): 0.0.1 → 0.0.2
git commit -m "Fix bug in API"

# Minor bump: 0.0.2 → 0.1.0
git commit -m "feat: add new endpoint"
git commit -m "[minor] improve performance"

# Major bump: 0.1.0 → 1.0.0
git commit -m "breaking: change API structure"
git commit -m "[major] rewrite authentication"
```

Version metadata `/opt/superdeploy/projects/{project}/versions.json` dosyasında saklanır:

```json
{
  "api": {
    "version": "1.2.5",
    "deployed_at": "2025-11-10T12:30:00Z",
    "git_sha": "abc1234...",
    "deployed_by": "user",
    "branch": "production"
  }
}
```

**Runner Validation:**

```bash
# Inside deploy job
RUNNER_PROJECT=$(cat /opt/superdeploy/.project)
if [ "$RUNNER_PROJECT" != "cheapa" ]; then
  echo "Wrong project!"
  exit 1
fi
```

---

## Konfigürasyon Yönetimi

### Secret Hierarchy

```yaml
# secrets.yml
secrets:
  shared:                     # Shared across all apps
    DOCKER_ORG: myorg
    DOCKER_USERNAME: user
    DOCKER_TOKEN: xxx
    POSTGRES_PASSWORD: xxx
  
  api:                        # App-specific secrets
    DATABASE_URL: postgres://...
    REDIS_URL: redis://...
  
  storefront:
    NEXT_PUBLIC_API_URL: https://api.com
```

**Merge Strategy:**
- `shared` secrets → merged with app-specific
- App secrets override shared secrets

### Secret Distribution

```bash
superdeploy myproject:sync
```

**Creates:**
1. **Repository Secrets** (build-time):
   - `DOCKER_ORG`, `DOCKER_USERNAME`, `DOCKER_TOKEN`

2. **Environment Secrets** (runtime):
   - All app-specific secrets
   - Available as `${{ secrets.KEY }}` in workflows

---

## Ölçeklendirme ve Çoklu Proje

### Yeni Proje Ekleme

```bash
# 1. Init project
superdeploy init -p newproject

# 2. Generate workflows
superdeploy newproject:generate

# 3. Deploy infrastructure (runners auto-register)
superdeploy newproject:up

# 4. Sync secrets
superdeploy newproject:sync

# 5. Push to production
cd ~/code/myorg/api
git push origin production
```

### Kaynak İzolasyonu

Her proje tamamen izoledir:

```
Project A:
├── Network: 172.30.0.0/24
├── Containers: projecta-*
├── Secrets: Separate GitHub secrets
└── Runners: projecta-app-0, projecta-core-0

Project B:
├── Network: 172.31.0.0/24
├── Containers: projectb-*
├── Secrets: Separate GitHub secrets
└── Runners: projectb-app-0, projectb-core-0
```

---

## Güvenlik Mimarisi

### Çok Katmanlı Güvenlik

**1. Secret Encryption:**
- GitHub encrypted storage
- Secrets never in Git
- Environment-based access control

**2. Network İzolasyonu:**
- Project-specific Docker networks
- VM firewall rules
- No inter-project communication

**3. Erişim Kontrolü:**
- SSH key-based VM access
- GitHub PAT for API access
- Project-specific runner tokens
- Label-based runner isolation

**4. Runner Security:**
- `.project` file validation
- Project-specific labels
- Guaranteed routing
- No cross-project access

---

## Bu Mimarinin Avantajları

### ✅ Basitlik

- GitHub Actions - bilinen workflow
- Self-hosted runners - direkt deployment
- No intermediate CI/CD layer
- Standard Docker Compose

### ✅ Guaranteed Routing

- Label-based matching
- GitHub native routing
- Double validation (.project file)
- Zero chance of cross-project deployment

### ✅ Tam Esneklik

- Yeni addon'lar ekle
- config.yml ile yapılandır
- İstediğin kadar proje
- Cloud-agnostic

### ✅ Developer Experience

- Heroku-like simplicity
- Single CLI for all operations
- Automated secret management
- Rich terminal UI

### ✅ İzolasyon

- Project-level isolation
- Network separation
- Independent scaling
- Separate secrets

---

## Teknik Kararlar

### Neden GitHub-Only?

**Problem:** İki CI/CD layer karmaşıklık ve maintenance yükü oluşturur.

**Çözüm:** GitHub Actions + self-hosted runners ile direkt deployment.

**Avantajlar:**
- Tek ekosistem
- Bilinen GitHub UI
- Native runner routing
- Basit maintenance
- Cost reduction

### Neden Self-Hosted Runners?

**Problem:** Deployment VM'lere güvenli erişim gerektiriyor.

**Çözüm:** GitHub self-hosted runner'ları VM'lerde çalıştır.

**Avantajlar:**
- Direkt VM erişimi
- Docker socket access
- Local file system
- No SSH needed
- GitHub native security

### Neden Label-Based Routing?

**Problem:** Birden fazla proje aynı GitHub organization'da - runner seçimi nasıl garantilenir?

**Çözüm:** Her runner unique label combination alır, GitHub otomatik match yapar.

**Avantajlar:**
- Guaranteed routing
- GitHub native feature
- Zero configuration
- Scalable
- Secure

---

## Son Güncellemeler

### GitHub Migration (2025)

1. **Intermediate CI/CD Layer Removed:** 
   - Direct GitHub Actions → VM deployment
   - Simpler architecture

2. **Self-Hosted Runners:** 
   - GitHub runners on project VMs
   - Label-based routing
   - `.project` file validation

3. **Workflow Generation:** 
   - `superdeploy generate` creates GitHub workflows
   - Type-aware (Python, Next.js)
   - Two jobs: build + deploy

4. **Secret Management:** 
   - GitHub-only secret storage
   - `gh` CLI integration
   - Repository + environment secrets

5. **VM-Specific Service Filtering:** 
   - Unchanged - still addon-based
   - Each VM runs only assigned services
   - Resource optimization

### CLI Refactoring (2025-11)

1. **Plugin Architecture:**
   - App type registry system (`app_type_registry.py`)
   - Extensible app type support
   - Explicit type field in config.yml
   - Priority: Explicit > Auto-detect > Default

2. **Command Structure:**
   - BaseCommand pattern for all commands
   - ProjectCommand extends BaseCommand
   - Orchestrator commands modularized
   - Type-safe dataclass models

3. **Service Layer:**
   - Clean service classes (ConfigService, StateService, etc.)
   - Dependency injection pattern
   - Business logic separation
   - Removed unused services

4. **Code Quality:**
   - Zero dead code (Vulture 80% confidence)
   - Full type hints coverage
   - SOLID principles
   - Clean exception hierarchy

---

## Gelecek Geliştirmeler

### Planlanan Özellikler

1. **Çoklu Cloud Desteği:** AWS, Azure, DigitalOcean
2. **Blue-Green Deployments:** Zero-downtime deployments
3. **Auto-scaling:** Metric-based container scaling
4. **Backup Automation:** Scheduled database backups
5. **Cost Optimization:** Resource usage monitoring
6. **Addon Marketplace:** Community-contributed addons
7. **Web UI:** Browser-based management interface

---

## Sonuç

SuperDeploy'un mimarisi self-hosted PaaS için **basit, güvenli ve ölçeklenebilir** bir platform sağlar. GitHub-first architecture karmaşıklığı azaltır, label-based routing garantili deployment sağlar, ve addon sistemi esneklik sunar. Bu mimari, ekiplerin kendi altyapılarında Heroku benzeri basitlikle production uygulamaları deploy etmelerini sağlar.
