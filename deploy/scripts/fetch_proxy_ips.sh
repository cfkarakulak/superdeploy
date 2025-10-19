#!/bin/bash
# Fetch Proxy IPs Script
# Retrieves current external IPs of all proxy VMs and updates the registry

set -e

# Configuration
PROXY_REGISTRY_URL="${PROXY_REGISTRY_URL:-http://localhost:8080/register}"
LOG_FILE="${LOG_FILE:-/var/log/proxy-ip-update.log}"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log() {
    echo -e "${GREEN}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} $1" | tee -a "$LOG_FILE"
}

error() {
    echo -e "${RED}[$(date '+%Y-%m-%d %H:%M:%S')] ERROR:${NC} $1" | tee -a "$LOG_FILE"
}

warn() {
    echo -e "${YELLOW}[$(date '+%Y-%m-%d %H:%M:%S')] WARNING:${NC} $1" | tee -a "$LOG_FILE"
}

# Get current external IP
get_external_ip() {
    local ip=""
    ip=$(curl -s https://api.ipify.org) || ip=$(curl -s https://ifconfig.me) || ip=$(curl -s https://icanhazip.com)
    echo "$ip"
}

# Register IP with proxy registry
register_ip() {
    local ip=$1
    local port=$2
    local proxy_type=$3
    
    log "Registering IP: $ip:$port ($proxy_type)"
    
    local response
    response=$(curl -s -X POST \
        -H "Content-Type: application/json" \
        -d "{\"ip\": \"$ip\", \"port\": $port, \"type\": \"$proxy_type\", \"status\": \"active\"}" \
        "$PROXY_REGISTRY_URL")
    
    if [ $? -eq 0 ]; then
        log "Successfully registered: $ip:$port"
        return 0
    else
        error "Failed to register IP: $ip:$port"
        return 1
    fi
}

# Main execution
main() {
    log "=== Proxy IP Update Started ==="
    
    # Get current IP
    CURRENT_IP=$(get_external_ip)
    
    if [ -z "$CURRENT_IP" ]; then
        error "Could not determine external IP"
        exit 1
    fi
    
    log "Current external IP: $CURRENT_IP"
    
    # Check if IP changed
    IP_CACHE_FILE="/tmp/last_proxy_ip.txt"
    LAST_IP=""
    
    if [ -f "$IP_CACHE_FILE" ]; then
        LAST_IP=$(cat "$IP_CACHE_FILE")
    fi
    
    if [ "$CURRENT_IP" = "$LAST_IP" ]; then
        log "IP unchanged, skipping update"
        exit 0
    fi
    
    log "IP changed from $LAST_IP to $CURRENT_IP, updating registry..."
    
    # Register SOCKS5 proxy
    register_ip "$CURRENT_IP" 1080 "socks5"
    
    # Register HTTP proxy
    register_ip "$CURRENT_IP" 3128 "http"
    
    # Save new IP
    echo "$CURRENT_IP" > "$IP_CACHE_FILE"
    
    log "=== Proxy IP Update Completed ==="
}

# Run main function
main "$@"

