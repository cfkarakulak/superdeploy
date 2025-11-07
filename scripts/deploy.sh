#!/bin/bash
# =============================================================================
# SuperDeploy Remote Deployment Script
# =============================================================================
# Fetched and executed by GitHub/Forgejo workflows
# This script builds, pushes, and deploys Docker containers
# =============================================================================

set -e

echo "🚀 SuperDeploy - Remote Deployment"
echo "=================================="
echo ""

# =============================================================================
# 1. READ CONFIGURATION
# =============================================================================

# Read .superdeploy marker file
if [ ! -f ".superdeploy" ]; then
    echo "❌ No .superdeploy file found!"
    echo "This repo is not managed by SuperDeploy."
    exit 1
fi

# Parse YAML (simple grep method)
PROJECT=$(grep "^project:" .superdeploy | cut -d: -f2 | xargs)
APP=$(grep "^app:" .superdeploy | cut -d: -f2 | xargs)

echo "📦 Project: $PROJECT"
echo "📦 App: $APP"
echo ""

# Validate required secrets
if [ -z "$ORCHESTRATOR_IP" ]; then
    echo "❌ ORCHESTRATOR_IP not set!"
    echo "Set this in GitHub/Forgejo secrets."
    exit 1
fi

if [ -z "$DOCKER_USERNAME" ]; then
    echo "❌ DOCKER_USERNAME not set!"
    echo "Set this in GitHub/Forgejo secrets."
    exit 1
fi

if [ -z "$DOCKER_TOKEN" ]; then
    echo "❌ DOCKER_TOKEN not set!"
    echo "Set this in GitHub/Forgejo secrets."
    exit 1
fi

# Docker image name
REGISTRY="${DOCKER_REGISTRY:-docker.io}"
IMAGE="${DOCKER_ORG:-$DOCKER_USERNAME}/${APP}"
TAG="${GITHUB_SHA:-${GITEA_SHA:-latest}}"
FULL_IMAGE="${REGISTRY}/${IMAGE}:${TAG}"
LATEST_IMAGE="${REGISTRY}/${IMAGE}:latest"

echo "🔧 Orchestrator: $ORCHESTRATOR_IP"
echo "🐳 Image: $FULL_IMAGE"
echo ""

# =============================================================================
# 2. BUILD DOCKER IMAGE
# =============================================================================

echo "📦 Building Docker image..."
echo "─────────────────────────────"

docker build -t "$FULL_IMAGE" -t "$LATEST_IMAGE" .

echo "✅ Build complete!"
echo ""

# =============================================================================
# 3. PUSH TO REGISTRY
# =============================================================================

echo "📤 Pushing to registry..."
echo "─────────────────────────────"

# Docker login
echo "$DOCKER_TOKEN" | docker login "$REGISTRY" -u "$DOCKER_USERNAME" --password-stdin

# Push both tags
docker push "$FULL_IMAGE"
docker push "$LATEST_IMAGE"

echo "✅ Push complete!"
echo ""

# =============================================================================
# 4. DEPLOY TO VM
# =============================================================================

echo "🚀 Deploying to VM..."
echo "─────────────────────────────"

# SSH key setup (if provided)
if [ -n "$SSH_PRIVATE_KEY" ]; then
    mkdir -p ~/.ssh
    echo "$SSH_PRIVATE_KEY" > ~/.ssh/deploy_key
    chmod 600 ~/.ssh/deploy_key
    SSH_OPTS="-i ~/.ssh/deploy_key"
fi

# Deploy command
ssh ${SSH_OPTS} -o StrictHostKeyChecking=no superdeploy@${ORCHESTRATOR_IP} << EOF
    set -e
    
    echo "📥 Pulling latest image..."
    cd /opt/superdeploy/projects/${PROJECT}/compose
    docker compose pull ${APP}
    
    echo "♻️  Restarting container..."
    docker compose up -d ${APP}
    
    echo "🧹 Cleaning up old images..."
    docker image prune -f
    
    echo "✅ Deployment complete!"
EOF

echo ""
echo "=================================="
echo "✅ Deployment successful!"
echo "=================================="
echo ""
echo "🔗 App: ${APP}"
echo "🏷️  Tag: ${TAG}"
echo "🌐 Image: ${FULL_IMAGE}"
echo ""
