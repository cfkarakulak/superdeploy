# SuperDeploy Logging System

## Overview

SuperDeploy now features an improved logging system that provides:
- **Clean console output** with progress indicators
- **Real-time logging** to files for debugging
- **Error highlighting** with context
- **Verbose mode** for detailed output

## Usage

### Default Mode (Clean UI)

```bash
superdeploy orchestrator up-v2
```

**Console Output:**
```
🚀 Deploying Global Orchestrator

▶ Loading orchestrator configuration
✓ Configuration loaded

▶ Checking secrets
✓ Using existing secrets from .env

▶ Provisioning VM with Terraform
✓ Initializing Terraform
✓ Provisioning infrastructure (this may take 2-3 minutes)
✓ VM provisioned successfully

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ Orchestrator Deployed!
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Logs saved to: logs/orchestrator_up_20251031_153000.log
```

### Verbose Mode (Full Output)

```bash
superdeploy orchestrator up-v2 --verbose
```

Shows all command output directly in console (like the old behavior).

## Log Files

### Location

All logs are saved to: `logs/`

Format: `{project}_{operation}_{timestamp}.log`

Examples:
- `logs/orchestrator_up_20251031_153000.log`
- `logs/cheapa_up_20251031_154500.log`

### Log Structure

```
================================================================================
SuperDeploy Deployment Log
================================================================================
Project: orchestrator
Operation: up
Started: 2025-10-31T15:30:00.123456
================================================================================

[15:30:00] [INFO] Step: Loading orchestrator configuration
[15:30:00] [INFO] Configuration loaded
[15:30:01] [DEBUG] Executing: terraform init
  [stdout] Initializing the backend...
  [stdout] Terraform has been successfully initialized!

================================================================================
Completed: 2025-10-31T15:35:00.123456
Status: SUCCESS
================================================================================
```

### Error Logs

Errors are marked with clear boundaries for easy grepping:

```
!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
ERROR OCCURRED
!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
Terraform apply failed

Context: Command: terraform apply -auto-approve
!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
```

**Grep for errors:**
```bash
grep -A 5 "ERROR OCCURRED" logs/orchestrator_up_*.log
```

## Error Display

When an error occurs, you'll see:

```
╭────────────────────────────────── ❌ Error ──────────────────────────────────╮
│ Terraform apply failed                                                       │
│                                                                              │
│ Command: terraform apply -auto-approve                                      │
╰──────────────────────────────────────────────────────────────────────────────╯

Full logs: logs/orchestrator_up_20251031_153000.log
```

## Real-Time Logging

Logs are written in real-time (unbuffered), so you can:

```bash
# Watch logs while deployment is running
tail -f logs/orchestrator_up_20251031_153000.log

# In another terminal
superdeploy orchestrator up-v2
```

## Migration Guide

### Old Commands

```bash
superdeploy orchestrator up
superdeploy up -p myproject
```

### New Commands (V2)

```bash
# Test new logging system
superdeploy orchestrator up-v2
superdeploy up-v2 -p myproject

# Once tested, old commands will be replaced
```

## Benefits

1. **Cleaner Console**: No more walls of Terraform/Ansible output
2. **Better Debugging**: All output saved to logs with timestamps
3. **Error Context**: Clear error messages with context
4. **Real-Time**: Watch logs while deployment runs
5. **Searchable**: Easy to grep for errors or specific steps

## Implementation

The logging system is implemented in `cli/logger.py`:

- `DeployLogger`: Main logger class
- `run_with_progress()`: Run commands with progress indicators
- Context manager support for automatic cleanup

Example usage:

```python
from cli.logger import DeployLogger, run_with_progress

with DeployLogger("myproject", "up", verbose=False) as logger:
    logger.step("Provisioning infrastructure")
    
    returncode, stdout, stderr = run_with_progress(
        logger,
        "terraform apply -auto-approve",
        "Applying Terraform changes"
    )
    
    if returncode != 0:
        logger.log_error("Terraform failed", context=stderr)
        raise SystemExit(1)
    
    logger.success("Infrastructure provisioned")
```
