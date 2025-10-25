# SuperDeploy İş Akışı ve Parametre Akışı

Bu doküman, SuperDeploy sisteminin iş mantığını ve parametrelerin sistem içinde nasıl aktığını açıklar. Teknik implementasyon detaylarından ziyade, **ne** olduğuna ve **neden** olduğuna odaklanır.

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
- Proje adı (örn: "cheapa")
- Proje açıklaması
- Hangi servislerin kullanılacağı (PostgreSQL, Redis, RabbitMQ, vb.)
- VM yapılandırması (makine tipi, disk boyutu)
- Uygulama servisleri (API, Dashboard, vb.)
- GitHub organizasyonu
- Domain bilgisi (opsiyonel)

**2. Proje Yapısı Oluşturma**
Sistem şu dizin yapısını oluşturur:
```
projects/[proje-adı]/
├── project.yml              # Ana proje yapılandırması
├── .passwords.yml           # Otomatik oluşturulan güvenli şifreler
└── compose/                 # Oluşturulacak Docker Compose dosyaları için
```

**3. Yapılandırma Dosyası Oluşturma (project.yml)**
Kullanıcı girişlerinden şu yapılandırma oluşturulur:
- Proje metadata (isim, açıklama, oluşturma tarihi)
- Altyapı gereksinimleri (Forgejo, monitoring, vb.)
- VM yapılandırması (kaç VM, hangi servisleri çalıştıracak)
- Core servisler (addon tabanlı: postgres, redis, rabbitmq)
- Uygulama servisleri (hangi uygulamalar, hangi portlar)
- Network yapılandırması (subnet, IP aralıkları)

**4. Güvenli Şifre Oluşturma (.passwords.yml)**
Her servis için kriptografik olarak güvenli rastgele şifreler oluşturulur:
- `POSTGRES_PASSWORD`: PostgreSQL veritabanı şifresi
- `RABBITMQ_PASSWORD`: RabbitMQ mesaj kuyruğu şifresi
- `REDIS_PASSWORD`: Redis cache şifresi
- `[SERVIS]_SECRET_KEY`: Her uygulama için benzersiz secret key'ler
- `AGE_SECRET_KEY`: Şifreleme için kullanılacak private key

**5. Addon Yapılandırması Hazırlama**
Her seçilen servis için addon template'lerinden yapılandırma hazırlanır:
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

- **Otomatik şifre oluşturma**: İnsan hatası riskini azaltır, güvenli şifreler garanti eder
- **Merkezi yapılandırma**: Tüm proje ayarları tek bir yerde (project.yml)
- **Template sistemi**: Addon'lar yeniden kullanılabilir, her proje için özelleştirilebilir
- **Ayrı şifre dosyası**: Şifreler version control'e girmez, güvenli saklanır

---

## Altyapı Sağlama Akışı (up komutu)

### Amaç
Bulut altyapısını oluşturmak ve tüm servisleri çalışır hale getirmek.

### İki Aşamalı Süreç

#### Aşama 1: Terraform - Altyapı Oluşturma

**Ne Olur?**
1. **VM'leri Oluşturma**
   - project.yml'deki VM yapılandırması okunur
   - Her VM için bulut sağlayıcıda (GCP, AWS, vb.) sanal makine oluşturulur
   - Disk, CPU, RAM özellikleri yapılandırılır

2. **Network Yapılandırması**
   - VPC (Virtual Private Cloud) oluşturulur
   - Subnet'ler tanımlanır (project.yml'deki network ayarlarından)
   - Firewall kuralları uygulanır
   - Statik IP adresleri atanır

3. **DNS Kayıtları**
   - Domain varsa, DNS kayıtları oluşturulur
   - VM'lerin IP adresleri domain'lere bağlanır

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
Terraform State (terraform.tfstate)
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

Her addon için şu adımlar gerçekleşir:

a. **Template Rendering**
   - Addon template'i (`superdeploy/addons/[addon]/compose.yml.j2`) okunur
   - project.yml ve .passwords.yml'deki değerler template'e enjekte edilir
   - Proje-spesifik Docker Compose dosyası oluşturulur
   - Örnek: `cheapa-postgres`, `cheapa-redis`, `cheapa-forgejo`

b. **Environment Dosyası Oluşturma**
   - Addon'un `env.yml` dosyası okunur
   - Şifreler ve yapılandırma değerleri birleştirilir
   - `.env` dosyası oluşturulur

c. **Yapılandırma Dosyaları**
   - Addon'a özel yapılandırma dosyaları (Caddyfile, prometheus.yml, vb.)
   - Template'lerden oluşturulur ve VM'e kopyalanır

d. **Container Başlatma**
   - Docker Compose ile container'lar başlatılır
   - Health check'ler yapılır
   - Servis hazır olana kadar beklenir

