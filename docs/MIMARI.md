# 🏗️ SuperDeploy Mimarisi

## Genel Bakış

SuperDeploy, Heroku benzeri bir self-hosted PaaS çözümüdür. Kendi sunucularınızda çalışır ve modern uygulama deployment'ı için gerekli tüm araçları sunar.

## Temel Bileşenler

### 1. Infrastructure Katmanı (Terraform)

**Ne yapar:**
- GCP üzerinde VM'leri otomatik oluşturur
- Network ayarlarını yapar
- Firewall kurallarını belirler
- SSH anahtarlarını dağıtır

**Neden önemli:**
Terraform sayesinde tüm altyapınız kod olarak saklanır. VM silseniz bile tek komutla tekrar oluşturabilirsiniz.

### 2. Konfigürasyon Katmanı (Ansible)

**Ne yapar:**
- VM'lere Docker kurar
- Forgejo (Git server) kurar ve yapılandırır
- Forgejo Actions runner'ı ayağa kaldırır
- Sistem güvenliği için gerekli paketleri kurar
- Database, queue ve diğer servisleri hazırlar

**Neden önemli:**
Manuel kurulum yerine, her şey otomatik olarak doğru şekilde kurulur. Aynı konfigürasyon her zaman aynı sonucu verir.

### 3. CI/CD Katmanı

SuperDeploy iki seviyeli CI/CD kullanır:

#### **GitHub Actions (Build & Push)**
- Uygulama kodunuzu build eder
- Docker image oluşturur
- Image'ı Docker Hub'a push eder
- Environment variable'ları AGE encryption ile şifreler
- Forgejo'yu tetikler

#### **Forgejo Actions (Deploy)**
- GitHub'dan gelen şifreli environment variable'ları açar
- Docker image'ı VM'e çeker
- Zero-downtime deployment yapar
- Health check yapar
- Email notification gönderir

**Neden iki seviye:**
GitHub Actions herkese açık, hızlı ve güvenilir. Build işlemleri burada yapılır. Forgejo ise kendi sunucunuzda çalışır ve production environment'a direk erişimi vardır. Deploy işlemleri güvenle burada yapılır.

### 4. Runtime Katmanı (Docker Compose)

**Servisler:**
- **PostgreSQL**: Ana veritabanı
- **RabbitMQ**: Message queue
- **Redis**: Cache ve session storage
- **API**: Backend servisiniz
- **Dashboard**: Frontend uygulamanız
- **Services**: Background worker'lar (Celery vb.)
- **Caddy**: Reverse proxy (otomatik HTTPS)

**Docker Compose'un Avantajları:**
Her servis izole bir container'da çalışır. Bir servis çöktüğünde diğerlerini etkilemez. Restart politikaları sayesinde otomatik toparlanır.

## Veri Akışı

### İlk Kurulum:
```
Developer → .env dosyası hazırlar
         ↓
      superdeploy init (interaktif setup)
         ↓
      superdeploy up (Terraform + Ansible)
         ↓
      VM'ler hazır, Forgejo çalışıyor
         ↓
      superdeploy sync (GitHub secrets otomatik set edilir)
         ↓
      Sistem hazır!
```

### Normal Deploy:
```
Developer → git push origin production
         ↓
   GitHub Actions → Docker build + push
         ↓
   Environment variable'ları şifreler
         ↓
   Forgejo API'sini tetikler
         ↓
   Forgejo Runner → Şifreyi açar
         ↓
   docker compose up -d (zero-downtime)
         ↓
   Health check → Email notification
         ↓
   Deploy tamamlandı!
```

### Rollback:
```
Developer → superdeploy rollback -a api v41
         ↓
   Forgejo API'sine rollback isteği gönderir
         ↓
   Eski image tag'i ile yeniden deploy
         ↓
   Hızlı geri dönüş!
```

## Güvenlik Katmanları

### 1. Network Güvenliği
- SSH sadece belirlenen IP'lerden
- Firewall kuralları Terraform ile yönetilir
- Internal servisler (DB, Queue) sadece internal network'te

