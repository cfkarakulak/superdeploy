# SuperDeploy İş Akışı ve Parametre Akışı

Bu doküman, SuperDeploy sisteminin iş mantığını ve parametrelerin sistem içinde nasıl aktığını açıklar.

## İçindekiler

1. [Başlangıç Akışı (init komutu)](#başlangıç-akışı-init-komutu)
2. [Orchestrator Kurulum Akışı (orchestrator up)](#orchestrator-kurulum-akışı-orchestrator-up)
3. [Proje Altyapı Sağlama Akışı (up komutu)](#proje-altyapı-sağlama-akışı-up-komutu)
4. [Sır Senkronizasyon Akışı (sync komutu)](#sır-senkronizasyon-akışı-sync-komutu)
5. [Deployment Akışı (git push)](#deployment-akışı-git-push)
6. [Parametre Akış Diyagramları](#parametre-akış-diyagramları)

---

## Başlangıç Akışı (init komutu)

### Amaç
Yeni bir proje için gerekli tüm yapılandırma dosyalarını, dizin yapısını ve güvenli şifreleri oluşturmak.

### Ne Olur?

**1. Kullanıcı Girişi Toplama**
- Proje adı (örn: "myproject")
- Hangi servislerin kullanılacağı (PostgreSQL, Redis, RabbitMQ, vb.)
- VM yapılandırması (makine tipi, disk boyutu)
- Uygulama servisleri (API, Dashboard, vb.)
- Network yapılandırması (subnet)

**2. Proje Yapısı Oluşturma**
```
projects/[proje-adı]/
├── project.yml              # Ana proje yapılandırması
├── .passwords.yml           # Otomatik oluşturulan güvenli şifreler
└── compose/                 # Oluşturulacak Docker Compose dosyaları için
```

**3. Yapılandırma Dosyası Oluşturma (project.yml)**
- Proje metadata (isim, açıklama, oluşturma tarihi)
- VM yapılandırması (kaç VM, hangi servisleri çalıştıracak)
- Addon'lar (postgres, redis, rabbitmq, forgejo)
- Uygulama servisleri (hangi uygulamalar, hangi portlar)
- Network yapılandırması (subnet, IP aralıkları)

**4. Güvenli Şifre Oluşturma (.passwords.yml)**
Her servis için kriptografik olarak güvenli rastgele şifreler:
- `POSTGRES_PASSWORD`: PostgreSQL veritabanı şifresi
- `RABBITMQ_PASSWORD`: RabbitMQ mesaj kuyruğu şifresi
- `REDIS_PASSWORD`: Redis cache şifresi
- `FORGEJO_ADMIN_PASSWORD`: Forgejo admin şifresi

**5. Addon Yapılandırması Hazırlama**
- Template'ler `superdeploy/addons/[servis-adı]/` dizininden okunur
- Proje-spesifik değerler (isim, port, şifreler) ile birleştirilir
- Sonuç olarak proje için özelleştirilmiş yapılandırma oluşur

### Parametre Kaynakları ve Hedefleri

```
Kullanıcı Girişi
    ↓
project.yml ────────────────┐
    ↓                       ↓
.passwords.yml          Addon Templates
    ↓                   (superdeploy/addons/)
    ↓                       ↓
    └───────────────────────┘
              ↓
    Proje-Spesifik Yapılandırma
    (projects/[proje-adı]/)
```

### Neden Bu Şekilde?

- **Otomatik şifre oluşturma**: İnsan hatası riskini azaltır
- **Merkezi yapılandırma**: Tüm proje ayarları tek yerde
- **Template sistemi**: Addon'lar yeniden kullanılabilir
- **Ayrı şifre dosyası**: Şifreler version control'e girmez

---

## Orchestrator Kurulum Akışı (orchestrator up)

### Amaç
Tüm projeler için merkezi Forgejo, monitoring ve reverse proxy altyapısını kurmak.

### Ne Olur?

**1. Orchestrator VM Oluşturma**
- Terraform ile orchestrator VM provision edilir
- Sabit IP adresi atanır (preserve_ip: true)
- Firewall kuralları yapılandırılır

**2. Temel Sistem Kurulumu**
- Docker ve Docker Compose kurulumu
- Sistem paketleri ve güvenlik yapılandırması

**3. Forgejo Deployment**
- PostgreSQL container (Forgejo için)
- Forgejo container
- Admin user oluşturma
- Organization ve repository kurulumu

**4. Monitoring Deployment**
- Prometheus container
- Grafana container
- Otomatik proje keşfi yapılandırması

**5. Caddy Reverse Proxy**
- Subdomain-based routing
- Otomatik SSL sertifikaları (Let's Encrypt)
- forgejo.domain.com, grafana.domain.com, prometheus.domain.com

**6. Orchestrator Runner**
- Forgejo runner kurulumu
- Label: [orchestrator, linux, docker, ubuntu-latest]

### Parametre Akışı

```
orchestrator project.yml
    ↓
Terraform Variables
    ↓
GCP VM (orchestrator)
    ↓
Ansible Playbook
    ├── Forgejo + PostgreSQL
    ├── Monitoring (Prometheus + Grafana)
    ├── Caddy (reverse proxy)
    └── Orchestrator Runner
    ↓
Merkezi Altyapı Hazır
```

---

## Proje Altyapı Sağlama Akışı (up komutu)

### Amaç
Bulut altyapısını oluşturmak ve tüm servisleri çalışır hale getirmek.

### İki Aşamalı Süreç

#### Aşama 1: Terraform - Altyapı Oluşturma

**Ne Olur?**
1. **VM'leri Oluşturma**
   - project.yml'deki VM yapılandırması okunur
   - Her VM için bulut sağlayıcıda sanal makine oluşturulur
   - Disk, CPU, RAM özellikleri yapılandırılır

2. **Network Yapılandırması**
   - VPC (Virtual Private Cloud) oluşturulur
   - Subnet'ler tanımlanır
   - Firewall kuralları uygulanır
   - Statik IP adresleri atanır

**Parametre Akışı:**
```
project.yml
    ↓
Terraform Variables
    ↓
Cloud Provider API
    ↓
Oluşturulan Kaynaklar
    ↓
Terraform State
    ↓
Ansible Inventory (IP adresleri, host bilgileri)
```

#### Aşama 2: Ansible - Sistem Yapılandırması ve Servis Deployment

**Ne Olur?**

**1. Sistem Hazırlığı (Base Role)**
- İşletim sistemi güncellemeleri
- Gerekli paketlerin kurulumu
- Swap alanı yapılandırması
- Güvenlik ayarları (firewall, SSH hardening)

**2. Docker Kurulumu (Docker Role)**
- Docker Engine kurulumu
- Docker Compose kurulumu
- Docker daemon yapılandırması
- Docker network'leri oluşturma

**3. Addon Deployment (Addon-Deployer Role)**

Her addon için:

a. **VM-Specific Filtering**
   - VM'nin services listesi kontrol edilir
   - Sadece ilgili addon'lar deploy edilir
   - Örnek: web VM'de sadece postgres ve redis

b. **Template Rendering**
   - Addon template'i okunur
   - project.yml ve .passwords.yml değerleri enjekte edilir
   - Proje-spesifik Docker Compose dosyası oluşturulur

c. **Environment Dosyası Oluşturma**
   - Addon'un `env.yml` dosyası okunur
   - Şifreler ve yapılandırma değerleri birleştirilir

d. **Container Başlatma**
   - Docker Compose ile container'lar başlatılır
   - Health check'ler yapılır
   - Servis hazır olana kadar beklenir

**4. Forgejo Runner Kurulumu**
- Her VM'de proje-specific runner kurulur
- Orchestrator Forgejo'ya register edilir
- Label: [{project}, {vm_role}, linux, docker, ubuntu-latest]

### Parametre Akışı - Detaylı

```
project.yml + .passwords.yml
         ↓
Ansible Playbook Variables
         ↓
    ┌────┴────┐
    ↓         ↓
Base Vars   Addon Vars
    ↓         ↓
System      Addon Templates
Config      (compose.yml.j2, env.yml)
    ↓         ↓
Docker      Rendered Files
Install     (docker-compose.yml, .env)
    ↓         ↓
Network     Docker Compose Up
Setup       ↓
            Running Containers
```

---

## Sır Senkronizasyon Akışı (sync komutu)

### Amaç
Yerel yapılandırma dosyalarındaki şifreleri ve environment variable'ları GitHub ve Forgejo'ya senkronize etmek.

### Ne Olur?

**1. Kaynak Dosyaları Toplama**

Sistem şu dosyalardan bilgi toplar:
- `superdeploy/.env`: Altyapı seviyesi secret'lar
- `projects/[proje-adı]/.passwords.yml`: Otomatik oluşturulan servis şifreleri
- `app-repos/[servis]/.env`: Kullanıcının sağladığı uygulama-spesifik değerler

**2. Birleştirme ve Önceliklendirme**

Öncelik sırası:
```
1. Kullanıcı .env dosyaları (--env-file)  [EN YÜKSEK]
2. .passwords.yml (proje şifreleri)
3. superdeploy/.env (altyapı secret'ları)  [EN DÜŞÜK]
```

**3. Hedef Sistemlere Dağıtım**

#### A. GitHub Repository Secrets
- `FORGEJO_PAT`: Forgejo'ya erişim için
- `AGE_PUBLIC_KEY`: Şifreleme için public key
- `DOCKER_TOKEN`: Docker registry erişimi

#### B. GitHub Environment Secrets
- `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_USER`, `POSTGRES_PASSWORD`
- `REDIS_HOST`, `REDIS_PORT`, `REDIS_PASSWORD`
- `RABBITMQ_HOST`, `RABBITMQ_PORT`, `RABBITMQ_USER`, `RABBITMQ_PASSWORD`

#### C. Forgejo Repository Secrets
- GitHub Environment Secrets ile aynı değerler
- Deployment için gerekli

### Parametre Akışı - Detaylı

```
Kaynak Dosyalar                    Hedef Sistemler
─────────────────                  ───────────────

superdeploy/.env          ──→  GitHub Repo Secrets
projects/[proje]/.passwords.yml ──→  GitHub Env Secrets
app-repos/[servis]/.env   ──→  Forgejo Repo Secrets
```

---

## Deployment Akışı (git push)

### Amaç
Uygulama kodundaki değişiklikleri otomatik olarak production ortamına deploy etmek.

### Dört Aşamalı Süreç

#### Aşama 1: GitHub Actions - Build ve Şifreleme

**Ne Olur?**

**1. Kod Checkout**
- GitHub Actions runner, repository kodunu çeker

**2. Environment Hazırlama**
- `.env` dosyası okunur (local development değerleri)
- `.env.superdeploy` dosyası okunur (production override'ları)
- İki dosya birleştirilir

**3. GitHub Secrets Enjeksiyonu**
- GitHub Environment Secrets enjekte edilir
- Örnek: `POSTGRES_PASSWORD`, `REDIS_PASSWORD`

**4. Docker Image Build**
- Dockerfile kullanılarak Docker image build edilir
- Image tag'i: commit SHA

**5. Docker Registry'ye Push**
- Build edilen image registry'ye push edilir

**6. Environment Bundle Şifreleme**
- Environment variable'lar AGE ile şifrelenir
- Şifrelenmiş dosya: `env.age`

#### Aşama 2: GitHub Actions - Forgejo Tetikleme

**Ne Olur?**

**1. Forgejo Workflow Tetikleme**
- Orchestrator Forgejo API'sine POST request gönderilir
- Endpoint: `http://ORCHESTRATOR_IP:3001/api/v1/repos/{org}/{repo}/actions/workflows/deploy.yml/dispatches`
- Parametreler: project, service, image, encrypted env, vm_role

#### Aşama 3: Orchestrator Forgejo - Workflow Routing

**Ne Olur?**

**1. Workflow Dispatch**
- Orchestrator Forgejo workflow'u alır
- runs-on label'ına göre runner seçer
- Örnek: runs-on: [self-hosted, cheapa, api]

**2. Proje-Specific Runner'a Yönlendirir**
- Label matching ile doğru VM'deki runner'ı bulur
- Job'u ilgili runner'a atar

#### Aşama 4: Project VM Runner - Şifre Çözme ve Hazırlık

**Ne Olur?**

**1. Şifrelenmiş Dosyayı Alma**
- Project VM runner parametreleri alır

**2. Şifre Çözme**
- `env.age` dosyası AGE private key ile şifre çözülür

**3. Docker Image Pull**
- GitHub Actions'da build edilen image pull edilir

**4. Environment Hazırlama**
- Şifresi çözülmüş environment variable'lar hazırlanır

#### Aşama 5: Project VM Runner - Container Deployment

**Ne Olur?**

**1. Mevcut Container'ı Durdurma**
- Çalışan container varsa graceful shutdown

**2. Yeni Container Başlatma**
- Docker Compose ile yeni container başlatılır
- Environment variable'lar enjekte edilir

**3. Health Check**
- Container başladıktan sonra health check yapılır
- Başarısız olursa rollback

**4. Eski Container'ı Temizleme**
- Yeni container sağlıklı çalışıyorsa eski container silinir

---

## Parametre Akış Diyagramları

### 1. Proje Başlangıcından Deployment'a Tam Akış

```
ORCHESTRATOR KURULUMU (Bir Kere)
    ↓
superdeploy orchestrator up
    ↓
Orchestrator VM
├── Forgejo (merkezi)
├── Monitoring (Prometheus + Grafana)
└── Caddy (reverse proxy + SSL)
    ↓
PROJE KURULUMU
    ↓
KULLANICI GİRİŞİ
    ↓
INIT KOMUTU
    ↓
project.yml + .passwords.yml
    ↓
UP KOMUTU
    ↓
Terraform → Project VM'ler
Ansible → Container'lar + Runners
    ↓
SYNC KOMUTU
    ↓
GitHub/Forgejo Secrets
    ↓
GIT PUSH
    ↓
GitHub Actions → Build
    ↓
Orchestrator Forgejo → Route to Project Runner
    ↓
Project VM Runner → Deploy
    ↓
PRODUCTION CONTAINER
```

### 2. Template'ten Instance'a Dönüşüm

```
TEMPLATE (addons/postgres/)
    ↓
project.yml + .passwords.yml
    ↓
Jinja2 Rendering
    ↓
INSTANCE (myproject-postgres)
```

---

## Özet

SuperDeploy, beş ana komut etrafında organize edilmiş bir deployment sistemidir:

1. **orchestrator up**: Merkezi Forgejo, monitoring ve reverse proxy altyapısını kurar (bir kere)
2. **init**: Proje yapılandırmasını ve güvenli şifreleri oluşturur
3. **up**: Bulut altyapısını sağlar ve servisleri deploy eder
4. **sync**: Şifreleri GitHub ve Forgejo'ya senkronize eder
5. **git push**: Otomatik deployment pipeline'ını tetikler

### Temel Prensipler

**1. Orchestrator Pattern**
- Merkezi Forgejo tüm projeler için
- Merkezi monitoring (Prometheus + Grafana)
- Caddy reverse proxy ile subdomain routing

**2. Template-Based Architecture**
- Addon'lar yeniden kullanılabilir template'lerdir
- Her proje kendi instance'larını oluşturur
- VM-specific filtering ile sadece ilgili addon'lar deploy edilir

**3. Güvenli Şifre Yönetimi**
- Şifreler otomatik oluşturulur
- Transit sırasında şifrelenir (AGE)

**4. Environment Separation**
- Local (.env) ve production (.env.superdeploy) ayrıdır

**5. Otomatik Deployment**
- Git push otomatik deployment tetikler
- Orchestrator Forgejo workflow'u proje-specific runner'a yönlendirir
- Health check ve rollback built-in
