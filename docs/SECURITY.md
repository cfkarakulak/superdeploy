# SuperDeploy Security Guide

Security best practices and architecture for SuperDeploy.

---

## 🔐 Security Architecture

### Multi-Layer Defense

SuperDeploy implements **defense in depth** with multiple security layers:

```
┌─────────────────────────────────────────────────────────────────┐
│ Layer 1: Secret Management (GitHub Encrypted Storage)          │
├─────────────────────────────────────────────────────────────────┤
│ Layer 2: Access Control (SSH Keys, GitHub PAT, Runner Labels)  │
├─────────────────────────────────────────────────────────────────┤
│ Layer 3: Network Isolation (Docker Networks, VM Firewalls)     │
├─────────────────────────────────────────────────────────────────┤
│ Layer 4: Runner Validation (.project file, Label matching)     │
├─────────────────────────────────────────────────────────────────┤
│ Layer 5: Audit & Monitoring (GitHub Actions logs, VM logs)     │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🔑 Secret Management

### Secret Storage

**Never store secrets in:**
- ❌ Git repositories
- ❌ Plain text files
- ❌ Environment variables in Dockerfile
- ❌ Docker image layers

**Always store secrets in:**
- ✅ `secrets.yml` (local, gitignored)
- ✅ GitHub Secrets (encrypted at rest)
- ✅ Environment variables (runtime only)

### Secret Hierarchy

```yaml
# secrets.yml
secrets:
  shared:                     # Shared across all apps
    DOCKER_TOKEN: xxx         # Never commit!
  
  api:                        # App-specific
    DATABASE_URL: xxx         # Merged with shared
```

**Priority:** `app-specific > shared`

### Secret Sync

```bash
# Sync to GitHub (encrypted)
superdeploy myproject:sync

# Creates:
# - Repository Secrets (build-time: Docker credentials)
# - Environment Secrets (runtime: app configuration)
```

**Security features:**
- ✅ Encrypted at rest in GitHub
- ✅ Encrypted in transit (HTTPS)
- ✅ Access controlled by GitHub permissions
- ✅ Audit log in GitHub

### Secret Rotation

**Recommended schedule:**
- **Every 90 days:** Rotate all passwords
- **Immediately:** If compromised or exposed
- **After team changes:** When people leave

**Rotation process:**

```bash
# 1. Update secrets.yml
vim projects/myproject/secrets.yml

# 2. Sync to GitHub
superdeploy myproject:sync

# 3. Restart containers (picks up new secrets)
ssh superdeploy@<VM_IP>
docker compose restart api
```

---

## 🔒 Access Control

### SSH Access

**Best practices:**

```bash
# 1. Use ED25519 keys (strongest)
ssh-keygen -t ed25519 -f ~/.ssh/superdeploy -C "superdeploy"

# 2. Use passphrase (production)
# Enter passphrase when prompted

# 3. Restrict permissions
chmod 600 ~/.ssh/superdeploy
chmod 644 ~/.ssh/superdeploy.pub

# 4. Use ssh-agent
eval "$(ssh-agent -s)"
ssh-add ~/.ssh/superdeploy

# 5. Disable password auth on VMs
# Ansible automatically does this
```

**VM SSH Configuration:**

```bash
# /etc/ssh/sshd_config (Ansible sets this)
PermitRootLogin no
PasswordAuthentication no
PubkeyAuthentication yes
ChallengeResponseAuthentication no
```

### GitHub Access

**Personal Access Token (PAT):**

```bash
# Minimum required scopes:
# - repo (full control of private repositories)
# - workflow (update GitHub Action workflows)

# Create PAT:
# https://github.com/settings/tokens/new

# Use in CLI
gh auth login --with-token < pat-token.txt

# Never commit PAT!
```

### Runner Tokens

**GitHub runner registration (automatic):**

```bash
# No manual token needed! Ansible automatically:
# 1. Uses REPOSITORY_TOKEN to call GitHub API
# 2. Gets registration token from: POST /orgs/{org}/actions/runners/registration-token
# 3. Registers runner with the token
# 4. Runner gets persistent authentication after registration

# Just run:
superdeploy myproject:up

