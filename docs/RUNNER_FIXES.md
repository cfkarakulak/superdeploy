# Forgejo Runner Registration Fixes

## Problem Summary

The Forgejo Actions runner system had several critical issues that prevented project runners from being created properly or caused label mismatches:

### 1. **Label Mismatch Between Orchestrator and Project Runners**
- **Orchestrator runner** used: `ubuntu-latest:docker://node:20-bookworm`
- **Project runners** used: `ubuntu-latest:host`
- **Issue**: Workflows expecting `ubuntu-latest` label would match different runners with different executors, causing inconsistent behavior

### 2. **YAML Syntax Error**
- **Location**: `shared/ansible/roles/system/forgejo-runner/tasks/main.yml` line 230-233
- **Issue**: Missing `stat:` key in the "Re-check runner registration status" task
- **Impact**: Ansible would fail to parse the playbook

### 3. **Silent Token Generation Failures**
- **Issue**: Token generation from orchestrator could fail silently
- **Impact**: Project runners would skip registration without clear error messages
- **Root cause**: Missing orchestrator in inventory or Forgejo not ready

### 4. **No Orchestrator Validation**
- **Issue**: No validation that orchestrator VM is in inventory before attempting delegation
- **Impact**: Cryptic errors or silent failures when orchestrator not available

### 5. **Documentation Mismatch**
- **Issue**: RUNNER_ARCHITECTURE.md showed incorrect label formats
- **Impact**: Developers would configure workflows incorrectly

## Solutions Applied

### 1. Unified Label Format ✅

**Changed all runners to use Docker executor with consistent image:**

```yaml
# Orchestrator Runner Labels:
- self-hosted:docker://node:20-bookworm
- ubuntu-latest:docker://node:20-bookworm
- orchestrator:docker://node:20-bookworm
- linux:docker://node:20-bookworm
- docker:docker://node:20-bookworm

# Project Runner Labels:
- self-hosted:docker://node:20-bookworm
- project-runner:docker://node:20-bookworm
- ubuntu-latest:docker://node:20-bookworm
- {project}:docker://node:20-bookworm
- {vm_role}:docker://node:20-bookworm
- linux:docker://node:20-bookworm
- docker:docker://node:20-bookworm
```

**Benefits:**
- All runners use same Node.js 20 environment
- Workflows match runners predictably
- Consistent Debian bookworm base
- Better Docker image caching

**Files Changed:**
- `shared/ansible/roles/system/forgejo-runner/tasks/main.yml` (line 264)
- `addons/forgejo/tasks/setup-runner.yml` (line 189)

### 2. Fixed YAML Syntax Error ✅

**Before:**
```yaml
- name: Re-check runner registration status
  stat:                                    # ❌ This line was formatted incorrectly
    path: /opt/forgejo-runner/.runner
  register: runner_registration_check
```

**After:**
```yaml
- name: Re-check runner registration status
  stat:                                    # ✅ Correct YAML structure
    path: /opt/forgejo-runner/.runner
  register: runner_registration_check
```

**File Changed:**
- `shared/ansible/roles/system/forgejo-runner/tasks/main.yml` (line 230-233)

### 3. Enhanced Error Handling ✅

**Added comprehensive error handling:**

1. **Orchestrator Validation** (before token generation):
```yaml
- name: Validate orchestrator is in inventory
  fail:
    msg: |
      Orchestrator not found in inventory!
      The orchestrator group must be defined in inventory for runner registration.
```

2. **Token Generation Debug Output**:
```yaml
- name: Display token generation result
  debug:
    msg:
      - "Token generation result: {{ 'SUCCESS' if ... }}"
      - "Token length: {{ runner_token_result.stdout | length }}"
      - "Error (if any): {{ runner_token_result.stderr }}"
```

3. **Detailed Failure Messages**:
```yaml
- name: Fail if token generation failed
  fail:
    msg: |
      Failed to generate runner registration token!
      
      Possible causes:
      1. Forgejo container 'orchestrator-forgejo' not running
      2. Forgejo not fully initialized yet (wait 30s and retry)
      3. Database connection issues
      4. Network connectivity problems
      
      Try running on orchestrator VM:
        docker exec -u 1000:1000 orchestrator-forgejo forgejo actions generate-runner-token
```

4. **Retry Logic**:
```yaml
- name: Generate runner registration token from Forgejo
  command: docker exec -u 1000:1000 orchestrator-forgejo forgejo actions generate-runner-token
  retries: 3
  delay: 5
```

**Files Changed:**
- `shared/ansible/roles/system/forgejo-runner/tasks/main.yml` (lines 235-304)

### 4. Updated Documentation ✅

**Updated RUNNER_ARCHITECTURE.md to reflect actual implementation:**
- Corrected label formats for all runner types
- Added troubleshooting section for token generation
- Documented Docker executor usage
- Added consistency notes

**File Changed:**
- `docs/RUNNER_ARCHITECTURE.md`

### 5. Updated Runner Config Template ✅

