#!/bin/sh
# IP Monitor Script - Reports external IP to proxy registry

set -e

# Get current external IP
CURRENT_IP=$(wget -qO- https://api.ipify.org)

# Check if IP changed
IP_FILE="/tmp/last_ip.txt"
LAST_IP=""

if [ -f "$IP_FILE" ]; then
    LAST_IP=$(cat "$IP_FILE")
fi

if [ "$CURRENT_IP" != "$LAST_IP" ]; then
    echo "$(date): IP changed from $LAST_IP to $CURRENT_IP"
    
    # Register new IP with proxy registry
    if [ -n "$PROXY_REGISTRY_URL" ]; then
        wget --post-data="{\"ip\": \"$CURRENT_IP\", \"port\": 1080, \"type\": \"socks5\"}" \
             --header="Content-Type: application/json" \
             --quiet \
             -O - \
             "$PROXY_REGISTRY_URL" || echo "Failed to register IP"
    fi
    
    # Save new IP
    echo "$CURRENT_IP" > "$IP_FILE"
else
    echo "$(date): IP unchanged: $CURRENT_IP"
fi

