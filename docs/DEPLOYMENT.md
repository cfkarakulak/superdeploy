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
│ 2. GITHUB (github.com/cheapaio/api)                             │
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
│    → Repository: cheapaio/api                                   │
│    → Branch: production                                         │
│                                                                  │
│  Step 2: Docker login (docker.io)                               │
│    → Username: ${{ secrets.DOCKER_USERNAME }}                   │
│    → Password: ${{ secrets.DOCKER_TOKEN }}                      │
│                                                                  │
│  Step 3: Build & Push Docker Image                              │
│    → Image: docker.io/cheapaio/api:abc123                       │
│    → Tag: Git SHA (commit hash)                                 │
│    → Cache: GitHub Actions cache                                │
│                                                                  │
│  Step 4: Merge Environment Variables                            │
│    → Read: .env (local development values)                      │
│    → Read: .env.superdeploy (production overrides)              │
│    → Process: ${VAR} placeholders → GitHub Secrets              │
│    → Merge: .env.superdeploy values override .env values        │
│    → Output: /tmp/app.env (merged environment)                  │
│                                                                  │
│  Step 5: Encrypt Environment Bundle (AGE)                       │
│    → Tool: AGE (age-encryption.org)                             │
│    → Public Key: ${{ secrets.AGE_PUBLIC_KEY }}                  │
│    → Input: /tmp/app.env (merged environment)                   │
│    → Command: cat /tmp/app.env | age -r <pubkey> | base64      │
│    → Output: Base64 encoded encrypted string                    │
│                                                                  │
│  Step 6: Trigger Forgejo Deployment                             │
│    → HTTP POST request                                          │
│    → URL: http://[CORE_EXTERNAL_IP]:3001/api/v1/repos/...      │
│    → Auth: Bearer ${{ secrets.FORGEJO_PAT }}                    │
│    → Body: {                                                    │
│         project: "cheapa",                                      │
│         service: "api",                                         │
│         image: "docker.io/cheapaio/api:abc123",                 │
│         env_bundle: "<encrypted_base64_string>",                │
│         git_sha: "abc123",                                      │
│         git_ref: "production"                                   │
│       }                                                         │
└──────────────────────────────────────────────────────────────────┘
                    │
                    │ HTTP POST to Forgejo API
                    ▼
┌──────────────────────────────────────────────────────────────────┐
│ 4. FORGEJO (GCP VM - Port 3001)                                 │
│                                                                  │
│  • Workflow dispatch request alır                               │
│  • Runner'a job atar (.forgejo/workflows/deploy.yml)            │
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
│  AGE Private Key: /opt/forgejo-runner/.age/key.txt              │
│                                                                  │
│  Step 1: Checkout superdeploy code                              │
│    → Repository: cheapa/superdeploy (Forgejo)                   │
│    → Branch: master                                             │
│                                                                  │
│  Step 2: Decrypt Environment Bundle (AGE)                       │
│    → Tool: age -d -i /opt/forgejo-runner/.age/key.txt          │
│    → Input: Base64 decoded encrypted env_bundle                 │
│    → Command: echo "$ENV_BUNDLE" | base64 -d | age -d -i key   │
│    → Output: /tmp/decrypted.env (plaintext environment)         │
│    → Contains: POSTGRES_HOST, POSTGRES_PASSWORD, etc.           │
│                                                                  │
│  Step 3: Load Environment Variables                             │
│    → Source: /tmp/decrypted.env                                 │
│    → Export: All variables to shell environment                 │
│    → Save: Variables to $GITHUB_ENV for next steps             │
│                                                                  │
│  Step 4: Docker Hub Login                                       │
│    → Username: ${{ secrets.DOCKER_USERNAME }}                   │
│    → Password: ${{ secrets.DOCKER_TOKEN }}                      │
│    → Registry: docker.io                                        │
│                                                                  │
│  Step 5: Load Project Configuration                             │
│    → Source: /opt/superdeploy/projects/cheapa/config.yml        │
│    → Parse: Service port mappings (external:internal)           │
│    → Extract: api → 8000:8000, dashboard → 80:3000             │
│                                                                  │
│  Step 6: Generate Docker Compose File                           │
│    → Template: Embedded in workflow                             │
│    → Substitute: Image, ports, networks, labels                 │
│    → Output: /opt/apps/cheapa/compose/docker-compose-api.yml    │
│    → env_file: /tmp/decrypted.env                               │
│                                                                  │
│  Step 7: Create Networks                                        │
│    → docker network create cheapa-network                       │
│    → docker network create superdeploy-proxy                    │
│                                                                  │
│  Step 8: Deploy Core Services (if needed)                       │
│    → File: /opt/superdeploy/projects/cheapa/compose/            │
│             docker-compose.core.yml                             │
│    → Services: postgres, rabbitmq, redis                        │
│    → Command: docker compose up -d --wait                       │
│                                                                  │
│  Step 9: Register with Caddy Reverse Proxy                      │
│    → Generate: /opt/superdeploy/shared/caddy/routes/            │
│                cheapa-api.caddy                                 │
│    → Content: :8000 { reverse_proxy cheapa-api:8000 }          │
│    → Restart: docker restart superdeploy-caddy                  │
│                                                                  │
│  Step 10: Backup Current Deployment                             │
│    → Inspect: Current container image tag                       │
│    → Save: For rollback if deployment fails                     │
│                                                                  │
│  Step 11: Pull Docker Image                                     │
│    → docker pull docker.io/cheapaio/api:abc123                  │
│    → Retry: 3 attempts with 5 second delay                      │
│                                                                  │
│  Step 12: Deploy Service (Zero-Downtime)                        │
│    → Command: docker compose up -d --wait                       │
│    → Strategy: Rolling restart (health check aware)             │
│    → Wait: Health check to pass (max 180 seconds)               │
│                                                                  │
│  Step 13: Health Checks                                         │
│    → Check: docker inspect --format="{{.State.Health.Status}}"  │
│    → Endpoint: http://localhost:8000/health                     │
│    → Interval: 15s, Timeout: 10s, Retries: 5                   │
│    → Start Period: 60s (grace period)                           │
│                                                                  │
│  Step 14: Cleanup Secrets                                       │
│    → rm -f /tmp/decrypted.env                                   │
│    → rm -f /tmp/encrypted.age                                   │
│    → Security: Remove plaintext secrets from disk               │
│                                                                  │
│  Step 15: Rollback on Failure (if needed)                       │
│    → Trigger: If health check fails                             │
│    → Action: Restore previous container image                   │
│    → Notify: Send alert about rollback                          │
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
  DOCKER_USERNAME=cheapaio
  DOCKER_TOKEN=dckr_pat_XXXXX...