# REPOSITORY_TOKEN must have 'admin:org' scope for runner management
```

---

## 🌐 Network Security

### Docker Network Isolation

**Project-specific networks:**

```yaml
# docker-compose.yml
networks:
  myproject-network:
    driver: bridge
    ipam:
      config:
        - subnet: 172.30.0.0/24
```

**Benefits:**
- ✅ Projects cannot communicate
- ✅ No port conflicts
- ✅ Clean subnet allocation
- ✅ Easy to firewall

### VM Firewall Rules

**GCP firewall (Terraform):**

```hcl
# Allow SSH from anywhere (or restrict to your IPs)
allow {
  protocol = "tcp"
  ports    = ["22"]
}

# Allow HTTP/HTTPS (for apps)
allow {
  protocol = "tcp"
  ports    = ["80", "443"]
}

# Block all other inbound traffic
```

**iptables (Ansible):**

```bash
# Default: Deny all inbound
iptables -P INPUT DROP

# Allow established connections
iptables -A INPUT -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT

# Allow SSH
iptables -A INPUT -p tcp --dport 22 -j ACCEPT

# Allow HTTP/HTTPS
iptables -A INPUT -p tcp --dport 80 -j ACCEPT
iptables -A INPUT -p tcp --dport 443 -j ACCEPT
```

### Internal Communication

**VM-to-VM (same project):**

```bash
# Use internal IPs (free, secure)
DATABASE_URL=postgres://user:pass@10.1.0.2:5432/db

# Not external IPs (costs egress, less secure)
DATABASE_URL=postgres://user:pass@34.123.45.67:5432/db
```

---

## 🎯 Runner Security

### Label-Based Isolation

**How it works:**

```yaml
# Workflow specifies ALL labels
runs-on:
  - self-hosted
  - superdeploy
  - cheapa       # ← Project isolation
  - app          # ← VM role isolation
```

**GitHub's routing:**
- Matches ALL labels
- Only runners with exact match can pick up job
- **Impossible** for wrong runner to execute

### .project File Validation

**Extra safety:**

```bash
# Inside deployment job
RUNNER_PROJECT=$(cat /opt/superdeploy/.project)
if [ "$RUNNER_PROJECT" != "cheapa" ]; then
  echo "❌ Wrong project!"
  exit 1
fi
```

**Why double-check?**
- Defense in depth
- Explicit validation
- Clear error messages
- Audit trail

### Runner Isolation

**Each runner:**
- ✅ Project-specific labels
- ✅ Unique registration
- ✅ Isolated workspace
- ✅ Project validation file
- ✅ No shared state

---

## 📊 Audit & Monitoring

### GitHub Actions Logs

**What's logged:**
- Every deployment
- Who triggered it
- What code was deployed
- Success/failure
- Complete output

**Retention:**
- 90 days (GitHub free)
- 400 days (GitHub Pro)
- Longer (GitHub Enterprise)

**Access:**

```bash
# Web UI
https://github.com/myorg/api/actions

# CLI
gh run list -R myorg/api
gh run view <run-id> -R myorg/api --log
```

### VM Logs

**GitHub runner:**

```bash
# Service logs
sudo journalctl -u github-runner -f

# Check for errors
sudo journalctl -u github-runner --no-pager -n 100 | grep -i error
```

**Container logs:**

```bash
# All containers
docker compose logs -f

# Specific app
docker logs myproject_api -f --tail 100

# Search for errors
docker logs myproject_api --tail 1000 | grep -i error
```

### Security Monitoring

**Regular checks:**

```bash
# 1. Failed SSH attempts
sudo grep "Failed password" /var/log/auth.log

# 2. Failed deployments
gh run list -R myorg/api --status failure

# 3. Unauthorized access attempts
sudo grep "REJECT" /var/log/syslog

# 4. Disk usage (DoS indicator)
df -h

