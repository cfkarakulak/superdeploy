# SuperDeploy Mimari

## Genel Bakış

SuperDeploy, kendi altyapınızda **Heroku benzeri deployment deneyimi** sunan **self-hosted PaaS platformu**dur. Tüm servislerin yeniden kullanılabilir template'ler olarak tanımlandığı ve proje-spesifik instance'lar olarak deploy edildiği **dinamik, addon-tabanlı mimari** kullanır.

## Temel Prensipler

1. **Addon-Tabanlı Mimari**: Tüm servisler (veritabanları, kuyruklar, proxy'ler) addon olarak tanımlanır
2. **Dinamik Konfigürasyon**: Hardcoded servis isimleri veya mantık yok - her şey `project.yml` ile yönetilir
3. **Proje İzolasyonu**: Her proje kendi izole kaynaklarına ve network'üne sahiptir
4. **Template → Instance Pattern**: Addon'lar template'dir, deployment'lar instance'dır

---

## Sistem Bileşenleri

### 1. CLI Katmanı (`cli/`)

Tüm operasyonları orkestra eden komut satırı arayüzü:

```
cli/
├── main.py                    # Giriş noktası, komut kaydı
├── commands/                  # Komut implementasyonları
│   ├── init.py               # Proje başlatma
│   ├── up.py                 # Altyapı deployment
│   ├── orchestrator.py       # Orchestrator VM yönetimi
│   ├── sync.py               # Secret senkronizasyonu
│   ├── deploy.py             # Uygulama deployment
│   ├── status.py             # Sistem durumu
│   └── ...                   # Diğer operasyonel komutlar
└── core/                      # Temel fonksiyonellik
    ├── addon.py              # Addon veri modeli
    ├── addon_loader.py       # Dinamik addon keşfi
    ├── config_loader.py      # Proje konfigürasyonu
    └── validator.py          # Konfigürasyon validasyonu
```

**Temel Özellikler:**
- Progress bar'lı zengin terminal UI
- Kurulum için interaktif wizard'lar
- Kapsamlı hata yönetimi
- Mümkün olduğunda paralel operasyonlar
- Orchestrator ve proje VM'leri için ayrı komutlar

### 2. Addon Sistemi (`addons/`)

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
├── forgejo/                   # Git server + CI/CD (orchestrator'da)
├── caddy/                     # Reverse proxy + SSL
└── monitoring/                # Prometheus + Grafana (orchestrator'da)
```

**Orchestrator-Specific Addon'lar:**
- **forgejo**: Tüm projeler için merkezi Git server ve CI/CD
- **monitoring**: Tüm projeler için merkezi monitoring (Prometheus + Grafana)
- **caddy**: Subdomain-based routing ve otomatik SSL sertifikaları

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
    ├── project.yml           # Proje konfigürasyonu
    ├── .env                  # Environment variable'lar
    ├── .passwords.yml        # Otomatik oluşturulan secret'lar
    └── compose/              # Render edilmiş Docker Compose dosyaları
        ├── docker-compose.core.yml    # Altyapı servisleri
        └── docker-compose.apps.yml    # Uygulama container'ları
```

**project.yml Yapısı:**
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
  web:
    count: 1
    machine_type: e2-small
    disk_size: 20
    services:
      - postgres
      - redis
  api:
    count: 1
    machine_type: e2-small
    disk_size: 20
    services: []

# Addon konfigürasyonu
addons:
  postgres:
    version: "15-alpine"
    user: "myproject_user"
    database: "myproject_db"
  redis:
    version: "7-alpine"

# Orchestrator referansı (Forgejo merkezi)
orchestrator:
  host: "34.72.179.175"
  port: 3001
  org: "myorg"
  repo: "superdeploy"

# Uygulama servisleri
apps:
  api:
    path: "../app-repos/api"
    port: 8000
    vm: "api"
  dashboard:
    path: "../app-repos/dashboard"
    port: 3000
    vm: "web"

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
    │   └── site.yml          # Ana orkestrasyon playbook
    └── roles/
        ├── system/           # Foundation katmanı
        │   ├── base/         # OS paketleri, kullanıcılar, swap
        │   ├── docker/       # Docker kurulumu
        │   └── security/     # Firewall, SSH hardening
        └── orchestration/    # Deployment katmanı
            ├── addon-deployer/      # Generic addon deployment
            └── project-deployer/    # Proje deployment
```

---

## Deployment Mimarisi

### Orchestrator Pattern

SuperDeploy, **merkezi orchestrator VM** ve **proje-specific VM'ler** kullanan hibrit bir mimari kullanır:

```
Orchestrator VM (Global)
├── Forgejo (tüm projeler için)
├── Monitoring (Prometheus + Grafana)
└── Caddy (reverse proxy + SSL)

Project VMs (Proje-specific)
├── Infrastructure services (postgres, redis, rabbitmq)
├── Application containers
└── Forgejo runners (deployment için)
```

### Template → Instance Pattern

SuperDeploy, addon'ların bir kez tanımlanıp her proje için instance'lanması prensibine dayanan **template-tabanlı mimari** kullanır:

```
TEMPLATE (addons/postgres/)
    ↓
project.yml konfigürasyonu
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

Render Edilmiş Instance (`projects/myproject/compose/docker-compose.core.yml`):
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
Orchestrator VM:
├── orchestrator-network
│   ├── orchestrator-forgejo
│   ├── orchestrator-postgres (forgejo için)
│   ├── orchestrator-prometheus
│   ├── orchestrator-grafana
│   └── orchestrator-caddy

Project VM (myproject):
├── myproject-network (172.30.0.0/24)
│   ├── myproject-postgres
│   ├── myproject-redis
│   ├── myproject-api
│   └── myproject-dashboard

Project VM (otherapp):
└── otherapp-network (172.31.0.0/24)
    ├── otherapp-postgres
    ├── otherapp-redis
    └── otherapp-api
```

**Avantajlar:**
- Projeler arası tam izolasyon
- Port çakışması yok
- Bağımsız ölçeklendirme
- Ayrı secret yönetimi
- Merkezi Forgejo ve monitoring

---

## Deployment Akışı

### 1. Proje Başlatma (`superdeploy init`)

```
Kullanıcı Girişi
    ↓
project.yml oluştur
    ↓
Güvenli şifreler oluştur (.passwords.yml)
    ↓
Konfigürasyonu valide et
    ↓
Proje yapısını oluştur
```

**Ne olur:**
- İnteraktif wizard proje gereksinimlerini toplar
- Tüm konfigürasyonla `project.yml` oluşturur
- Tüm servisler için kriptografik olarak güvenli şifreler oluşturur
- Konfigürasyonu mevcut addon'lara karşı valide eder
- Proje dizin yapısını oluşturur

### 2. Orchestrator Deployment (`superdeploy orchestrator up`)

```
Terraform Fazı:
    Orchestrator VM oluştur
    
Ansible Fazı:
    ├── Forgejo + PostgreSQL deploy et
    ├── Monitoring (Prometheus + Grafana) deploy et
    ├── Caddy reverse proxy deploy et
    └── Orchestrator runner kur
```

### 3. Proje Deployment (`superdeploy up`)

```
Terraform Fazı:
    project.yml → tfvars → GCP API → VM'ler + Network
    
Ansible Fazı:
    project.yml + .passwords.yml
        ↓
    VM-specific addon'ları filtrele
        ↓
    Template'leri render et (compose.yml.j2, env.yml)
        ↓
    Container'ları deploy et
        ↓
    Proje-specific runner'ları kur
        ↓
    Health check'ler
        ↓
    Çalışan altyapı
```

**Terraform Fazı:**
1. `project.yml`'den VM konfigürasyonunu oku
2. Terraform variable'larını oluştur
3. Cloud provider'da VM'leri provision et
4. Network'ü yapılandır (VPC, subnet'ler, firewall)
5. VM IP'lerini proje `.env`'ine yaz
6. IP preservation desteği (VM restart'ta IP korunur)

**Ansible Fazı:**
1. Sistem paketlerini ve Docker'ı kur
2. Güvenliği yapılandır (firewall, SSH)
3. Addon template'lerini dinamik yükle
4. VM-specific service filtering (sadece ilgili addon'lar deploy edilir)
5. Template'leri proje-spesifik değerlerle render et
6. Container'ları Docker Compose ile deploy et
7. Proje-specific Forgejo runner'ları kur ve orchestrator'a register et
8. Health check'leri çalıştır

### 4. Secret Senkronizasyonu (`superdeploy sync`)

```
Kaynak Dosyalar:
├── superdeploy/.env (altyapı secret'ları)
├── projects/myproject/.passwords.yml (oluşturulan secret'lar)
└── app-repos/api/.env (uygulama secret'ları)
    ↓
Öncelikle merge et
    ↓
Dağıt:
├── GitHub Repository Secrets (build-time)
├── GitHub Environment Secrets (runtime)
└── Forgejo Repository Secrets (deployment)
```

**Secret Önceliği (yüksekten düşüğe):**
1. Kullanıcı tarafından sağlanan `.env` dosyaları (`--env-file`)
2. Proje-spesifik secret'lar (`.passwords.yml`)
3. Altyapı secret'ları (`superdeploy/.env`)

### 5. Uygulama Deployment (git push)

```
Developer Push
    ↓
GitHub Actions
    ├── Docker image build et
    ├── Registry'ye push et
    ├── Environment'ı şifrele (.env + .env.superdeploy)
    └── Forgejo workflow'unu tetikle (orchestrator'da)
    ↓
Orchestrator Forgejo
    ├── Workflow'u proje-specific runner'a yönlendir
    └── runs-on: [self-hosted, {project}, {vm_role}]
    ↓
Project VM Runner
    ├── Environment'ı decrypt et
    ├── Docker image'ı pull et
    ├── Eski container'ı durdur
    ├── Yeni container'ı başlat
    └── Health check
    ↓
Production Container Çalışıyor
```

---

## Addon Sistemi Detaylı

### Addon Keşfi

`AddonLoader` sınıfı addon'ları dinamik olarak keşfeder ve yükler:

```python
# Tüm mevcut addon'ları keşfet
available_addons = addon_loader.discover_available_addons()
# Döner: ['postgres', 'redis', 'rabbitmq', 'forgejo', ...]

# Belirli bir addon'ı yükle
addon = addon_loader.load_addon('postgres')

# Bir proje için tüm addon'ları yükle
addons = addon_loader.load_addons_for_project(project_config)
```

**Kod tabanında hiçbir yerde hardcoded addon isimleri yok!**

### Addon Rendering

Template'ler proje-spesifik context ile render edilir:

```python
# project.yml ve .passwords.yml'den context
context = {
    'project_name': 'myproject',
    'postgres_version': '15-alpine',
    'postgres_user': 'myproject_user',
    'postgres_password': 'secure_generated_password',
    'postgres_database': 'myproject_db'
}

# Compose template'ini render et
rendered_compose = addon.render_compose(context)

# Sonuç: Deploy edilmeye hazır Docker Compose servis tanımı
```

### Bağımlılık Çözümlemesi

Addon'lar bağımlılıkları ve çakışmaları tanımlayabilir:

```yaml
# addon.yml
requires:
  - postgres  # Bu addon PostgreSQL'e ihtiyaç duyar

conflicts:
  - mysql     # MySQL ile birlikte çalışamaz
```

`AddonLoader` otomatik olarak bağımlılıkları çözer ve döngüsel bağımlılıkları tespit eder.

### Health Check'ler

Her addon kendi health check stratejisini tanımlar:

```yaml
# addon.yml
healthcheck:
  command: "pg_isready -U ${POSTGRES_USER}"
  interval: 10s
  timeout: 5s
  retries: 5
  start_period: 30s
```

Deployment sistemi devam etmeden önce health check'lerin geçmesini bekler.

---

## Konfigürasyon Yönetimi

### Environment Variable Stratejisi

SuperDeploy environment variable'lar için **iki dosya yaklaşımı** kullanır:

**1. `.env` (Yerel Geliştirme)**
- Developer'lar tarafından yönetilir
- Yerel geliştirme değerlerini içerir
- **SuperDeploy tarafından asla değiştirilmez**
- Git'e commit edilmez

**2. `.env.superdeploy` (Production Override'ları)**
- SuperDeploy tarafından otomatik oluşturulur
- Production altyapı bağlantılarını içerir
- Deployment sırasında `.env` değerlerini override eder
- Git'e commit edilmez

**Merge Stratejisi:**
```bash
# Deployment sırasında (GitHub Actions)
.env (temel değerler)
    +
.env.superdeploy (override'lar)
    =
Container için final environment
```

### Secret Yönetimi

**Secret Oluşturma:**
```bash
# Init sırasında otomatik
superdeploy init -p myproject
# Oluşturur: projects/myproject/.passwords.yml

# İçerir:
POSTGRES_PASSWORD: <32-karakter güvenli rastgele>
REDIS_PASSWORD: <32-karakter güvenli rastgele>
RABBITMQ_PASSWORD: <32-karakter güvenli rastgele>
```

**Secret Dağıtımı:**
```bash
# GitHub ve Forgejo'ya sync et
superdeploy sync -p myproject

# Dağıtır:
# - GitHub Repository Secrets (build-time)
# - GitHub Environment Secrets (runtime)
# - Forgejo Repository Secrets (deployment)
```

**Secret Şifreleme:**
- Secret'lar transfer sırasında AGE ile şifrelenir
- Sadece Forgejo runner decrypt edebilir (private key'e sahip)
- Secret'lar Forgejo'da asla plaintext olarak saklanmaz

---

## Ölçeklendirme ve Çoklu Proje

### Yeni Proje Ekleme

```bash
# Yeni proje başlat
superdeploy init -p newproject

# Altyapıyı deploy et
superdeploy up -p newproject

# Secret'ları sync et
superdeploy sync -p newproject
```

**Otomatik Kaynak Tahsisi:**
- Benzersiz Docker network subnet
- Benzersiz port atamaları
- İzole container'lar
- Ayrı secret'lar

### Kaynak İzolasyonu

Her proje tamamen izoledir:

```
Proje A:
├── Network: 172.30.0.0/24
├── Container'lar: projecta-postgres, projecta-redis, projecta-api
├── Secret'lar: Ayrı GitHub/Forgejo secret'ları
└── Forgejo: Ayrı organizasyon

Proje B:
├── Network: 172.31.0.0/24
├── Container'lar: projectb-postgres, projectb-redis, projectb-api
├── Secret'lar: Ayrı GitHub/Forgejo secret'ları
└── Forgejo: Ayrı organizasyon
```

---

## Monitoring ve Gözlemlenebilirlik

### Merkezi Monitoring (Orchestrator)

SuperDeploy, orchestrator VM'de çalışan **Prometheus** ve **Grafana** ile merkezi monitoring sağlar:

**Prometheus:**
- Tüm projeleri otomatik keşfeder
- Her proje için ayrı scrape job'ları
- Node exporter metrikleri (CPU, RAM, disk)
- Container metrikleri

**Grafana:**
- Pre-configured dashboard'lar
- Proje bazlı filtreleme
- Alert yönetimi
- Caddy üzerinden subdomain erişimi (grafana.yourdomain.com)

**Caddy Reverse Proxy:**
- Subdomain-based routing
- Otomatik SSL sertifikaları (Let's Encrypt)
- Forgejo, Grafana, Prometheus için ayrı subdomain'ler

### Health Check Sistemi

SuperDeploy kapsamlı health check'ler uygular:

**Health Check Metodları:**
1. HTTP endpoint check'leri (web servisleri için)
2. Komut-tabanlı check'ler (veritabanları, kuyruklar için)
3. Container status check'leri (fallback)

**Health Check Konfigürasyonu:**
```yaml
# addon.yml
healthcheck:
  command: "redis-cli ping"
  interval: 10s
  timeout: 5s
  retries: 5
  start_period: 10s
```

**Hata Raporlama:**
Health check'ler başarısız olduğunda detaylı diagnostik sağlanır:
- Exit code ve output
- Container status ve log'ları
- Çalışan process'ler
- Troubleshooting adımları
- Resume komutları

### Deployment Doğrulama

Deployment sonrası sistem şunları doğrular:
- Tüm container'lar çalışıyor
- Health check'ler geçiyor
- Servisler erişilebilir
- Log'lar hata göstermiyor

---

## Güvenlik Mimarisi

### Çok Katmanlı Güvenlik

**1. Secret Şifreleme:**
- Secret transferi için AGE şifreleme
- Public key şifreleme (sadece runner decrypt edebilir)
- Secret'lar Forgejo'da asla plaintext değil

**2. Network İzolasyonu:**
- Proje başına Docker network'leri
- VM'lerde firewall kuralları
- Projeler arası iletişim yok

**3. Erişim Kontrolü:**
- VM erişimi için SSH key-tabanlı
- API erişimi için GitHub PAT
- Deployment için Forgejo PAT
- Proje başına ayrı credential'lar

**4. Secret Yönetimi:**
- Secret'lar GitHub/Forgejo şifreli depolamada
- Asla Git'e commit edilmez
- Otomatik rotasyon desteği
- Audit logging

---

## Bu Mimarinin Avantajları

### ✅ Tam Esneklik

- Kod değişikliği olmadan yeni addon'lar ekle
- `project.yml` üzerinden herhangi bir servisi yapılandır
- Herhangi bir cloud provider'ı destekle (GCP, AWS, Azure)
- İstediğin kadar proje deploy et

### ✅ Sıfır Hardcoding

- Kodda servis isimleri yok
- Kodda port numaraları yok
- Kodda IP adresleri yok
- Her şey konfigürasyonla yönetiliyor

### ✅ Yeniden Kullanılabilirlik

- Addon'lar bir kez tanımlanır, her yerde kullanılır
- Template'ler projeler arasında paylaşılır
- Tutarlı deployment pattern'leri
- Bakımı ve güncellemeyi kolay

### ✅ İzolasyon

- Tam proje izolasyonu
- Network seviyesinde ayrım
- Bağımsız ölçeklendirme
- Ayrı secret yönetimi

### ✅ Developer Deneyimi

- Heroku benzeri basitlik
- Tüm operasyonlar için tek CLI
- Otomatik secret yönetimi
- Zengin terminal UI

---

## Teknik Kararlar

### Neden Addon-Tabanlı Mimari?

**Problem:** Geleneksel PaaS platformları servis entegrasyonlarını hardcode eder, bu da onları esnek olmaktan çıkarır.

**Çözüm:** Servisleri metadata ile addon olarak tanımla, dinamik keşif ve deployment'a izin ver.

**Avantajlar:**
- Kod değişikliği olmadan yeni servisler ekle
- Tutarlı deployment pattern'leri
- Test etmesi ve valide etmesi kolay
- Topluluk addon'lar katkıda bulunabilir

### Neden Template → Instance Pattern?

**Problem:** Her proje için konfigürasyonu kopyalamak hata yapmaya açık ve bakımı zor.

**Çözüm:** Servisleri template olarak tanımla, her proje için spesifik değerlerle render et.

**Avantajlar:**
- DRY prensibi (Don't Repeat Yourself)
- Tutarlı servis tanımları
- Tüm projeleri güncellemeyi kolay
- Açık sorumluluk ayrımı

### Neden İki .env Dosyası?

**Problem:** Yerel geliştirme ve production değerlerini karıştırmak kafa karışıklığına ve güvenlik risklerine yol açar.

**Çözüm:** Yerel (`.env`) ve production (`.env.superdeploy`) için ayrı dosyalar, açık merge stratejisi ile.

**Avantajlar:**
- Yerel environment asla etkilenmez
- Production secret'ları asla yerel dosyalarda değil
- Açık override mekanizması
- Developer özgürlüğü

### Neden AGE Şifreleme?

**Problem:** Secret'ları GitHub'dan Forgejo'ya güvenli transfer etmek.

**Çözüm:** AGE public key ile şifrele, runner'da private key ile decrypt et.

**Avantajlar:**
- Basit ve güvenli
- Paylaşılan secret yok
- Audit trail
- Endüstri standardı

---

## Son Güncellemeler

### Yeni Özellikler (2025)

1. **Orchestrator Mimarisi:** Merkezi Forgejo ve monitoring
2. **Caddy Reverse Proxy:** Subdomain-based routing + otomatik SSL
3. **Merkezi Monitoring:** Prometheus + Grafana tüm projeler için
4. **VM-Specific Service Filtering:** Sadece ilgili addon'lar deploy edilir
5. **IP Preservation:** VM restart'ta IP adresleri korunur
6. **Selective Addon Deployment:** `--addon` flag ile belirli addon'ları deploy et
7. **GitHub Actions → Forgejo Integration:** Düzeltilmiş API endpoint'leri

## Gelecek Geliştirmeler

### Planlanan Özellikler

1. **Çoklu Cloud Desteği:** AWS, Azure, DigitalOcean
2. **Otomatik Ölçeklendirme:** Metrik'lere dayalı otomatik container ölçeklendirme
3. **Blue-Green Deployment'lar:** Sıfır downtime deployment'lar
4. **Backup Otomasyonu:** Zamanlanmış veritabanı backup'ları
5. **Maliyet Optimizasyonu:** Kaynak kullanımı monitoring ve öneriler
6. **Addon Marketplace:** Topluluk katkılı addon'lar
7. **Web UI:** Tarayıcı-tabanlı yönetim arayüzü
8. **Çoklu Bölge:** Birden fazla bölgeye deployment

### Genişletilebilirlik Noktaları

Mimari genişletilebilirlik için tasarlandı:

- **Özel Addon'lar:** Kendi servis tanımlarını ekle
- **Özel Komutlar:** CLI'yi yeni komutlarla genişlet
- **Özel Validator'lar:** Validasyon kuralları ekle
- **Özel Health Check'ler:** Servise-özel check'ler tanımla
- **Özel Deployment Stratejileri:** Yeni deployment pattern'leri uygula

---

## Sonuç

SuperDeploy'un mimarisi self-hosted PaaS için **esnek, ölçeklenebilir ve bakımı kolay** bir platform sağlar. Addon-tabanlı sistem hardcoding'i ortadan kaldırır, template pattern tutarlılığı sağlar ve izolasyon modeli güvenlik sunar. Bu mimari, ekiplerin kendi altyapılarında Heroku benzeri basitlikle production uygulamaları deploy etmelerini sağlar.
