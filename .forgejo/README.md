# SuperDeploy

Bu repo **deployment orkestrasyonu** içindir. Uygulama kodları GitHub'da tutulur.

**Repo:** `cradexco/superdeploy` (Forgejo'da tek repo)

## Mimari

```
GitHub (Source of Truth)
├── cheapaio/api → App code + secrets
├── cheapaio/dashboard → App code + secrets
└── cheapaio/services → App code + secrets
    ↓ Build & Push
    ↓ Trigger Forgejo
    ↓
Forgejo (Deployment Only)
└── cradexco/superdeploy
    └── .forgejo/workflows/deploy.yml
        ↓ Parametreli workflow
        ↓ runs-on: [self-hosted, {project}]
        ↓
    Runner (Project-specific)
    └── Deploy to Docker
```

## Workflow Parametreleri

- `project`: Proje adı (cheapa, myapp)
- `service`: Servis adı (api, dashboard, services)
- `image`: Docker image with digest
- `env_bundle`: AGE-encrypted environment variables
- `git_sha`: Git commit SHA
- `git_ref`: Git branch/tag

## Kullanım

### Manuel Trigger (Test)
```bash
# Trigger deployment workflow
curl -X POST \
  -H "Authorization: token YOUR_PAT" \
  -H "Content-Type: application/json" \
  "http://ORCHESTRATOR_IP:3001/api/v1/repos/YOUR_ORG/superdeploy/actions/workflows/deploy.yml/dispatches" \
  -d '{
    "ref": "master",
    "inputs": {
      "project": "cheapa",
      "service": "api",
      "image": "docker.io/c100394/cheapa-api:abc123",
      "env_bundle": "BASE64_ENCRYPTED_ENV",
      "git_sha": "abc123",
      "git_ref": "production"
    }
  }'
```

### Otomatik (GitHub Actions)
GitHub'a push → Build → Trigger Forgejo → Deploy

## Runner Architecture

SuperDeploy uses a **hybrid runner architecture** for maximum flexibility:

### 1. Orchestrator Runner (Fixed, Multi-Project)
- **Location:** Orchestrator VM (where Forgejo runs)
- **Name:** `orchestrator-runner`
- **Labels:** `[self-hosted, orchestrator, linux, docker, ubuntu-latest]`
- **Purpose:** Handles workflows that need to run on the Forgejo VM itself
- **Usage:** `runs-on: [self-hosted, orchestrator]`

### 2. Project-Specific Runners (Dynamic, Per-VM)
- **Location:** Each project VM (web, api, worker, etc.)
- **Name:** `{project}-{vm_role}-{hostname}`
- **Labels:** `[self-hosted, {project}, {vm_role}, linux, docker, ubuntu-latest]`
- **Purpose:** Handles project-specific deployments on their respective VMs
- **Usage:** `runs-on: [self-hosted, {project}]`

### Example: cheapa Project

```yaml
# project.yml
vms:
  web:
    count: 1
  api:
    count: 1
```

**Runners Created:**
- `orchestrator-runner` (on Forgejo VM) → Labels: `[orchestrator, linux, docker]`
- `cheapa-web-cheapa-web-0` (on web VM) → Labels: `[cheapa, web, linux, docker]`
- `cheapa-api-cheapa-api-0` (on api VM) → Labels: `[cheapa, api, linux, docker]`

**Workflow Usage:**
```yaml
# Deploy to project VMs
runs-on: [self-hosted, cheapa]

# Deploy to specific VM role
runs-on: [self-hosted, cheapa, web]

# Run on orchestrator (for infra tasks)
runs-on: [self-hosted, orchestrator]
```

### Benefits

✅ **Multi-Project Support:** One Forgejo instance serves multiple projects  
✅ **Isolation:** Each project's workflows run on their own VMs  
✅ **Flexibility:** Can target specific VM roles (web, api, worker)  
✅ **Scalability:** Add more VMs = more runners automatically  
✅ **Fixed Orchestrator:** Forgejo VM name never changes

## Güvenlik

- ✅ App secrets GitHub'da (AGE encrypted)
- ✅ Forgejo'da hiçbir secret yok
- ✅ Runner'da geçici decrypt, sonra temizlik
- ✅ Image digest ile immutable deployment

# Trigger new workflow run
