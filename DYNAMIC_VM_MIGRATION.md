# SuperDeploy: Dynamic VM Architecture Migration

## 🎯 Summary

SuperDeploy artık **tamamen dinamik VM mimarisi** kullanıyor. Statik `core`, `scrape`, `proxy` yapısı kaldırıldı. Her proje istediği VM yapısını tanımlayabilir.

## ✨ Değişiklikler

### 1. Terraform (shared/terraform/)

**Öncesi:**
```hcl
# Statik VM modülleri
module "vm_core" { ... }
module "vm_scrape" { ... }
module "vm_proxy" { ... }
```

**Sonrası:**
```hcl
# Dinamik VM oluşturma
module "vms" {
  for_each = var.vm_groups
  # Her VM grubu project.yml'den okunur
}
```

**Değişiklikler:**
- ✅ `main.tf`: Statik modüller kaldırıldı, dinamik `for_each` ile değiştirildi
- ✅ `variables.tf`: `vm_groups` map variable eklendi, statik yapı kaldırıldı
- ✅ `outputs.tf`: Dinamik output'lar eklendi, tüm VM'ler destekleniyor

### 2. ConfigLoader (cli/core/config_loader.py)

**Öncesi:**
```python
def to_terraform_vars(self):
    return {
        'machine_type': vm_config['machine_type'],
        'disk_size': vm_config['disk_size'],
    }
```

**Sonrası:**
```python
def to_terraform_vars(self):
    # project.yml'deki vms yapısından dinamik vm_groups oluştur
    vm_groups = {}
    for vm_role, vm_definition in vms_config.items():
        for i in range(count):
            vm_groups[f"{vm_role}-{i}"] = {
                'role': vm_role,
                'machine_type': vm_definition['machine_type'],
                'disk_size': vm_definition['disk_size'],
                ...
            }
    return {'vm_groups': vm_groups, ...}
```

### 3. up.py (cli/commands/up.py)