# 5. Network connections
ss -tulpn
```

---

## 🛡️ Best Practices

### Development

1. **Never commit secrets**
   ```bash
   # .gitignore
   secrets.yml
   .env
   *.key
   *.pem
   ```

2. **Use separate credentials per environment**
   ```yaml
   # dev secrets != staging secrets != production secrets
   ```

3. **Minimum permissions**
   ```bash
   # GitHub PAT: Only required scopes
   # GCP Service Account: Only required roles
   # SSH: Only specific users
   ```

4. **Code reviews**
   ```bash
   # All changes go through PR
   # At least 1 approval required
   # Security-sensitive changes: 2+ approvals
   ```

### Operations

1. **Regular updates**
   ```bash
   # Weekly: Check for security updates
   sudo apt update && sudo apt upgrade -y
   ```

2. **Monitor failed logins**
   ```bash
   # Daily: Check for brute force attempts
   sudo grep "Failed password" /var/log/auth.log | tail -20
   ```

3. **Backup regularly**
   ```bash
   # Weekly: Database backups
   # Monthly: Full VM snapshots
   ```

4. **Rotate secrets**
   ```bash
   # Quarterly: Rotate all passwords
   # Immediately: After security incident
   ```

### Incident Response

1. **Security incident detected**
   ```bash
   # 1. Isolate affected resources
   # 2. Rotate all credentials
   # 3. Review audit logs
   # 4. Patch vulnerabilities
   # 5. Update procedures
   ```

2. **Compromised secret**
   ```bash
   # 1. Immediately rotate secret
   superdeploy myproject:sync
   
   # 2. Review access logs
   gh run list -R myorg/api
   
   # 3. Check for unauthorized access
   docker logs myproject_api --tail 1000 | grep -i unauthorized
   ```

---

## 🚨 Security Checklist

### Initial Setup

- [ ] Strong SSH key with passphrase
- [ ] SSH public key only (no password auth)
- [ ] GitHub PAT with minimum scopes
- [ ] GCP service account with minimum roles
- [ ] Firewall rules configured
- [ ] secrets.yml in .gitignore

### Pre-Deployment

- [ ] secrets.yml updated
- [ ] Secrets synced to GitHub
- [ ] Code reviewed
- [ ] Dependencies updated
- [ ] No secrets in code

### Post-Deployment

- [ ] Deployment successful
- [ ] Containers healthy
- [ ] Logs show no errors
- [ ] Secrets working
- [ ] Access restricted

### Regular Maintenance

- [ ] Secrets rotated (90 days)
- [ ] System packages updated (weekly)
- [ ] Failed logins reviewed (daily)
- [ ] Backups verified (monthly)
- [ ] Audit logs reviewed (weekly)

---

## 🔍 Security Scanning

### Container Scanning

```bash
# Scan images for vulnerabilities
docker scan myorg/api:latest

# Use minimal base images
FROM python:3.11-slim  # Not python:3.11 (smaller attack surface)
```

### Dependency Scanning

```bash
# Python
pip-audit

# Node.js
npm audit
npm audit fix

# GitHub (automatic)
Dependabot alerts
```

### Infrastructure Scanning

```bash
# Terraform
tfsec shared/terraform/

# Ansible
ansible-lint shared/ansible/
```

---

## 📞 Security Contact

**Report security issues:**
- **Private:** security@yourdomain.com
- **GitHub:** Security advisories (private)

**Do NOT:**
- Open public issues for security vulnerabilities
- Share secrets in issues/PRs
- Commit credentials

---

## 📚 Additional Resources

- [GitHub Security Best Practices](https://docs.github.com/en/actions/security-guides)
- [Docker Security](https://docs.docker.com/engine/security/)
- [GCP Security](https://cloud.google.com/security/best-practices)
- [OWASP Top 10](https://owasp.org/www-project-top-ten/)

---

## ✅ Summary

**Key Security Features:**

1. ✅ **Encrypted secrets** (GitHub encrypted storage)
2. ✅ **Network isolation** (Project-specific networks)
3. ✅ **Access control** (SSH keys, GitHub PAT, runner labels)
4. ✅ **Runner isolation** (Label matching + .project validation)
5. ✅ **Audit logging** (GitHub Actions + VM logs)
6. ✅ **Regular rotation** (90-day secret rotation)
7. ✅ **Minimum permissions** (Least privilege principle)
8. ✅ **Defense in depth** (Multiple security layers)

**Remember:**
> Security is not a feature, it's a process. Follow best practices, rotate credentials regularly, and monitor for anomalies.