**4. Özel Görevler (Addon-Specific Tasks)**
Bazı addon'lar ek yapılandırma gerektirir:

- **Forgejo**: Admin kullanıcı oluşturma, organizasyon kurma, runner kurulumu
- **Monitoring**: Prometheus target'ları yapılandırma, Grafana dashboard'ları yükleme
- **PostgreSQL**: Veritabanı ve kullanıcı oluşturma

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

### Karar Noktaları

**1. Hangi VM'de Hangi Servisler?**
- project.yml'deki `vms.[vm-adı].services` listesi kontrol edilir
- Her servis belirtilen VM'e deploy edilir
- Örnek: `core` VM'de postgres, redis, rabbitmq, forgejo

**2. Port Çakışması Kontrolü**
- Her servisin port numarası kontrol edilir
- Çakışma varsa hata verilir, deployment durur
- Kullanıcı port numaralarını değiştirmeli

**3. Bağımlılık Sıralaması**
- Bazı servisler diğerlerine bağımlıdır
- Örnek: Monitoring, diğer servislerin çalışıyor olmasını bekler
- Ansible, bağımlılık sırasına göre deployment yapar

### Neden Bu Şekilde?

- **İki aşamalı yaklaşım**: Altyapı ve yapılandırma ayrı, her biri kendi aracıyla
- **Terraform**: Altyapı oluşturma için industry standard
- **Ansible**: Yapılandırma yönetimi için güçlü ve esnek
- **Template sistemi**: Aynı addon, farklı projeler için farklı yapılandırmalarla kullanılabilir
- **Health check'ler**: Servisler gerçekten hazır olana kadar beklenir, yarım deployment önlenir

---

## Sır Senkronizasyon Akışı (sync komutu)

### Amaç
Yerel yapılandırma dosyalarındaki şifreleri ve environment variable'ları GitHub ve Forgejo'ya senkronize etmek.

### Ne Olur?

**1. Kaynak Dosyaları Toplama**

Sistem şu dosyalardan bilgi toplar:
- `superdeploy/.env`: Altyapı seviyesi secret'lar (FORGEJO_PAT, AGE_PUBLIC_KEY, DOCKER_TOKEN)
- `projects/[proje-adı]/.passwords.yml`: Otomatik oluşturulan servis şifreleri
- `app-repos/[servis]/.env`: Kullanıcının sağladığı uygulama-spesifik değerler (--env-file ile)

**2. Birleştirme ve Önceliklendirme**

Aynı değişken birden fazla yerde tanımlıysa, öncelik sırası:
```
1. Kullanıcı .env dosyaları (--env-file)  [EN YÜKSEK ÖNCELİK]
2. .passwords.yml (proje şifreleri)
3. superdeploy/.env (altyapı secret'ları)  [EN DÜŞÜK ÖNCELİK]
```

**Neden bu sıra?**
- Kullanıcının manuel olarak verdiği değerler her zaman kazanır
- Otomatik oluşturulan şifreler fallback olarak kullanılır
- Altyapı secret'ları en genel seviyedir

**3. Hedef Sistemlere Dağıtım**

Birleştirilen secret'lar üç farklı yere gönderilir:

#### A. GitHub Repository Secrets
**Ne gider?**
- `FORGEJO_PAT`: Forgejo'ya erişim için Personal Access Token
- `AGE_PUBLIC_KEY`: Şifreleme için public key
- `DOCKER_TOKEN`: Docker registry erişimi
- `SSH_PRIVATE_KEY`: VM'lere SSH erişimi

**Neden buraya?**
- GitHub Actions build aşamasında bu secret'lara ihtiyaç duyar
- Docker image build etmek için registry erişimi gerekir
- Forgejo'yu tetiklemek için PAT gerekir

#### B. GitHub Environment Secrets
**Ne gider?**
- `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`
- `REDIS_HOST`, `REDIS_PORT`, `REDIS_PASSWORD`
- `RABBITMQ_HOST`, `RABBITMQ_PORT`, `RABBITMQ_USER`, `RABBITMQ_PASSWORD`
- Uygulama-spesifik secret'lar (API keys, JWT secrets, vb.)

**Neden buraya?**
- Runtime'da container'ların ihtiyaç duyduğu değerler
- Environment-specific (dev, staging, prod farklı olabilir)
- GitHub Actions, bu secret'ları şifreleyip Forgejo'ya gönderir

#### C. Forgejo Repository Secrets
**Ne gider?**
- GitHub Environment Secrets ile aynı değerler
- Yani: Veritabanı bağlantıları, cache bağlantıları, mesaj kuyruğu bağlantıları

**Neden buraya?**
- Forgejo runner, deployment yaparken bu secret'lara ihtiyaç duyar
- Container'ları başlatırken environment variable olarak enjekte edilir

### Parametre Akışı - Detaylı

