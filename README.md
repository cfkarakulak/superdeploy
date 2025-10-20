# 🚀 SuperDeploy - Full-Auto Multi-VM Deployment System

**Deploy a complete production system in 6 minutes with 2 commands!**

```bash
make init    # Create .env
make deploy  # Deploy everything!
```

---

## ⚡ Quick Start

```bash
# 1. Clone & Setup
cd superdeploy
make init
nano .env  # Fill GCP_PROJECT_ID + passwords

# 2. Deploy!
make deploy

# 🎉 Done! System ready in ~6 minutes
```

---

## 📋 What Gets Deployed?

### 🖥️ **3 VMs on GCP**
- **CORE VM**: Forgejo (Git+CI/CD), API, PostgreSQL, RabbitMQ, Dashboard, Caddy
- **SCRAPE VM**: Playwright workers, scraping engine
- **PROXY VM**: SOCKS5 + HTTP proxies, IP rotation

### 🔧 **Services**
- **Forgejo**: Self-hosted Git with Actions (NO WIZARD!)
- **API**: FastAPI backend
- **PostgreSQL**: Database
- **RabbitMQ**: Message queue
- **Dashboard**: Web UI
- **Caddy**: Reverse proxy
- **Workers**: Playwright-based scrapers
- **Proxies**: SOCKS5 + HTTP with auto-rotation

### 🤖 **Full Automation**
- ✅ Terraform → Creates VMs
- ✅ Ansible → Installs everything
- ✅ Forgejo → Auto-setup (admin, repo, runner)
- ✅ CI/CD → Workflows auto-deploy apps
- ✅ Single `.env` → Controls everything

---

## 📖 Documentation

- **[SETUP.md](SETUP.md)**: Complete installation guide
- **[ENV.example](ENV.example)**: Configuration template
- **[Makefile](Makefile)**: All automation commands

---

## 🎯 Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      GCP Infrastructure                     │
└─────────────────────────────────────────────────────────────┘

┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│   CORE VM       │  │  SCRAPE VM      │  │  PROXY VM       │
│  34.56.43.99    │  │ 34.67.236.167   │  │ 34.173.11.246   │
├─────────────────┤  ├─────────────────┤  ├─────────────────┤
│ • Forgejo       │  │ • Playwright    │  │ • SOCKS5 :1080  │
│ • API :8000     │  │ • Workers       │  │ • HTTP :3128    │
│ • Registry :8080│  │ • Scraper       │  │ • IP Rotation   │
│ • Dashboard     │  │                 │  │ • Monitoring    │
│ • PostgreSQL    │  │                 │  │                 │
│ • RabbitMQ      │  │                 │  │                 │
│ • Caddy         │  │                 │  │                 │
└─────────────────┘  └─────────────────┘  └─────────────────┘
       ↓                    ↓                     ↓
       └────────────────────┴─────────────────────┘
                     Private Network
                      10.0.0.0/24
```

---

## 🛠️ Makefile Commands

```bash
make help          # Show all commands
make init          # Create .env from ENV.example
make check-env     # Validate .env configuration
make deploy        # 🚀 Full deployment (one command!)
make update-ips    # Extract IPs from Terraform → update .env
make terraform-init    # Initialize Terraform
make terraform-apply   # Create VMs
make ansible-deploy    # Deploy with Ansible
make git-push      # Push code to Forgejo
make test          # Test all services
make destroy       # Destroy all infrastructure
make clean         # Clean temporary files
```

---

## 📂 Project Structure

```
superdeploy/
├── Makefile                    # ⭐ Full automation
├── SETUP.md                   # ⭐ Installation guide
├── README.md                  # ⭐ This file
├── ENV.example                # ⭐ Config template
├── .env                       # ⭐ Live config (gitignored)
├── deploy/
│   └── compose/
│       ├── vm1-core/         # Core services compose
│       ├── vm2-scrape/       # Scrape workers compose
│       └── vm3-proxy/        # Proxy servers compose
└── .forgejo/
    └── workflows/
        ├── deploy-core.yml   # Core VM deployment
        ├── deploy-scrape.yml # Scrape VM deployment
        └── deploy-proxy.yml  # Proxy VM deployment

superdeploy-infra/
├── terraform-wrapper.sh       # ⭐ .env → Terraform bridge
├── main.tf                   # Terraform main config
├── modules/                  # Terraform modules
│   ├── network/             # VPC, subnets, firewall
│   └── instance/            # VM instances
└── ansible/
    ├── playbooks/
    │   └── site.yml         # Main playbook
    └── roles/
        ├── system-base/     # Base system setup
        ├── git-server/      # Forgejo (Git + CI/CD)
        ├── scrape-workers/  # Scraping workers
        └── proxy-servers/   # Proxy servers
```

---

## 🔧 Configuration

### Single `.env` File

**Everything** is configured via one file: `superdeploy/.env`

```env
# GCP Configuration
GCP_PROJECT_ID=your-project-id
SSH_KEY_PATH=~/.ssh/cfk_gcp

