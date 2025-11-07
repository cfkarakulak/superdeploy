# Orchestrator VM Kurulum Rehberi

## 🎯 Konsept

**Orchestrator VM:** Tüm projeler için tek bir Forgejo instance'ı, merkezi monitoring (Prometheus + Grafana) ve reverse proxy (Caddy) çalıştıran global VM.

**Tek Seferlik Kurulum:** Orchestrator bir kere kurulur, tüm projeler bu merkezi altyapıyı kullanır.

## 📋 İlk Kurulum (Bir Kere)

### 1. Orchestrator Config Oluştur

```bash
superdeploy orchestrator:init
```

**Bu komut:**
- İnteraktif wizard ile orchestrator config'i oluşturur
- GCP project ID, region, zone ayarlarını alır
- SSL email ve admin credentials'ı toplar
- Domain bilgilerini alır (opsiyonel)
- `shared/orchestrator/config.yml` dosyasını oluşturur

### 2. Orchestrator config.yml (Otomatik Oluşturulur)

```yaml
project: orchestrator
description: Global Forgejo orchestrator for all projects

cloud:
  gcp:
    project_id: "your-gcp-project"
    region: "us-central1"
    zone: "us-central1-a"

vms:
  orchestrator:  # ← FIXED İSİM
    count: 1
    machine_type: e2-medium
    disk_size: 50
    preserve_ip: true  # IP korunur
    services:
      - forgejo
      - monitoring
      - caddy

addons:
  forgejo:
    version: "1.21.0"
    port: 3001
    ssh_port: 2222
    admin_user: "admin"
    admin_email: "admin@yourdomain.com"
    org: "myorg"
    repo: "superdeploy"
  
  monitoring:
    prometheus_port: 9090
    grafana_port: 3000
  
  caddy:
    domain: "yourdomain.com"
    email: "admin@yourdomain.com"
    subdomains:
      forgejo: "forgejo"
      grafana: "grafana"
      prometheus: "prometheus"

apps: {}  # Orchestrator'da app yok
```

### 3. Deploy Orchestrator

```bash
superdeploy orchestrator:up
```

**Bu komut şunları yapar:**
- ✅ Orchestrator VM oluşturur (e2-medium, 50GB, statik IP ile)
- ✅ Forgejo + PostgreSQL kurar (tüm projeler için)
- ✅ Prometheus + Grafana kurar (merkezi monitoring)
- ✅ Caddy reverse proxy kurar (SSL + subdomain routing)
- ✅ Orchestrator runner kurar (workflow routing için)
- ✅ Admin user ve organization otomatik oluşturur
- ✅ Pre-configured Grafana dashboard'ları yükler

**Süre:** ~8-10 dakika

### 4. Orchestrator IP'sini Kaydet

Deployment sonunda IP adresi ve credentials ekranda gösterilir:

```
✅ Orchestrator Deployed!
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📍 Orchestrator IP: 34.72.179.175

🔐 Access Credentials:
🌐 Forgejo (Git Server):
   URL: http://34.72.179.175:3001
   Username: admin
   Password: [otomatik oluşturulan şifre]

📊 Grafana (Monitoring):
   URL: http://34.72.179.175:3000
   Username: admin
   Password: [otomatik oluşturulan şifre]

📈 Prometheus (Metrics):
   URL: http://34.72.179.175:9090
```

IP adresi ve şifreler `shared/orchestrator/.env` dosyasında saklanır.

## 📦 Diğer Projeler (Her Proje İçin)

### 1. Proje Oluştur

```bash
superdeploy init -p cheapa
```

### 2. Project.yml (Orchestrator Referansı)

