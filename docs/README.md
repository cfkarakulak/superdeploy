# SuperDeploy Documentation

SuperDeploy, kendi altyapınızda Heroku benzeri deployment deneyimi sunan self-hosted PaaS platformudur.

## 📚 Dokümantasyon İçeriği

### 🏗️ [ARCHITECTURE.md](./ARCHITECTURE.md)
Sistemin genel mimarisi, bileşenleri ve tasarım kararları:
- Orchestrator pattern (merkezi Forgejo + monitoring)
- Addon-tabanlı mimari
- Template → Instance pattern
- Network izolasyonu
- Güvenlik mimarisi
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

### 🏃 [RUNNER_ARCHITECTURE.md](./RUNNER_ARCHITECTURE.md)
Forgejo runner mimarisi ve kullanımı:
- Runner tipleri (orchestrator vs project-specific)
- Label stratejisi
- Workflow kullanımı
- Runner registration
- Configuration dosyaları
- Güvenlik considerations
- Best practices

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
Orchestrator VM (Global)
├── Forgejo (tüm projeler için)
├── Monitoring (Prometheus + Grafana)
└── Caddy (reverse proxy + SSL)

Project VMs (Proje-specific)
├── Infrastructure services (postgres, redis, rabbitmq)
├── Application containers
└── Forgejo runners (deployment için)
```

### Addon-Tabanlı Mimari

Tüm servisler (veritabanları, kuyruklar, proxy'ler) addon olarak tanımlanır:

```
addons/
├── postgres/      # PostgreSQL
├── redis/         # Redis
├── rabbitmq/      # RabbitMQ
├── forgejo/       # Git server + CI/CD
├── caddy/         # Reverse proxy + SSL
└── monitoring/    # Prometheus + Grafana
```

Her addon:
- **addon.yml**: Metadata
- **env.yml**: Environment variable şeması
- **compose.yml.j2**: Docker Compose template
- **ansible.yml**: Deployment görevleri

### Template → Instance Pattern

Addon'lar template'dir, her proje kendi instance'larını oluşturur:

```
Template (addons/postgres/)
    ↓
project.yml konfigürasyonu
    ↓
Jinja2 rendering
    ↓
Instance (myproject-postgres container)
```

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
# Proje oluştur
superdeploy init -p myproject

# Altyapı deploy et
superdeploy up -p myproject

# Secrets sync et
superdeploy sync -p myproject

# Durum kontrol et
superdeploy status -p myproject

# Logs
superdeploy logs -p myproject -a api

# SSH
superdeploy ssh -p myproject

# Selective addon deployment
superdeploy up -p myproject --addon postgres

# Altyapıyı sil
superdeploy destroy -p myproject
```

---

## 🆕 Yeni Özellikler (2025)

1. **Orchestrator Mimarisi**: Merkezi Forgejo ve monitoring
2. **Caddy Reverse Proxy**: Subdomain-based routing + otomatik SSL
3. **Merkezi Monitoring**: Prometheus + Grafana tüm projeler için
4. **VM-Specific Service Filtering**: Sadece ilgili addon'lar deploy edilir
5. **IP Preservation**: VM restart'ta IP adresleri korunur
6. **Selective Addon Deployment**: `--addon` flag ile belirli addon'ları deploy et
7. **GitHub Actions → Forgejo Integration**: Düzeltilmiş API endpoint'leri

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