**Updated runner config template for consistency:**
- Changed from `docker://catthehacker/ubuntu:act-latest` to `docker://node:20-bookworm`
- Added comment explaining labels are stored in `.runner` file
- Aligned with actual registration labels

**File Changed:**
- `addons/forgejo/templates/runner-config.yml.j2`

### 6. Updated Label Verification ✅

**Updated label check to match new format:**

**Before:**
```yaml
- name: Check runner labels if already registered
  shell: cat /opt/forgejo-runner/.runner | grep -o '"{{ vm_role }}:host"'
```

**After:**
```yaml
- name: Check runner labels if already registered
  shell: cat /opt/forgejo-runner/.runner | grep -o '"{{ vm_role }}:docker://node:20-bookworm"'
```

**File Changed:**
- `shared/ansible/roles/system/forgejo-runner/tasks/main.yml` (line 214)

## Testing & Validation

### How to Test the Fixes

#### 1. Clean Deployment Test

```bash
# Deploy orchestrator
superdeploy orchestrator up

# Deploy project
superdeploy up -p cheapa

# Verify runners are registered correctly
```

#### 2. Check Runner Registration

**On orchestrator VM:**
```bash
# SSH to orchestrator
ssh superdeploy@<ORCHESTRATOR_IP>

# Check orchestrator runner status
sudo systemctl status forgejo-runner

# View runner logs
sudo journalctl -u forgejo-runner -f

# Check runner file
cat /opt/forgejo-runner/.runner
# Should show: "orchestrator:docker://node:20-bookworm"
```

**On project VMs:**
```bash
# SSH to project VM (e.g., cheapa-core-0)
ssh superdeploy@<PROJECT_VM_IP>

# Check runner status
sudo systemctl status forgejo-runner

# View runner logs
sudo journalctl -u forgejo-runner -f

# Check runner file and verify labels
cat /opt/forgejo-runner/.runner
# Should show: "cheapa:docker://node:20-bookworm", "core:docker://node:20-bookworm", etc.
```

#### 3. Verify in Forgejo UI

1. Access Forgejo: `http://<ORCHESTRATOR_IP>:3001`
2. Login as admin
3. Go to: Site Administration → Actions → Runners
4. Verify:
   - ✅ Orchestrator runner is registered with correct labels
   - ✅ All project VMs have registered runners
   - ✅ Labels show `docker://node:20-bookworm` executor
   - ✅ Runner names match VM hostnames

#### 4. Test Workflow Execution

Create a test workflow in your project:

```yaml
# .forgejo/workflows/test-runner.yml
name: Test Runner Labels
on: [workflow_dispatch]

jobs:
  test-orchestrator:
    runs-on: [self-hosted, orchestrator]
    steps:
      - name: Test orchestrator runner
        run: |
          echo "Running on orchestrator"
          node --version
          
  test-project:
    runs-on: [self-hosted, cheapa]
    steps:
      - name: Test project runner
        run: |
          echo "Running on project VM"
          node --version
          
  test-specific-vm:
    runs-on: [self-hosted, cheapa, core]
    steps:
      - name: Test specific VM
        run: |
          echo "Running on core VM"
          node --version
```

Push workflow and trigger manually:
1. Go to repository in Forgejo
2. Actions tab
3. Select "Test Runner Labels" workflow
4. Click "Run workflow"
5. Verify all jobs execute successfully on correct runners

#### 5. Check for Common Issues

**Issue: Token generation fails**
```bash
# On orchestrator VM
docker ps | grep forgejo
docker exec -u 1000:1000 orchestrator-forgejo forgejo actions generate-runner-token

# If fails, check logs
docker logs orchestrator-forgejo
```

**Issue: Runner not registered**
```bash
# Check if runner file exists
ls -la /opt/forgejo-runner/.runner

# If not, check Ansible logs in:
# superdeploy/logs/<project>/up/*.log

# Look for:
# - "Orchestrator not found in inventory!"
# - "Failed to generate runner registration token!"
# - "Token generation result: FAILED"
```

**Issue: Wrong labels after upgrade**
```bash
# Remove old runner registration
sudo systemctl stop forgejo-runner
rm /opt/forgejo-runner/.runner

# Re-run Ansible to re-register
superdeploy up -p cheapa --skip-terraform --tags foundation
```

## Migration Guide

### For Existing Deployments

If you have existing runners with old labels (`:host` executor), follow these steps:

#### 1. Update Codebase
```bash
cd /path/to/superdeploy
git pull  # Get latest fixes
```

#### 2. Re-register Orchestrator Runner
```bash
# SSH to orchestrator
ssh superdeploy@<ORCHESTRATOR_IP>

# Stop runner
sudo systemctl stop forgejo-runner

# Remove old registration
rm /opt/forgejo-runner/.runner

# Redeploy orchestrator (will re-register with correct labels)
superdeploy orchestrator up --skip-terraform --addon forgejo
```

#### 3. Re-register Project Runners
```bash
# For each project, run:
superdeploy up -p <project> --skip-terraform --tags foundation

# This will:
# 1. Check existing runner labels
# 2. Remove old runner config if labels are wrong
# 3. Re-register with correct labels
```