Usage:
  docker login -u $DOCKER_USERNAME -p $DOCKER_TOKEN docker.io
```

### **2. GitHub → Forgejo**

```
Authentication: Bearer Token (PAT)
Direction: GitHub Actions → Forgejo API
Protocol: HTTP (external IP)
Port: 3001

Secrets:
  FORGEJO_BASE_URL=http://[CORE_EXTERNAL_IP]:3001
  FORGEJO_PAT=<personal_access_token>
  FORGEJO_ORG=cheapa

Usage:
  curl -X POST \
    -H "Authorization: token ${FORGEJO_PAT}" \
    -H "Content-Type: application/json" \
    ${FORGEJO_BASE_URL}/api/v1/repos/${FORGEJO_ORG}/superdeploy/actions/workflows/deploy.yml/dispatches
```

### **3. AGE Encryption (GitHub → Forgejo)**

AGE (Actually Good Encryption), environment variable'ları güvenli bir şekilde GitHub'dan Forgejo'ya iletmek için kullanılır.

```
Algorithm: X25519 (Curve25519)
Key Type: Asymmetric (Public/Private keypair)
Tool: age-encryption.org

Public Key (GitHub Secrets):
  AGE_PUBLIC_KEY=age1yau6xngmezg5jtv65mv6m0hpx2...
  Location: GitHub Repository Secrets
  Usage: Encryption only

Private Key (Forgejo VM):
  Location: /opt/forgejo-runner/.age/key.txt
  Owner: forgejo-runner:forgejo-runner
  Permissions: 600 (read-only for owner)
  Usage: Decryption only

Encryption Process (GitHub Actions):
  1. Merge .env + .env.superdeploy → /tmp/app.env
  2. cat /tmp/app.env | age -r ${AGE_PUBLIC_KEY} > encrypted.age
  3. base64 -w 0 encrypted.age > encrypted.txt
  4. Send encrypted.txt to Forgejo via API

Decryption Process (Forgejo Runner):
  1. Receive encrypted base64 string
  2. echo "$ENV_BUNDLE" | base64 -d > encrypted.age
  3. age -d -i /opt/forgejo-runner/.age/key.txt encrypted.age > /tmp/decrypted.env
  4. source /tmp/decrypted.env
  5. rm /tmp/decrypted.env (cleanup)

Security Benefits:
  ✅ End-to-end encryption (GitHub → Forgejo)
  ✅ Private key never leaves VM
  ✅ Secrets not exposed in logs or API calls
  ✅ Automatic cleanup after deployment
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
  ssh -i ~/.ssh/superdeploy_deploy superdeploy@[CORE_EXTERNAL_IP]

VM User: superdeploy
Sudoers: Yes (for Docker commands)
```

---

## 🌐 Network & Ports

### **GCP VM (CORE_EXTERNAL_IP)**

| Port  | Service         | Access      | Purpose                  |
|-------|----------------|-------------|--------------------------|
| 22    | SSH            | Developer   | Remote access (deploy key)|
| 80    | Caddy (HTTP)   | Public      | Dashboard (root domain)  |
| 443   | Caddy (HTTPS)  | Public      | Future SSL               |
| 3001  | Forgejo        | GitHub      | Webhook & API            |
| 8000  | API            | Public      | Backend API (via Caddy)  |

### **Internal Network (CORE_INTERNAL_IP = 10.0.0.5)**

| Port  | Service         | Access      | Purpose                  |
|-------|----------------|-------------|--------------------------|
| 5432  | PostgreSQL     | Internal    | Database                 |
| 5672  | RabbitMQ       | Internal    | Message Queue            |
| 15672 | RabbitMQ Mgmt  | Internal    | Management UI            |
| 6379  | Redis          | Internal    | Cache                    |

### **Docker Networks**

```
cheapa-network (bridge)
  ├── cheapa-postgres
  ├── cheapa-rabbitmq
  ├── cheapa-redis
  ├── cheapa-api
  └── cheapa-dashboard

