#!/bin/bash
# =============================================================================
# Terraform Wrapper - Reads .env and generates tfvars
# =============================================================================

set -e

# Load .env from current directory
ENV_FILE=".env"

if [ ! -f "$ENV_FILE" ]; then
    echo "❌ ERROR: $ENV_FILE not found!"
    echo "Run: make init"
    exit 1
fi

# Source .env
set -a
source "$ENV_FILE"
set +a

# Validate required vars
if [ -z "$GCP_PROJECT_ID" ] || [ "$GCP_PROJECT_ID" = "your-gcp-project-id-here" ]; then
    echo "❌ ERROR: GCP_PROJECT_ID not configured in .env"
    exit 1
fi

if [ -z "$SSH_KEY_PATH" ]; then
    echo "❌ ERROR: SSH_KEY_PATH not configured in .env"
    exit 1
fi

# Expand tilde in SSH_KEY_PATH
SSH_KEY_PATH_EXPANDED="${SSH_KEY_PATH/#\~/$HOME}"

# Check if SSH public key exists
if [ ! -f "${SSH_KEY_PATH_EXPANDED}.pub" ]; then
    echo "❌ ERROR: SSH public key not found: ${SSH_KEY_PATH_EXPANDED}.pub"
    echo "💡 Generate it with: ssh-keygen -t rsa -b 4096 -f ${SSH_KEY_PATH_EXPANDED}"
    exit 1
fi

# Generate tfvars
cat > envs/dev/gcp.auto.tfvars <<EOF
# Auto-generated from .env - DO NOT EDIT MANUALLY
# Edit ../superdeploy/.env instead

project_id  = "$GCP_PROJECT_ID"
environment = "dev"

region = "${GCP_REGION:-us-central1}"
zone   = "${GCP_ZONE:-us-central1-a}"

vm_counts = {
  core   = 1
  scrape = 1
  proxy  = 1
}

machine_types = {
  core   = "${VM_MACHINE_TYPE:-e2-standard-2}"
  scrape = "e2-standard-4"
  proxy  = "e2-small"
}

disk_sizes = {
  core   = ${VM_DISK_SIZE:-50}
  scrape = 100
  proxy  = 20
}

network_name = "superdeploy-dev-network"
subnet_cidr  = "10.0.0.0/24"

admin_source_ranges = ["0.0.0.0/0"]
ssh_pub_key_path = "${SSH_KEY_PATH_EXPANDED}.pub"

vm_image = "${VM_IMAGE:-debian-cloud/debian-11}"

tags = {
  core   = ["core", "edge", "api", "queue", "db", "proxy-registry"]
  scrape = ["worker", "scrape", "browser"]
  proxy  = ["proxy", "socks", "tinyproxy"]
}
EOF

echo "✅ Generated envs/dev/gcp.auto.tfvars from .env"

# Run terraform command with tfvars file (only for plan/apply, not for output)
if [[ "$1" == "output" ]]; then
    terraform "$@"
else
    terraform "$@" -var-file=envs/dev/gcp.auto.tfvars
fi