```yaml
project: cheapa

# Orchestrator referansı
orchestrator:
  host: "34.72.179.175"  # Orchestrator VM IP
  port: 3001
  org: "myorg"
  repo: "superdeploy"

cloud:
  gcp:
    project_id: "your-gcp-project"
    region: "us-central1"
    zone: "us-central1-a"

vms:
  web:
    count: 1
    machine_type: e2-small
    services: []
  
  api:
    count: 1
    machine_type: e2-small
    services: []

addons: {}  # Forgejo yok, orchestrator kullanacak

apps:
  api:
    path: /path/to/api
    vm: api
    port: 8000
  dashboard:
    path: /path/to/dashboard
    vm: web
    port: 3000
```

### 3. Deploy Project

```bash
superdeploy cheapa:up
```

**Bu şunları yapar:**
- ✅ `cheapa-web-0`, `cheapa-api-0` VM'leri oluşturur
- ✅ Her VM'de project-specific runner kurar
- ✅ Runner'ları orchestrator Forgejo'ya register eder
- ✅ Forgejo'ya **DOKUNMAZ** (zaten var)

## 🔄 Workflow

### Orchestrator'da

```yaml
# .forgejo/workflows/deploy.yml
jobs:
  deploy:
    runs-on: [self-hosted, "${{ inputs.project }}"]
```

### GitHub Actions'da

```yaml
# .github/workflows/deploy.yml
- name: Trigger Forgejo deployment
  env:
    FORGEJO_BASE_URL: "http://34.72.179.175:3001"  # Orchestrator IP
    FORGEJO_PAT: ${{ secrets.FORGEJO_PAT }}
  run: |
    curl -X POST \
      -H "Authorization: token $FORGEJO_PAT" \
      "$FORGEJO_BASE_URL/api/v1/repos/myorg/superdeploy/actions/workflows/deploy.yml/dispatches" \
      -d '{"ref":"master","inputs":{"project":"cheapa","service":"api",...}}'
```

## 🎯 Çoklu Proje Örneği

### Orchestrator (Bir Kere)

```bash
superdeploy orchestrator:up
```

**Sonuç:**
- VM: `orchestrator` (34.72.179.175)
- Forgejo: https://forgejo.yourdomain.com (veya http://34.72.179.175:3001)
- Grafana: https://grafana.yourdomain.com (veya http://34.72.179.175:3000)
- Prometheus: https://prometheus.yourdomain.com (veya http://34.72.179.175:9090)
- Runner: `orchestrator-runner`

### Proje 1: cheapa

```bash
superdeploy cheapa:up
```

**Sonuç:**
- VM'ler: `cheapa-web-0`, `cheapa-api-0`
- Runner'lar: `cheapa-web-*`, `cheapa-api-*`
- Forgejo: Orchestrator'ı kullanır

### Proje 2: myapp

```bash
superdeploy myapp:up
```

**Sonuç:**
- VM'ler: `myapp-app-0`, `myapp-worker-0`
- Runner'lar: `myapp-app-*`, `myapp-worker-*`
- Forgejo: Orchestrator'ı kullanır

### Proje 3: acme

```bash
superdeploy acme:up
```

**Sonuç:**
- VM'ler: `acme-frontend-0`, `acme-backend-0`
- Runner'lar: `acme-frontend-*`, `acme-backend-*`
- Forgejo: Orchestrator'ı kullanır

## 📊 Final Mimari