superdeploy-proxy (bridge)
  ├── superdeploy-caddy (reverse proxy)
  ├── cheapa-api (connected to both networks)
  └── cheapa-dashboard (connected to both networks)
```

**Firewall:** Sadece 22, 80, 443, 3001, 8000 portları internet'e açık. Diğerleri sadece internal network'ten erişilebilir.

---

## 🔑 Environment Variables Akışı

Environment variable'lar, local development'tan production container'lara kadar birçok katmandan geçer. Bu bölüm, her katmanın rolünü ve değerlerin nasıl merge edildiğini açıklar.

### **1. Local Development (.env)**

```bash
# app-repos/api/.env
# Developer'ın local environment'ı
# ⚠️ SuperDeploy bu dosyayı ASLA değiştirmez

POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_USER=dev_user
POSTGRES_PASSWORD=dev_password
POSTGRES_DB=dev_db

API_SECRET_KEY=local_dev_secret
DEBUG=true
```

**Amaç:** Local development için kullanılır  
**Değiştirilir mi:** Hayır, developer tarafından manuel olarak düzenlenir  
**Commit edilir mi:** Hayır (.gitignore'da)

### **2. Production Overrides (.env.superdeploy)**

```bash
# app-repos/api/.env.superdeploy
# SuperDeploy tarafından otomatik generate edilir
# Production değerleri için placeholder'lar içerir

# PostgreSQL relational database
POSTGRES_HOST=${POSTGRES_HOST}
POSTGRES_PORT=5432
POSTGRES_USER=cheapa_user
POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
POSTGRES_DB=cheapa_db

# RabbitMQ message broker
RABBITMQ_HOST=${RABBITMQ_HOST}
RABBITMQ_PORT=5672
RABBITMQ_DEFAULT_USER=cheapa_user
RABBITMQ_DEFAULT_PASS=${RABBITMQ_DEFAULT_PASS}
RABBITMQ_DEFAULT_VHOST=cheapa_vhost
```

**Amaç:** Production değerlerini override etmek  
**Değiştirilir mi:** Evet, `superdeploy generate` komutu ile  
**Commit edilir mi:** Evet (placeholder'lar içerir, gerçek değerler yok)  
**Placeholder'lar:** `${VAR}` formatındaki değerler GitHub Secrets'tan doldurulur

### **3. GitHub Repository Secrets**

```bash
# GitHub Repository → Settings → Secrets → Actions

# Build için
DOCKER_USERNAME=cheapaio
DOCKER_TOKEN=dckr_pat_XXXXX...

# Forgejo trigger için
FORGEJO_BASE_URL=http://[CORE_EXTERNAL_IP]:3001
FORGEJO_PAT=<personal_access_token>
FORGEJO_ORG=cheapa

# Encryption için
AGE_PUBLIC_KEY=age1yau6xngmezg5...
```

**Amaç:** GitHub Actions workflow'u için gerekli secrets  
**Nasıl set edilir:** `superdeploy sync` komutu ile otomatik  
**Kullanım:** Docker build, Forgejo trigger, AGE encryption

### **4. GitHub Environment Secrets (production)**

```bash
# GitHub Repository → Settings → Environments → production → Secrets

# Core services (superdeploy sync tarafından set edilir)
POSTGRES_HOST=10.0.0.5
POSTGRES_PORT=5432
POSTGRES_USER=cheapa_user
POSTGRES_PASSWORD=<auto_generated>
POSTGRES_DB=cheapa_db

RABBITMQ_HOST=10.0.0.5
RABBITMQ_PORT=5672
RABBITMQ_DEFAULT_USER=cheapa_user
RABBITMQ_DEFAULT_PASS=<auto_generated>
RABBITMQ_DEFAULT_VHOST=cheapa_vhost

# Forgejo credentials
FORGEJO_ADMIN_USER=admin
FORGEJO_ADMIN_PASSWORD=<auto_generated>
FORGEJO_DB_PASSWORD=<auto_generated>
FORGEJO_SECRET_KEY=<auto_generated>
FORGEJO_INTERNAL_TOKEN=<auto_generated>
```

**Amaç:** Runtime application secrets  
**Nasıl set edilir:** `superdeploy sync` komutu ile otomatik  
**Kullanım:** .env.superdeploy placeholder'larını doldurmak

### **5. Merge Process (GitHub Actions)**

GitHub Actions workflow'u, deployment sırasında iki dosyayı merge eder:

```python
# .github/workflows/deploy.yml içinde
env_vars = {}

# 1. Read .env (local development values)
if Path('.env').exists():
    with open('.env') as f:
        for line in f:
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                env_vars[key] = value

