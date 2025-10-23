# 🔄 Sync Workflow - Ne Zaman, Nasıl?

Bu döküman **secrets sync** işlemlerinin ne zaman gerekli olduğunu ve nasıl çalıştığını açıklar.

---

## 🎯 TL;DR (Özet)

```bash
# İlk kurulumda (bir kez)
superdeploy sync -p myproject

# Sonra otomatik! 🎉
git push origin production  # Her şey otomatik sync olur
```

**Sync'e tekrar ihtiyacın olur mu?** Sadece şu durumlarda:
- ✅ Yeni bir secret eklediğinde
- ✅ Secret değerini değiştirdiğinde
- ✅ Yeni bir environment eklediğinde (staging, dev)
- ✅ VM IP'si değiştiğinde

---

## 📊 Sync Akışı (Otomatik vs Manuel)

### **Otomatik Sync (Her Deployment'ta)**

```
git push origin production
    ↓
GitHub Actions
    ↓
1. Build Docker image
2. Encrypt .env with AGE ✅ (otomatik)
3. Push to Forgejo ✅ (otomatik)
    ↓
Forgejo Runner
    ↓
1. Decrypt .env ✅ (otomatik)
2. Deploy container ✅ (otomatik)
```

**Sonuç:** Her deployment'ta secrets otomatik olarak container'a gider!

### **Manuel Sync (GitHub Secrets Güncelleme)**

```bash
superdeploy sync -p myproject
```

Bu komut:
1. ✅ AGE public key'i VM'den alır
2. ✅ Forgejo PAT oluşturur (eğer yoksa)
3. ✅ **GitHub Secrets**'ı günceller (tüm repo'lar için)
4. ✅ **Forgejo Secrets**'ı günceller (superdeploy repo için)

---

## 🔑 Secrets'lar Nerede Saklanır?

### **1. Local (Senin Bilgisayarın)**
```
superdeploy/.env                    # Infrastructure secrets
superdeploy/projects/cheapa/.passwords.yml  # Project secrets
```

**Kullanım:** `superdeploy sync` komutu buradan okur

---

### **2. GitHub Secrets (Her App Repo'sunda)**
```
cheapaio/api → Settings → Secrets
cheapaio/dashboard → Settings → Secrets
cheapaio/services → Settings → Secrets
```

**İçerik:**
- `AGE_PUBLIC_KEY` - Encryption için
- `FORGEJO_BASE_URL` - Forgejo URL
- `FORGEJO_PAT` - Forgejo token
- `PROJECT_NAME` - Project adı (cheapa)
- `FORGEJO_ORG` - Forgejo org (cradexco)
- `FORGEJO_REPO` - Forgejo repo (superdeploy)
- `POSTGRES_*` - Database credentials
- `RABBITMQ_*` - Queue credentials
- `REDIS_*` - Cache credentials
- `API_SECRET_KEY` - App secret

**Ne zaman güncellenir?**
```bash
superdeploy sync -p myproject  # Manuel
```

**Kullanım:** GitHub Actions bu secrets'ları kullanır

---

### **3. Forgejo Secrets (superdeploy repo'sunda)**
```
http://CORE_IP:3001/cradexco/superdeploy → Settings → Secrets
```

**İçerik:**
- `POSTGRES_*` - Database credentials
- `RABBITMQ_*` - Queue credentials
- `REDIS_*` - Cache credentials
- `DOCKER_USERNAME` - Docker Hub
- `DOCKER_TOKEN` - Docker Hub
- `ALERT_EMAIL` - Notification email

**Ne zaman güncellenir?**
```bash
superdeploy sync -p myproject  # Manuel
```

**Kullanım:** Forgejo Actions bu secrets'ları kullanır (core services deployment için)

---

### **4. Runtime (Container'da)**
```
/tmp/decrypted.env  # Geçici, deployment sırasında
```

**İçerik:** GitHub Actions'dan encrypted olarak gelir, Forgejo Runner decrypt eder

**Ne zaman güncellenir?** Her deployment'ta otomatik!

**Kullanım:** Container bu dosyayı okur

**Güvenlik:** Deployment bittikten sonra otomatik silinir

---

## 🔄 Sync Senaryoları

### **Senaryo 1: İlk Kurulum**

```bash
# 1. Infrastructure deploy
superdeploy up -p myproject

# 2. Secrets sync (ilk kez)
superdeploy sync -p myproject

# 3. İlk deployment
cd app-repos/api
git push origin production

# ✅ Artık her push otomatik!
```