```
┌─────────────────────────────────────────────┐
│  Orchestrator VM (34.72.179.175)           │
│  ┌─────────────────────────────────────┐   │
│  │  Forgejo (Port 3001)                │   │
│  │  - myorg/superdeploy repo           │   │
│  │  - Workflows for all projects       │   │
│  │  - forgejo.yourdomain.com (SSL)     │   │
│  └─────────────────────────────────────┘   │
│  ┌─────────────────────────────────────┐   │
│  │  Monitoring                         │   │
│  │  - Prometheus (Port 9090)           │   │
│  │  - Grafana (Port 3000)              │   │
│  │  - prometheus.yourdomain.com (SSL)  │   │
│  │  - grafana.yourdomain.com (SSL)     │   │
│  └─────────────────────────────────────┘   │
│  ┌─────────────────────────────────────┐   │
│  │  Caddy (Ports 80, 443)              │   │
│  │  - Reverse proxy                    │   │
│  │  - Automatic SSL certificates       │   │
│  └─────────────────────────────────────┘   │
│  ┌─────────────────────────────────────┐   │
│  │  orchestrator-runner                │   │
│  │  Labels: [orchestrator]             │   │
│  └─────────────────────────────────────┘   │
└─────────────────────────────────────────────┘
         │
         ├──────────────┬──────────────┬──────────────┐
         ▼              ▼              ▼              ▼
┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐
│ cheapa VMs  │  │ myapp VMs   │  │ acme VMs    │  │ ...         │
│ - web       │  │ - app       │  │ - frontend  │  │             │
│ - api       │  │ - worker    │  │ - backend   │  │             │
│             │  │             │  │             │  │             │
│ Runners:    │  │ Runners:    │  │ Runners:    │  │             │
│ cheapa-*    │  │ myapp-*     │  │ acme-*      │  │             │
└─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘
```

## ✅ Avantajlar

1. **Tek Forgejo:** Tüm projeler için merkezi yönetim
2. **Merkezi Monitoring:** Tüm projeler için tek Prometheus + Grafana
3. **SSL Sertifikaları:** Caddy ile otomatik Let's Encrypt sertifikaları
4. **Subdomain Routing:** Her servis için ayrı subdomain
5. **İzolasyon:** Her proje kendi VM'lerinde çalışır
6. **Ölçeklenebilir:** Yeni proje = sadece yeni VM'ler
7. **Maliyet:** Forgejo ve monitoring için tek VM yeterli
8. **Bakım:** Forgejo ve monitoring güncellemesi tek yerde
9. **IP Preservation:** VM restart'ta IP korunur

## 🔧 Bakım

### Orchestrator Güncelleme

```bash
# Orchestrator'ı güncelle
superdeploy orchestrator:up --tags addons

# Diğer projelere dokunmaz
```

### Yeni Proje Ekleme

```bash
# Sadece yeni proje VM'lerini oluştur
superdeploy newproject:up

# Orchestrator'a dokunmaz
```

### Runner Yeniden Kaydetme

```bash
# Bir projenin runner'larını yeniden kaydet
superdeploy cheapa:up --tags runner
```

## 🚨 Önemli Notlar

1. **Orchestrator IP:** Tüm projelerde aynı IP kullanılmalı
2. **Forgejo Org/Repo:** Tüm projelerde aynı olmalı
3. **İlk Kurulum:** Orchestrator mutlaka ilk kurulmalı
4. **DNS Kayıtları:** Subdomain'ler için A kayıtları gerekli
5. **SSL Sertifikaları:** DNS propagation sonrası otomatik oluşur
6. **Backup:** Orchestrator VM'i düzenli yedeklenmeli
7. **Network:** Tüm VM'ler aynı VPC'de olmalı
8. **IP Preservation:** preserve_ip: true ile IP korunur

## 📝 Troubleshooting

### Runner Orchestrator'a Bağlanamıyor

```bash
# Orchestrator IP'sini kontrol et
ping 34.72.179.175

# Firewall kurallarını kontrol et
gcloud compute firewall-rules list

# Runner log'larını kontrol et
sudo journalctl -u forgejo-runner -f
```

### Forgejo Erişilemiyor

```bash
# Orchestrator VM'de Forgejo durumunu kontrol et
ssh orchestrator
docker ps | grep forgejo
docker logs orchestrator-forgejo
```

### Yeni Proje Runner'ı Görünmüyor

```bash
# Forgejo UI'da kontrol et
http://34.72.179.175:3001/admin/actions/runners

# Runner registration token'ı yenile
ssh orchestrator
docker exec -u 1000:1000 orchestrator-forgejo forgejo actions generate-runner-token
```