# 2. Override with .env.superdeploy (production values)
if Path('.env.superdeploy').exists():
    with open('.env.superdeploy') as f:
        for line in f:
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                # Replace ${VAR} with GitHub Secret
                if value.startswith('${') and value.endswith('}'):
                    var_name = value[2:-1]
                    value = os.environ.get(var_name, '')
                env_vars[key] = value  # OVERRIDE

# 3. Write merged file
with open('/tmp/app.env', 'w') as f:
    for key, value in env_vars.items():
        f.write(f'{key}={value}\n')
```

**Merge Priority:**
1. .env değerleri önce okunur (base values)
2. .env.superdeploy değerleri override eder (production values)
3. ${VAR} placeholder'lar GitHub Secrets ile doldurulur

**Örnek Merge:**

```bash
# .env
POSTGRES_HOST=localhost
POSTGRES_PASSWORD=dev_password
DEBUG=true

# .env.superdeploy
POSTGRES_HOST=${POSTGRES_HOST}
POSTGRES_PASSWORD=${POSTGRES_PASSWORD}

# GitHub Secrets
POSTGRES_HOST=10.0.0.5
POSTGRES_PASSWORD=SuperSecure123Pass

# Merged Result (/tmp/app.env)
POSTGRES_HOST=10.0.0.5          # .env.superdeploy override
POSTGRES_PASSWORD=SuperSecure123Pass  # .env.superdeploy override
DEBUG=true                       # .env (not overridden)
```

### **6. Encrypted Bundle (AGE)**

Merge edilen environment, AGE ile şifrelenir:

```bash
# Encryption (GitHub Actions)
cat /tmp/app.env | age -r ${AGE_PUBLIC_KEY} | base64 -w 0 > encrypted.txt

# Forgejo'ya gönderilen payload
{
  "env_bundle": "<base64_encrypted_string>"
}
```

### **7. Forgejo Repository Secrets**

```bash
# Forgejo → Settings → Secrets

# Docker Hub credentials (superdeploy sync tarafından set edilir)
DOCKER_USERNAME=cheapaio
DOCKER_TOKEN=dckr_pat_XXXXX...
```

**Amaç:** Forgejo runner'ın Docker Hub'a login olması  
**Nasıl set edilir:** `superdeploy sync` komutu ile otomatik

### **8. Decrypted Environment (Forgejo Runner)**

```bash
# Forgejo Runner workflow'u
echo "$ENV_BUNDLE" | base64 -d | age -d -i /opt/forgejo-runner/.age/key.txt > /tmp/decrypted.env

# /tmp/decrypted.env içeriği (plaintext)
POSTGRES_HOST=10.0.0.5
POSTGRES_PASSWORD=SuperSecure123Pass
DEBUG=true
...
```

### **9. Docker Container Environment**

```yaml
# /opt/apps/cheapa/compose/docker-compose-api.yml
services:
  cheapa-api:
    image: docker.io/cheapaio/api:abc123
    env_file:
      - /tmp/decrypted.env  # Decrypted environment loaded here
    networks:
      - cheapa-network
      - superdeploy-proxy
```

**Container içinde:**
```bash
$ docker exec cheapa-api env | grep POSTGRES
POSTGRES_HOST=10.0.0.5
POSTGRES_PASSWORD=SuperSecure123Pass
POSTGRES_DB=cheapa_db
```

---

## 📊 Environment Variables Flow Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│ LOCAL DEVELOPMENT                                               │
├─────────────────────────────────────────────────────────────────┤
│ .env (not committed)                                            │
│   POSTGRES_HOST=localhost                                       │
│   POSTGRES_PASSWORD=dev_password                                │
│   DEBUG=true                                                    │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ git push (only code, not .env)
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ GITHUB REPOSITORY                                               │
├─────────────────────────────────────────────────────────────────┤
│ .env.superdeploy (committed)                                    │
│   POSTGRES_HOST=${POSTGRES_HOST}                                │
│   POSTGRES_PASSWORD=${POSTGRES_PASSWORD}                        │
│                                                                 │
│ GitHub Secrets (set by superdeploy sync)                        │
│   POSTGRES_HOST=10.0.0.5                                        │
│   POSTGRES_PASSWORD=SuperSecure123Pass                          │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ GitHub Actions Workflow
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ MERGE PROCESS                                                   │
├─────────────────────────────────────────────────────────────────┤
│ 1. Read .env → base values                                      │
│ 2. Read .env.superdeploy → override values                      │
│ 3. Replace ${VAR} → GitHub Secrets                              │
│ 4. Write /tmp/app.env → merged result                           │
│                                                                 │
│ Result:                                                         │
│   POSTGRES_HOST=10.0.0.5                                        │
│   POSTGRES_PASSWORD=SuperSecure123Pass                          │
│   DEBUG=true                                                    │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ AGE Encryption
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ ENCRYPTED BUNDLE                                                │
├─────────────────────────────────────────────────────────────────┤
│ cat /tmp/app.env | age -r <pubkey> | base64                    │
│ → Base64 encoded encrypted string                               │
│ → Sent to Forgejo via API                                       │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ HTTP POST to Forgejo
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ FORGEJO RUNNER                                                  │
├─────────────────────────────────────────────────────────────────┤
│ 1. Receive encrypted bundle                                     │
│ 2. base64 -d → decrypt base64                                   │
│ 3. age -d -i key.txt → decrypt AGE                              │
│ 4. Write /tmp/decrypted.env → plaintext                         │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ Docker Compose
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ DOCKER CONTAINER                                                │
├─────────────────────────────────────────────────────────────────┤
│ env_file: /tmp/decrypted.env                                    │
│                                                                 │
│ Container Environment:                                          │
│   POSTGRES_HOST=10.0.0.5                                        │
│   POSTGRES_PASSWORD=SuperSecure123Pass                          │
│   DEBUG=true                                                    │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🔐 AGE Encryption & Decryption Detayları

AGE (Actually Good Encryption), environment variable'ları güvenli bir şekilde GitHub'dan Forgejo'ya iletmek için kullanılan modern bir encryption tool'udur.

### **Neden AGE?**

- ✅ Modern ve güvenli (X25519 Curve25519 algoritması)
- ✅ Basit kullanım (tek komut ile encrypt/decrypt)
- ✅ Asymmetric encryption (public key ile şifrele, private key ile çöz)
- ✅ Küçük ve hızlı (Go ile yazılmış, tek binary)
- ✅ Secrets log'larda görünmez

### **Key Pair Oluşturma**

```bash
# superdeploy init sırasında otomatik oluşturulur
age-keygen -o /opt/forgejo-runner/.age/key.txt

