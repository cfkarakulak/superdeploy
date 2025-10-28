# SuperDeploy İş Akışı ve Parametre Akışı

Bu doküman, SuperDeploy sisteminin iş mantığını ve parametrelerin sistem içinde nasıl aktığını açıklar.

## İçindekiler

1. [Başlangıç Akışı (init komutu)](#başlangıç-akışı-init-komutu)
2. [Altyapı Sağlama Akışı (up komutu)](#altyapı-sağlama-akışı-up-komutu)
3. [Sır Senkronizasyon Akışı (sync komutu)](#sır-senkronizasyon-akışı-sync-komutu)
4. [Deployment Akışı (git push)](#deployment-akışı-git-push)
5. [Parametre Akış Diyagramları](#parametre-akış-diyagramları)

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

## Altyapı Sağlama Akışı (up komutu)

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

a. **Template Rendering**
   - Addon template'i okunur
   - project.yml ve .passwords.yml değerleri enjekte edilir
   - Proje-spesifik Docker Compose dosyası oluşturulur

b. **Environment Dosyası Oluşturma**
   - Addon'un `env.yml` dosyası okunur
   - Şifreler ve yapılandırma değerleri birleştirilir

c. **Container Başlatma**
   - Docker Compose ile container'lar başlatılır
   - Health check'ler yapılır
   - Servis hazır olana kadar beklenir

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
- Forgejo API'sine POST request gönderilir
- Parametreler: project, service, image, encrypted env

#### Aşama 3: Forgejo Runner - Şifre Çözme ve Hazırlık

**Ne Olur?**

**1. Şifrelenmiş Dosyayı Alma**
- Forgejo runner parametreleri alır

**2. Şifre Çözme**
- `env.age` dosyası AGE private key ile şifre çözülür

**3. Docker Image Pull**
- GitHub Actions'da build edilen image pull edilir

**4. Environment Hazırlama**
- Şifresi çözülmüş environment variable'lar hazırlanır

#### Aşama 4: Forgejo Runner - Container Deployment

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
KULLANICI GİRİŞİ
    ↓
INIT KOMUTU
    ↓
project.yml + .passwords.yml
    ↓
UP KOMUTU
    ↓
Terraform → VM'ler
Ansible → Container'lar
    ↓
SYNC KOMUTU
    ↓
GitHub/Forgejo Secrets
    ↓
GIT PUSH
    ↓
GitHub Actions → Build
    ↓
Forgejo Runner → Deploy
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

SuperDeploy, dört ana komut etrafında organize edilmiş bir deployment sistemidir:

1. **init**: Proje yapılandırmasını ve güvenli şifreleri oluşturur
2. **up**: Bulut altyapısını sağlar ve servisleri deploy eder
3. **sync**: Şifreleri GitHub ve Forgejo'ya senkronize eder
4. **git push**: Otomatik deployment pipeline'ını tetikler

### Temel Prensipler

**1. Template-Based Architecture**
- Addon'lar yeniden kullanılabilir template'lerdir
- Her proje kendi instance'larını oluşturur

**2. Güvenli Şifre Yönetimi**
- Şifreler otomatik oluşturulur
- Transit sırasında şifrelenir (AGE)

**3. Environment Separation**
- Local (.env) ve production (.env.superdeploy) ayrıdır

**4. Otomatik Deployment**
- Git push otomatik deployment tetikler
- Health check ve rollback built-in
