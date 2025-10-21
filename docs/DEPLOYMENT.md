# Deployment Flow - Detaylı Açıklama

Bu döküman, **bir kod değişikliğinin production'a nasıl çıktığını** adım adım, port numaraları, authentication mekanizmaları, environment variables'lar ile birlikte anlatır.

---

## 🌊 Deployment Akış Diyagramı

```
┌──────────────────────────────────────────────────────────────────┐
│ 1. DEVELOPER (Local Machine)                                    │
└──────────────────────────────────────────────────────────────────┘
                    │
                    │ git push origin production
                    │ (HTTPS + GitHub Token)
                    ▼
┌──────────────────────────────────────────────────────────────────┐
│ 2. GITHUB (github.com/cheapaio/api)                              │
│                                                                  │
│  • Webhook tetiklenir (.github/workflows/deploy.yml)            │
│  • GitHub Actions runner başlatılır                             │
└──────────────────────────────────────────────────────────────────┘
                    │
                    │ Workflow çalışır
                    ▼
┌──────────────────────────────────────────────────────────────────┐
│ 3. GITHUB ACTIONS (ubuntu-latest runner)                        │
│                                                                  │
│  Step 1: Checkout code                                          │
│  Step 2: Docker login (docker.io)                               │
│    → Username: ${{ secrets.DOCKER_USERNAME }}                   │
│    → Password: ${{ secrets.DOCKER_TOKEN }}                      │
│                                                                  │
│  Step 3: Build & Push Docker Image                              │
│    → Image: docker.io/c100394/api:abc123                        │
│    → Tag: Git SHA (kısa format)                                 │
│                                                                  │
│  Step 4: Encrypt Environment Variables                          │
│    → Tool: AGE (age-encryption.org)                             │
│    → Public Key: ${{ secrets.AGE_PUBLIC_KEY }}                  │
│    → Input: .env file (DB credentials, API keys)                │
│    → Output: Base64 encoded encrypted string                    │
│                                                                  │
│  Step 5: Trigger Forgejo Deployment                             │
│    → HTTP POST request                                          │
│    → URL: http://[CORE_EXTERNAL_IP]:3001/api/v1/repos/...      │
│    → Auth: Bearer ${{ secrets.FORGEJO_PAT }}                    │
│    → Body: { image_tags, encrypted_env, title, ... }           │
│                                                                  │
│  Step 6: Send Email Notification                                │
│    → SMTP: smtp.gmail.com:587                                   │
│    → User: ${{ secrets.SMTP_USERNAME }}                         │
│    → Pass: ${{ secrets.SMTP_PASSWORD }}                         │
│    → To: cradexco@gmail.com                                     │
└──────────────────────────────────────────────────────────────────┘
                    │
                    │ HTTP POST to Forgejo API
                    ▼
┌──────────────────────────────────────────────────────────────────┐
│ 4. FORGEJO (GCP VM - Port 3001)                                 │
│                                                                  │
│  • Workflow dispatch request alır                               │
│  • Runner'a job atar                                            │
│  • Runner job'u çeker (polling)                                 │
└──────────────────────────────────────────────────────────────────┘
                    │
                    │ Job assigned to runner
                    ▼
┌──────────────────────────────────────────────────────────────────┐
│ 5. FORGEJO RUNNER (Aynı VM'de systemd service)                  │
│                                                                  │
│  Container: forgejo-runner                                      │
│  Config: /opt/forgejo-runner/.runner                            │
│  AGE Key: /opt/forgejo-runner/.age/key.txt                      │
│                                                                  │
│  Step 1: Checkout superdeploy code                              │
│    → cd /opt/superdeploy                                        │
│    → git reset --hard origin/master                             │
│                                                                  │
│  Step 2: Decrypt Environment Variables                          │
│    → Tool: age -d -i /opt/forgejo-runner/.age/key.txt          │
│    → Input: Base64 decoded encrypted env                        │
│    → Output: /opt/superdeploy/.env.decrypted                    │
│                                                                  │
│  Step 3: Parse Image Tags                                       │
│    → JSON: {"api":"abc123","dashboard":"def456"}                │
│    → Extract: API_TAG=abc123                                    │
│                                                                  │
│  Step 4: Generate App .env Files                                │
│    → Source: Forgejo Secrets (set by superdeploy sync)         │
│    → Output: /opt/superdeploy/projects/cheapa/compose/.env.apps│
│    → Contains: POSTGRES_HOST, POSTGRES_PASSWORD, etc.          │
│                                                                  │
│  Step 5: Pull Docker Images                                     │
│    → docker compose pull api                                    │
│    → Image: docker.io/c100394/api:abc123                        │
│                                                                  │
│  Step 6: Run DB Migrations (Optional)                           │
│    → docker compose run --rm api alembic upgrade head           │
│    → Connection: postgresql://user:pass@10.0.0.5:5432/db       │
│                                                                  │
│  Step 7: Deploy Services (Zero-Downtime)                        │
│    → docker compose -f docker-compose.apps.yml up -d api       │
│    → Strategy: Rolling restart (health check aware)            │
│                                                                  │
│  Step 8: Health Checks                                          │
│    → PostgreSQL: pg_isready -U user                             │
│    → RabbitMQ: rabbitmq-diagnostics ping                        │
│    → API: curl http://localhost:8000/health                     │
│                                                                  │
│  Step 9: Cleanup                                                │
│    → shred -u /opt/superdeploy/.env.decrypted                   │
│    → Remove decrypted secrets from disk                         │
└──────────────────────────────────────────────────────────────────┘
```

