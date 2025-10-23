# 🆕 Yeni Service Ekleme Rehberi

Bu döküman mevcut bir projeye (örn: cheapa) yeni bir service nasıl eklenir gösterir.

---

## 📋 Senaryo 1: Mevcut Projeye Yeni Service Eklemek

### Örnek: Cheapa projesine "worker" service'i eklemek

#### Adım 1: Config'e Ekle

```bash
nano superdeploy/projects/cheapa/config.yml
```

**Ekle:**
```yaml
# Services to deploy
services:
  - api
  - dashboard
  - services
  - worker  # ✅ YENİ!

# Port Assignments
ports:
  api:
    external: 8000
    internal: 8000
  dashboard:
    external: 3002
    internal: 3000
  services:
    external: 9000
    internal: 8000
  worker:  # ✅ YENİ!
    external: 9001
    internal: 8000

# GitHub Configuration
github:
  repositories:
    api: cheapaio/api
    dashboard: cheapaio/dashboard
    services: cheapaio/services
    worker: cheapaio/worker  # ✅ YENİ!
```

#### Adım 2: GitHub Repo Oluştur

```bash
# GitHub'da yeni repo oluştur: cheapaio/worker
gh repo create cheapaio/worker --public

# Veya web'den: https://github.com/new
```

#### Adım 3: Worker App Kodunu Hazırla

```bash
mkdir -p app-repos/worker
cd app-repos/worker

# Git init
git init
git remote add origin https://github.com/cheapaio/worker.git

# Dockerfile oluştur
cat > Dockerfile <<'EOF'
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "worker.py"]
EOF

# requirements.txt
cat > requirements.txt <<'EOF'
celery==5.3.4
redis==5.0.1
psycopg2-binary==2.9.9
EOF

# worker.py (örnek)
cat > worker.py <<'EOF'
import os
from celery import Celery

app = Celery('worker',
             broker=os.getenv('RABBITMQ_URL'),
             backend=os.getenv('REDIS_URL'))

@app.task
def process_job(job_id):
    print(f"Processing job {job_id}")
    return f"Job {job_id} completed"

if __name__ == '__main__':
    app.worker_main()
EOF

# Health endpoint (opsiyonel)
cat > health.py <<'EOF'
from flask import Flask
app = Flask(__name__)

@app.route('/health')
def health():
    return {'status': 'healthy'}

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000)
EOF
```

#### Adım 4: GitHub Actions Workflow Ekle

