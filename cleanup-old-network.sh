#!/bin/bash
# Cleanup old shared network (superdeploy-dev-network)

set -e

echo "🗑️  Cleaning up old shared network..."

# Delete firewall rules
echo "Deleting firewall rules..."
for rule in $(gcloud compute firewall-rules list --filter="network:superdeploy-dev-network" --format="value(name)"); do
    echo "  - Deleting $rule"
    gcloud compute firewall-rules delete "$rule" --quiet
done

# Delete subnet
echo "Deleting subnet..."
gcloud compute networks subnets delete superdeploy-dev-network-subnet --region=us-central1 --quiet 2>/dev/null || echo "  (subnet not found or already deleted)"

# Delete network
echo "Deleting network..."
gcloud compute networks delete superdeploy-dev-network --quiet

echo "✅ Cleanup complete!"