```
Kaynak Dosyalar                    Birleştirme                    Hedef Sistemler
─────────────────                  ───────────                    ───────────────

superdeploy/.env                       ↓
  - FORGEJO_PAT                        ↓
  - AGE_PUBLIC_KEY          ──→  Merge Logic  ──→  GitHub Repo Secrets
  - DOCKER_TOKEN                   (Priority)         - FORGEJO_PAT
  - SSH_PRIVATE_KEY                    ↓              - AGE_PUBLIC_KEY
                                       ↓              - DOCKER_TOKEN
projects/[proje]/.passwords.yml        ↓              - SSH_PRIVATE_KEY
  - POSTGRES_PASSWORD                  ↓
  - REDIS_PASSWORD          ──→        ↓         ──→  GitHub Env Secrets
  - RABBITMQ_PASSWORD                  ↓              - POSTGRES_*
  - SECRET_KEY                         ↓              - REDIS_*
                                       ↓              - RABBITMQ_*
app-repos/[servis]/.env                ↓              - APP_SECRET_KEY
  - APP_SECRET_KEY          ──→        ↓              - JWT_SECRET
  - JWT_SECRET                         ↓              - API_KEY
  - API_KEY                            ↓
  - CUSTOM_CONFIG                      ↓         ──→  Forgejo Repo Secrets
                                       ↓              (GitHub Env ile aynı)
                                       ↓              - POSTGRES_*
                                       ↓              - REDIS_*
                                       ↓              - RABBITMQ_*
                                       ↓              - APP_SECRET_KEY
                                       ↓              - JWT_SECRET
                                       ↓              - API_KEY
```

### Çakışma Çözümü

**Senaryo 1: Aynı değişken farklı değerlerle**
```
.passwords.yml:     POSTGRES_PASSWORD=auto-generated-123
app-repos/api/.env: POSTGRES_PASSWORD=my-custom-password

Sonuç: my-custom-password kullanılır (kullanıcı öncelikli)
```

**Senaryo 2: Boş değer**
```
app-repos/api/.env: API_KEY=

Sonuç: Bu değişken senkronize edilmez (boş değerler atlanır)
```

**Senaryo 3: Sadece bir yerde tanımlı**
```
.passwords.yml: POSTGRES_PASSWORD=auto-generated-123

Sonuç: auto-generated-123 kullanılır (tek kaynak)
```

### Karar Noktaları

**1. Hangi repository'lere senkronize edilecek?**
- project.yml'deki `apps` listesi kontrol edilir
- Her app için GitHub ve Forgejo repository'si belirlenir
- Sadece bu repository'lere secret'lar gönderilir

**2. Hangi secret'lar hangi repository'ye?**
- Repository secrets: Tüm app'ler için aynı (altyapı seviyesi)
- Environment secrets: Her app için farklı olabilir (app-spesifik)

**3. Hata durumunda ne olur?**
- Bir repository'ye gönderim başarısız olursa, diğerleri devam eder
- Sonuçta başarı/başarısızlık raporu gösterilir
- Kullanıcı hangi repository'lerde sorun olduğunu görür

### Neden Bu Şekilde?

- **Üç katmanlı dağıtım**: Her sistem kendi ihtiyacı olan secret'ları alır
- **Öncelik sistemi**: Kullanıcı kontrolü, otomasyondan önce gelir
- **Güvenlik**: Secret'lar asla kod repository'sine commit edilmez
- **Esneklik**: Her app farklı secret'lara sahip olabilir
- **Hata toleransı**: Bir başarısızlık tüm süreci durdurmaz

---

## Deployment Akışı (git push)

### Amaç
Uygulama kodundaki değişiklikleri otomatik olarak production ortamına deploy etmek.

### Dört Aşamalı Süreç

#### Aşama 1: GitHub Actions - Build ve Şifreleme

**Tetikleyici**: Developer, app repository'sine kod push'lar (örn: `cheapaio/api`)

**Ne Olur?**

**1. Kod Checkout**
- GitHub Actions runner, repository kodunu çeker
- Belirtilen branch (main, develop, vb.) checkout edilir

**2. Environment Hazırlama**
- `.env` dosyası repository'den okunur (local development değerleri)
- `.env.superdeploy` dosyası repository'den okunur (production override'ları)
- İki dosya birleştirilir: `.env.superdeploy` değerleri `.env` değerlerini override eder

**Neden iki dosya?**
- `.env`: Developer'ın local development için kullandığı değerler
- `.env.superdeploy`: SuperDeploy'un production için oluşturduğu değerler
- Birleştirme: Local değerler base, production değerleri override

**3. GitHub Secrets Enjeksiyonu**
- GitHub Environment Secrets, environment variable olarak enjekte edilir
- Örnek: `POSTGRES_PASSWORD`, `REDIS_PASSWORD`, `JWT_SECRET`
- Bu değerler birleştirilmiş `.env` dosyasına eklenir