# VM IPs (auto-filled by Terraform)
CORE_EXTERNAL_IP=34.56.43.99
CORE_INTERNAL_IP=10.0.0.12
# ... (more IPs)

# Passwords (fill these!)
POSTGRES_PASSWORD=CHANGE_ME
RABBITMQ_DEFAULT_PASS=CHANGE_ME
API_SECRET_KEY=CHANGE_ME
# ... (more passwords)

# Service Configuration (auto-generated)
API_DATABASE_URL=postgresql://...
API_RABBITMQ_URL=amqp://...
# ... (more URLs)
```

### What Reads `.env`?

1. **terraform-wrapper.sh**: Generates `tfvars` from `.env`
2. **Ansible**: Reads from repo's `.env` via workflows
3. **Docker Compose**: Uses `.env` for all services
4. **Forgejo Actions**: Workflows read `.env` directly

---

## 🎯 Workflows

### How CI/CD Works

```
1. git push master
   ↓
2. Forgejo Actions triggered
   ↓
3. Runner checks out code (with .env)
   ↓
4. Reads .env for IPs and config
   ↓
5. SSHs to target VM
   ↓
6. docker compose up -d
   ↓
7. Done! ✅
```

### Available Workflows

- **deploy-core.yml**: Deploys to CORE VM
- **deploy-scrape.yml**: Deploys to SCRAPE VM  
- **deploy-proxy.yml**: Deploys to PROXY VM
- **ansible.yml**: Runs Ansible playbook (manual trigger)

---

## 🔄 VM Restart / IP Change

If VMs restart and IPs change:

```bash
# 1. Update .env with new IPs
make update-ips

# 2. Commit & push
git add .env
git commit -m "config: update IPs"
git push

# 3. Workflows auto-deploy! ✨
```

---

## 🧪 Testing

```bash
# Test all services
make test

# Manual tests
curl http://34.56.43.99:8000/health    # API
curl http://34.56.43.99:8080/health    # Proxy Registry
open http://34.56.43.99:8001           # Dashboard
open http://34.56.43.99:3001           # Forgejo
open http://34.56.43.99:15672          # RabbitMQ
```

---

## 🆘 Troubleshooting

See [SETUP.md](SETUP.md) for detailed troubleshooting.

**Common Issues:**

```bash
# .env not configured
make check-env

# Terraform errors
gcloud auth list
gcloud config list

# Ansible dpkg lock
sleep 30 && make ansible-deploy

# Runner not working
ssh superdeploy@CORE_IP
sudo systemctl status forgejo-runner
```

---

## 🎨 Features

### ✨ Full Automation
- ✅ Single command deployment
- ✅ Zero manual configuration
- ✅ Auto IP extraction
- ✅ Auto service registration

### 🔐 Security
- ✅ All secrets in `.env`
- ✅ SSH key-based auth
- ✅ Firewall rules
- ✅ Non-root users

### 📊 Monitoring
- ✅ Health check endpoints
- ✅ Service logs
- ✅ RabbitMQ management UI
- ✅ Forgejo Actions UI

### 🚀 Developer Experience
- ✅ 2-command setup
- ✅ Clear documentation
- ✅ Makefile help
- ✅ Error messages

---

## 📈 Deployment Timeline

```
00:00 → make deploy
00:30 → Terraform creates VMs
01:00 → IPs extracted to .env
01:30 → Ansible installs Docker
02:30 → Forgejo deployed
03:00 → Admin + repo created
03:30 → Runner registered
04:00 → Code pushed
04:30 → Workflows triggered
06:00 → All services ready! ✅
```

---

## 💡 Tips

### Generate Passwords

```bash
openssl rand -base64 32  # 32-char password
openssl rand -base64 64  # 64-char password
```

### List GCP Projects

```bash
gcloud projects list
```

### Create SSH Key

```bash
ssh-keygen -t rsa -b 4096 -f ~/.ssh/cfk_gcp
```

### View Logs

```bash
ssh superdeploy@CORE_IP
sudo journalctl -u forgejo-runner -f
docker compose logs -f api
```

---

## 🎯 Philosophy

### Single Source of Truth: `.env`

Everything flows from one file. No duplicates, no conflicts, no confusion.

```
.env → Terraform → VMs
    → Ansible → Services  
    → Docker → Containers
    → Forgejo → Workflows
```

### Maximum Automation, Minimum Commands

```bash
make init    # Once
make deploy  # Always works
```

### Production-Ready from Day 1

- Proper secrets management
- Health checks
- Logging
- Monitoring
- CI/CD
- Zero downtime updates

---

## 📜 License

MIT

---

## 🤝 Contributing

Issues and PRs welcome!

---

## 📞 Support

- **Docs**: [SETUP.md](SETUP.md)
- **Issues**: Open a GitHub issue
- **Email**: admin@superdeploy.io

---

**🚀 Built with ❤️ for developers who hate manual deployment**

---

## 🎉 Summary

| What | Command | Time |
|------|---------|------|
| Setup | `make init` + edit `.env` | 2 min |
| Deploy | `make deploy` | 6 min |
| **TOTAL** | **2 commands** | **8 min** |

**One `.env` + One command = Full production system! 🎯**
