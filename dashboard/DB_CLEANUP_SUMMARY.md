# Database Cleanup - Migration Summary

## 🎯 Goal
Remove database redundancy and use real-time CLI data instead of stale DB copies.

## ✅ Completed Changes

### 1. Dropped Tables (5 total)

#### ❌ `vms` Table
- **Before:** Stored VM data (name, role, ip, zone, machine_type, status)
- **After:** Use CLI `project:status --json`
- **Endpoint Updated:** `GET /projects/{project_name}/vms` now calls CLI

#### ❌ `addons` Table
- **Before:** Stored addon data (name, type, category, version, credentials)
- **After:** Use CLI `project:status -a app --json`
- **Endpoint Updated:** Removed `/addons/{project}/list-db`, kept CLI-based `/list`

#### ❌ `environments` Table
- **Before:** Stored production/staging/review environments per project
- **After:** Hardcoded array `["production", "staging"]`
- **Endpoint Updated:** `GET /environments/` returns hardcoded list

#### ❌ `secrets` Table
- **Before:** Stored environment variables with environment_id FK
- **After:** Use CLI `project:config:list/set/unset`
- **Already Done:** Secrets endpoint already uses CLI (completed earlier)

#### ❌ `metrics_cache` Table
- **Before:** Cached container metrics
- **After:** Use Prometheus real-time queries
- **Status:** Already using Prometheus, cache was unused

---

### 2. Simplified Tables (2 total)

#### 🔧 `apps` Table
**Before:**
```sql
id, project_id, name, type, vm, domain, port, 
dockerfile_path, processes, repo, owner, created_at
```

**After:**
```sql
id, project_id, name, repo, owner, created_at
```

**Reason:** Only `repo` and `owner` are needed for GitHub integration. All other data (type, vm, domain, port, processes) come from CLI.

---

#### 🔧 `projects` Table
**Before:**
```sql
id, name, gcp_project_id, github_org, domain, 
cloud_provider, cloud_region, cloud_zone, created_at
```

**After:**
```sql
id, name, domain, github_org, created_at
```

**Reason:** Only metadata fields (`domain`, `github_org`) are manually set. Cloud provider, region, VMs etc. come from CLI.

---

### 3. Kept Tables (3 total)

#### ✅ `settings`
- **Purpose:** Dashboard-specific settings (GitHub token, API keys)
- **Why:** No CLI equivalent, dashboard needs persistent storage

#### ✅ `activity_logs`
- **Purpose:** Audit trail for user actions
- **Why:** History/logging not available in CLI

#### ✅ `deployment_history`
- **Purpose:** Track deployment history for rollback
- **Why:** CLI only shows current deployment, we need history

---

## 📊 Database Size Reduction

| Category | Before | After | Change |
|----------|--------|-------|--------|
| **Total Tables** | 11 | 6 | -5 tables |
| **apps columns** | 11 | 6 | -5 columns |
| **projects columns** | 9 | 5 | -4 columns |

---

## 🚀 Benefits

1. **Real-time Data:** No more stale database copies, always shows current state
2. **Single Source of Truth:** CLI config.yml is the master, not database
3. **Less Sync Issues:** No need to keep DB in sync with server state
4. **Faster Development:** No DB migrations for infrastructure changes
5. **Cleaner Architecture:** Dashboard is a view layer, not a data store

---

## 🔄 Affected Endpoints

### Updated to Use CLI:
- ✅ `GET /projects/{project_name}/vms` - Now calls `project:status --json`
- ✅ `GET /addons/{project}/list` - Already using CLI
- ✅ `GET /environments/` - Returns hardcoded `["production", "staging"]`
- ✅ `GET /secrets/{project}/{app}` - Already using CLI (done earlier)
- ✅ `GET /resources/{project}/{app}` - Already using CLI for addons

### Removed Endpoints:
- ❌ `GET /addons/{project}/list-db` - Redundant DB endpoint removed
- ❌ `GET /environments/project/{project_id}` - Replaced with simple list
- ❌ `GET /environments/{environment_id}` - No longer needed

---

## 📝 Migration Script

Location: `dashboard/backend/migrate_cleanup_db.py`

Run once after deployment:
```bash
cd dashboard/backend
python migrate_cleanup_db.py
```

**What it does:**
1. Drops 5 unused tables
2. Removes unused columns from `apps` table
3. Removes unused columns from `projects` table

**Safe to run:** Uses `IF EXISTS` and `CASCADE` for clean removal.

---

## 🎓 Key Learnings

1. **CLI is Source of Truth:** config.yml + secrets.yml contain all infrastructure state
2. **Database for Metadata Only:** Only store what users manually configure
3. **Real-time > Cached:** Always prefer CLI/API queries over cached DB data
4. **Simplicity Wins:** Fewer tables = less maintenance, fewer bugs

---

## 🔮 Future Improvements

1. Consider removing `apps` table entirely if GitHub integration can work without it
2. Consider removing `projects` table if domain/github_org can be stored in config.yml
3. Keep monitoring `deployment_history` - might be replaceable with GitHub API

---

## ✅ Migration Status: COMPLETED

- [x] Drop unused tables
- [x] Simplify apps table
- [x] Simplify projects table
- [x] Update all endpoints
- [x] Run migration script
- [x] Test dashboard functionality

**Date:** 2025-11-17
**Executed by:** Database cleanup automation

