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
curl -X POST \
  -H "Authorization: token YOUR_PAT" \
  -H "Content-Type: application/json" \
  "http://34.44.228.225:3001/api/v1/repos/cradexco/superdeploy/dispatches" \
  -d '{
    "event_type": "deploy",
    "client_payload": {
      "project": "cheapa",
      "service": "api",
      "image": "ghcr.io/cheapaio/api@sha256:abc123",
      "env_bundle": "BASE64_ENCRYPTED_ENV",
      "git_sha": "abc123",
      "git_ref": "production"
    }
  }'
```

### Otomatik (GitHub Actions)
GitHub'a push → Build → Trigger Forgejo → Deploy

## Runner Labels

Her proje kendi runner'ını kullanır:
- `cheapa-runner`: `[self-hosted, cheapa, linux, docker]`
- `myapp-runner`: `[self-hosted, myapp, linux, docker]`

Workflow'da `runs-on: [self-hosted, {project}]` ile doğru runner seçilir.

## Güvenlik

- ✅ App secrets GitHub'da (AGE encrypted)
- ✅ Forgejo'da hiçbir secret yok
- ✅ Runner'da geçici decrypt, sonra temizlik
- ✅ Image digest ile immutable deployment