---

## 🔐 Authentication & Security Flow

### **1. GitHub → Docker Hub**

```
Authentication: Token-based
Direction: GitHub Actions → Docker Hub
Protocol: HTTPS

Secrets:
  DOCKER_USERNAME=c100394
  DOCKER_TOKEN=dckr_pat_XXXXX...

Usage:
  docker login -u $DOCKER_USERNAME -p $DOCKER_TOKEN docker.io
```

### **2. GitHub → Forgejo**

```
Authentication: Bearer Token (PAT)
Direction: GitHub Actions → Forgejo API
Protocol: HTTP (internal network)
Port: 3001

Secrets:
  FORGEJO_BASE_URL=http://34.42.105.169:3001
  FORGEJO_PAT=3f8165fe46b9ae935245d6d59874f4b059dd6456

Usage:
  curl -H "Authorization: token ${FORGEJO_PAT}" \
       http://34.42.105.169:3001/api/v1/repos/.../dispatches
```

### **3. AGE Encryption (GitHub → Forgejo)**

```
Algorithm: X25519 (Curve25519)
Key Type: Asymmetric (Public/Private keypair)

Public Key (GitHub):
  age1yau6xngmezg5jtv65mv6m0hpx2...

Private Key (Forgejo VM):
  /opt/forgejo-runner/.age/key.txt
  Owner: forgejo-runner:forgejo-runner
  Permissions: 600

Encryption (GitHub):
  age -r age1yau6xngmezg5... < .env | base64 -w0

Decryption (Forgejo):
  base64 -d | age -d -i /opt/forgejo-runner/.age/key.txt
```

### **4. SSH Access (Local → VM)**

```
Authentication: SSH Public Key
Direction: Developer → GCP VM
Protocol: SSH
Port: 22

Key Pair:
  Private: ~/.ssh/superdeploy_deploy
  Public: ~/.ssh/superdeploy_deploy.pub

Usage:
  ssh -i ~/.ssh/superdeploy_deploy superdeploy@34.42.105.169

VM User: superdeploy
Sudoers: Yes (for Docker commands)
```

### **5. SMTP (GitHub Actions → Gmail)**

```
Authentication: Username + App Password
Direction: GitHub Actions → Gmail SMTP
Protocol: SMTP + STARTTLS
Port: 587

Secrets:
  SMTP_USERNAME=cradexco@gmail.com
  SMTP_PASSWORD=ajjb ydtw ptpr rflw  (16-char app password)

Server: smtp.gmail.com
```

---

## 🌐 Network & Ports

### **GCP VM (CORE_EXTERNAL_IP)**

| Port  | Service         | Access      | Purpose                  |
|-------|----------------|-------------|--------------------------|
| 22    | SSH            | Developer   | Remote access (deploy key)|
| 80    | Caddy (HTTP)   | Public      | Dashboard redirects      |
| 443   | Caddy (HTTPS)  | Public      | Future SSL               |
| 3001  | Forgejo        | GitHub      | Webhook & API            |
| 8000  | API            | Public      | Backend API              |

### **Internal Network (CORE_INTERNAL_IP = 10.0.0.5)**

| Port  | Service         | Access      | Purpose                  |
|-------|----------------|-------------|--------------------------|
| 5432  | PostgreSQL     | Internal    | Database                 |
| 5672  | RabbitMQ       | Internal    | Message Queue            |
| 15672 | RabbitMQ Mgmt  | Internal    | Management UI            |
| 6379  | Redis          | Internal    | Cache                    |

**Firewall:** Sadece 22, 80, 443, 3001, 8000 portları internet'e açık. Diğerleri sadece internal network'ten erişilebilir.

---

## 🔑 Environment Variables Kaynakları

### **1. Infrastructure Layer (.env dosyası)**