#### 4. Verify Migration
```bash
# On orchestrator and each VM:
cat /opt/forgejo-runner/.runner | grep labels

# Should see: "docker://node:20-bookworm" in all labels
# Should NOT see: ":host" anywhere
```

#### 5. Clean Up Duplicate Runners (if any)

In Forgejo UI:
1. Go to Site Administration → Actions → Runners
2. Delete any offline or duplicate runners
3. Keep only the latest runners with correct labels

Or via CLI on orchestrator:
```bash
# View runners in database
docker exec orchestrator-forgejo-db psql -U forgejo -d forgejo -c "SELECT id, name, labels FROM action_runner;"

# Delete duplicates (keep highest ID for each name)
docker exec orchestrator-forgejo-db psql -U forgejo -d forgejo -c "
DELETE FROM action_runner 
WHERE name = 'RUNNER_NAME' 
AND id NOT IN (
  SELECT MAX(id) FROM action_runner 
  WHERE name = 'RUNNER_NAME'
);"
```

## Expected Behavior After Fixes

### 1. Orchestrator Runner
- **Created during**: `superdeploy orchestrator up`
- **Registration**: Automatic, uses CLI token generation
- **Labels**: All use `docker://node:20-bookworm` executor
- **Scope**: Multi-project (serves all projects)
- **Service**: Running as systemd service

### 2. Project Runners
- **Created during**: `superdeploy up -p <project>`
- **Registration**: Automatic, delegates token generation to orchestrator
- **Labels**: All use `docker://node:20-bookworm` executor
- **Scope**: Project-specific (one per VM)
- **Service**: Running as systemd service on each VM

### 3. Workflow Matching
- `runs-on: [self-hosted, orchestrator]` → Runs on orchestrator VM
- `runs-on: [self-hosted, cheapa]` → Runs on any cheapa project VM
- `runs-on: [self-hosted, cheapa, core]` → Runs specifically on core VM
- `runs-on: ubuntu-latest` → Matches ANY runner with ubuntu-latest label

### 4. Error Messages
- Clear validation errors if orchestrator not in inventory
- Detailed token generation failure messages
- Helpful troubleshooting steps in error output
- Retry logic with delays for transient failures

## Files Changed Summary

| File | Changes | Impact |
|------|---------|--------|
| `shared/ansible/roles/system/forgejo-runner/tasks/main.yml` | Label format, YAML fix, error handling, validation | ⭐⭐⭐ Critical |
| `addons/forgejo/tasks/setup-runner.yml` | Label format, display messages | ⭐⭐⭐ Critical |
| `docs/RUNNER_ARCHITECTURE.md` | Documentation corrections | ⭐⭐ Important |
| `addons/forgejo/templates/runner-config.yml.j2` | Label format in config template | ⭐ Nice-to-have |

## Rollback Plan

If issues occur after applying fixes:

1. **Revert code changes:**
```bash
git revert <commit-hash>
```

2. **Keep existing runners running:**
```bash
# Don't stop existing runners if they're working
# Just redeploy with reverted code
```

3. **Manual runner registration:**
```bash
# If automated registration fails, register manually:
sudo systemctl stop forgejo-runner
rm /opt/forgejo-runner/.runner

forgejo-runner register \
  --no-interactive \
  --instance "http://<ORCHESTRATOR_IP>:3001" \
  --token "<TOKEN>" \
  --name "<HOSTNAME>" \
  --labels "self-hosted:docker://node:20-bookworm,ubuntu-latest:docker://node:20-bookworm,<project>:docker://node:20-bookworm,<role>:docker://node:20-bookworm"
```

## Related Issues Resolved

1. ✅ Runners not being created on project VMs
2. ✅ Label mismatch causing workflow failures
3. ✅ Silent failures during token generation
4. ✅ YAML syntax errors in Ansible playbooks
5. ✅ Missing orchestrator validation
6. ✅ Inconsistent documentation

## Future Improvements

1. **Automated runner health checks**: Monitor runner status and auto-restart if unhealthy
2. **Runner label validation**: Add pre-flight checks to validate label consistency
3. **Token caching**: Cache registration tokens to avoid repeated generation
4. **Runner pool management**: Implement runner scaling based on workload
5. **Better duplicate cleanup**: Automated cleanup of stale/duplicate runners

## Support

If you encounter issues after applying these fixes:

1. Check the logs: `superdeploy/logs/<project>/up/*.log`
2. Review this document's testing section
3. Check runner status: `sudo systemctl status forgejo-runner`
4. View runner logs: `sudo journalctl -u forgejo-runner -f`
5. Verify Forgejo is running: `docker ps | grep forgejo`
6. Check Forgejo logs: `docker logs orchestrator-forgejo`

For persistent issues, collect:
- Ansible logs from `superdeploy/logs/`
- Runner logs: `sudo journalctl -u forgejo-runner --since "1 hour ago" > runner.log`
- Forgejo logs: `docker logs orchestrator-forgejo > forgejo.log`
- Runner file: `cat /opt/forgejo-runner/.runner`