# Output:
# Public key: age1yau6xngmezg5jtv65mv6m0hpx2...
# Private key: /opt/forgejo-runner/.age/key.txt
```

**Public Key:**
- GitHub Secrets'a kaydedilir (`AGE_PUBLIC_KEY`)
- Encryption için kullanılır
- Paylaşılabilir (public)

**Private Key:**
- Forgejo Runner VM'de saklanır (`/opt/forgejo-runner/.age/key.txt`)
- Decryption için kullanılır
- Asla paylaşılmaz (private)
- Permissions: 600 (sadece owner okuyabilir)

### **Encryption Process (GitHub Actions)**

```bash
# Step 1: Merge .env + .env.superdeploy
python3 merge_env.py > /tmp/app.env

# Step 2: Encrypt with AGE
cat /tmp/app.env | age -r ${AGE_PUBLIC_KEY} > /tmp/encrypted.age

# Step 3: Base64 encode (for JSON transport)
base64 -w 0 /tmp/encrypted.age > /tmp/encrypted.txt

# Step 4: Send to Forgejo
ENCRYPTED=$(cat /tmp/encrypted.txt)
curl -X POST \
  -H "Authorization: token ${FORGEJO_PAT}" \
  -H "Content-Type: application/json" \
  -d "{\"inputs\": {\"env_bundle\": \"${ENCRYPTED}\"}}" \
  ${FORGEJO_BASE_URL}/api/v1/repos/.../dispatches

# Step 5: Cleanup
rm -f /tmp/app.env /tmp/encrypted.age /tmp/encrypted.txt
```

**Güvenlik:**
- Plaintext .env dosyası hemen siliniyor
- Encrypted data JSON içinde güvenli şekilde taşınıyor
- Log'larda sadece encrypted string görünüyor

### **Decryption Process (Forgejo Runner)**

```bash
# Step 1: Receive encrypted bundle from API
ENV_BUNDLE="${{ inputs.env_bundle }}"

# Step 2: Base64 decode
echo "$ENV_BUNDLE" | base64 -d > /tmp/encrypted.age

# Step 3: Decrypt with AGE
age -d -i /opt/forgejo-runner/.age/key.txt /tmp/encrypted.age > /tmp/decrypted.env

# Step 4: Load environment variables
set -a
source /tmp/decrypted.env
set +a

# Step 5: Use in Docker Compose
docker compose --env-file /tmp/decrypted.env up -d

# Step 6: Cleanup (CRITICAL!)
rm -f /tmp/decrypted.env /tmp/encrypted.age
```

**Güvenlik:**
- Private key VM'den asla çıkmıyor
- Decrypted file sadece deployment sırasında var
- Deployment sonrası hemen siliniyor
- Disk'te plaintext secret kalmıyor

### **Security Best Practices**

```bash
# Private key permissions
chmod 600 /opt/forgejo-runner/.age/key.txt
chown forgejo-runner:forgejo-runner /opt/forgejo-runner/.age/key.txt

# Temporary file cleanup
trap 'rm -f /tmp/decrypted.env /tmp/encrypted.age' EXIT

# Secure delete (optional, for paranoid mode)
shred -u /tmp/decrypted.env
```

### **Troubleshooting**

**Problem:** "age: error: no identity matched any of the recipients"

```bash
# Çözüm: Public key ve private key eşleşmiyor
# Public key'i kontrol et
cat /opt/forgejo-runner/.age/key.txt | grep "public key:"