```bash
mkdir -p .github/workflows

# Deploy workflow'u kopyala (api'den)
cp ../api/.github/workflows/deploy.yml .github/workflows/

# Veya manuel oluştur:
cat > .github/workflows/deploy.yml <<'EOF'
name: Build and Deploy

on:
  push:
    branches:
      - production
  workflow_dispatch:

env:
  REGISTRY: docker.io
  IMAGE_NAME: c100394/worker  # ✅ Service adını değiştir!

jobs:
  build-and-deploy:
    runs-on: ubuntu-latest
    
    steps:
      - name: Checkout code
        uses: actions/checkout@v4
      
      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3
      
      - name: Log in to Docker Hub
        uses: docker/login-action@v3
        with:
          username: ${{ secrets.DOCKER_USERNAME }}
          password: ${{ secrets.DOCKER_TOKEN }}
      
      - name: Extract metadata
        id: meta
        uses: docker/metadata-action@v5
        with:
          images: ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}
          tags: |
            type=sha,prefix={{branch}}-
            type=ref,event=branch
            type=raw,value=latest,enable={{is_default_branch}}
      
      - name: Build and push Docker image
        id: build
        uses: docker/build-push-action@v5
        with:
          context: .
          push: true
          tags: ${{ steps.meta.outputs.tags }}
          labels: ${{ steps.meta.outputs.labels }}
          cache-from: type=gha
          cache-to: type=gha,mode=max
      
      - name: Get image digest
        id: digest
        run: |
          DIGEST="${{ steps.build.outputs.digest }}"
          IMAGE_WITH_DIGEST="${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}@${DIGEST}"
          echo "image=${IMAGE_WITH_DIGEST}" >> $GITHUB_OUTPUT
          echo "short_sha=${GITHUB_SHA:0:7}" >> $GITHUB_OUTPUT
      
      - name: Cache age binary
        id: cache-age
        uses: actions/cache@v3
        with:
          path: /usr/local/bin/age
          key: age-v1.1.1-linux-amd64
      
      - name: Install age
        if: steps.cache-age.outputs.cache-hit != 'true'
        run: |
          curl -sL https://github.com/FiloSottile/age/releases/download/v1.1.1/age-v1.1.1-linux-amd64.tar.gz | tar xz
          sudo mv age/age age/age-keygen /usr/local/bin/
          age --version
      
      - name: Prepare environment bundle
        id: env_bundle
        run: |
          cat > /tmp/app.env <<EOF
          # Database
          POSTGRES_HOST=${{ secrets.POSTGRES_HOST }}
          POSTGRES_PORT=${{ secrets.POSTGRES_PORT }}
          POSTGRES_USER=${{ secrets.POSTGRES_USER }}
          POSTGRES_PASSWORD=${{ secrets.POSTGRES_PASSWORD }}
          POSTGRES_DB=${{ secrets.POSTGRES_DB }}
          
          # Message Queue
          RABBITMQ_HOST=${{ secrets.RABBITMQ_HOST }}
          RABBITMQ_PORT=${{ secrets.RABBITMQ_PORT }}
          RABBITMQ_USER=${{ secrets.RABBITMQ_USER }}
          RABBITMQ_PASSWORD=${{ secrets.RABBITMQ_PASSWORD }}
          
          # Cache
          REDIS_HOST=${{ secrets.REDIS_HOST }}
          REDIS_PORT=${{ secrets.REDIS_PORT }}
          REDIS_PASSWORD=${{ secrets.REDIS_PASSWORD }}
          
          # App-specific
          WORKER_SECRET_KEY=${{ secrets.WORKER_SECRET_KEY }}
          SENTRY_DSN=${{ secrets.SENTRY_DSN }}
          LOG_LEVEL=${{ secrets.LOG_LEVEL }}
          EOF
          
          cat /tmp/app.env | age -r "${{ secrets.AGE_PUBLIC_KEY }}" | base64 -w 0 > /tmp/encrypted.txt
          ENCRYPTED=$(cat /tmp/encrypted.txt)
          echo "encrypted=${ENCRYPTED}" >> $GITHUB_OUTPUT
          rm -f /tmp/app.env /tmp/encrypted.txt
      
      - name: Trigger Forgejo deployment
        env:
          FORGEJO_URL: ${{ secrets.FORGEJO_BASE_URL }}
          FORGEJO_PAT: ${{ secrets.FORGEJO_PAT }}
        run: |
          REPO_NAME="${{ github.repository }}"
          SERVICE="${REPO_NAME##*/}"
          
          PROJECT="${{ secrets.PROJECT_NAME }}"
          FORGEJO_ORG="${{ secrets.FORGEJO_ORG }}"
          FORGEJO_REPO="${{ secrets.FORGEJO_REPO }}"
          
          PAYLOAD=$(cat <<EOF
          {
            "ref": "master",
            "inputs": {
              "project": "${PROJECT}",
              "service": "${SERVICE}",
              "image": "${{ steps.digest.outputs.image }}",
              "env_bundle": "${{ steps.env_bundle.outputs.encrypted }}",
              "git_sha": "${{ github.sha }}",
              "git_ref": "${{ github.ref_name }}"
            }
          }
          EOF
          )
          
          echo "📦 Payload preview:"
          echo "${PAYLOAD}" | jq -r '.inputs | "project=\(.project), service=\(.service)"'
          
          curl -X POST \
            -H "Authorization: token ${FORGEJO_PAT}" \
            -H "Content-Type: application/json" \
            -d "${PAYLOAD}" \
            "${FORGEJO_URL}/api/v1/repos/${FORGEJO_ORG}/${FORGEJO_REPO}/actions/workflows/deploy.yml/dispatches"
          
          echo "✅ Deployment triggered!"
          echo "🌐 Check status: ${FORGEJO_URL}/${FORGEJO_ORG}/${FORGEJO_REPO}/actions"
EOF
```

#### Adım 5: Secrets Sync Et

```bash
cd superdeploy

# Yeni service için secrets ekle (opsiyonel)
echo "WORKER_SECRET_KEY=$(openssl rand -base64 32)" >> .env

# Sync et (tüm repo'lara secrets gönderir)
superdeploy sync -p cheapa

# ✅ Otomatik olarak cheapaio/worker repo'suna da secrets eklenir!
```