**4. Docker Image Build**
- Dockerfile kullanılarak Docker image build edilir
- Image tag'i: commit SHA veya branch adı
- Build sırasında environment variable'lar image'a gömülmez (güvenlik)

**5. Docker Registry'ye Push**
- Build edilen image, Docker registry'ye push edilir
- Registry: Docker Hub, GitHub Container Registry, veya private registry
- Credentials: GitHub Repository Secrets'tan (`DOCKER_TOKEN`)

**6. Environment Bundle Şifreleme**
- Birleştirilmiş environment variable'lar bir dosyaya yazılır
- AGE encryption ile şifrelenir (public key: GitHub Repository Secrets'tan)
- Şifrelenmiş dosya: `env.age`

**Neden şifreleme?**
- Environment variable'lar hassas bilgiler içerir (şifreler, API keys)
- GitHub Actions'dan Forgejo'ya güvenli transfer için şifreleme gerekir
- Sadece Forgejo runner şifreyi çözebilir (private key'e sahip)

#### Aşama 2: GitHub Actions - Forgejo Tetikleme

**Ne Olur?**

**1. Forgejo Repository'ye Push**
- Şifrelenmiş `env.age` dosyası Forgejo repository'sine push edilir
- Commit message: Deployment trigger bilgisi
- Branch: Genellikle `deploy` veya `main`

**2. Forgejo Webhook Tetikleme**
- Push işlemi Forgejo'da webhook tetikler
- Webhook, Forgejo Actions workflow'unu başlatır

**Parametre Geçişi:**
```
GitHub Actions
    ↓
Şifrelenmiş env.age
    ↓
Forgejo Repository
    ↓
Forgejo Webhook
    ↓
Forgejo Actions Workflow
```

#### Aşama 3: Forgejo Runner - Şifre Çözme ve Hazırlık

**Ne Olur?**

**1. Şifrelenmiş Dosyayı Alma**
- Forgejo runner, repository'den `env.age` dosyasını çeker
- AGE private key Forgejo Secrets'tan alınır

**2. Şifre Çözme**
- `env.age` dosyası AGE private key ile şifre çözülür
- Sonuç: Plain text environment variable'lar

**3. Docker Image Pull**
- GitHub Actions'da build edilen image, registry'den pull edilir
- Image tag: GitHub Actions'da push edilen tag ile aynı

**4. Environment Hazırlama**
- Şifresi çözülmüş environment variable'lar `.env` dosyasına yazılır
- Docker Compose için hazır hale getirilir

#### Aşama 4: Forgejo Runner - Container Deployment

**Ne Olur?**

**1. Mevcut Container'ı Durdurma**
- Çalışan container varsa, graceful shutdown yapılır
- Health check başarısız olursa, force stop

**2. Yeni Container Başlatma**
- Docker Compose ile yeni container başlatılır
- Environment variable'lar container'a enjekte edilir
- Volume'lar ve network'ler bağlanır

**3. Health Check**
- Container başladıktan sonra health check yapılır
- HTTP endpoint kontrolü veya container status kontrolü
- Başarısız olursa, rollback yapılır

**4. Eski Container'ı Temizleme**
- Yeni container sağlıklı çalışıyorsa, eski container silinir
- Eski image'lar temizlenir (disk alanı için)

**5. Deployment Sonucu Raporlama**
- Başarılı/başarısız deployment bilgisi loglanır
- Webhook veya notification gönderilebilir (opsiyonel)

### Parametre Akışı - Tam Süreç

```
Developer Push
    ↓
GitHub Actions Runner
    ↓
┌───────────────────────────────────┐
│ 1. .env + .env.superdeploy merge  │
│ 2. GitHub Secrets enjekte         │
│ 3. Docker build                   │
│ 4. Registry push                  │
│ 5. Environment şifreleme          │
└───────────────────────────────────┘
    ↓
Forgejo Repository (env.age push)
    ↓
Forgejo Webhook Trigger
    ↓
Forgejo Runner
    ↓
┌───────────────────────────────────┐
│ 1. env.age şifre çözme            │
│ 2. Docker image pull              │
│ 3. Container stop                 │
│ 4. Container start (yeni image)   │
│ 5. Health check                   │
└───────────────────────────────────┘
    ↓
Running Container (Production)
```

### Karar Noktaları

**1. Hangi branch deploy edilecek?**
- GitHub Actions workflow'unda tanımlı (genellikle `main` veya `production`)
- Sadece belirtilen branch'lere push deployment tetikler

**2. Health check başarısız olursa?**
- Yeni container durdurulur
- Eski container tekrar başlatılır (rollback)
- Deployment başarısız olarak işaretlenir

**3. Şifre çözme başarısız olursa?**
- Deployment durur
- Hata mesajı loglanır
- Mevcut container çalışmaya devam eder (değişiklik yapılmaz)

**4. Image pull başarısız olursa?**
- Registry erişim kontrol edilir
- Credentials doğru mu kontrol edilir
- Başarısız olursa deployment durur

### Güvenlik Katmanları

**1. Şifreleme**
- Environment variable'lar transit sırasında şifreli
- Sadece Forgejo runner şifreyi çözebilir

**2. Secret Yönetimi**
- Secret'lar asla kod repository'sine commit edilmez
- GitHub ve Forgejo secret management kullanılır

**3. Erişim Kontrolü**
- GitHub Actions: Repository erişimi gerekir
- Forgejo: PAT (Personal Access Token) ile kimlik doğrulama
- VM: SSH key ile erişim

**4. Network İzolasyonu**
- Container'lar private network'te çalışır
- Sadece gerekli portlar expose edilir
- Firewall kuralları ile korunur

### Neden Bu Şekilde?

- **Otomatik deployment**: Manuel müdahale gerektirmez, hata riski azalır
- **Güvenli transfer**: Şifreleme ile hassas bilgiler korunur
- **İki aşamalı build**: GitHub'da build, Forgejo'da deploy (separation of concerns)
- **Rollback mekanizması**: Sorun olursa eski versiyona dönülebilir
- **Health check**: Broken deployment production'a çıkmaz

---

## Parametre Akış Diyagramları

Bu bölüm, parametrelerin sistem içinde nasıl aktığını görsel olarak gösterir.

### 1. Proje Başlangıcından Deployment'a Tam Akış

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         KULLANICI GİRİŞİ                                │
│  (Proje adı, servisler, VM config, app'ler, GitHub org, domain)        │
└────────────────────────────────┬────────────────────────────────────────┘
                                 ↓
┌─────────────────────────────────────────────────────────────────────────┐
│                         INIT KOMUTU                                      │
│                                                                          │
│  Oluşturur:                                                             │
│  • projects/[proje]/project.yml        (kullanıcı girişinden)          │
│  • projects/[proje]/.passwords.yml     (otomatik oluşturulur)          │
│  • projects/[proje]/compose/           (boş dizin)                      │
└────────────────────────────────┬────────────────────────────────────────┘
                                 ↓
┌─────────────────────────────────────────────────────────────────────────┐
│                         UP KOMUTU                                        │
│                                                                          │
│  Terraform Aşaması:                                                     │
│  project.yml → Terraform vars → Cloud API → VM'ler + Network           │
│                                                                          │
│  Ansible Aşaması:                                                       │
│  project.yml + .passwords.yml → Ansible vars → Addon templates →       │
│  → Rendered configs → Docker Compose → Running containers              │
└────────────────────────────────┬────────────────────────────────────────┘
                                 ↓
┌─────────────────────────────────────────────────────────────────────────┐
│                         SYNC KOMUTU                                      │
│                                                                          │
│  Kaynak:                                                                │
│  • superdeploy/.env                                                     │
│  • projects/[proje]/.passwords.yml                                      │
│  • app-repos/[app]/.env (opsiyonel)                                     │
│                                                                          │
│  Hedef:                                                                 │
│  • GitHub Repository Secrets    (altyapı secret'ları)                   │
│  • GitHub Environment Secrets   (runtime secret'ları)                   │
│  • Forgejo Repository Secrets   (deployment secret'ları)                │
└────────────────────────────────┬────────────────────────────────────────┘
                                 ↓
┌─────────────────────────────────────────────────────────────────────────┐
│                         GIT PUSH (Developer)                             │
│                                                                          │
│  app-repos/[app] → GitHub → GitHub Actions                              │
└────────────────────────────────┬────────────────────────────────────────┘
                                 ↓
┌─────────────────────────────────────────────────────────────────────────┐
│                         GITHUB ACTIONS                                   │
│                                                                          │
│  1. .env + .env.superdeploy merge                                       │
│  2. GitHub Secrets enjekte                                              │
│  3. Docker build + registry push                                        │
│  4. Environment şifreleme (AGE)                                         │
│  5. Forgejo'ya push (env.age)                                           │
└────────────────────────────────┬────────────────────────────────────────┘
                                 ↓
┌─────────────────────────────────────────────────────────────────────────┐
│                         FORGEJO RUNNER                                   │
│                                                                          │
│  1. env.age şifre çözme                                                 │
│  2. Docker image pull                                                   │
│  3. Container stop (eski)                                               │
│  4. Container start (yeni)                                              │
│  5. Health check                                                        │
└────────────────────────────────┬────────────────────────────────────────┘
                                 ↓
┌─────────────────────────────────────────────────────────────────────────┐
│                    PRODUCTION CONTAINER (ÇALIŞIYOR)                      │
└─────────────────────────────────────────────────────────────────────────┘
```

### 2. project.yml Parametre Yayılımı

```
project.yml
    │
    ├─→ Terraform
    │   ├─→ vms.core.count          → VM sayısı
    │   ├─→ vms.core.machine_type   → VM tipi
    │   ├─→ vms.core.disk_size      → Disk boyutu
    │   └─→ network.subnet          → Network CIDR
    │
    ├─→ Ansible
    │   ├─→ project                 → Proje adı (container prefix)
    │   ├─→ core_services           → Hangi addon'lar deploy edilecek
    │   ├─→ apps                    → Hangi uygulamalar deploy edilecek
    │   └─→ infrastructure.forgejo  → Forgejo yapılandırması
    │
    └─→ Addon Templates
        ├─→ compose.yml.j2
        │   ├─→ container_name: {{ project }}-{{ addon }}
        │   ├─→ ports: {{ addon_config.port }}
        │   └─→ environment: {{ passwords[addon + '_PASSWORD'] }}
        │
        └─→ env.yml
            ├─→ HOST: {{ project }}-{{ addon }}
            ├─→ PORT: {{ addon_config.port }}
            └─→ PASSWORD: {{ passwords[addon + '_PASSWORD'] }}
```

### 3. Şifre Oluşturma ve Dağıtım Akışı

```
INIT KOMUTU
    ↓
Güvenli Rastgele Şifre Oluşturma
    ↓
.passwords.yml
    ├─→ POSTGRES_PASSWORD: abc123...
    ├─→ REDIS_PASSWORD: def456...
    ├─→ RABBITMQ_PASSWORD: ghi789...
    └─→ AGE_SECRET_KEY: age1...
    │
    ├─→ UP KOMUTU (Ansible)
    │   ├─→ Addon env.yml templates
    │   ├─→ Docker Compose environment
    │   └─→ Container environment variables
    │
    └─→ SYNC KOMUTU
        ├─→ GitHub Environment Secrets
        │   ├─→ POSTGRES_PASSWORD
        │   ├─→ REDIS_PASSWORD
        │   └─→ RABBITMQ_PASSWORD
        │
        └─→ Forgejo Repository Secrets
            ├─→ POSTGRES_PASSWORD
            ├─→ REDIS_PASSWORD
            └─→ RABBITMQ_PASSWORD
            │
            └─→ DEPLOYMENT (Forgejo Runner)
                └─→ Container environment variables
```

### 4. Environment Variable Birleştirme ve Override

```
DEPLOYMENT SIRASINDA:

app-repos/api/.env                    app-repos/api/.env.superdeploy
┌──────────────────────┐              ┌──────────────────────────┐
│ DEBUG=true           │              │ DEBUG=false              │
│ PORT=3000            │              │ POSTGRES_HOST=cheapa-pg  │
│ LOG_LEVEL=debug      │              │ POSTGRES_PORT=5432       │
│ API_KEY=dev-key      │              │ POSTGRES_PASSWORD=***    │
└──────────────────────┘              │ REDIS_HOST=cheapa-redis  │
                                      │ REDIS_PORT=6379          │
                                      └──────────────────────────┘
         │                                      │
         └──────────────┬───────────────────────┘
                        ↓
              GitHub Actions Merge
                        ↓
         ┌──────────────────────────────┐
         │ DEBUG=false          (override)
         │ PORT=3000            (from .env)
         │ LOG_LEVEL=debug      (from .env)
         │ API_KEY=dev-key      (from .env)
         │ POSTGRES_HOST=cheapa-pg  (from .superdeploy)
         │ POSTGRES_PORT=5432       (from .superdeploy)
         │ POSTGRES_PASSWORD=***    (from .superdeploy)
         │ REDIS_HOST=cheapa-redis (from .superdeploy)
         │ REDIS_PORT=6379         (from .superdeploy)
         └──────────────────────────────┘
                        ↓
              GitHub Secrets Enjekte
                        ↓
         ┌──────────────────────────────┐
         │ (yukarıdaki tüm değerler)    │
         │ + JWT_SECRET=***             │
         │ + SECRET_KEY=***             │
         │ + API_TOKEN=***              │
         └──────────────────────────────┘
                        ↓
              AGE Şifreleme
                        ↓
                    env.age
                        ↓
              Forgejo'ya Push
                        ↓
              Forgejo Runner
                        ↓
              AGE Şifre Çözme
                        ↓
         ┌──────────────────────────────┐
         │ Container Environment        │
         │ (tüm değerler plain text)    │
         └──────────────────────────────┘
```

### 5. Sync Komutu - Kaynak ve Hedef Eşleştirmesi

```
KAYNAK DOSYALAR                          HEDEF SİSTEMLER

superdeploy/.env                         GitHub Repository Secrets
├─→ FORGEJO_PAT          ────────────→   ├─→ FORGEJO_PAT
├─→ AGE_PUBLIC_KEY       ────────────→   ├─→ AGE_PUBLIC_KEY
├─→ DOCKER_TOKEN         ────────────→   ├─→ DOCKER_TOKEN
└─→ SSH_PRIVATE_KEY      ────────────→   └─→ SSH_PRIVATE_KEY

projects/cheapa/.passwords.yml           GitHub Environment Secrets
├─→ POSTGRES_PASSWORD    ────────────→   ├─→ POSTGRES_PASSWORD
├─→ REDIS_PASSWORD       ────────────→   ├─→ REDIS_PASSWORD
├─→ RABBITMQ_PASSWORD    ────────────→   ├─→ RABBITMQ_PASSWORD
└─→ SECRET_KEY           ────────────→   └─→ SECRET_KEY

app-repos/api/.env                       Forgejo Repository Secrets
├─→ API_KEY              ────────────→   ├─→ POSTGRES_PASSWORD (from .passwords.yml)
├─→ JWT_SECRET           ────────────→   ├─→ REDIS_PASSWORD (from .passwords.yml)
└─→ CUSTOM_CONFIG        ────────────→   ├─→ RABBITMQ_PASSWORD (from .passwords.yml)
                                         ├─→ SECRET_KEY (from .passwords.yml)
                                         ├─→ API_KEY (from .env)
                                         ├─→ JWT_SECRET (from .env)
                                         └─→ CUSTOM_CONFIG (from .env)
```

### 6. Addon Template'ten Instance'a Dönüşüm

```
TEMPLATE (superdeploy/addons/postgres/)

addon.yml
├─→ name: postgres
├─→ version: 15
└─→ ports: [5432]

compose.yml.j2
├─→ container_name: {{ project }}-postgres
├─→ image: postgres:{{ version }}
├─→ ports: ["{{ port }}:5432"]
└─→ environment:
    ├─→ POSTGRES_USER: {{ user }}
    ├─→ POSTGRES_PASSWORD: {{ password }}
    └─→ POSTGRES_DB: {{ database }}

env.yml
├─→ POSTGRES_HOST: {{ project }}-postgres
├─→ POSTGRES_PORT: {{ port }}
├─→ POSTGRES_USER: {{ user }}
├─→ POSTGRES_PASSWORD: {{ password }}
└─→ POSTGRES_DB: {{ database }}

         │
         │ RENDER WITH:
         │ • project.yml (project: cheapa, port: 5432)
         │ • .passwords.yml (POSTGRES_PASSWORD: abc123)
         │
         ↓

INSTANCE (projects/cheapa/compose/)

docker-compose.core.yml
├─→ container_name: cheapa-postgres
├─→ image: postgres:15
├─→ ports: ["5432:5432"]
└─→ environment:
    ├─→ POSTGRES_USER: cheapa
    ├─→ POSTGRES_PASSWORD: abc123
    └─→ POSTGRES_DB: cheapa

.env (for apps)
├─→ POSTGRES_HOST: cheapa-postgres
├─→ POSTGRES_PORT: 5432
├─→ POSTGRES_USER: cheapa
├─→ POSTGRES_PASSWORD: abc123
└─→ POSTGRES_DB: cheapa
```

### 7. Deployment Sırasında Karar Ağacı

```
Developer: git push
    ↓
GitHub Actions Tetiklendi mi?
    ├─→ Hayır: İşlem yok
    └─→ Evet
        ↓
    Branch doğru mu? (main/production)
        ├─→ Hayır: İşlem yok
        └─→ Evet
            ↓
        .env dosyaları var mı?
            ├─→ Hayır: Hata, deployment dur
            └─→ Evet
                ↓
            Docker build başarılı mı?
                ├─→ Hayır: Hata, deployment dur
                └─→ Evet
                    ↓
                Registry push başarılı mı?
                    ├─→ Hayır: Hata, deployment dur
                    └─→ Evet
                        ↓
                    Şifreleme başarılı mı?
                        ├─→ Hayır: Hata, deployment dur
                        └─→ Evet
                            ↓
                        Forgejo push başarılı mı?
                            ├─→ Hayır: Hata, deployment dur
                            └─→ Evet
                                ↓
                            Forgejo Runner Başladı
                                ↓
                            Şifre çözme başarılı mı?
                                ├─→ Hayır: Hata, deployment dur
                                └─→ Evet
                                    ↓
                                Image pull başarılı mı?
                                    ├─→ Hayır: Hata, deployment dur
                                    └─→ Evet
                                        ↓
                                    Container start başarılı mı?
                                        ├─→ Hayır: Rollback, eski container başlat
                                        └─→ Evet
                                            ↓
                                        Health check başarılı mı?
                                            ├─→ Hayır: Rollback, eski container başlat
                                            └─→ Evet
                                                ↓
                                            DEPLOYMENT BAŞARILI
                                            Eski container temizle
```

---

## Özet: Tüm Sistem Akışı

SuperDeploy, dört ana komut etrafında organize edilmiş bir deployment sistemidir:

1. **init**: Proje yapılandırmasını ve güvenli şifreleri oluşturur
2. **up**: Bulut altyapısını sağlar ve servisleri deploy eder
3. **sync**: Şifreleri GitHub ve Forgejo'ya senkronize eder
4. **git push**: Otomatik deployment pipeline'ını tetikler

### Temel Prensipler

**1. Template-Based Architecture**
- Addon'lar yeniden kullanılabilir template'lerdir
- Her proje, addon'lardan kendi instance'larını oluşturur
- Yapılandırma project.yml'de merkezi olarak yönetilir

**2. Güvenli Şifre Yönetimi**
- Şifreler otomatik oluşturulur, güvenli saklanır
- Asla kod repository'sine commit edilmez
- Transit sırasında şifrelenir (AGE encryption)

**3. Environment Separation**
- Local development (.env) ve production (.env.superdeploy) ayrıdır
- Production değerleri local değerleri override eder
- Developer'ın local ortamı korunur

**4. Otomatik Deployment**
- Git push otomatik olarak deployment tetikler
- Build, şifreleme, deployment tamamen otomatik
- Health check ve rollback mekanizması built-in

**5. Parametre Akışı Şeffaflığı**
- Her parametre nereden geldiği ve nereye gittiği bellidir
- Öncelik sırası açık ve tutarlıdır
- Debugging ve troubleshooting kolaydır

Bu akış, sıfırdan production'a kadar tüm süreci kapsayan, güvenli ve otomatik bir deployment sistemi sağlar.


## 🔄 Resuming Failed Deployments

### Using --start-from Flag

When a deployment fails at a specific addon, you can resume from that point without redeploying previous addons:

```bash
# Scenario: Deployment failed at rabbitmq
superdeploy up cheapa --start-from rabbitmq
```

**What happens:**
1. System validates that `rabbitmq` exists in project configuration
2. Displays deployment plan showing which addons will be skipped
3. Skips all addons before `rabbitmq` (e.g., postgres, redis)
4. Deploys from `rabbitmq` onwards
5. System roles (foundation) always run regardless of --start-from

**Example output:**
```
📋 Deployment Plan
──────────────────────────────────────────────────
  ○ postgres (before rabbitmq)
  ○ redis (before rabbitmq)
  ✓ rabbitmq
  ✓ monitoring
  ✓ caddy
──────────────────────────────────────────────────
Total: 3/5 addons will be deployed
```

### Using --skip Flag

Skip specific addon(s) during deployment:

```bash
# Skip single addon
superdeploy up cheapa --skip monitoring

# Skip multiple addons
superdeploy up cheapa --skip monitoring --skip caddy
```

**Use cases:**
- Temporarily disable optional addons
- Skip problematic addons during testing
- Deploy only specific addons

### Combining Flags

You can combine --start-from and --skip:

```bash
# Start from rabbitmq but skip monitoring
superdeploy up cheapa --start-from rabbitmq --skip monitoring
```

### Common Scenarios

#### 1. Health Check Failure
```bash
# Deployment failed at rabbitmq health check
# Fix: Increase retries in addon.yml
# Resume:
superdeploy up cheapa --start-from rabbitmq
```

#### 2. Configuration Error
```bash
# Deployment failed due to wrong configuration
# Fix: Update project.yml
# Resume from failed addon:
superdeploy up cheapa --start-from <failed-addon>
```

#### 3. Resource Issues
```bash
# Deployment failed due to insufficient memory
# Fix: Increase VM resources or reduce addon memory limits
# Resume:
superdeploy up cheapa --start-from <failed-addon>
```

#### 4. Testing Specific Addon
```bash
# Deploy only specific addon for testing
superdeploy up cheapa --start-from postgres --skip redis --skip rabbitmq
```

### Best Practices

1. **Always check logs first**: Understand why deployment failed
   ```bash
   docker logs <project>-<addon>
   ```

2. **Fix root cause**: Don't just retry without fixing the issue

3. **Use --start-from for transient failures**: Network issues, timeouts

4. **Use --skip for optional addons**: Monitoring, caching during development

5. **Validate configuration**: Run validation before resuming
   ```bash
   superdeploy validate project -p cheapa
   superdeploy validate addons -p cheapa
   ```

### Limitations

- System roles (foundation, docker, security) always run
- Cannot start from middle of an addon (all-or-nothing)
- Skipped addons won't have their dependencies checked
- --start-from validates addon exists in project config
