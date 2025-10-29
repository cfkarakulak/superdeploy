# 🚀 SuperDeploy

> **Heroku-like PaaS for Self-Hosted Infrastructure**

Modern, Python-based CLI for deploying production applications on your own infrastructure.

---

## ✨ Features

- 🐍 **Modern Python CLI** - Rich terminal UI with progress bars and colors
- 🔐 **Encrypted Secrets** - AGE encryption for secure environment transfer
- 🤖 **Full Automation** - Zero manual steps after initial setup
- 🎯 **Heroku-like UX** - Familiar commands (`up`, `logs`, `scale`, `rollback`)
- 🔄 **Auto-sync** - Secrets sync from local `.env` to GitHub/Forgejo
- 📊 **Interactive Setup** - Wizard-style configuration
- 🌍 **Multi-Environment** - Production, staging, and development environments
- 📈 **Metrics & Monitoring** - Track deployments, uptime, and resource usage
- 💾 **Backup & Restore** - Automated database and configuration backups
- 🔄 **Auto-Rollback** - Automatic rollback on deployment failures
- ✅ **Config Validation** - Validate before deploy to catch errors early

---

## 🚀 Quick Start

### 1. Install CLI

```bash
cd superdeploy
python3 -m venv venv
source venv/bin/activate
pip install -e .
```

Or use Makefile:

```bash
make install
source venv/bin/activate
```

### 2. Initialize Configuration

```bash
superdeploy init -p myproject
```

This will:
- Detect your GCP project
- Generate secure passwords
- Create SSH keys
- Setup project configuration
- Validate configuration

### 3. Deploy Infrastructure

```bash
superdeploy up -p myproject
```

This will (~10 minutes):
- ☁️ Provision GCP VMs with Terraform
- ⚙️ Configure services with Ansible  
- 🔧 Setup Forgejo + Runner
- 📤 Push code to GitHub & Forgejo

### 4. Sync Secrets

```bash
superdeploy sync -p myproject
```

This will:
- 🔑 Fetch AGE public key from VM
- 🎫 Create Forgejo PAT
- 📤 Push ALL secrets to GitHub (using `gh` CLI)
- 🔐 Configure multi-environment secrets

**DONE!** Now just push to GitHub:

```bash
git push origin production
```

Deployment auto-triggers! 🎉

---

## 📚 Commands

### Setup & Deployment

```bash
superdeploy init -p myproject         # Interactive wizard
superdeploy up -p myproject           # Deploy infrastructure  
superdeploy sync -p myproject         # Sync secrets to GitHub
superdeploy validate -p myproject     # Validate configuration
superdeploy doctor                    # Health check
```

### Daily Operations

```bash
superdeploy status -p myproject                    # Show infrastructure status
superdeploy logs -p myproject -a api -f            # Watch logs (follow)
superdeploy run -p myproject -a api "python manage.py migrate"  # Run commands
superdeploy scale -p myproject -a api --replicas 3 # Scale service
superdeploy restart -p myproject -a api            # Restart service
superdeploy metrics -p myproject                   # Show metrics & stats
```

### Configuration

```bash
superdeploy config -p myproject                    # List all config
superdeploy config:set -p myproject KEY=VAL        # Set config var
superdeploy config:get -p myproject KEY            # Get config var
superdeploy config:unset -p myproject KEY          # Unset config var
```

### Deployment & Rollback

```bash
superdeploy deploy -p myproject -a api -e production    # Deploy to production
superdeploy deploy -p myproject -a api -e staging       # Deploy to staging
superdeploy promote -p myproject -a api                 # Promote staging → prod
superdeploy releases -p myproject -a api                # List releases
superdeploy rollback -p myproject -a api v42            # Rollback to v42
```

### Backup & Restore

```bash
superdeploy backup -p myproject                    # Backup database & configs
superdeploy backup -p myproject -o /path/to/backup # Custom backup location
```

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  GitHub (Source of Truth)                                   │
│  ├─ cheapaio/api                                            │
│  ├─ cheapaio/dashboard                                      │
│  └─ cheapaio/services                                       │
└─────────────────────────────────────────────────────────────┘
                            │
                    (git push production)
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│  GitHub Actions                                             │
│  1. Build Docker image                                      │
│  2. Push to registry                                        │
│  3. Encrypt .env with AGE                                   │
│  4. Trigger Forgejo workflow (with encrypted env)           │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│  Forgejo Runner (VM)                                        │
│  1. Decrypt .env with AGE private key                       │
│  2. Pull Docker image                                       │
│  3. Deploy with docker-compose                              │
│  4. Send email notification                                 │
│  5. Cleanup decrypted env (security)                        │
└─────────────────────────────────────────────────────────────┘
```

### Secret Flow

```
.env (local)
    │
    │ superdeploy sync
    ▼
GitHub Secrets (per app)
    │
    │ GitHub Actions
    ▼
Encrypted with AGE public key
    │
    │ workflow_dispatch
    ▼
Forgejo Runner (decrypt with AGE private key)
    │
    │ deploy
    ▼
Running containers
    │
    │ cleanup
    ▼