**Neler oldu?**
- ✅ AGE key pair oluşturuldu (VM'de)
- ✅ Forgejo PAT oluşturuldu
- ✅ GitHub Secrets set edildi (3 repo)
- ✅ Forgejo Secrets set edildi

---

### **Senaryo 2: Yeni Secret Ekleme**

```bash
# 1. Local .env'e ekle
echo "NEW_API_KEY=abc123xyz" >> superdeploy/.env

# 2. Sync et
superdeploy sync -p myproject

# 3. App kodunda kullan
# app.py:
# NEW_API_KEY = os.getenv("NEW_API_KEY")

# 4. Deploy et
git push origin production

# ✅ Yeni secret otomatik container'a gider!
```

**Neler oldu?**
- ✅ GitHub Secrets güncellendi
- ✅ Forgejo Secrets güncellendi
- ✅ Deployment sırasında container'a inject edildi

---

### **Senaryo 3: Secret Değiştirme**

```bash
# 1. Local .env'de değiştir
nano superdeploy/.env
# POSTGRES_PASSWORD=old123 → POSTGRES_PASSWORD=new456

# 2. Sync et
superdeploy sync -p myproject

# 3. Core services'i restart et (yeni password için)
ssh superdeploy@CORE_IP
cd /opt/superdeploy/projects/myproject/compose
docker compose -f docker-compose.core.yml restart postgres

# 4. App'i redeploy et
cd app-repos/api
git push origin production

# ✅ Yeni password her yerde!
```

**Dikkat:** Core services (PostgreSQL, RabbitMQ) için restart gerekir!

---

### **Senaryo 4: VM IP Değişti**

```bash
# 1. superdeploy up otomatik günceller
superdeploy up -p myproject

# 2. Sync et (yeni IP GitHub'a gider)
superdeploy sync -p myproject

# 3. Test deployment
cd app-repos/api
git commit --allow-empty -m "test: new IP"
git push origin production

# ✅ Yeni IP ile çalışır!
```

**Neler oldu?**
- ✅ `FORGEJO_BASE_URL` güncellendi (yeni IP)
- ✅ `CORE_EXTERNAL_IP` güncellendi
- ✅ GitHub Actions yeni IP'yi kullanır

---

### **Senaryo 5: Yeni Environment Ekleme (Staging)**

```bash
# 1. Staging secrets ekle
nano superdeploy/projects/myproject/secrets.staging.env

# 2. Sync et (staging environment için)
superdeploy sync -p myproject -e staging

# 3. Staging'e deploy et
cd app-repos/api
git push origin staging

# ✅ Staging environment hazır!
```

**Not:** Şu an sadece production var, staging support gelecek!

---

## 🤔 Sık Sorulan Sorular

### **Q: Her deployment'ta sync gerekli mi?**
**A:** Hayır! Sadece `git push origin production` yeterli. Secrets otomatik encrypt/decrypt olur.

---

### **Q: Secret değiştirdim ama deployment yapmadım, ne olur?**
**A:** Hiçbir şey! Container hala eski secret'ı kullanır. Yeni secret için deployment gerekli.

```bash
# Secret değiştir
superdeploy sync -p myproject

# Deployment yap (yeni secret aktif olur)
git push origin production
```

---

### **Q: GitHub Secrets'ı manuel değiştirirsem ne olur?**
**A:** Çalışır ama önerilmez! `superdeploy sync` ile yap ki local .env ile senkron olsun.

---

### **Q: Forgejo Secrets'ı manuel değiştirirsem ne olur?**
**A:** Core services deployment'ında kullanılır. Ama yine önerilmez, `superdeploy sync` kullan.

---

### **Q: .env dosyasını git'e commit etmeli miyim?**
**A:** HAYIR! `.env` dosyası `.gitignore`'da olmalı. Sadece `ENV.example` commit edilir.

---

### **Q: Secrets'ları nasıl backup alırım?**
**A:** 
```bash
# Local .env zaten backup
cp superdeploy/.env superdeploy/.env.backup

# Veya superdeploy backup komutu
superdeploy backup -p myproject
```

---

### **Q: Secrets'lar güvenli mi?**
**A:** Evet!
- ✅ Local: `.env` dosyası git'e commit edilmez
- ✅ GitHub: Secrets encrypted saklanır
- ✅ Transport: AGE encryption (public key)
- ✅ Runtime: Geçici dosya, deployment sonrası silinir
- ✅ Forgejo: Secrets encrypted saklanır

---

### **Q: AGE key'i kaybedersem ne olur?**
**A:** Yeni key oluşturulur:
```bash
# VM'de yeni key oluştur
ssh superdeploy@CORE_IP
age-keygen -o /opt/forgejo-runner/.age/key.txt

# Sync et (yeni public key GitHub'a gider)
superdeploy sync -p myproject
```

---

## 📋 Sync Checklist

### **İlk Kurulumda**
- [ ] `superdeploy up -p myproject`
- [ ] `superdeploy sync -p myproject`
- [ ] Test deployment: `git push origin production`
- [ ] Verify: `superdeploy status -p myproject`

### **Secret Değişikliğinde**
- [ ] Local .env'i güncelle
- [ ] `superdeploy sync -p myproject`
- [ ] Core services restart (eğer gerekiyorsa)
- [ ] App redeploy: `git push origin production`

### **VM IP Değişiminde**
- [ ] `superdeploy up -p myproject` (otomatik günceller)
- [ ] `superdeploy sync -p myproject`
- [ ] Test deployment

### **Yeni Secret Eklemede**
- [ ] Local .env'e ekle
- [ ] `superdeploy sync -p myproject`
- [ ] App kodunda kullan
- [ ] Deploy: `git push origin production`

---

## 🎯 Best Practices

1. **Sync sonrası test et**
   ```bash
   superdeploy sync -p myproject
   git push origin production  # Test deployment
   ```

2. **Secrets'ları version control et (local)**
   ```bash
   # .env dosyasını backup al
   cp superdeploy/.env superdeploy/.env.$(date +%Y%m%d)
   ```

3. **Secrets rotation (düzenli değiştir)**
   ```bash
   # Her 90 günde bir
   superdeploy secrets:rotate -p myproject  # (gelecek feature)
   ```

4. **Audit log tut**
   ```bash
   # Kim ne zaman sync etti?
   git log --all --grep="sync" --oneline
   ```

---

## 🔗 İlgili Dökümanlar

- **SETUP.md:** İlk kurulum adımları
- **OPERATIONS.md:** Günlük operasyonlar
- **DEPLOYMENT.md:** Deployment flow detayları

---

**Hala kafan karışık mı?**
- GitHub Issues: https://github.com/cfkarakulak/superdeploy/issues
- Email: cradexco@gmail.com
