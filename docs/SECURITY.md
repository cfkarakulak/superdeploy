# Güvenlik Rehberi

## Development vs Production

SuperDeploy varsayılan olarak **development/debugging** modunda yapılandırılmıştır. Bu sayede servisleri incelemek ve sorunları gidermek kolaydır.

### Mevcut Yapılandırma (Development Modu)

Aşağıdaki servisler **herkese açık** şekilde erişilebilir (debugging için):

- **RabbitMQ Management**: `http://VM_IP:15672` (guest/guest)
- **Grafana**: `http://ORCHESTRATOR_IP:3000` (admin/otomatik şifre)
- **Prometheus**: `http://ORCHESTRATOR_IP:9090`
- **Forgejo**: `http://ORCHESTRATOR_IP:3001` (admin/otomatik şifre)

⚠️ **Bu development için kasıtlıdır ancak production için ÖNERİLMEZ!**

**Production için:**
- Caddy reverse proxy ile HTTPS kullan
- Subdomain'ler ile erişim (grafana.domain.com, forgejo.domain.com)
- Firewall kurallarını sıkılaştır

---

## Production Hardening (Sıkılaştırma)

### 1. Management Interface'leri Kısıtla

`shared/terraform/modules/network/main.tf` dosyasını düzenle ve `source_ranges`'ı değiştir:

```hcl
# Önce (Development)
source_ranges = ["0.0.0.0/0"]  # Internet'e açık

# Sonra (Production)
source_ranges = var.admin_source_ranges  # Sadece admin IP'leri
```

Bu firewall kurallarına uygula:
- `allow_rabbitmq_management` (port 15672)
- `allow_monitoring` (ports 3000, 9090) - Orchestrator için
- `allow_forgejo` (port 3001) - Orchestrator için

### 2. Configure Admin IP Ranges

Add your admin IPs to `terraform.tfvars`:

```hcl
admin_source_ranges = [
  "YOUR_OFFICE_IP/32",
  "YOUR_HOME_IP/32",
  "YOUR_VPN_IP/32"
]
```

### 3. Use SSH Tunnels

For secure access without opening ports:

```bash
# RabbitMQ Management
ssh -L 15672:localhost:15672 superdeploy@VM_IP
# Access: http://localhost:15672

# Grafana
ssh -L 3000:localhost:3000 superdeploy@VM_IP
# Access: http://localhost:3000

# Prometheus
ssh -L 9090:localhost:9090 superdeploy@VM_IP
# Access: http://localhost:9090
```

### 4. Bind Docker Ports to Localhost

Edit addon compose files to bind only to localhost:

```yaml
# Before (accessible from network)
ports:
  - "5432:5432"

# After (localhost only)
ports:
  - "127.0.0.1:5432:5432"
```

---

## Güvenlik Özellikleri (Zaten Aktif)

✅ **SSH Hardening**
- Root login devre dışı
- Şifre authentication devre dışı
- Sadece SSH key authentication
- Maksimum 3 authentication denemesi

✅ **Fail2Ban**
- 3 başarısız SSH denemesinden sonra otomatik IP ban
- 1 saat ban süresi

✅ **UFW Firewall**
- Varsayılan olarak tüm gelen trafiği engelle
- Sadece açıkça izin verilen portlar açık
- Her proje için yapılandırılmış

✅ **Otomatik Güvenlik Güncellemeleri**
- Unattended upgrades aktif
- Güvenlik yamaları otomatik uygulanır

✅ **Sysctl Hardening**
- SYN flood koruması
- ICMP redirect devre dışı
- Source routing devre dışı

✅ **Secret Encryption**
- AGE public key encryption
- Secret'lar transit sırasında şifrelenir
- Forgejo'da asla plaintext olarak saklanmaz

✅ **Network İzolasyonu**
- Her proje kendi Docker network'üne sahip
- Projeler arası iletişim yok
- VM'ler arası izolasyon

---

## Monitoring Security

### Change Default Passwords

**Grafana:**
```bash
# Set in shared/orchestrator/.env
GRAFANA_ADMIN_PASSWORD=your-strong-password
```

**RabbitMQ:**
```bash
# Set in projects/{project}/.env
RABBITMQ_PASSWORD=your-strong-password
```

### Enable HTTPS

Use Caddy for automatic HTTPS:

```yaml
# project.yml
apps:
  api:
    domain: "api.yourdomain.com"  # Caddy will auto-provision SSL
```

---

## Security Checklist

### Development
- [ ] Strong passwords for all services
- [ ] SSH keys configured
- [ ] Fail2Ban active

### Production
- [ ] Restrict management interfaces to admin IPs
- [ ] Use SSH tunnels for debugging
- [ ] Bind Docker ports to localhost
- [ ] Enable HTTPS with real domains
- [ ] Regular security updates
- [ ] Monitor access logs

---

## Getting Your IP

```bash
# Your current public IP
curl ifconfig.me

# Add to admin_source_ranges
echo "$(curl -s ifconfig.me)/32"
```

---

## Questions?

- Development: Keep current config, it's fine for testing
- Production: Follow hardening steps above
- Need help? Check logs: `journalctl -u fail2ban -f`
