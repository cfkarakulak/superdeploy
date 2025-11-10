# SuperDeploy Documentation

Comprehensive documentation for SuperDeploy - GitHub Actions-first Infrastructure as Code platform.

---

## 📚 Documentation Index

### Getting Started

- **[Setup Guide](SETUP.md)** - First-time installation from scratch
  - Prerequisites
  - GCP setup
  - GitHub runner configuration
  - First deployment

### Core Concepts

- **[Architecture](ARCHITECTURE.md)** - System architecture and design decisions
  - GitHub-first architecture
  - Self-hosted runners
  - Label-based routing
  - Addon system
  - Template → Instance pattern
  - Security architecture

### Daily Operations

- **[Operations Guide](OPERATIONS.md)** - Day-to-day management
  - Deployment operations
  - Infrastructure scaling
  - Secret management
  - Monitoring & debugging
  - Disaster recovery

### Reference

- **[Flow Diagram](FLOW.md)** - Visual deployment flow
- **[Security](SECURITY.md)** - Security best practices

---

## 🎯 Quick Start

```bash
# 1. Install SuperDeploy
git clone https://github.com/cfkarakulak/superdeploy.git
cd superdeploy && pip install -e .

# 2. Create project
mkdir -p projects/myproject
# ... configure config.yml and secrets.yml ...

# 3. Get GitHub runner token
# https://github.com/yourorg/settings/actions/runners/new

# 4. Deploy infrastructure
GITHUB_RUNNER_TOKEN=xxx superdeploy myproject:up

# 5. Sync secrets
superdeploy myproject:sync

# 6. Generate workflows
superdeploy myproject:generate

# 7. Deploy apps
git push origin production
```

---

## 🏗️ Architecture Overview

```
GitHub Repo → GitHub Actions (build) → Self-Hosted Runner (VM) → Docker Compose
```

**Key Components:**
- **GitHub Actions**: CI/CD orchestration
- **Self-Hosted Runners**: Project-specific runners on VMs
- **Label-Based Routing**: Guaranteed project isolation
- **Addon System**: Reusable service templates (postgres, redis, etc.)
- **Terraform**: Infrastructure provisioning
- **Ansible**: Configuration management

---

## 🎓 Learning Path

### 1. New to SuperDeploy?

Start here:
1. Read [Architecture](ARCHITECTURE.md) for concepts
2. Follow [Setup Guide](SETUP.md) for installation
3. Review [Operations Guide](OPERATIONS.md) for daily use

### 2. Experienced User?

Quick reference:
- [Operations Guide](OPERATIONS.md) - Common tasks
- [Security](SECURITY.md) - Best practices

### 3. Contributing?

Development docs:
- Architecture deep-dive
- Code structure
- Testing guidelines

---

## 💡 Core Concepts

### GitHub-First Architecture

SuperDeploy uses **GitHub Actions + self-hosted runners** for deployment. No intermediate CI/CD layer.

**Benefits:**
- Single ecosystem
- Native GitHub features
- Simple maintenance
- Cost effective

### Label-Based Routing

Each runner gets unique labels:

```
cheapa-app-0: [self-hosted, superdeploy, cheapa, app]
blogapp-app-0: [self-hosted, superdeploy, blogapp, app]
```

Workflows specify ALL labels → GitHub routes to correct runner → **Guaranteed isolation**

### Addon System

Services are **templates** that become **instances**:

```
Template (addons/postgres/) → config.yml → Instance (myproject-postgres)
```

**Benefits:**
- No hardcoded service names
- Consistent deployments
- Easy to maintain
- Reusable across projects

---

## 🔐 Security

### Multi-Layer Security

1. **Secrets**: GitHub encrypted storage, never in Git
2. **Network**: Project-specific Docker networks, VM firewalls
3. **Access**: SSH keys, GitHub PAT, runner labels
4. **Isolation**: Label-based routing, `.project` file validation

See [Security Guide](SECURITY.md) for details.

---

## 🚀 Commands Reference

### Infrastructure

```bash
superdeploy myproject:up              # Deploy infrastructure
superdeploy myproject:down            # Destroy infrastructure
superdeploy myproject:status          # Check status (includes versions)
superdeploy myproject:status -v       # Verbose status with debug info
```

### Deployment

```bash
superdeploy myproject:generate        # Generate workflows
superdeploy myproject:sync            # Sync secrets to GitHub
```

### Configuration

```bash
superdeploy myproject:config show     # Show configuration
superdeploy myproject:config validate # Validate configuration
```

### Versioning

SuperDeploy automatically tracks semantic versions for deployments:

```bash
# Versions are auto-incremented based on commit messages:
git commit -m "fix: bug"              # Patch: 0.0.1 → 0.0.2
git commit -m "feat: new feature"     # Minor: 0.0.2 → 0.1.0
git commit -m "breaking: api change"  # Major: 0.1.0 → 1.0.0

# View versions
superdeploy myproject:status

# Version metadata stored at:
# /opt/superdeploy/projects/{project}/versions.json
```

---

## 📊 Project Structure

```
superdeploy/
├── cli/                    # CLI commands
│   ├── commands/          # Command implementations
│   ├── core/              # Core functionality
│   └── stubs/             # Templates (workflows, configs)
├── addons/                 # Service templates
│   ├── postgres/
│   ├── redis/
│   └── ...
├── projects/               # Project configs
│   └── myproject/
│       ├── config.yml    # Infrastructure config
│       └── secrets.yml    # Encrypted secrets
├── shared/
│   ├── terraform/         # Infrastructure provisioning
│   └── ansible/           # Configuration management
└── docs/                   # Documentation
```

---

## 🤝 Contributing

We welcome contributions!

**Areas to contribute:**
- New addon templates
- Cloud provider support (AWS, Azure)
- Documentation improvements
- Bug fixes and features

---

## 📖 FAQ

### Q: Do I need to know Terraform/Ansible?

A: No! SuperDeploy abstracts the complexity. Just configure `config.yml`.

### Q: Can I use AWS instead of GCP?

A: Not yet, but it's planned. Contributions welcome!

### Q: How much does it cost?

A: Only cloud provider costs (GCP VMs). SuperDeploy is open source and free.

### Q: Is it production-ready?

A: Yes! Used in production for multiple projects.

### Q: How do I scale horizontally?

A: Add more VMs in `config.yml` and configure a load balancer.

---

## 📞 Support

- **GitHub Issues**: https://github.com/cfkarakulak/superdeploy/issues
- **Documentation**: https://github.com/cfkarakulak/superdeploy/tree/main/docs

---

## 📄 License

MIT License - see LICENSE file for details.
