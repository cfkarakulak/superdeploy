# SuperDeploy Dokümantasyonu

SuperDeploy, kendi altyapınızda Heroku benzeri deployment deneyimi sunan self-hosted PaaS platformudur.

## 📚 Dokümantasyon İçeriği

### 🏗️ [ARCHITECTURE.md](./ARCHITECTURE.md)
Sistemin genel mimarisi, bileşenleri ve tasarım kararları:
- Orchestrator pattern (merkezi Forgejo + monitoring)
- Addon-tabanlı mimari
- Template → Instance pattern
- Network izolasyonu
- Güvenlik mimarisi
- VM-specific service filtering
- IP preservation
- Yeni özellikler (2025)

### 🔄 [FLOW.md](./FLOW.md)
İş akışları ve parametre akışları:
- Orchestrator kurulum akışı
- Proje başlatma akışı (init)
- Altyapı sağlama akışı (up)
- Secret senkronizasyon akışı (sync)
- Deployment akışı (git push)
- Parametre akış diyagramları

### 🚀 [SETUP.md](./SETUP.md)
İlk kurulum rehberi (sıfırdan başlangıç):
- Ön gereksinimler
- GCP projesi hazırlığı
- SSH key oluşturma
- Orchestrator kurulumu
- Proje oluşturma
- İlk deployment

### 📊 [OPERATIONS.md](./OPERATIONS.md)
Günlük operasyonlar ve bakım:
- Sistem durumu kontrolü
- Deployment senaryoları
- Logs ve debugging
- Secrets yönetimi
- Database işlemleri
- Container yönetimi
- Monitoring erişimi
- Sorun giderme

### 🎯 [ORCHESTRATOR_SETUP.md](./ORCHESTRATOR_SETUP.md)
Orchestrator VM kurulum ve yönetim rehberi:
- Orchestrator konsepti
- İlk kurulum (bir kere)
- Çoklu proje yapılandırması
- Workflow routing
- Runner yönetimi
- Troubleshooting

### 🔐 [SECURITY.md](./SECURITY.md)
Güvenlik mimarisi ve best practices:
- Development vs Production
- Secret yönetimi
- Network izolasyonu
- Erişim kontrolü
- Production hardening

---

## 🚀 Hızlı Başlangıç

### 1. Orchestrator Kurulumu (Bir Kere)

```bash
# Orchestrator projesi oluştur
superdeploy init -p orchestrator

# Orchestrator'ı deploy et
superdeploy orchestrator up
```

**Sonuç:**
- ✅ Merkezi Forgejo (tüm projeler için)
- ✅ Monitoring (Prometheus + Grafana)
- ✅ Caddy reverse proxy (SSL sertifikaları ile)

### 2. Proje Kurulumu

```bash
# Yeni proje oluştur
superdeploy init -p myproject

# Altyapıyı deploy et
superdeploy up -p myproject

# Secrets'ları sync et
superdeploy sync -p myproject
```

### 3. Uygulama Deployment

```bash
# Kod değişikliği yap
cd app-repos/api
git add .
git commit -m "feat: new feature"

# Production'a push et
git push origin production
```

**Otomatik olur:**
1. GitHub Actions build yapar
2. Orchestrator Forgejo workflow'u alır
3. Project VM runner deploy eder
4. Container çalışır

---

## 🎯 Temel Konseptler

### Orchestrator Pattern

SuperDeploy, merkezi orchestrator VM ve proje-specific VM'ler kullanan hibrit bir mimari kullanır:

```
Orchestrator VM (Global - Tek Seferlik Kurulum)
├── Forgejo (tüm projeler için merkezi Git server + CI/CD)
├── Monitoring (Prometheus + Grafana - tüm projeler için)
└── Caddy (reverse proxy + otomatik SSL sertifikaları)

Project VMs (Her Proje İçin)
├── Infrastructure services (postgres, redis, rabbitmq, vb.)
├── Application containers (api, dashboard, services, vb.)
└── Project-specific Forgejo runners (deployment için)
```

**Avantajlar:**
- Tek Forgejo instance'ı tüm projeler için
- Merkezi monitoring ve metrics
- Otomatik SSL sertifikaları
- Her proje izole VM'lerde çalışır
- IP preservation ile VM restart'ta IP korunur

### Addon-Tabanlı Mimari

