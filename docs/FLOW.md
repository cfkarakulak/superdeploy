# SuperDeploy Deployment Flow

Visual guide to understand how code becomes running containers.

---

## 🎯 Complete Deployment Flow

```
┌─────────────────────────────────────────────────────────────────┐
│ 1. DEVELOPMENT                                                  │
│                                                                 │
│  Developer                                                      │
│     ↓                                                          │
│  git commit & push → production branch                         │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ 2. GITHUB ACTIONS (Build Job - GitHub-hosted runner)           │
│                                                                 │
│  ✓ Checkout code                                               │
│  ✓ Read .superdeploy marker                                    │
│     → project: cheapa                                          │
│     → app: api                                                 │
│     → vm_role: app                                             │
│  ✓ Build Docker image                                          │
│  ✓ Push to Docker Hub                                          │
│  ✓ Output metadata for deploy job                             │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ 3. GITHUB RUNNER ROUTING                                        │
│                                                                 │
│  GitHub finds runner with ALL labels:                          │
│  ┌──────────────────────────────────────────────────────┐     │
│  │ runs-on:                                             │     │
│  │   - self-hosted    ← Self-hosted runner             │     │
│  │   - superdeploy    ← SuperDeploy runner             │     │
│  │   - cheapa         ← Project name                   │     │
│  │   - app            ← VM role                        │     │
│  └──────────────────────────────────────────────────────┘     │
│                                                                 │
│  Matches: cheapa-app-0                                         │
│  ✅ Guaranteed routing to correct VM!                          │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ 4. DEPLOYMENT (Self-hosted runner on VM)                       │
│                                                                 │
│  ✓ Validate runner project                                     │
│    → cat /opt/superdeploy/.project                            │
│    → if != "cheapa" → ERROR                                   │
│                                                                 │
│  ✓ Check if app exists on this VM                             │
│    → docker compose config | grep "api:"                      │
│    → if not found → SKIP (other VM)                          │
│                                                                 │
│  ✓ Pull latest image                                          │
│    → docker compose pull api                                  │
│                                                                 │
│  ✓ Restart container                                          │
│    → docker compose up -d api                                 │
│                                                                 │
│  ✓ Health check                                               │
│    → Wait 5s                                                  │
│    → docker inspect cheapa_api                                │
│    → if status != "running" → ERROR                          │
│                                                                 │
│  ✓ Cleanup                                                    │
│    → docker image prune -f                                    │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ 5. PRODUCTION                                                   │
│                                                                 │
│  ✅ New container running                                       │
│  ✅ Old container stopped                                       │
│  ✅ Zero-downtime deployment                                    │
└─────────────────────────────────────────────────────────────────┘
```

---

## 📋 Detailed Step-by-Step

### Step 1: Developer Push

```bash
cd ~/code/myorg/api
git add .
git commit -m "Add new feature"
git push origin production  # ← Triggers GitHub Actions
```

**What happens:**
- GitHub detects push to `production` branch
- Looks for `.github/workflows/deploy.yml`
- Starts workflow execution

### Step 2: Build Job (GitHub-hosted runner)

```yaml
# .github/workflows/deploy.yml
jobs:
  build:
    runs-on: ubuntu-latest  # ← GitHub-hosted
    steps:
      - uses: actions/checkout@v4
      
      - name: Read .superdeploy marker
        run: |
          PROJECT=$(grep "^project:" .superdeploy | cut -d: -f2 | xargs)
          APP=$(grep "^app:" .superdeploy | cut -d: -f2 | xargs)
          VM_ROLE=$(grep "^vm:" .superdeploy | cut -d: -f2 | xargs)
          echo "project=$PROJECT" >> $GITHUB_OUTPUT
          echo "app=$APP" >> $GITHUB_OUTPUT
          echo "vm_role=$VM_ROLE" >> $GITHUB_OUTPUT
      
      - name: Build Docker image
        run: |
          docker build -t myorg/api:latest .
          docker tag myorg/api:latest myorg/api:${{ github.sha }}
      
      - name: Push to Docker Hub
        run: |
          echo "${{ secrets.DOCKER_TOKEN }}" | docker login -u "${{ secrets.DOCKER_USERNAME }}" --password-stdin
          docker push myorg/api:latest
          docker push myorg/api:${{ github.sha }}
```

