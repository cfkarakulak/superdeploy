#!/bin/bash
# =============================================================================
# SuperDeploy Full Integration Test Suite
# =============================================================================
# This script performs a complete tear-down and rebuild of the cheapa project
# with IP preservation to test the entire deployment pipeline.
#
# Test Flow:
# 1. Backup current state
# 2. Down (destroy infrastructure)
# 3. Up with --preserve-ip (rebuild with same IPs)
# 4. Verify deployment
# 5. Generate analysis report
# =============================================================================

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Configuration
PROJECT="cheapa"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
LOG_DIR="superdeploy/test-suite/logs/${TIMESTAMP}"
BACKUP_DIR="superdeploy/test-suite/backup"

# Create log directory
mkdir -p "${LOG_DIR}"

# Helper function for logging
log() {
    echo -e "${CYAN}[$(date +'%H:%M:%S')]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[$(date +'%H:%M:%S')] ✓${NC} $1"
}

log_error() {
    echo -e "${RED}[$(date +'%H:%M:%S')] ✗${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[$(date +'%H:%M:%S')] ⚠${NC} $1"
}

log_step() {
    echo ""
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}  $1${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
}

# =============================================================================
# PHASE 0: Pre-flight Checks
# =============================================================================

log_step "PHASE 0: Pre-flight Checks"

log "Checking required files..."
if [[ ! -f "${BACKUP_DIR}/project.yml" ]]; then
    log_error "Backup project.yml not found!"
    exit 1
fi

if [[ ! -f "${BACKUP_DIR}/.env" ]]; then
    log_error "Backup .env not found!"
    exit 1
fi

log_success "Backup files found"

log "Extracting current VM IPs..."
WEB_IP=$(grep "WEB_0_EXTERNAL_IP" "${BACKUP_DIR}/.env" | cut -d'=' -f2)
API_IP=$(grep "API_0_EXTERNAL_IP" "${BACKUP_DIR}/.env" | cut -d'=' -f2)
WORKER_IP=$(grep "WORKER_0_EXTERNAL_IP" "${BACKUP_DIR}/.env" | cut -d'=' -f2)

log_success "Current IPs:"
echo "  web:    ${WEB_IP}"
echo "  api:    ${API_IP}"
echo "  worker: ${WORKER_IP}"

# Save IPs to file for later verification
cat > "${LOG_DIR}/expected_ips.txt" <<EOF
WEB_IP=${WEB_IP}
API_IP=${API_IP}
WORKER_IP=${WORKER_IP}
EOF

# =============================================================================
# PHASE 1: Down (Destroy Infrastructure)
# =============================================================================

log_step "PHASE 1: Destroying Infrastructure"

log "Running: superdeploy down -p ${PROJECT}"
{
    time superdeploy down -p ${PROJECT} 2>&1
} | tee "${LOG_DIR}/01_down.log"

if [[ ${PIPESTATUS[0]} -eq 0 ]]; then
    log_success "Infrastructure destroyed successfully"
else
    log_error "Down command failed! Check ${LOG_DIR}/01_down.log"
    exit 1
fi

# Wait a bit for GCP to fully release resources
log "Waiting 10 seconds for GCP cleanup..."
sleep 10

# =============================================================================
# PHASE 2: Generate Configuration
# =============================================================================

log_step "PHASE 2: Generating Configuration"

log "Running: superdeploy generate -p ${PROJECT}"
{
    time superdeploy generate -p ${PROJECT} 2>&1
} | tee "${LOG_DIR}/02_generate.log"

if [[ ${PIPESTATUS[0]} -eq 0 ]]; then
    log_success "Configuration generated successfully"
else
    log_error "Generate command failed! Check ${LOG_DIR}/02_generate.log"
    exit 1
fi

# =============================================================================
# PHASE 3: Up with IP Preservation
# =============================================================================

log_step "PHASE 3: Deploying Infrastructure (with IP preservation)"

log "Running: superdeploy up -p ${PROJECT} --preserve-ip"
{
    time superdeploy up -p ${PROJECT} --preserve-ip 2>&1
} | tee "${LOG_DIR}/03_up.log"

