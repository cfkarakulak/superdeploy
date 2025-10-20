#!/bin/bash
# =============================================================================
# SuperDeploy Rollback Script
# =============================================================================
# Instantly rollback to a previous version by redeploying an old image tag
#
# Usage:
#   ./scripts/rollback.sh <vm> <service> <tag>
#
# Examples:
#   ./scripts/rollback.sh core api abc123
#   ./scripts/rollback.sh core dashboard v1.2.0
#   ./scripts/rollback.sh scrape worker xyz789

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# ============================================================================
# Validate arguments
# ============================================================================
if [ $# -ne 3 ]; then
    echo -e "${RED}❌ ERROR: Invalid arguments${NC}"
    echo ""
    echo "Usage: $0 <vm> <service> <tag>"
    echo ""
    echo "Examples:"
    echo "  $0 core api abc123"
    echo "  $0 core dashboard v1.2.0"
    echo "  $0 scrape worker xyz789"
    echo ""
    exit 1
fi

VM=$1
SERVICE=$2
TAG=$3

# ============================================================================
# Load environment
# ============================================================================
if [ ! -f .env ]; then
    echo -e "${RED}❌ ERROR: .env not found!${NC}"
    echo "Run this script from superdeploy/ directory"
    exit 1
fi

set -a
source .env
set +a

# ============================================================================
# Determine workflow and input parameter
# ============================================================================
case "$VM" in
    core)
        WORKFLOW="deploy-core-v2.yml"
        case "$SERVICE" in
            api)
                INPUT_PARAM="api_image_tag"
                ;;
            dashboard)
                INPUT_PARAM="dashboard_image_tag"
                ;;
            proxy-registry|proxy_registry)
                INPUT_PARAM="proxy_registry_image_tag"
                ;;
            *)
                echo -e "${RED}❌ ERROR: Invalid service '$SERVICE' for VM 'core'${NC}"
                echo "Valid services: api, dashboard, proxy-registry"
                exit 1
                ;;
        esac
        ;;
    scrape)
        WORKFLOW="deploy-scrape-v2.yml"
        case "$SERVICE" in
            worker)
                INPUT_PARAM="worker_image_tag"
                ;;
            *)
                echo -e "${RED}❌ ERROR: Invalid service '$SERVICE' for VM 'scrape'${NC}"
                echo "Valid services: worker"
                exit 1
                ;;
        esac
        ;;
    proxy)
        echo -e "${YELLOW}⚠️  Proxy VM doesn't use image-based deployment yet${NC}"
        exit 1
        ;;
    *)
        echo -e "${RED}❌ ERROR: Invalid VM '$VM'${NC}"
        echo "Valid VMs: core, scrape, proxy"
        exit 1
        ;;
esac

# ============================================================================
# Confirmation
# ============================================================================
echo -e "${YELLOW}⚠️  ROLLBACK CONFIRMATION${NC}"
echo ""
echo -e "  ${BLUE}VM:${NC}      $VM"
echo -e "  ${BLUE}Service:${NC} $SERVICE"
echo -e "  ${BLUE}Tag:${NC}     $TAG"
echo ""
read -p "Are you sure you want to rollback? (yes/no): " CONFIRM

if [ "$CONFIRM" != "yes" ]; then
    echo -e "${YELLOW}❌ Rollback cancelled${NC}"
    exit 0
fi

# ============================================================================
# Trigger deployment with old tag
# ============================================================================
echo ""
echo -e "${GREEN}🚀 Triggering rollback...${NC}"

API_URL="http://${CORE_EXTERNAL_IP}:3001/api/v1/repos/cradexco/superdeploy-app/actions/workflows/${WORKFLOW}/dispatches"

# Build JSON payload
PAYLOAD=$(cat <<EOF
{
  "ref": "master",
  "inputs": {
    "${INPUT_PARAM}": "${TAG}"
  }
}
EOF
)

# Get Forgejo credentials from .env
ADMIN_USER=${FORGEJO_ADMIN_USER:-cradexco}
ADMIN_PASS=${FORGEJO_ADMIN_PASSWORD}

# URL-encode password
ENCODED_PASS=$(printf '%s' "$ADMIN_PASS" | jq -sRr @uri)

# Trigger workflow
HTTP_CODE=$(curl -X POST \
    -u "${ADMIN_USER}:${ADMIN_PASS}" \
    -H "Content-Type: application/json" \
    -d "$PAYLOAD" \
    -w "%{http_code}" \
    -o /tmp/rollback-response.json \
    -s \
    "$API_URL")

if [ "$HTTP_CODE" -eq 204 ] || [ "$HTTP_CODE" -eq 200 ]; then
    echo -e "${GREEN}✅ Rollback triggered successfully!${NC}"
    echo ""
    echo -e "${BLUE}📊 Monitor deployment:${NC}"
    echo "  http://${CORE_EXTERNAL_IP}:3001/cradexco/superdeploy-app/actions"
    echo ""
    echo -e "${YELLOW}⏳ Rollback will complete in ~60 seconds${NC}"
else
    echo -e "${RED}❌ Failed to trigger rollback (HTTP $HTTP_CODE)${NC}"
    cat /tmp/rollback-response.json
    exit 1
fi

# ============================================================================
# Show version history
# ============================================================================
echo ""
echo -e "${BLUE}📜 Recent version history:${NC}"
git log --oneline -5 -- "deploy/compose/vm${VM}/.*env.versions" 2>/dev/null || echo "  (no history found)"
echo ""