# GitHub Secrets'taki AGE_PUBLIC_KEY ile karşılaştır
```

**Problem:** "age: error: failed to decrypt"

```bash
# Çözüm: Encrypted data bozulmuş olabilir
# Base64 decode'u kontrol et
echo "$ENV_BUNDLE" | base64 -d | file -
# Output: data (binary file expected)
```

**Problem:** "Permission denied: /opt/forgejo-runner/.age/key.txt"

```bash
# Çözüm: File permissions yanlış
sudo chmod 600 /opt/forgejo-runner/.age/key.txt
sudo chown forgejo-runner:forgejo-runner /opt/forgejo-runner/.age/key.txt
```

---

## 🔄 Parameter Passing: GitHub Actions → Forgejo

GitHub Actions'dan Forgejo'ya parametre geçişi, HTTP POST request ile yapılır.

### **GitHub Actions Workflow**

```yaml
# .github/workflows/deploy.yml
- name: Trigger Forgejo deployment
  run: |
    curl -X POST \
      -H "Authorization: token ${{ secrets.FORGEJO_PAT }}" \
      -H "Content-Type: application/json" \
      -d '{
        "ref": "master",
        "inputs": {
          "project": "cheapa",
          "service": "api",
          "image": "${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}:${{ github.sha }}",
          "env_bundle": "${{ steps.env_bundle.outputs.encrypted }}",
          "git_sha": "${{ github.sha }}",
          "git_ref": "production"
        }
      }' \
      "${{ secrets.FORGEJO_BASE_URL }}/api/v1/repos/${{ secrets.FORGEJO_ORG }}/superdeploy/actions/workflows/deploy.yml/dispatches"
```

### **Forgejo Workflow Input**

```yaml
# .forgejo/workflows/deploy.yml
on:
  workflow_dispatch:
    inputs:
      project:
        description: 'Project name (e.g., cheapa, myapp)'
        required: true
        type: string
      service:
        description: 'Service name (e.g., api, dashboard, services)'
        required: true
        type: string
      image:
        description: 'Docker image with tag (e.g., docker.io/cheapaio/api:abc123)'
        required: true
        type: string
      env_bundle:
        description: 'AGE-encrypted environment variables bundle'
        required: true
        type: string
      git_sha:
        description: 'Git commit SHA (for tracking)'
        required: true
        type: string
      git_ref:
        description: 'Git ref (branch/tag)'
        required: false
        default: 'production'
        type: string
```

### **Parameter Flow**

```
GitHub Actions                    Forgejo Workflow
─────────────                     ────────────────

project: "cheapa"          →      ${{ inputs.project }}
service: "api"             →      ${{ inputs.service }}
image: "docker.io/..."     →      ${{ inputs.image }}
env_bundle: "<encrypted>"  →      ${{ inputs.env_bundle }}
git_sha: "abc123"          →      ${{ inputs.git_sha }}
git_ref: "production"      →      ${{ inputs.git_ref }}
```

### **Forgejo Workflow Usage**

```yaml
jobs:
  deploy:
    runs-on: [self-hosted, linux]
    
    env:
      PROJECT: ${{ inputs.project }}
      SERVICE: ${{ inputs.service }}
      IMAGE: ${{ inputs.image }}
      ENV_BUNDLE: ${{ inputs.env_bundle }}
      GIT_SHA: ${{ inputs.git_sha }}
      GIT_REF: ${{ inputs.git_ref }}
    
    steps:
      - name: Decrypt environment bundle
        run: |
          echo "${{ env.ENV_BUNDLE }}" | base64 -d > /tmp/encrypted.age
          age -d -i /opt/forgejo-runner/.age/key.txt /tmp/encrypted.age > /tmp/decrypted.env
      
      - name: Deploy service
        run: |
          cd /opt/apps/${{ env.PROJECT }}/compose
          docker compose -f docker-compose-${{ env.SERVICE }}.yml up -d
```

### **API Endpoint**

```
POST /api/v1/repos/{owner}/{repo}/actions/workflows/{workflow}/dispatches

Headers:
  Authorization: token <FORGEJO_PAT>
  Content-Type: application/json

Body:
{
  "ref": "master",
  "inputs": {
    "key": "value",
    ...
  }
}

Response:
  204 No Content (success)
  401 Unauthorized (invalid PAT)
  404 Not Found (workflow not found)
```

### **Debugging Parameter Passing**

```bash
# Forgejo workflow içinde
- name: Debug inputs
  run: |
    echo "Project: ${{ inputs.project }}"
    echo "Service: ${{ inputs.service }}"
    echo "Image: ${{ inputs.image }}"
    echo "Git SHA: ${{ inputs.git_sha }}"
    echo "Env bundle length: ${#ENV_BUNDLE}"
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
superdeploy logs -p myproject -a api --tail 100
```

### **"Migration failed"**

**Sebep:** Database schema conflict  
**Çözüm:**
```bash
# Manuel migration
ssh superdeploy@[IP]
cd /opt/apps/myproject/compose
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

## 🔧 Forgejo Workflow Implementation

Forgejo workflow'u, GitHub Actions'dan gelen deployment request'lerini işler ve container'ları deploy eder.

### **Workflow Dosyası**

```yaml
# superdeploy/.forgejo/workflows/deploy.yml
name: Deploy Service

on:
  workflow_dispatch:
    inputs:
      project: string (required)
      service: string (required)
      image: string (required)
      env_bundle: string (required)
      git_sha: string (required)
      git_ref: string (optional, default: production)

jobs:
  deploy:
    runs-on: [self-hosted, linux]
```