**Outputs:**
- `project`: cheapa
- `app`: api
- `vm_role`: app

### Step 3: GitHub Runner Routing

```yaml
deploy:
  needs: build
  runs-on: 
    - self-hosted    # Must be self-hosted
    - superdeploy    # Must be superdeploy runner
    - ${{ needs.build.outputs.project }}   # Must be project-specific
    - ${{ needs.build.outputs.vm_role }}   # Must be VM role-specific
```

**GitHub's Routing Logic:**

```
Available runners:
  - cheapa-app-0: [self-hosted, superdeploy, cheapa, app]
  - cheapa-core-0: [self-hosted, superdeploy, cheapa, core]
  - blogapp-app-0: [self-hosted, superdeploy, blogapp, app]

Required labels: [self-hosted, superdeploy, cheapa, app]

Match:
  ✓ cheapa-app-0: ALL labels match → SELECTED
  ✗ cheapa-core-0: Missing "app" label
  ✗ blogapp-app-0: Missing "cheapa" label
```

✅ **Guaranteed: Only `cheapa-app-0` will run this job!**

### Step 4: Deployment Execution

```bash
# 1. Validate runner
RUNNER_PROJECT=$(cat /opt/superdeploy/.project)
if [ "$RUNNER_PROJECT" != "cheapa" ]; then
  echo "❌ Wrong project!"
  exit 1
fi

# 2. Check if app exists
cd /opt/superdeploy/projects/cheapa/compose
if ! docker compose config | grep -q "^  api:"; then
  echo "⏭️ App not on this VM, skipping"
  exit 0
fi

# 3. Deploy
docker compose pull api
docker compose up -d api

# 4. Health check
sleep 5
STATUS=$(docker inspect -f '{{.State.Status}}' cheapa_api)
if [ "$STATUS" != "running" ]; then
  echo "❌ Container failed!"
  docker logs cheapa_api --tail 50
  exit 1
fi

# 5. Cleanup
docker image prune -f
echo "✅ Deployment successful!"
```

### Step 5: Verification

GitHub Actions shows:

```
✅ Build job completed
✅ Deploy job completed
✅ Workflow successful
```

Container is running:

```bash
ssh superdeploy@<VM_IP>
docker ps | grep api
# cheapa_api  Up 2 minutes  0.0.0.0:8000->8000/tcp
```

---

## 🔄 Infrastructure Setup Flow

### Initial Setup (One-time)

