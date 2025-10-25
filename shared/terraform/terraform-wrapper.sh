#!/bin/bash
# =============================================================================
# Terraform Wrapper - Uses environment variables passed from Python
# =============================================================================

set -e

# Environment variables are now passed from Python CLI (via load_env)
# No need to read .env file anymore

# Validate required vars
if [ -z "$GCP_PROJECT_ID" ] || [ "$GCP_PROJECT_ID" = "your-gcp-project-id-here" ]; then
    echo "❌ ERROR: GCP_PROJECT_ID not set"
    echo "This should be passed from the CLI via project.yml"
    exit 1
fi

if [ -z "$SSH_KEY_PATH" ]; then
    echo "❌ ERROR: SSH_KEY_PATH not set"
    echo "This should be passed from the CLI via project.yml"
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
# Auto-generated from environment variables - DO NOT EDIT MANUALLY

project_id   = "$GCP_PROJECT_ID"
project_name = "${PROJECT_NAME:-superdeploy}"
environment  = "dev"

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

network_name = "${PROJECT_NAME:-superdeploy}-dev-network"
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

echo "✅ Generated envs/dev/gcp.auto.tfvars"

# Select or create workspace for project isolation
if [ -n "$PROJECT_NAME" ]; then
    echo "🔧 Using Terraform workspace: $PROJECT_NAME"
    terraform workspace select "$PROJECT_NAME" 2>/dev/null || terraform workspace new "$PROJECT_NAME"
fi

# Run terraform command with tfvars file (only for plan/apply, not for output)
if [[ "$1" == "init" ]]; then
    # Init - conditionally pass backend config only if USE_REMOTE_STATE=true
    if [ "${USE_REMOTE_STATE:-false}" == "true" ]; then
        echo "🪣 Using GCS backend"
        BUCKET="superdeploy-tfstate-${GCP_PROJECT_ID}"
        terraform "$@" -backend-config="bucket=${BUCKET}"
    else
        echo "💾 Using local backend (per-project workspace)"
        terraform "$@"
    fi
elif [[ "$1" == "output" ]]; then
    terraform "$@"
else
    terraform "$@" -var-file=envs/dev/gcp.auto.tfvars
fi