### **Workflow Steps**

**1. Checkout superdeploy repo**
```yaml
- name: Checkout superdeploy repo
  uses: actions/checkout@v4
```
Forgejo'daki superdeploy repository'sini checkout eder (project configuration için).

**2. Decrypt environment bundle**
```yaml
- name: Decrypt environment bundle
  run: |
    echo "${{ env.ENV_BUNDLE }}" | base64 -d > /tmp/encrypted.age
    age -d -i /opt/forgejo-runner/.age/key.txt /tmp/encrypted.age > /tmp/decrypted.env
```
GitHub'dan gelen encrypted environment'ı decrypt eder.

**3. Load environment variables**
```yaml
- name: Load environment variables
  run: |
    set -a
    source /tmp/decrypted.env
    set +a
    grep -v '^#' /tmp/decrypted.env | grep -v '^$' >> $GITHUB_ENV
```
Decrypted environment'ı shell'e ve sonraki step'lere yükler.

**4. Login to Docker Hub**
```yaml
- name: Login to Docker Hub
  run: |
    echo "${{ secrets.DOCKER_TOKEN }}" | docker login docker.io -u "${{ secrets.DOCKER_USERNAME }}" --password-stdin
```
Docker image'ları pull edebilmek için Docker Hub'a login olur.

**5. Load project configuration**
```yaml
- name: Load project configuration
  run: |
    CONFIG_FILE="/opt/superdeploy/projects/${{ env.PROJECT }}/config.yml"
    PORTS_OUTPUT=$(python3 .forgejo/scripts/parse_config.py "$CONFIG_FILE" "${{ env.SERVICE }}")
    read EXTERNAL_PORT INTERNAL_PORT <<< "$PORTS_OUTPUT"
```
Project configuration'dan service port mapping'lerini okur.

**6. Generate docker-compose file**
```yaml
- name: Generate docker-compose for service
  run: |
    mkdir -p /opt/apps/${{ env.PROJECT }}/compose
    cat > /opt/apps/${{ env.PROJECT }}/compose/docker-compose-${{ env.SERVICE }}.yml <<'EOF'
    version: '3.8'
    services:
      SERVICE_NAME:
        image: IMAGE_PLACEHOLDER
        env_file: /tmp/decrypted.env
        networks:
          - PROJECT_NETWORK
          - superdeploy-proxy
    EOF
    # Replace placeholders...
```
Service için docker-compose file'ı generate eder.

**7. Create networks**
```yaml
- name: Create networks first
  run: |
    docker network create ${{ env.PROJECT }}-network || true
    docker network create superdeploy-proxy || true
```
Docker network'leri oluşturur (yoksa).

**8. Deploy core services**
```yaml
- name: Deploy core services first
  run: |
    CORE_COMPOSE="/opt/superdeploy/projects/${{ env.PROJECT }}/compose/docker-compose.core.yml"
    if [ -f "$CORE_COMPOSE" ]; then
      cd /opt/superdeploy/projects/${{ env.PROJECT }}/compose
      docker compose -f docker-compose.core.yml up -d --wait
    fi
```
PostgreSQL, RabbitMQ, Redis gibi core service'leri deploy eder.

**9. Register with Caddy**
```yaml
- name: Register service with Caddy
  run: |
    cat > /opt/superdeploy/shared/caddy/routes/${{ env.PROJECT }}-${{ env.SERVICE }}.caddy <<EOF
    :${EXTERNAL_PORT} {
      reverse_proxy ${{ env.PROJECT }}-${{ env.SERVICE }}:${INTERNAL_PORT}
    }
    EOF
    docker restart superdeploy-caddy
```
Service'i Caddy reverse proxy'ye register eder.

**10. Backup current deployment**
```yaml
- name: Backup current deployment
  run: |
    CURRENT_IMAGE=$(docker inspect ${{ env.PROJECT }}-${{ env.SERVICE }} --format '{{.Config.Image}}' 2>/dev/null || echo "none")
```
Rollback için mevcut image'ı backup'lar.

**11. Deploy service**
```yaml
- name: Deploy service
  run: |
    cd /opt/apps/${{ env.PROJECT }}/compose
    docker pull ${{ env.IMAGE }}
    docker compose -f docker-compose-${{ env.SERVICE }}.yml up -d --wait
```
Yeni image'ı pull eder ve deploy eder.

**12. Health checks**
```yaml
- name: Deploy service
  run: |
    TIMEOUT=180
    while [ $ELAPSED -lt $TIMEOUT ]; do
      STATUS=$(docker inspect --format="{{.State.Health.Status}}" ${{ env.PROJECT }}-${{ env.SERVICE }})
      if [ "$STATUS" = "healthy" ]; then
        break
      fi
      sleep 5
    done
```
Container'ın healthy olmasını bekler (max 180 saniye).

**13. Rollback on failure**
```yaml
- name: Rollback on failure
  if: failure() && steps.backup.outputs.current_image != 'none'
  run: |
    docker run -d --name ${{ env.PROJECT }}-${{ env.SERVICE }} "$ROLLBACK_IMAGE"
```
Deployment başarısız olursa önceki versiona rollback yapar.