Encrypted env deleted (secure!)
```

---

## 🔐 Security Model

1. **Local Secrets**: Stored in `.env` (git-ignored)
2. **GitHub Secrets**: Stored in repo/environment secrets
3. **Transport**: AGE-encrypted (public key encryption)
4. **Runner**: AGE private key (never leaves VM)
5. **Cleanup**: Decrypted env is shredded after use

**Result**: Secrets never stored in plaintext on Forgejo!

---

## 🛠️ Requirements

- Python 3.9+
- Terraform
- Ansible
- GCloud SDK
- GitHub CLI (`gh`)
- `jq`, `age`

Install all (macOS):

```bash
brew install python terraform ansible google-cloud-sdk gh jq age
```

---

## 📁 Project Structure

```
superdeploy/
├── superdeploy_cli/          # Python CLI
│   ├── commands/              # Command modules
│   │   ├── init.py            # Interactive setup
│   │   ├── up.py              # Infrastructure deploy
│   │   ├── sync.py            # Secret sync
│   │   ├── status.py          # Status checks
│   │   ├── logs.py            # Log viewer
│   │   ├── deploy.py          # App deployment
│   │   └── ...
│   ├── main.py                # CLI entry point
│   └── utils.py               # Shared utilities
├── ansible/                   # Ansible playbooks
├── .forgejo/workflows/        # Forgejo CI/CD
├── compose/                   # Docker Compose configs
├── bin/                       # Legacy bash scripts
├── setup.py                   # Python package config
├── requirements.txt           # Python dependencies
├── ENV.example                # Example config
└── README.md                  # This file
```

---

## 🎯 Design Principles

1. **Single Command Surface** - All operations via `superdeploy` CLI
2. **Zero Manual Steps** - Full automation after `superdeploy init`
3. **Secret Isolation** - Infra secrets ≠ app secrets
4. **Encrypted Transport** - AGE encryption for env transfer
5. **Heroku UX** - Familiar, intuitive commands
6. **Interactive Wizards** - Smart defaults, easy setup

---

## 🔄 Workflow

### Initial Setup (Once)

```bash
# 1. Clone repo
git clone https://github.com/cfkarakulak/superdeploy.git
cd superdeploy

# 2. Install CLI
make install
source venv/bin/activate

# 3. Interactive setup
superdeploy init

# 4. Deploy infrastructure
superdeploy up

# 5. Sync secrets
superdeploy sync
```

**Time**: ~12 minutes

### Daily Development

```bash
# Edit code in app repo (api/dashboard/services)
git add .
git commit -m "feat: new feature"
git push origin production

# Done! Deployment auto-triggers.

# Watch logs
superdeploy logs -a api -f
```

### Scaling & Operations

```bash
# Scale up
superdeploy scale api=5

# Restart
superdeploy restart api

# Run migrations
superdeploy run api "python manage.py migrate"

# Rollback
superdeploy rollback v41 -a api
```

---

## 📖 Documentation

### Getting Started
- **[QUICKSTART.md](QUICKSTART.md)** - 12-minute E2E guide
- **[docs/SETUP.md](docs/SETUP.md)** - First-time setup
- **[docs/SYNC-WORKFLOW.md](docs/SYNC-WORKFLOW.md)** - 🔄 When to sync secrets? (Important!)

### Operations
- **[docs/OPERATIONS.md](docs/OPERATIONS.md)** - Daily operations & troubleshooting
- **[docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)** - Deployment flow details
- **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)** - System architecture
- **[docs/OVERVIEW.md](docs/OVERVIEW.md)** - High-level overview

---

## 🤝 Contributing

PRs welcome! Please follow existing code style.

---

## 📜 License

MIT

---

## 🎉 What's New

### v2.0.0 - Production Ready

- ✨ **Multi-Environment Support** - Deploy to production, staging, or development
- ✨ **Promote Command** - Safely promote staging → production
- ✨ **Backup & Restore** - Database and config backups
- ✨ **Metrics & Monitoring** - Deployment stats and resource usage
- ✨ **Auto-Rollback** - Automatic rollback on deployment failure
- ✨ **Config Validation** - Validate project configuration before deploy
- ⚡ **Performance** - Age binary caching, retry logic, better health checks
- 🔐 **Enhanced Security** - No hardcoded values, full isolation between projects

### v1.0.0 - Python CLI

- ✅ **Modern Python CLI** (Click + Rich)
- ✅ **Interactive setup wizard** (`superdeploy init`)
- ✅ **Auto secret sync** (`superdeploy sync`)
- ✅ **Progress bars & colored output**
- ✅ **Smart .env detection**
- ✅ **Makefile deprecated** (backward compat only)

---

**Made with ❤️ for devs who want Heroku-like experience on their own infra.**

## Updating Ports

If you change application ports in `project.yml`:

```bash
# 1. Edit project.yml and change port
vim projects/myproject/project.yml

# 2. Update firewall rules (fast, doesn't touch VMs)
superdeploy update-firewall -p myproject

# 3. Redeploy the app with new port
git push origin production  # Triggers auto-deployment
```

The `update-firewall` command only updates GCP firewall rules, it doesn't recreate VMs.
