# SuperDeploy

**GitHub Actions-first Infrastructure as Code** - Deploy production-ready infrastructure and applications with zero-downtime deployments, automated secret management, and self-hosted runners.

## 🎯 Architecture

```
GitHub Repo (code) → GitHub Actions (build) → GitHub Runner (VM) → Docker Compose (deploy)
```

- **No intermediate CI/CD layer** - GitHub Actions talks directly to VMs
- **Self-hosted runners** on project VMs with project-specific labels
- **Guaranteed routing** - Runners only pick up jobs for their project
- **Zero-downtime** - Blue-green deployments via Docker Compose

## 🚀 Quick Start

```bash
# 1. Install SuperDeploy
git clone https://github.com/cfkarakulak/superdeploy.git
cd superdeploy
python3 -m venv venv
source venv/bin/activate
pip install -e .

# 2. Create project
mkdir -p projects/myproject
cp projects/cheapa/config.yml projects/myproject/

# 3. Configure secrets
cp projects/cheapa/secrets.yml projects/myproject/
# Edit secrets.yml with your values

# 4. Generate deployment files
superdeploy myproject:generate

# 5. Deploy infrastructure (runners auto-register via REPOSITORY_TOKEN)
superdeploy myproject:up

# 6. Sync secrets to GitHub
superdeploy myproject:sync
```

## 📝 How It Works

### 1. Infrastructure Setup (`superdeploy myproject:up`)

- Creates GCP VMs with Terraform
- Installs Docker, Node.js, and GitHub self-hosted runner
- Configures runner with project-specific labels: `[self-hosted, superdeploy, myproject, app]`
- Creates `.project` file on VM to identify which project it runs
- Deploys infrastructure addons (Postgres, RabbitMQ, Redis, etc.)

### 2. Application Deployment (`git push production`)

- **Build job** (GitHub-hosted runner):
  - Reads `superdeploy` marker file for project/app/vm_role
  - Builds Docker image
  - Pushes to Docker registry
  - Outputs project metadata

- **Deploy job** (Self-hosted runner on VM):
  - Validates runner is correct project (checks `.project` file)
  - Pulls latest Docker image
  - Restarts container via `docker compose up -d`
  - Verifies container health

### 3. Runner Label Matching

```yaml
# In app repo: .github/workflows/deploy.yml
jobs:
  deploy:
    runs-on: 
      - self-hosted    # Self-hosted runner
      - superdeploy    # SuperDeploy runner
      - myproject      # Project name
      - app            # VM role (app, core, etc.)
```

GitHub automatically routes the job to the runner with ALL matching labels.

## 🗂️ Project Structure

```
superdeploy/
├── projects/
│   └── myproject/
│       ├── config.yml      # Infrastructure config
│       └── secrets.yml      # Encrypted secrets
├── cli/
│   └── commands/
│       ├── up.py           # Deploy infrastructure
│       ├── down.py         # Destroy infrastructure
│       ├── generate.py     # Generate workflows
│       └── sync.py         # Sync secrets to GitHub
├── shared/
│   ├── terraform/          # GCP infrastructure
│   └── ansible/
│       ├── playbooks/      # Deployment playbooks
│       └── roles/
│           └── system/
│               └── github-runner/  # Runner setup
└── addons/
    ├── postgres/
    ├── rabbitmq/
    ├── redis/
    └── caddy/
```

## 🎛️ Configuration

### config.yml

```yaml
name: myproject
region: us-central1

github:
  organization: myorg

vms:
  app:
    machine_type: e2-medium
    disk_size: 30
    services: []
  
  core:
    machine_type: e2-medium
    disk_size: 20
    services:
      - postgres
      - rabbitmq

apps:
  api:
    path: ~/code/myorg/api
    vm: app
  
  storefront:
    path: ~/code/myorg/storefront
    vm: app
```

### secrets.yml

```yaml
secrets:
  shared:
    DOCKER_ORG: myorg
    DOCKER_USERNAME: myuser
    DOCKER_TOKEN: xxx
    POSTGRES_PASSWORD: xxx
    RABBITMQ_PASSWORD: xxx
  
  api:
    DATABASE_URL: postgres://...
    REDIS_URL: redis://...
  
  storefront:
    NEXT_PUBLIC_API_URL: https://api.myproject.com
```

## 🔐 Secret Management

1. **Hierarchical secrets**: `shared` → merged with app-specific
2. **Sync to GitHub**: `superdeploy myproject:sync`
   - Repository secrets (Docker credentials)
   - Environment secrets (per-app configuration)
3. **Access in workflows**: `${{ secrets.DOCKER_TOKEN }}`

## 🛠️ Commands

```bash
# Infrastructure
superdeploy myproject:up              # Deploy infrastructure
superdeploy myproject:down            # Destroy infrastructure
superdeploy myproject:generate        # Generate workflows

# Secrets
superdeploy myproject:sync            # Sync secrets to GitHub

# Config
superdeploy myproject:config show     # Show configuration
superdeploy myproject:config validate # Validate configuration
```

## 🏗️ Adding a New App

1. **Update config.yml**:
```yaml
apps:
  newapp:
    path: ~/code/myorg/newapp
    vm: app
```

2. **Add secrets** to `secrets.yml`:
```yaml
secrets:
  newapp:
    API_KEY: xxx
```

3. **Generate workflow**:
```bash
superdeploy myproject:generate --app newapp
```

4. **Commit workflow** to app repo:
```bash
cd ~/code/myorg/newapp
git add superdeploy .github/workflows/deploy.yml
git commit -m "Add SuperDeploy"
```

5. **Sync secrets**:
```bash
superdeploy myproject:sync
```

6. **Deploy**:
```bash
git push origin production
```

## 🔄 How Routing Works (Detailed)

### Problem: Multiple Projects on Same Organization

If you have `project1` and `project2`, both deploying to `yourorg/*` repositories, how does GitHub know which runner to use?

### Solution: Label-based Routing

Each runner gets **unique labels** based on its project:

```bash
# Project 1 - cheapa
cheapa-app-0:  [self-hosted, superdeploy, cheapa, app]
cheapa-core-0: [self-hosted, superdeploy, cheapa, core]

# Project 2 - blogapp
blogapp-app-0:  [self-hosted, superdeploy, blogapp, app]
blogapp-core-0: [self-hosted, superdeploy, blogapp, core]
```

### Workflow Specifies ALL Labels

```yaml
# In yourorg/api (part of cheapa project)
runs-on: 
  - self-hosted
  - superdeploy
  - cheapa      # ← Only cheapa runners match
  - app         # ← Only app VMs match
```

**Result**: Only `cheapa-app-0` runner will pick up this job. `blogapp-app-0` won't even see it.

### Double-Check Inside Job

Even with label matching, we validate again:

```bash
RUNNER_PROJECT=$(cat /opt/superdeploy/.project)
if [ "$RUNNER_PROJECT" != "cheapa" ]; then
  echo "Wrong project!"
  exit 1
fi
```

## 📊 Monitoring

Coming soon:
- Prometheus metrics
- Grafana dashboards
- Log aggregation

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## 📄 License

MIT

## 🙏 Credits

Built with:
- [Terraform](https://www.terraform.io/) - Infrastructure provisioning
- [Ansible](https://www.ansible.com/) - Configuration management
- [GitHub Actions](https://github.com/features/actions) - CI/CD
- [Docker](https://www.docker.com/) - Containerization
- [GCP](https://cloud.google.com/) - Cloud infrastructure