**14. Cleanup secrets**
```yaml
- name: Clean up secrets
  if: always()
  run: |
    rm -f /tmp/decrypted.env
    rm -f /tmp/encrypted.age
```
Temporary secret file'ları siler.

### **Workflow Execution Flow**

```
GitHub Actions Trigger
        ↓
Forgejo API receives POST request
        ↓
Forgejo assigns job to runner
        ↓
Runner polls and picks up job
        ↓
Checkout superdeploy repo
        ↓
Decrypt environment bundle (AGE)
        ↓
Load environment variables
        ↓
Login to Docker Hub
        ↓
Load project configuration
        ↓
Generate docker-compose file
        ↓
Create Docker networks
        ↓
Deploy core services (postgres, rabbitmq, redis)
        ↓
Register with Caddy reverse proxy
        ↓
Backup current deployment
        ↓
Pull new Docker image
        ↓
Deploy service (zero-downtime)
        ↓
Wait for health check (max 180s)
        ↓
Cleanup secrets
        ↓
Success! (or Rollback on failure)
```

### **Configuration Helper Script**

```python
# .forgejo/scripts/parse_config.py
import sys
import yaml

config_file = sys.argv[1]
service_name = sys.argv[2]

with open(config_file) as f:
    config = yaml.safe_load(f)

apps = config.get('apps', {})
service = apps.get(service_name, {})

external_port = service.get('port', 8000)
internal_port = service.get('internal_port', external_port)

print(f"{external_port} {internal_port}")
```

Bu script, project configuration'dan service port mapping'lerini parse eder.

### **Forgejo Runner Setup**

```bash
# Runner systemd service
/etc/systemd/system/forgejo-runner.service

[Unit]
Description=Forgejo Actions Runner
After=docker.service

[Service]
Type=simple
User=forgejo-runner
WorkingDirectory=/opt/forgejo-runner
ExecStart=/usr/local/bin/forgejo-runner daemon
Restart=always

[Install]
WantedBy=multi-user.target
```

**Runner Configuration:**
```yaml
# /opt/forgejo-runner/.runner
log:
  level: info

runner:
  name: cheapa-runner
  capacity: 1
  labels:
    - "self-hosted:docker://node:16-bullseye"
    - "linux:docker://node:16-bullseye"

cache:
  enabled: true
  dir: /opt/forgejo-runner/.cache

container:
  network: host
  privileged: false
  options: -v /var/run/docker.sock:/var/run/docker.sock
```

---

## 📦 Addon System ve Forgejo

Forgejo, SuperDeploy addon sistemi üzerinden deploy edilir. Bu, Forgejo'nun diğer addon'lar (PostgreSQL, RabbitMQ, Redis) ile aynı pattern'i takip ettiği anlamına gelir.

### **Forgejo Addon Yapısı**

```
superdeploy/addons/forgejo/
├── addon.yml              # Addon metadata
├── env.yml                # Environment variable definitions
├── ansible.yml            # Deployment tasks
├── compose.yml.j2         # Docker compose template
├── tasks/
│   ├── setup-admin.yml    # Admin user setup
│   ├── setup-runner.yml   # Runner registration
│   └── setup-secrets.yml  # Secret synchronization
└── templates/
    ├── forgejo.env.j2     # Environment file template
    └── runner-config.yml.j2  # Runner config template
```

### **Project Configuration**

```yaml
# projects/cheapa/project.yml
infrastructure:
  forgejo:
    version: "13"
    port: 3001
    ssh_port: 2222
    admin_user: "admin"
    admin_email: "admin@cheapa.local"
    org: "cheapa"
    repo: "superdeploy"
```

### **Deployment Process**

```bash
# 1. superdeploy up komutu çalıştırılır
superdeploy up -p cheapa

# 2. Ansible addon-deployer role çalışır
# → addons/forgejo/addon.yml okunur
# → addons/forgejo/env.yml + project.yml merge edilir
# → addons/forgejo/compose.yml.j2 render edilir
# → addons/forgejo/ansible.yml tasks çalıştırılır

# 3. Forgejo container başlatılır
docker compose -f docker-compose.core.yml up -d forgejo

# 4. Admin user oluşturulur
docker exec cheapa-forgejo forgejo admin user create \
  --username admin \
  --password *** \
  --email admin@cheapa.local \
  --admin

# 5. Runner register edilir
forgejo-runner register \
  --instance http://localhost:3001 \
  --token *** \
  --name cheapa-runner

# 6. Secrets sync edilir
superdeploy sync -p cheapa
```

### **Avantajlar**

✅ **Consistent pattern:** Tüm addon'lar aynı yapıyı takip eder  
✅ **Dynamic configuration:** project.yml'de değişiklik yap, redeploy  
✅ **Multi-project support:** Her proje kendi Forgejo instance'ına sahip olabilir  
✅ **No code changes:** Konfigürasyon değişikliği için kod değişikliği gerekmez  
✅ **Automated setup:** Admin user, runner, secrets otomatik configure edilir

---

**Sonraki adım:** `OPERATIONS.md` - Günlük operasyonlar ve CLI kullanımı