#### Adım 6: İlk Deployment

```bash
cd app-repos/worker

git add .
git commit -m "feat: initial worker service"
git branch -M production
git push -u origin production

# ✅ Otomatik deployment başlar!
```

#### Adım 7: Kontrol Et

```bash
# Status kontrol
superdeploy status -p cheapa

# Logs
superdeploy logs -p cheapa -a worker -f

# Container kontrol
ssh superdeploy@CORE_IP
docker ps | grep cheapa-worker
```

---

## 📋 Senaryo 2: Yeni Bir Proje Eklemek (örn: "myapp")

### Adım 1: Proje Oluştur

```bash
cd superdeploy

# Interactive wizard
superdeploy init -p myapp

# Bu komut:
# ✅ projects/myapp/ klasörü oluşturur
# ✅ config.yml oluşturur
# ✅ .passwords.yml oluşturur (güvenli şifreler)
# ✅ compose/ klasörü oluşturur
```

### Adım 2: Infrastructure Deploy

```bash
# VM'leri deploy et (eğer yeni VM gerekiyorsa)
superdeploy up -p myapp

# Secrets sync et
superdeploy sync -p myapp
```

### Adım 3: App Repo'larını Oluştur

```bash
# GitHub'da repo'lar oluştur
gh repo create myapporg/api --public
gh repo create myapporg/dashboard --public

# App kodlarını hazırla (Senaryo 1'deki gibi)
mkdir -p app-repos-myapp/{api,dashboard}
# ... kod yaz ...
```

### Adım 4: Deploy

```bash
cd app-repos-myapp/api
git push origin production

# ✅ Otomatik deployment!
```

---

## ✅ Otomatik Olan Şeyler

### 1. **Caddy Route Oluşturma** ✅
```bash
# Forgejo workflow otomatik oluşturur:
/opt/superdeploy/shared/caddy/routes/cheapa-worker.caddy
```

**İçerik:**
```
:9001 {
  reverse_proxy cheapa-worker:8000
}
```

### 2. **Docker Compose Oluşturma** ✅
```bash
# Forgejo workflow otomatik oluşturur:
/opt/apps/cheapa/compose/docker-compose-worker.yml
```

### 3. **Network Bağlantısı** ✅
```bash
# Otomatik olarak:
# - cheapa-network
# - superdeploy-proxy
# network'lerine bağlanır
```

### 4. **Health Check** ✅
```yaml
# Otomatik eklenir:
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
  interval: 15s
  timeout: 10s
  retries: 5
  start_period: 60s
```

### 5. **Secrets Injection** ✅
```bash
# GitHub Secrets → AGE encrypt → Forgejo decrypt → Container
# Tamamen otomatik!
```

---

## 🎯 Özet: Ne Yapman Gerekiyor?

### Yeni Service İçin:
1. ✅ `config.yml`'e ekle (3 satır)
2. ✅ GitHub repo oluştur
3. ✅ App kodunu yaz (Dockerfile + kod)
4. ✅ `.github/workflows/deploy.yml` ekle (kopyala-yapıştır)
5. ✅ `superdeploy sync -p cheapa`
6. ✅ `git push origin production`

**Toplam süre:** ~15 dakika

### Yeni Proje İçin:
1. ✅ `superdeploy init -p myapp`
2. ✅ `superdeploy up -p myapp`
3. ✅ `superdeploy sync -p myapp`
4. ✅ App repo'larını oluştur
5. ✅ `git push origin production`

**Toplam süre:** ~20 dakika

---

## 🚨 Dikkat Edilmesi Gerekenler

### ❌ YAPMA:
- Caddy route'ları manuel oluşturma (otomatik!)
- Docker compose manuel yazma (otomatik!)
- Secrets'ları hardcode etme (sync kullan!)

### ✅ YAP:
- Her zaman `config.yml`'den başla
- `superdeploy sync` kullan
- Port çakışmalarına dikkat et
- Health endpoint ekle (`/health`)

---

## 🎉 Sonuç

**Evet, her şey otomatik!** 🚀

- ✅ Caddy routes otomatik oluşur
- ✅ Docker compose otomatik oluşur
- ✅ Network'ler otomatik bağlanır
- ✅ Secrets otomatik inject edilir
- ✅ Health check otomatik çalışır
- ✅ Rollback otomatik (hata durumunda)

**Tek yapman gereken:** Config'e ekle → Kod yaz → Push et!
