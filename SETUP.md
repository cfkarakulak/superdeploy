# 🚀 SuperDeploy - Sıfırdan Kurulum

## ⚡ TL;DR (5 Dakika)

```bash
# 1. Terraform ile VM'leri oluştur
cd superdeploy-infra
terraform apply -var-file=envs/dev/gcp.auto.tfvars -auto-approve

# 2. IP'leri al ve .env'i güncelle
terraform output
cd ../superdeploy
nano .env  # Internal IP'leri güncelle

# 3. SSH known_hosts temizle
ssh-keygen -R 34.56.43.99
ssh-keygen -R 34.67.236.167
ssh-keygen -R 34.173.11.246

# 4. VM'lerin hazır olmasını bekle (90 saniye)
sleep 90

# 5. Ansible ile tam otomatik deployment
cd ../superdeploy-infra/ansible
ansible-playbook -i inventories/dev.ini playbooks/site.yml --tags system-base,git-server

# 6. Kodu push et
cd ../../superdeploy
git add .env
git commit -m "config: initial deployment"
git remote add forgejo http://cradexco:Admin123%21ChangeME@34.56.43.99:3001/cradexco/superdeploy-app.git
git push -u forgejo master

# 7. Done! 🎉
open http://34.56.43.99:3001/cradexco/superdeploy-app/actions
```

---

## 📋 Detaylı Adımlar

### 1️⃣ Ön Gereksinimler

```bash
# GCP hesabı ve gcloud CLI
gcloud auth login
gcloud config set project YOUR_PROJECT_ID

# SSH key oluştur (yoksa)
ssh-keygen -t rsa -b 4096 -f ~/.ssh/cfk_gcp
```

### 2️⃣ Terraform ile VM'leri Oluştur

```bash
cd superdeploy-infra

# GCP project ID'yi güncelle
nano envs/dev/gcp.auto.tfvars  # project_id = "YOUR_PROJECT"

# VM'leri oluştur
terraform init
terraform apply -var-file=envs/dev/gcp.auto.tfvars -auto-approve
```

**Output'tan IP'leri not al:**
```
vm_core_internal_ips = ["10.0.0.X"]
vm_scrape_internal_ips = ["10.0.0.Y"]
vm_proxy_internal_ips = ["10.0.0.Z"]
```

### 3️⃣ .env Dosyasını Güncelle

```bash
cd ../superdeploy
nano .env
```

**Güncelle:**
```env
CORE_INTERNAL_IP=10.0.0.X    # Terraform output'tan
SCRAPE_INTERNAL_IP=10.0.0.Y
PROXY_INTERNAL_IP=10.0.0.Z
```

### 4️⃣ SSH Known Hosts Temizle

```bash
ssh-keygen -R 34.56.43.99
ssh-keygen -R 34.67.236.167
ssh-keygen -R 34.173.11.246
```

### 5️⃣ VM Hazırlığını Bekle

```bash
# VM'lerin startup script'i çalışıyor
sleep 90
```

### 6️⃣ Ansible ile Tam Otomatik Deployment

```bash
cd ../superdeploy-infra/ansible
ansible-playbook -i inventories/dev.ini playbooks/site.yml --tags system-base,git-server
```

**Bu adım:**
- ✅ Docker kurar
- ✅ Firewall yapılandırır
- ✅ Forgejo kurar (NO WIZARD!)
- ✅ Admin user oluşturur: `cradexco` / `Admin123!ChangeME`
- ✅ Repository oluşturur: `superdeploy-app`
- ✅ Runner register eder ve başlatır

### 7️⃣ Kodu Forgejo'ya Push Et

```bash
cd ../../superdeploy

# .env'i commit et
git add .env
git commit -m "config: initial deployment"

# Forgejo'ya push
git remote add forgejo http://cradexco:Admin123%21ChangeME@34.56.43.99:3001/cradexco/superdeploy-app.git
git push -u forgejo master
```

### 8️⃣ Workflow'ları İzle

```bash
# Browser'da aç
open http://34.56.43.99:3001/cradexco/superdeploy-app/actions
```

**Workflow'lar otomatik başlar:**
- 🚀 Deploy CORE VM
- 🔍 Deploy SCRAPE VM
- 🌐 Deploy PROXY VM

---

## ✅ Test

```bash
# 2-3 dakika sonra servisler hazır:

# API
curl http://34.56.43.99:8000/health

# Proxy Registry
curl http://34.56.43.99:8080/health

# Dashboard
open http://34.56.43.99:8001

# RabbitMQ Management
open http://34.56.43.99:15672
```

---

## 🔄 VM Restart Sonrası

```bash
# 1. Yeni IP'leri al
cd superdeploy-infra
terraform output

# 2. .env'i güncelle
cd ../superdeploy
nano .env  # Internal IP'leri güncelle

# 3. Push et
git add .env
git commit -m "config: update IPs after restart"
git push

# 4. Otomatik deploy! ✨
```

---

## 🎯 Özet

| Adım | Süre | Komut |
|------|------|-------|
| Terraform | 30s | `terraform apply -auto-approve` |
| Bekle | 90s | `sleep 90` |
| Ansible | 3-4m | `ansible-playbook ... --tags system-base,git-server` |
| Push | 10s | `git push forgejo master` |
| **TOPLAM** | **~6 dakika** | **4 komut** |

---

## 📚 Kaynaklar

- **Forgejo UI**: http://34.56.43.99:3001
- **Admin**: cradexco / Admin123!ChangeME
- **Workflow'lar**: http://34.56.43.99:3001/cradexco/superdeploy-app/actions
- **API Docs**: http://34.56.43.99:8000/docs

---

## 🆘 Sorun Giderme

### Ansible "dpkg lock" Hatası
```bash
# 30 saniye daha bekle ve tekrar dene
sleep 30
ansible-playbook ...
```

### Runner Çalışmıyor
```bash
ssh superdeploy@34.56.43.99
sudo systemctl status forgejo-runner
sudo systemctl restart forgejo-runner
```

### Workflow Başlamıyor
```bash
# Runner loglarını kontrol et
ssh superdeploy@34.56.43.99
sudo journalctl -u forgejo-runner -f
```

---

**🎉 Hepsi bu kadar! 6 dakikada tam sistem!**
