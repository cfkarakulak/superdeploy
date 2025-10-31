# Security Guide

## Development vs Production

SuperDeploy is configured for **development/debugging by default** to make it easy to inspect services and troubleshoot issues.

### Current Configuration (Development Mode)

The following services are **publicly accessible** for debugging:

- **RabbitMQ Management**: `http://VM_IP:15672` (guest/guest)
- **Grafana**: `http://VM_IP:3000` (admin/password)
- **Prometheus**: `http://VM_IP:9090`
- **Proxy Ports**: 1080, 3128, 8888
- **Proxy Registry**: `http://VM_IP:8080`

⚠️ **This is intentional for development but NOT recommended for production!**

---

## Production Hardening

### 1. Restrict Management Interfaces

Edit `shared/terraform/modules/network/main.tf` and change `source_ranges`:

```hcl
# Before (Development)
source_ranges = ["0.0.0.0/0"]  # Open to internet

# After (Production)
source_ranges = var.admin_source_ranges  # Only admin IPs
```

Apply to these firewall rules:
- `allow_rabbitmq_management` (port 15672)
- `allow_monitoring` (ports 3000, 9090)
- `allow_proxy` (ports 1080, 3128, 8888)
- `allow_proxy_registry` (port 8080)

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

## Security Features (Already Enabled)

✅ **SSH Hardening**
- Root login disabled
- Password authentication disabled
- Only SSH key authentication
- Max 3 authentication attempts

✅ **Fail2Ban**
- Automatic IP banning after 3 failed SSH attempts
- 1 hour ban duration

✅ **UFW Firewall**
- Default deny incoming
- Only explicitly allowed ports open
- Configured per-project

✅ **Automatic Security Updates**
- Unattended upgrades enabled
- Security patches applied automatically

✅ **Sysctl Hardening**
- SYN flood protection
- ICMP redirect disabled
- Source routing disabled

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