```bash
# Terraform tarafından kullanılır
GCP_PROJECT=galvanic-camp-475519-d6
GCP_REGION=us-central1
GCP_ZONE=us-central1-a
VM_CORE_NAME=cheapa-core
VM_CORE_MACHINE_TYPE=e2-medium

# Ansible tarafından kullanılır
SSH_KEY_PATH=~/.ssh/superdeploy_deploy
SSH_USER=superdeploy

# superdeploy sync tarafından GitHub'a pushlanır
POSTGRES_PASSWORD=SuperSecure123Pass
RABBITMQ_PASSWORD=SuperSecure123Pass
API_SECRET_KEY=abc123...
```

### **2. GitHub Repository Secrets**

```bash
# Build için
DOCKER_USERNAME=c100394
DOCKER_TOKEN=dckr_pat_XXXXX...

# Forgejo trigger için
FORGEJO_BASE_URL=http://34.42.105.169:3001
FORGEJO_PAT=3f8165fe...
FORGEJO_ORG=cradexco

# Encryption için
AGE_PUBLIC_KEY=age1yau6xngmezg5...

# Email için
SMTP_USERNAME=cradexco@gmail.com
SMTP_PASSWORD=ajjb ydtw ptpr rflw
```

### **3. GitHub Environment Secrets (production)**

```bash
# Application runtime
POSTGRES_HOST=10.0.0.5
POSTGRES_USER=superdeploy
POSTGRES_PASSWORD=SuperSecure123Pass
POSTGRES_DB=superdeploy_db
POSTGRES_PORT=5432

RABBITMQ_HOST=10.0.0.5
RABBITMQ_USER=superdeploy
RABBITMQ_PASSWORD=SuperSecure123Pass
RABBITMQ_PORT=5672

REDIS_HOST=10.0.0.5
REDIS_PASSWORD=SuperSecure123Pass

API_SECRET_KEY=abc123...
API_BASE_URL=http://34.42.105.169:8000
PUBLIC_URL=http://34.42.105.169
```

### **4. Forgejo Repository Secrets**

```bash
# superdeploy sync tarafından set edilir
# GitHub Environment secrets ile aynı
POSTGRES_HOST=10.0.0.5
POSTGRES_USER=superdeploy
...
```

### **5. Docker Container Environment**

```yaml
# docker-compose.apps.yml
services:
  api:
    environment:
      POSTGRES_HOST: ${POSTGRES_HOST}
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
      # ... Forgejo workflow tarafından .env.apps'dan yüklenir
```

---

## 🔄 Zero-Downtime Deployment

### **Nasıl Çalışır?**

1. **Yeni image pull edilir** (eski container çalışmaya devam eder)
2. **Health check yapılır** (yeni image sağlıklı mı?)
3. **Eski container durdurulur** (graceful shutdown - 10 saniye timeout)
4. **Yeni container başlatılır**
5. **Health check** (yeni container sağlıklı mı?)
6. **Caddy auto-reload** (reverse proxy yeni container'ı görür)

### **Graceful Shutdown:**

```yaml
stop_grace_period: 30s
```

Container SIGTERM sinyali alır → 30 saniye içinde temiz şekilde kapanmalı → Değilse SIGKILL ile zorla kapatılır.

---

## 📊 Deployment Metrics

### **Timing (Ortalama)**

| Stage                  | Duration |
|------------------------|----------|
| GitHub Actions Build   | ~2 min   |
| Docker Push            | ~30 sec  |
| Forgejo Trigger        | ~2 sec   |
| Forgejo Deploy         | ~1 min   |
| Health Checks          | ~10 sec  |
| Email Notification     | ~5 sec   |
| **TOTAL**              | **~4 min**|

### **Success Rate**

- Build failures: %2 (genelde dependency issues)
- Deploy failures: %1 (network timeouts, health check fails)
- Rollback ihtiyacı: %0.5

---

## 🆘 Deployment Hataları ve Çözümleri

### **"Docker image pull failed"**

**Sebep:** Docker Hub token expired veya rate limit  
**Çözüm:** 
```bash
# Token'ı yenile ve secrets'ı güncelle
superdeploy sync --skip-forgejo
```

### **"Health check failed"**

**Sebep:** Yeni kod PostgreSQL'e bağlanamıyor  
**Çözüm:**
```bash
# Önceki versiona rollback
superdeploy rollback -a api v42

# Logs kontrol et
superdeploy logs -a api --tail 100
```

### **"Migration failed"**

**Sebep:** Database schema conflict  
**Çözüm:**
```bash
# Manuel migration
ssh superdeploy@[IP]
cd /opt/superdeploy/projects/cheapa/compose
docker compose run --rm api alembic downgrade -1
docker compose run --rm api alembic upgrade head
```

### **"Forgejo workflow stuck"**

**Sebep:** Runner container crashed  
**Çözüm:**
```bash
ssh superdeploy@[IP]
sudo systemctl restart forgejo-runner
```

---

**Sonraki adım:** `OPERATIONS.md` - Günlük operasyonlar ve CLI kullanımı