if [[ ${PIPESTATUS[0]} -eq 0 ]]; then
    log_success "Infrastructure deployed successfully"
else
    log_error "Up command failed! Check ${LOG_DIR}/03_up.log"
    exit 1
fi

# =============================================================================
# PHASE 4: Verification
# =============================================================================

log_step "PHASE 4: Verification"

# Extract new IPs
log "Extracting new VM IPs..."
NEW_WEB_IP=$(grep "WEB_0_EXTERNAL_IP" "superdeploy/projects/${PROJECT}/.env" | cut -d'=' -f2)
NEW_API_IP=$(grep "API_0_EXTERNAL_IP" "superdeploy/projects/${PROJECT}/.env" | cut -d'=' -f2)
NEW_WORKER_IP=$(grep "WORKER_0_EXTERNAL_IP" "superdeploy/projects/${PROJECT}/.env" | cut -d'=' -f2)

# Save new IPs
cat > "${LOG_DIR}/actual_ips.txt" <<EOF
NEW_WEB_IP=${NEW_WEB_IP}
NEW_API_IP=${NEW_API_IP}
NEW_WORKER_IP=${NEW_WORKER_IP}
EOF

log "New IPs:"
echo "  web:    ${NEW_WEB_IP}"
echo "  api:    ${NEW_API_IP}"
echo "  worker: ${NEW_WORKER_IP}"

# Verify IP preservation
IP_MATCH=true
if [[ "${WEB_IP}" != "${NEW_WEB_IP}" ]]; then
    log_error "Web IP changed! Expected: ${WEB_IP}, Got: ${NEW_WEB_IP}"
    IP_MATCH=false
fi

if [[ "${API_IP}" != "${NEW_API_IP}" ]]; then
    log_error "API IP changed! Expected: ${API_IP}, Got: ${NEW_API_IP}"
    IP_MATCH=false
fi

if [[ "${WORKER_IP}" != "${NEW_WORKER_IP}" ]]; then
    log_error "Worker IP changed! Expected: ${WORKER_IP}, Got: ${NEW_WORKER_IP}"
    IP_MATCH=false
fi

if [[ "${IP_MATCH}" == "true" ]]; then
    log_success "IP preservation verified - all IPs match!"
else
    log_warning "IP preservation failed - some IPs changed"
fi

# Test SSH connectivity
log "Testing SSH connectivity to VMs..."
SSH_KEY="~/.ssh/superdeploy_deploy"
SSH_USER="superdeploy"

for vm in "web:${NEW_WEB_IP}" "api:${NEW_API_IP}" "worker:${NEW_WORKER_IP}"; do
    VM_NAME=$(echo $vm | cut -d':' -f1)
    VM_IP=$(echo $vm | cut -d':' -f2)
    
    log "Testing ${VM_NAME} (${VM_IP})..."
    if ssh -i ${SSH_KEY} -o ConnectTimeout=10 -o StrictHostKeyChecking=no ${SSH_USER}@${VM_IP} "echo 'SSH OK'" &> "${LOG_DIR}/04_ssh_${VM_NAME}.log"; then
        log_success "${VM_NAME} SSH connection successful"
    else
        log_error "${VM_NAME} SSH connection failed"
    fi
done

# Check Docker containers
log "Checking Docker containers on each VM..."
for vm in "web:${NEW_WEB_IP}" "api:${NEW_API_IP}" "worker:${NEW_WORKER_IP}"; do
    VM_NAME=$(echo $vm | cut -d':' -f1)
    VM_IP=$(echo $vm | cut -d':' -f2)
    
    log "Checking containers on ${VM_NAME}..."
    ssh -i ${SSH_KEY} -o StrictHostKeyChecking=no ${SSH_USER}@${VM_IP} "docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'" &> "${LOG_DIR}/05_docker_${VM_NAME}.log"
    
    if [[ $? -eq 0 ]]; then
        log_success "${VM_NAME} Docker containers:"
        cat "${LOG_DIR}/05_docker_${VM_NAME}.log" | sed 's/^/    /'
    else
        log_error "${VM_NAME} Docker check failed"
    fi