**Değişiklikler:**
- ✅ `update_ips_in_env()`: Dinamik IP extraction (tüm VM'ler)
- ✅ `generate_ansible_inventory()`: Dinamik inventory generation (role bazlı gruplar)
- ✅ `clean_ssh_known_hosts()`: Tüm VM IP'lerini temizler
- ✅ Terraform entegrasyonu: `terraform_utils.py` kullanımı (wrapper yerine)
- ✅ Forgejo IP bulma: Dinamik olarak ilk "core" VM'ini veya ilk VM'i kullanır

### 4. ansible_utils.py

**Değişiklikler:**
- ✅ `build_ansible_command()`: Proje-spesifik inventory dosyası kullanır (`cheapa.ini`, `myapp.ini`)

## 📋 project.yml VM Yapısı

Her proje `project.yml` içinde VM'lerini tanımlar:

```yaml
vms:
  core:                          # VM role adı (inventory grup adı)
    count: 1                     # Bu role'den kaç VM
    machine_type: e2-medium      # GCP machine type
    disk_size: 20                # GB cinsinden disk
    services:                    # Bu VM'de çalışacak servisler
      - postgres
      - rabbitmq
      - forgejo
  
  worker:                        # Başka bir VM role
    count: 3                     # 3 worker VM
    machine_type: e2-standard-4
    disk_size: 100
    services:
      - scraper
      - browser
  
  proxy:                         # Proxy VM'ler
    count: 2
    machine_type: e2-small
    disk_size: 20
    services:
      - tinyproxy
```

## 🔄 Terraform Variable Transformation

**project.yml'den Terraform'a dönüşüm:**

```yaml
# project.yml
vms:
  core:
    count: 2
    machine_type: e2-medium
    disk_size: 20
    services: [postgres, rabbitmq]
```

↓ ConfigLoader.to_terraform_vars()

```json
{
  "vm_groups": {
    "core-0": {
      "role": "core",
      "index": 0,
      "machine_type": "e2-medium",
      "disk_size": 20,
      "tags": ["core", "postgres", "rabbitmq"],
      "labels": {"has_postgres": "true", "has_rabbitmq": "true"}
    },
    "core-1": {
      "role": "core",
      "index": 1,
      "machine_type": "e2-medium",
      "disk_size": 20,
      "tags": ["core", "postgres", "rabbitmq"],
      "labels": {"has_postgres": "true", "has_rabbitmq": "true"}
    }
  }
}
```

↓ Terraform

```
VM names:
- cheapa-core-0
- cheapa-core-1
```

## 🌐 Environment Variables

**Dinamik olarak oluşturulan env vars:**

```bash
# project.yml: vms.core (count: 2)
CORE_0_EXTERNAL_IP=34.72.179.175
CORE_0_INTERNAL_IP=10.0.0.2
CORE_1_EXTERNAL_IP=34.72.180.88
CORE_1_INTERNAL_IP=10.0.0.3

# project.yml: vms.worker (count: 3)
WORKER_0_EXTERNAL_IP=34.72.181.99
WORKER_0_INTERNAL_IP=10.0.0.4
WORKER_1_EXTERNAL_IP=34.72.182.111
WORKER_1_INTERNAL_IP=10.0.0.5
WORKER_2_EXTERNAL_IP=34.72.183.122
WORKER_2_INTERNAL_IP=10.0.0.6
```

## 📦 Ansible Inventory

**Dinamik olarak oluşturulan inventory (`cheapa.ini`):**

```ini
[core]
cheapa-core-0 ansible_host=34.72.179.175 ansible_user=superdeploy
cheapa-core-1 ansible_host=34.72.180.88 ansible_user=superdeploy

[worker]
cheapa-worker-0 ansible_host=34.72.181.99 ansible_user=superdeploy
cheapa-worker-1 ansible_host=34.72.182.111 ansible_user=superdeploy
cheapa-worker-2 ansible_host=34.72.183.122 ansible_user=superdeploy

[proxy]
cheapa-proxy-0 ansible_host=34.72.184.133 ansible_user=superdeploy
```

## 🚀 Kullanım Örnekleri

### Örnek 1: Minimal Proje (Tek VM)

```yaml
# projects/simple/project.yml
vms:
  app:
    count: 1
    machine_type: e2-small
    disk_size: 20
    services:
      - postgres
      - api
```

**Sonuç:**
- 1 VM: `simple-app-0`
- Env vars: `APP_0_EXTERNAL_IP`, `APP_0_INTERNAL_IP`
- Inventory: `[app]` grubu

### Örnek 2: Çoklu Role (Her role'den 1 VM)

```yaml
# projects/medium/project.yml
vms:
  api:
    count: 1
    machine_type: e2-medium
    disk_size: 30
    services: [postgres, api]
  
  worker:
    count: 1
    machine_type: e2-standard-2
    disk_size: 50
    services: [worker, rabbitmq]
```

**Sonuç:**
- 2 VM: `medium-api-0`, `medium-worker-0`
- Inventory: `[api]` ve `[worker]` grupları

### Örnek 3: Scalable Proje (Çoklu VM'ler)

```yaml
# projects/cheapa/project.yml
vms:
  core:
    count: 1
    machine_type: e2-standard-2
    disk_size: 50
    services:
      - postgres
      - rabbitmq
      - forgejo
  
  scraper:
    count: 5
    machine_type: e2-standard-4
    disk_size: 100
    services:
      - scraper
      - browser
  
  proxy:
    count: 10
    machine_type: e2-small
    disk_size: 20
    services:
      - tinyproxy
```

**Sonuç:**
- 16 VM total
- 1 core VM: `cheapa-core-0`
- 5 scraper VM: `cheapa-scraper-0` to `cheapa-scraper-4`
- 10 proxy VM: `cheapa-proxy-0` to `cheapa-proxy-9`

## ⚙️ Komutlar

```bash
# 1. Proje oluştur
superdeploy init -p myproject

# 2. project.yml'i düzenle (vms section'ını ekle)
vim projects/myproject/project.yml

# 3. Infrastructure deploy
superdeploy up -p myproject

# 4. IP'leri kontrol et
cat projects/myproject/.env | grep _EXTERNAL_IP

# 5. Inventory'yi kontrol et
cat shared/ansible/inventories/myproject.ini
```

## 🎯 Migration Checklist

Mevcut bir proje varsa:

- [x] ✅ Terraform modülleri dinamikleştirildi
- [x] ✅ ConfigLoader.to_terraform_vars() güncellendi
- [x] ✅ up.py dinamik IP extraction
- [x] ✅ up.py dinamik inventory generation
- [x] ✅ ansible_utils proje-spesifik inventory
- [ ] ⚠️  project.yml'de `vms:` section eklenecek (kullanıcı yapacak)
- [ ] ⚠️  Eski `CORE_EXTERNAL_IP` env var'ları silinecek (otomatik güncellenir)
- [ ] ⚠️  `terraform state rm` ile eski statik VM'ler temizlenecek (gerekirse)

## ⚠️ Breaking Changes

1. **Environment Variables:**
   - Eski: `CORE_EXTERNAL_IP`, `SCRAPE_EXTERNAL_IP`
   - Yeni: `CORE_0_EXTERNAL_IP`, `SCRAPER_0_EXTERNAL_IP`

2. **Inventory Dosyaları:**
   - Eski: `inventories/dev.ini` (tüm projeler için)
   - Yeni: `inventories/{project_name}.ini` (proje-spesifik)

3. **Terraform State:**
   - Eski VM'ler: `module.vm_core[0]`, `module.vm_scrape[0]`
   - Yeni VM'ler: `module.vms["core-0"]`, `module.vms["scraper-0"]`

## 🔧 Troubleshooting

### Terraform state conflict

```bash
# Eski state'i temizle (dikkatli!)
cd shared/terraform
terraform workspace select cheapa
terraform state list | grep "module.vm_core" | xargs -I {} terraform state rm {}
terraform state list | grep "module.vm_scrape" | xargs -I {} terraform state rm {}
terraform state list | grep "module.vm_proxy" | xargs -I {} terraform state rm {}

# Yeniden deploy
superdeploy up -p cheapa
```

### Inventory bulunamadı hatası

```bash
# Inventory'yi manuel oluştur
superdeploy up -p cheapa --skip-terraform --skip-ansible

# .env'deki IP'leri kontrol et
cat projects/cheapa/.env | grep EXTERNAL_IP

# Inventory dosyası oluşturuldu mu?
cat shared/ansible/inventories/cheapa.ini
```

## 🎉 Avantajlar

1. ✅ **Her proje istediği VM yapısını tanımlar** - Artık core/scrape/proxy zorunluluğu yok
2. ✅ **Farklı projeler farklı VM tipleri kullanabilir** - Bir projede 1 VM, diğerinde 50 VM
3. ✅ **Dynamic scaling** - VM sayısını değiştirmek için sadece `count` değiştir
4. ✅ **Service labeling** - Her VM'in hangi servisleri çalıştırdığı açıkça belli
5. ✅ **Multi-project isolation** - Her projenin kendi inventory dosyası
6. ✅ **Future-proof** - Yeni VM rolleri eklemek için kod değişikliği gerektirmiyor

## 📚 Daha Fazla Bilgi

- `docs/ARCHITECTURE.md` - Mimari dokümantasyonu
- `docs/MULTI_PROJECT.md` - Çoklu proje yönetimi
- `shared/terraform/outputs.tf` - Dinamik Terraform outputs
- `cli/core/config_loader.py` - VM configuration parsing

