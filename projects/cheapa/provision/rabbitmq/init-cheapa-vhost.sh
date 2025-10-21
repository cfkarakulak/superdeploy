#!/bin/bash
set -e

# ═══════════════════════════════════════════════════════════════════════════
# CHEAPA PROJECT - RabbitMQ Vhost Initialization
# ═══════════════════════════════════════════════════════════════════════════
# This script creates a dedicated vhost and user for Cheapa project
# Run manually after RabbitMQ is up
# ═══════════════════════════════════════════════════════════════════════════

RABBITMQ_CONTAINER="superdeploy-rabbitmq"

echo "Creating Cheapa RabbitMQ vhost and user..."

# Create vhost
docker exec $RABBITMQ_CONTAINER rabbitmqctl add_vhost cheapa || echo "Vhost already exists"

# Create user
docker exec $RABBITMQ_CONTAINER rabbitmqctl add_user cheapa_user "${CHEAPA_RABBITMQ_PASSWORD}" || echo "User already exists"

# Set permissions
docker exec $RABBITMQ_CONTAINER rabbitmqctl set_permissions -p cheapa cheapa_user ".*" ".*" ".*"

# Set tags (optional - for management UI access)
docker exec $RABBITMQ_CONTAINER rabbitmqctl set_user_tags cheapa_user management

echo "✅ Cheapa RabbitMQ vhost initialized: cheapa → cheapa_user"