Tüm servisler (veritabanları, kuyruklar, proxy'ler) yeniden kullanılabilir addon'lar olarak tanımlanır:

```
addons/
├── postgres/      # PostgreSQL veritabanı
├── redis/         # Redis cache
├── rabbitmq/      # RabbitMQ message queue
├── forgejo/       # Git server + CI/CD (orchestrator'da)
├── caddy/         # Reverse proxy + SSL
├── monitoring/    # Prometheus + Grafana (orchestrator'da)
├── mongodb/       # MongoDB NoSQL
└── elasticsearch/ # Elasticsearch full-text search
```

Her addon şunları içerir:
- **addon.yml**: Metadata (isim, versiyon, kategori, bağımlılıklar)
- **env.yml**: Environment variable şeması (default'lar ve tipler)
- **compose.yml.j2**: Docker Compose template (Jinja2)
- **ansible.yml**: Deployment görevleri (kurulum, health check)

**Kod tabanında hiçbir yerde hardcoded addon isimleri yok!** Tüm addon'lar dinamik olarak keşfedilir ve yüklenir.

### Template → Instance Pattern

Addon'lar yeniden kullanılabilir template'lerdir, her proje kendi instance'larını oluşturur:

```
TEMPLATE (addons/postgres/)
    ↓ (project.yml konfigürasyonu ile)
Jinja2 rendering + VM-specific filtering
    ↓
INSTANCE (myproject-postgres container)
```

**Örnek:**
- Template: `addons/postgres/compose.yml.j2`
- Config: `projects/myproject/project.yml`
- Instance: `myproject-postgres` container (sadece belirtilen VM'lerde)

---

## 🔐 Güvenlik

### Secret Yönetimi

- **Otomatik şifre oluşturma**: Kriptografik olarak güvenli
- **AGE şifreleme**: Transit sırasında şifreleme
- **Ayrı dosyalar**: `.env` (local) ve `.env.superdeploy` (production)
- **GitHub/Forgejo secrets**: Otomatik senkronizasyon

### Network İzolasyonu

- Proje başına Docker network'leri
- VM'lerde firewall kuralları
- Projeler arası iletişim yok

### Erişim Kontrolü

- SSH key-tabanlı VM erişimi
- GitHub PAT ile API erişimi
- Forgejo PAT ile deployment
- Proje başına ayrı credential'lar

---

## 📊 Monitoring

### Global Monitoring (Orchestrator)

Grafana ve Prometheus orchestrator VM'de çalışır ve **tüm projeleri** izler:

- **Prometheus**: Tüm projeleri otomatik keşfeder
- **Grafana**: Pre-configured dashboard'lar
- **Caddy**: Subdomain erişimi (grafana.yourdomain.com)

### Erişim

```bash
# Subdomain ile (SSL)
https://grafana.yourdomain.com
https://prometheus.yourdomain.com

# Direkt IP ile
http://ORCHESTRATOR_IP:3000  # Grafana
http://ORCHESTRATOR_IP:9090  # Prometheus
```

---

## 🛠️ Komutlar

### Orchestrator Komutları

```bash
# Orchestrator kurulumu
superdeploy orchestrator up

# Orchestrator durumu
superdeploy orchestrator status

# Orchestrator SSH
superdeploy orchestrator ssh

# Orchestrator logs
superdeploy orchestrator logs -s forgejo

# Selective addon deployment
superdeploy orchestrator up --addon caddy
```

### Proje Komutları

```bash
# Proje oluştur (interaktif wizard)
superdeploy init -p myproject

# Altyapı deploy et (Terraform + Ansible)
superdeploy up -p myproject

# Secrets sync et (GitHub + Forgejo)
superdeploy sync -p myproject

# Durum kontrol et
superdeploy status -p myproject

# Logs (real-time)
superdeploy logs -p myproject -a api --follow

# SSH ile VM'ye bağlan
superdeploy ssh -p myproject

# Selective addon deployment (sadece belirli addon'lar)
superdeploy up -p myproject --addon postgres

# IP adresi korumalı deployment
superdeploy up -p myproject --preserve-ip

# Altyapıyı sil
superdeploy destroy -p myproject
```

---

## 🆕 Yeni Özellikler (2025)

1. **Orchestrator Mimarisi**: Merkezi Forgejo ve monitoring (tek seferlik kurulum)
2. **Caddy Reverse Proxy**: Subdomain-based routing + otomatik SSL (Let's Encrypt)
3. **Merkezi Monitoring**: Prometheus + Grafana tüm projeler için
4. **VM-Specific Service Filtering**: Her VM sadece ihtiyacı olan addon'ları çalıştırır
5. **IP Preservation**: VM restart'ta statik IP adresleri korunur (`preserve_ip: true`)
6. **Selective Addon Deployment**: `--addon` flag ile belirli addon'ları deploy et
7. **GitHub Actions → Forgejo Integration**: Düzeltilmiş API endpoint'leri ve workflow dispatch
8. **Otomatik Subnet Allocation**: Projeler için otomatik VPC ve Docker subnet tahsisi
9. **Dynamic Addon Discovery**: Kod tabanında hardcoded addon isimleri yok
10. **Environment Aliases**: App'ler için soyutlama katmanı (DB_HOST → POSTGRES_HOST)

---

## 📖 Detaylı Dokümantasyon

Her konuyla ilgili detaylı bilgi için ilgili dokümantasyon dosyasına bakın:

- **Mimari anlayışı için**: [ARCHITECTURE.md](./ARCHITECTURE.md)
- **İş akışlarını anlamak için**: [FLOW.md](./FLOW.md)
- **İlk kurulum için**: [SETUP.md](./SETUP.md)
- **Günlük kullanım için**: [OPERATIONS.md](./OPERATIONS.md)
- **Orchestrator kurulumu için**: [ORCHESTRATOR_SETUP.md](./ORCHESTRATOR_SETUP.md)
- **Runner mimarisi için**: [RUNNER_ARCHITECTURE.md](./RUNNER_ARCHITECTURE.md)

---

## 🤝 Katkıda Bulunma

SuperDeploy açık kaynak bir projedir. Katkılarınızı bekliyoruz!

---

## 📝 Lisans

MIT License

---

**Yardıma mı ihtiyacın var?**
- GitHub Issues: https://github.com/cfkarakulak/superdeploy/issues
