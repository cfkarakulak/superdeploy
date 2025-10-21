# 🎯 New Project Template

## Quick Start

### 1. Clone Template
```bash
cd superdeploy/projects
cp -r _template your-project-name
cd your-project-name
```

### 2. Update Configuration

**ansible/vars/project.yml:**
```yaml
project_name: your-project-name
project_id: your-project-id
project_domain: yourproject.com
subnet_cidr: "10.20.0.0/24"  # Choose unique subnet!
```

**Important:** Each project needs unique:
- `subnet_cidr`: Different IP range (e.g., 10.20.x.x, 10.30.x.x)
- `project_name`: Used for container/volume/network naming
- Ports: If on same VM, use different external ports

### 3. Update Compose Files

Find and replace all instances of:
- `cheapa` → `your-project-name`
- `cheapa-network` → `your-project-network`
- Container names, volume names, network names

### 4. Deploy
```bash
# From superdeploy root
export PROJECT=your-project-name
superdeploy up
```

## Project Isolation

Each project has:
- ✅ Own Docker network
- ✅ Own PostgreSQL database
- ✅ Own RabbitMQ vhost
- ✅ Own Redis instance
- ✅ Own volumes (data persistence)
- ✅ Own resource limits

## Network Isolation Example

```
Project A (Cheapa):
  Network: cheapa-network (10.10.0.0/24)
  Containers:
    - cheapa-postgres (10.10.0.2)
    - cheapa-rabbitmq (10.10.0.3)
    - cheapa-api (10.10.0.4)

Project B:
  Network: projectb-network (10.20.0.0/24)
  Containers:
    - projectb-postgres (10.20.0.2)
    - projectb-redis (10.20.0.3)
    - projectb-api (10.20.0.4)

❌ cheapa-api CANNOT access projectb-postgres
❌ projectb-api CANNOT access cheapa-rabbitmq
✅ Complete isolation!
```

## Deployment Models

### Model 1: Separate VMs (Recommended)
```
VM-Core-Cheapa (34.61.244.204)
  └─ Cheapa services

VM-Core-ProjectB (35.192.123.45)
  └─ ProjectB services
```

### Model 2: Same VM, Different Networks
```
VM-Core-Shared (34.61.244.204)
  ├─ Cheapa services (cheapa-network)
  └─ ProjectB services (projectb-network)
```
⚠️ Shared resources (CPU, Memory, Disk)

### Model 3: Hybrid
```
VM-Core-Cheapa → Cheapa DB/Queue
VM-App-Cheapa → Cheapa API/Dashboard

VM-Core-ProjectB → ProjectB DB/Redis
VM-App-ProjectB → ProjectB API/Dashboard
```

## Best Practices

1. **Naming Convention:**
   - Container: `{project}-{service}`
   - Volume: `{project}-{service}-data`
   - Network: `{project}-network`

2. **Resource Limits:**
   - Always set memory/CPU limits
   - Prevents one project from starving others

3. **Backups:**
   - Separate GCS buckets per project
   - Easy restore of single project

4. **Monitoring:**
   - Separate Prometheus/Grafana per project
   - Or use shared with project labels

5. **Secrets:**
   - Never share passwords between projects
   - Use different GitHub secrets per project repo