### 2. Secret Management
- Environment variable'lar asla Git'e push edilmez
- GitHub Secrets → AGE encryption → Forgejo Runner
- Şifreli transfer, deployment sonrası güvenli silme

### 3. SSH Key Management
- Passphrase-free deploy key (sadece deployment için)
- Ayrı bir key ile VM'lere manuel erişim
- Key'ler asla kod repository'sinde saklanmaz

### 4. Container Isolation
- Her servis kendi container'ında
- User permissions (non-root)
- Resource limits (CPU, Memory)

## Ölçeklenebilirlik

### Yatay Ölçekleme (Horizontal Scaling)
`superdeploy scale api=3` komutu ile aynı servisten birden fazla container çalıştırabilirsiniz. Load balancer (Caddy) istekleri otomatik dağıtır.

### Dikey Ölçekleme (Vertical Scaling)
`.env` dosyasında `VM_MACHINE_TYPE` değiştirerek daha güçlü VM'ler kullanabilirsiniz. Terraform yeniden çalıştırıldığında VM'ler upgrade edilir.

### Multi-Region Deployment
Her region için ayrı `.env` dosyası kullanarak farklı GCP region'larına deploy edebilirsiniz. DNS ayarları ile traffic yönlendirmesi yaparsınız.

## Monitoring & Logging

### Container Logs
Her container'ın logları Docker tarafından yönetilir:
```bash
superdeploy logs -a api          # Son 100 satır
superdeploy logs -a api -f       # Canlı takip
```

### Health Checks
Docker Compose health check'leri sayesinde servisler otomatik izlenir. Unhealthy container'lar restart edilir.

### Deployment Notifications
Her deployment sonunda email notification gönderilir:
- Deploy durumu (başarılı/başarısız)
- Hangi servisler deploy edildi
- Image tag'leri
- Erişim URL'leri

## Disaster Recovery

### VM Kaybolursa:
1. `.env` dosyanız varsa tek komut yeterli: `superdeploy up`
2. Terraform infrastructure'ı yeniden oluşturur
3. Ansible her şeyi yeniden konfigure eder
4. `superdeploy sync` ile GitHub secrets güncellenir
5. Normal deployment devam eder

### Database Backup:
PostgreSQL container'ı `/var/lib/postgresql/data` volume'unu kullanır. Bu volume GCP disk'te saklanır. Düzenli snapshot'lar alınmalıdır (manuel veya GCP Cloud Scheduler ile otomatik).

### Secrets Yedekleme:
`.env` dosyanız güvenli bir yerde saklanmalıdır (LastPass, 1Password, encrypted Git repo). Bu dosya olmadan sistemi yeniden kurmak zordur.

## Performans Optimizasyonları

### Docker Layer Caching
Multi-stage build kullanılır. Dependencies layer'ı cache'lenir, kod değişikliklerinde sadece son layer yeniden build edilir.

### Zero-Downtime Deployment
`docker compose up -d` kullanılır. Yeni container ayağa kalkarken eski container çalışmaya devam eder. Health check başarılı olunca eski container kapatılır.

### Resource Management
Her container için resource limit tanımlanır:
- CPU limit: Container CPU'yu tüketemez
- Memory limit: OOM durumunda sadece o container restart olur
- Restart policy: `unless-stopped` ile otomatik toparlanma

## Gelecek Geliştirmeler

### Planlanan Özellikler:
- **Kubernetes Desteği**: Daha büyük ölçekler için
- **Grafana Dashboard**: Görsel monitoring
- **Automated Backups**: GCS entegrasyonu
- **SSL/TLS**: Let's Encrypt otomasyonu
- **Blue-Green Deployment**: Tam sıfır downtime
- **Canary Releases**: Kademeli yayına alma

---

**Sonuç:**
SuperDeploy, modern uygulama deployment'ının tüm karmaşıklığını CLI komutlarına sığdırır. Infrastructure as Code, GitOps, Container Orchestration gibi best practice'leri kullanır ve Heroku'nun basitliğini kendi sunucunuzda sunar.

