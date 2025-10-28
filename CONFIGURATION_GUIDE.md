# SuperDeploy Configuration Guide

## 🎯 Quick Start

### Single VM Setup (Current)
```yaml
# project.yml
apps:
  api:
    path: /path/to/api
    vm: core
    port: 8000              # External & Internal port
  
  dashboard:
    path: /path/to/dashboard
    vm: core
    port: 3000              # External & Internal port
  
  services:
    path: /path/to/services
    vm: core
    external_port: 8001     # External port (firewall)
    internal_port: 8000     # Internal container port
```

**Access:**
- Dashboard: `http://IP:3000/`
- API: `http://IP:8000/`
- Services: `http://IP:8001/`

---

## 🔧 Configuration Options

### Option 1: Simple Port (Same External/Internal)
```yaml
apps:
  myapp:
    port: 8000
```
- Container exposes: `8000`
- Firewall opens: `8000`
- Access: `http://IP:8000/`

### Option 2: Different External/Internal Ports
```yaml
apps:
  myapp:
    external_port: 8001
    internal_port: 8000
```
- Container exposes: `8001:8000`
- Firewall opens: `8001`
- Access: `http://IP:8001/`

---

## 🌐 Multi-VM Setup

### Scenario 1: Services on Different VMs
```yaml
vms:
  web:
    count: 1
    machine_type: e2-small
  api:
    count: 1
    machine_type: e2-medium

apps:
  dashboard:
    path: /path/to/dashboard
    vm: web
    port: 3000
  
  api:
    path: /path/to/api
    vm: api
    port: 8000
```

**Result:**
- Dashboard on VM `web-0`: `http://WEB_IP:3000/`
- API on VM `api-0`: `http://API_IP:8000/`

### Scenario 2: Load Balanced (Multiple Instances)
```yaml
vms:
  api:
    count: 3              # 3 VMs
    machine_type: e2-medium

apps:
  api:
    path: /path/to/api
    vm: api
    port: 8000
```

**Result:**
- API on `api-0`: `http://IP1:8000/`
- API on `api-1`: `http://IP2:8000/`
- API on `api-2`: `http://IP3:8000/`

---

## 🔀 Caddy Reverse Proxy (Domain Setup)

### Enable Domain Routing
```yaml
# project.yml
addons:
  caddy:
    version: "2-alpine"
    email: "admin@example.com"
    domain: "myapp.com"      # Your domain

domain: "myapp.com"          # Enable domain mode
```

**Caddy automatically configures:**
- Dashboard: `https://myapp.com/`
- API: `https://myapp.com/api`
- Services: `https://myapp.com/services`

### Caddy Modes

#### Mode 1: IP-Only (No Domain)
```yaml
domain: ""                   # Empty = IP mode
```
- Services expose ports directly
- Access via `IP:PORT`
- Caddy optional

#### Mode 2: Domain (With SSL)
```yaml
domain: "myapp.com"
```
- Caddy handles all routing
- Automatic SSL (Let's Encrypt)
- Path-based routing
- Services don't expose ports

---

## 📝 Common Configurations

### Development (Single VM, No Domain)
```yaml
project: myapp
domain: ""

vms:
  core:
    count: 1
    machine_type: e2-medium

apps:
  api:
    vm: core
    port: 8000
  
  dashboard:
    vm: core
    port: 3000
```

### Production (Multi-VM, With Domain)
```yaml
project: myapp
domain: "myapp.com"

vms:
  web:
    count: 2              # Load balanced
    machine_type: e2-small
  
  api:
    count: 3              # Load balanced
    machine_type: e2-medium
  
  db:
    count: 1
    machine_type: e2-standard-2

apps:
  dashboard:
    vm: web
    port: 3000
  
  api:
    vm: api
    port: 8000
```

---

## 🚀 Deployment Commands

### Fresh Deployment
```bash
# 1. Edit configuration
vim projects/myapp/project.yml

# 2. Generate files
superdeploy generate -p myapp

# 3. Deploy infrastructure
superdeploy up -p myapp

# 4. Deploy apps (from app repos)
git push origin production
```

### Update Configuration
```bash
# 1. Edit project.yml
vim projects/myapp/project.yml

# 2. Regenerate
superdeploy generate -p myapp

# 3. Apply changes
superdeploy up -p myapp
```

---

## 🔍 Port Configuration Examples

### Example 1: Standard Ports
```yaml
apps:
  api:
    port: 8000           # http://IP:8000/
  
  dashboard:
    port: 3000           # http://IP:3000/
  
  admin:
    port: 9000           # http://IP:9000/
```

### Example 2: Custom Port Mapping
```yaml
apps:
  services:
    external_port: 8001  # Firewall opens 8001
    internal_port: 8000  # Container runs on 8000
```

### Example 3: Same Port, Different VMs
```yaml
apps:
  api-v1:
    vm: api-old
    port: 8000           # http://OLD_IP:8000/
  
  api-v2:
    vm: api-new
    port: 8000           # http://NEW_IP:8000/
```

---

## 🛠️ Troubleshooting

### Port Already in Use
```yaml
# Change external port
apps:
  myapp:
    external_port: 8002  # Instead of 8001
    internal_port: 8000
```

### Service Not Accessible
1. Check firewall rules: `gcloud compute firewall-rules list`
2. Check container: `docker ps`
3. Check port mapping: `docker port <container>`

### Caddy Not Working
1. Check domain DNS: `nslookup yourdomain.com`
2. Check Caddy logs: `docker logs <project>-caddy`
3. Verify Caddyfile: `docker exec <project>-caddy cat /etc/caddy/Caddyfile`

---

## 📚 Key Files

- `projects/<project>/project.yml` - Main configuration
- `projects/<project>/compose/docker-compose.core.yml` - Infrastructure
- `projects/<project>/compose/docker-compose.apps.yml` - Applications
- `projects/<project>/addons/caddy/Caddyfile` - Reverse proxy config

---

## ✅ Best Practices

1. **Development**: Use IP mode, single VM
2. **Staging**: Use IP mode, multi-VM
3. **Production**: Use domain mode, multi-VM, load balanced
4. **Port Range**: Use 8000-8999 for apps, 3000-3999 for web
5. **Firewall**: Only open necessary ports
6. **SSL**: Always use domain mode in production
