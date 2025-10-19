#!/bin/bash
# Generate Ansible Inventory from Terraform Outputs
# Run this after terraform apply to auto-generate inventory

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INFRA_DIR="$SCRIPT_DIR/../../infra"
INVENTORY_FILE="$SCRIPT_DIR/../../ansible/inventories/dev.ini"

echo "🔄 Generating Ansible inventory from Terraform outputs..."

# Change to infra directory
cd "$INFRA_DIR"

# Get Terraform outputs as JSON
TF_OUTPUT=$(terraform output -json)

# Extract VM IPs
CORE_IPS=$(echo "$TF_OUTPUT" | jq -r '.vm_core_public_ips.value[]' 2>/dev/null || echo "")
SCRAPE_IPS=$(echo "$TF_OUTPUT" | jq -r '.vm_scrape_public_ips.value[]' 2>/dev/null || echo "")
PROXY_IPS=$(echo "$TF_OUTPUT" | jq -r '.vm_proxy_public_ips.value[]' 2>/dev/null || echo "")

# Extract VM names
CORE_NAMES=$(echo "$TF_OUTPUT" | jq -r '.vm_core_names.value[]' 2>/dev/null || echo "")
SCRAPE_NAMES=$(echo "$TF_OUTPUT" | jq -r '.vm_scrape_names.value[]' 2>/dev/null || echo "")
PROXY_NAMES=$(echo "$TF_OUTPUT" | jq -r '.vm_proxy_names.value[]' 2>/dev/null || echo "")

# Generate inventory file
cat > "$INVENTORY_FILE" << 'HEADER'
# Auto-generated Ansible inventory from Terraform
# Generated at: $(date)

HEADER

# Add CORE hosts
echo "[core]" >> "$INVENTORY_FILE"
if [ -n "$CORE_IPS" ]; then
    i=0
    for ip in $CORE_IPS; do
        name=$(echo "$CORE_NAMES" | sed -n "$((i+1))p")
        echo "$name ansible_host=$ip ansible_user=superdeploy ansible_ssh_private_key_file=~/.ssh/cfk_gcp" >> "$INVENTORY_FILE"
        ((i++))
    done
fi
echo "" >> "$INVENTORY_FILE"

# Add SCRAPE hosts
echo "[scrape]" >> "$INVENTORY_FILE"
if [ -n "$SCRAPE_IPS" ]; then
    i=0
    for ip in $SCRAPE_IPS; do
        name=$(echo "$SCRAPE_NAMES" | sed -n "$((i+1))p")
        echo "$name ansible_host=$ip ansible_user=superdeploy ansible_ssh_private_key_file=~/.ssh/cfk_gcp" >> "$INVENTORY_FILE"
        ((i++))
    done
fi
echo "" >> "$INVENTORY_FILE"

# Add PROXY hosts
echo "[proxy]" >> "$INVENTORY_FILE"
if [ -n "$PROXY_IPS" ]; then
    i=0
    for ip in $PROXY_IPS; do
        name=$(echo "$PROXY_NAMES" | sed -n "$((i+1))p")
        echo "$name ansible_host=$ip ansible_user=superdeploy ansible_ssh_private_key_file=~/.ssh/cfk_gcp" >> "$INVENTORY_FILE"
        ((i++))
    done
fi
echo "" >> "$INVENTORY_FILE"

# Add global variables
cat >> "$INVENTORY_FILE" << 'FOOTER'
[all:vars]
ansible_python_interpreter=/usr/bin/python3
ansible_become=yes
ansible_become_method=sudo
FOOTER

echo "✅ Inventory generated at: $INVENTORY_FILE"
echo ""
echo "Preview:"
cat "$INVENTORY_FILE"