```
┌─────────────────────────────────────────────────────────────────┐
│ 1. CONFIGURATION                                                │
│                                                                 │
│  Create config.yml:                                           │
│    - VMs (app, core)                                           │
│    - Services (postgres, rabbitmq)                             │
│    - Apps (api, storefront)                                    │
│                                                                 │
│  Create secrets.yml:                                           │
│    - Docker credentials                                        │
│    - Infrastructure passwords                                  │
│    - App-specific secrets                                      │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ 2. GENERATE WORKFLOWS                                           │
│                                                                 │
│  superdeploy myproject:generate                                │
│    ↓                                                           │
│  For each app:                                                 │
│    ✓ Create .superdeploy marker                               │
│    ✓ Detect app type (Python, Next.js)                        │
│    ✓ Generate .github/workflows/deploy.yml                    │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ 3. INFRASTRUCTURE DEPLOYMENT                                    │
│                                                                 │
│  superdeploy myproject:up                                      │
│                                                                 │
│  Terraform Phase:                                              │
│    ✓ Create GCP VMs                                           │
│    ✓ Assign static IPs                                        │
│    ✓ Configure networking                                     │
│    ✓ Save state                                               │
│                                                                 │
│  Ansible Phase:                                                │
│    ✓ Install base system (Docker, Node.js)                    │
│    ✓ Setup GitHub runner (auto-registers via REPOSITORY_TOKEN)│
│       → Download runner binary                                │
│       → Get registration token from GitHub API                │
│       → Set labels: [self-hosted, superdeploy, project, role] │
│       → Create systemd service                                │
│    ✓ Create .project file                                     │
│    ✓ Deploy infrastructure addons                             │
│       → Postgres (on core VM)                                │
│       → RabbitMQ (on core VM)                                │
│    ✓ Health checks                                            │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ 4. SECRET SYNC                                                  │
│                                                                 │
│  superdeploy myproject:sync                                    │
│    ↓                                                           │
│  For each app:                                                 │
│    ✓ Set repository secrets (Docker)                          │
│    ✓ Create production environment                            │
│    ✓ Set environment secrets (app config)                     │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ 5. READY FOR DEPLOYMENT                                         │
│                                                                 │
│  Infrastructure running:                                       │
│    ✅ VMs provisioned                                          │
│    ✅ GitHub runners registered                                │
│    ✅ Secrets synced                                           │
│    ✅ Workflows generated                                      │
│                                                                 │
│  Next: git push origin production                             │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🔐 Secret Flow

```
┌─────────────────────────────────────────────────────────────────┐
│ 1. SECRET DEFINITION                                            │
│                                                                 │
│  secrets.yml:                                                  │
│    shared:                                                     │
│      DOCKER_TOKEN: xxx                                         │
│    api:                                                        │
│      DATABASE_URL: postgres://...                              │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ 2. SECRET SYNC                                                  │
│                                                                 │
│  superdeploy myproject:sync                                    │
│    ↓                                                           │
│  GitHub CLI (gh):                                              │
│    ✓ gh secret set DOCKER_TOKEN -R myorg/api                  │
│    ✓ gh secret set DATABASE_URL -e production -R myorg/api    │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ 3. SECRET STORAGE                                               │
│                                                                 │
│  GitHub (encrypted):                                           │
│    Repository Secrets:                                         │
│      - DOCKER_TOKEN (build-time)                              │
│    Environment Secrets (production):                           │
│      - DATABASE_URL (runtime)                                 │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ 4. SECRET ACCESS                                                │
│                                                                 │
│  GitHub Actions Workflow:                                      │
│    ${{ secrets.DOCKER_TOKEN }}  ← Repository secret           │
│    ${{ secrets.DATABASE_URL }}  ← Environment secret          │
│                                                                 │
│  Container Runtime:                                            │
│    Environment variables from docker-compose.yml              │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🎯 Key Takeaways

### 1. GitHub-First

- **No intermediate layer**: GitHub → Runner → Container
- **Native features**: Label routing, encrypted secrets
- **Simple**: Standard GitHub Actions workflow

### 2. Guaranteed Routing

- **Label matching**: ALL labels must match
- **Double validation**: `.project` file check
- **Zero mistakes**: Impossible to deploy to wrong project

### 3. Zero-Downtime

- **Pull first**: New image downloaded
- **Recreate**: Old container stopped, new started
- **Health check**: Verify before success
- **Rollback**: Re-run previous successful deployment

### 4. Scalable

- **Add VMs**: Just update `config.yml`
- **Add apps**: Generate workflow + sync secrets
- **Add projects**: Completely isolated
- **No conflicts**: Project-specific everything

---

## 🔍 Debugging Flow

```
Deployment Failed?
    ↓
Check GitHub Actions logs
    ├── Build failed? → Docker build issue
    └── Deploy failed?
           ↓
        SSH to VM
           ↓
        Check runner: journalctl -u github-runner
           ↓
        Check container: docker logs myproject_api
           ↓
        Check .project file: cat /opt/superdeploy/.project
           ↓
        Manual deployment: docker compose up -d api
```

---

## 📊 Timeline

Typical deployment timeline:

```
git push              : 0s
GitHub Actions start  : ~5s
Build job            : ~2-5 min (Docker build)
Runner pickup        : ~1s (instant)
Deploy job           : ~30s (pull + restart)
Health check         : ~5s
Total                : ~3-6 minutes
```

Subsequent deployments (cached build layers): **~1-2 minutes**

---

## ✅ Success Criteria

Deployment is successful when:

1. ✅ Build job completed
2. ✅ Deploy job completed
3. ✅ Container status = "running"
4. ✅ Health check passed
5. ✅ No errors in logs