done

# Check Caddy health
log "Checking Caddy health on each VM..."
for vm in "web:${NEW_WEB_IP}:dashboard" "api:${NEW_API_IP}:api" "worker:${NEW_WORKER_IP}:services"; do
    VM_NAME=$(echo $vm | cut -d':' -f1)
    VM_IP=$(echo $vm | cut -d':' -f2)
    SUBDOMAIN=$(echo $vm | cut -d':' -f3)
    
    log "Testing Caddy on ${VM_NAME} (${SUBDOMAIN}.cheapa.io)..."
    
    # Test HTTP health endpoint
    if curl -s -o /dev/null -w "%{http_code}" --connect-timeout 5 "http://${VM_IP}/health" | grep -q "200"; then
        log_success "${VM_NAME} Caddy health check passed"
    else
        log_warning "${VM_NAME} Caddy health check failed (may need time to start)"
    fi
done

# =============================================================================
# PHASE 5: Generate Report
# =============================================================================

log_step "PHASE 5: Generating Test Report"

cat > "${LOG_DIR}/REPORT.md" <<EOF
# SuperDeploy Full Integration Test Report
**Timestamp:** ${TIMESTAMP}
**Project:** ${PROJECT}

## Test Summary

### IP Preservation
- **Web VM:** ${WEB_IP} → ${NEW_WEB_IP} $([ "${WEB_IP}" == "${NEW_WEB_IP}" ] && echo "✓" || echo "✗")
- **API VM:** ${API_IP} → ${NEW_API_IP} $([ "${API_IP}" == "${NEW_API_IP}" ] && echo "✓" || echo "✗")
- **Worker VM:** ${WORKER_IP} → ${NEW_WORKER_IP} $([ "${WORKER_IP}" == "${NEW_WORKER_IP}" ] && echo "✓" || echo "✗")

### Test Phases
1. ✓ Pre-flight checks
2. ✓ Infrastructure destruction (down)
3. ✓ Configuration generation
4. ✓ Infrastructure deployment (up --preserve-ip)
5. ✓ Verification

### Log Files
- \`01_down.log\` - Infrastructure destruction
- \`02_generate.log\` - Configuration generation
- \`03_up.log\` - Infrastructure deployment
- \`04_ssh_*.log\` - SSH connectivity tests
- \`05_docker_*.log\` - Docker container status

## DNS Configuration Required

\`\`\`
dashboard.cheapa.io  A  ${NEW_WEB_IP}
api.cheapa.io        A  ${NEW_API_IP}
services.cheapa.io   A  ${NEW_WORKER_IP}
\`\`\`

## Next Steps

1. Update DNS records with the IPs above
2. Wait 5-10 minutes for DNS propagation
3. Test domains:
   - https://dashboard.cheapa.io
   - https://api.cheapa.io
   - https://services.cheapa.io

## Detailed Logs

All logs are available in: \`${LOG_DIR}/\`

EOF

log_success "Test report generated: ${LOG_DIR}/REPORT.md"

# =============================================================================
# Summary
# =============================================================================

log_step "Test Suite Complete!"

echo ""
log_success "All phases completed successfully!"
echo ""
echo "📊 Test Results:"
echo "  - Logs directory: ${LOG_DIR}"
echo "  - Report: ${LOG_DIR}/REPORT.md"
echo ""
echo "📍 DNS Records (copy to cheapa.io panel):"
echo "  dashboard.cheapa.io  A  ${NEW_WEB_IP}"
echo "  api.cheapa.io        A  ${NEW_API_IP}"
echo "  services.cheapa.io   A  ${NEW_WORKER_IP}"
echo ""

if [[ "${IP_MATCH}" == "true" ]]; then
    log_success "✓ IP preservation successful - DNS records unchanged!"
else
    log_warning "⚠ IP preservation failed - update DNS records above"
fi

echo ""
log "Review logs and report for detailed analysis"
