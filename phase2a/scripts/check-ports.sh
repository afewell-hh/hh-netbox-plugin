#!/bin/bash
# Port Conflict Detection Script for Parallel Deployment
# Ensures new platform ports don't conflict with existing NetBox/HNP

set -euo pipefail

echo "=================================================="
echo "Port Availability Check for Platform Modernization"
echo "=================================================="
echo ""

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Existing NetBox ports (DO NOT USE)
RESERVED_PORTS=(8000 5432 6379)

# New platform ports (MUST BE AVAILABLE)
NEW_PLATFORM_PORTS=(
    8100  # New web interface
    8101  # API gateway
    8102  # GraphQL endpoint
    8103  # WebSocket server
    8200  # ruv-swarm coordinator
    8201  # Agent memory store
    8202  # Quality gate validator
    8300  # WasmCloud control
    8301  # WASM actors
    8302  # Capability providers
    8400  # K8s API proxy
    8401  # GitOps webhook
    8402  # Fabric sync service
    3100  # Dev server
    6100  # Storybook
    9191  # Prometheus metrics
    3200  # Grafana dashboard
    5433  # New PostgreSQL
    6380  # New Redis
    27017 # MongoDB for agents
)

echo "Checking reserved NetBox/HNP ports (must remain in use)..."
echo "--------------------------------------------------------"

NETBOX_HEALTHY=true
for PORT in "${RESERVED_PORTS[@]}"; do
    if lsof -Pi :$PORT -sTCP:LISTEN -t >/dev/null 2>&1 || netstat -tuln 2>/dev/null | grep -q ":$PORT "; then
        echo -e "${GREEN}✓${NC} Port $PORT: NetBox/HNP service active (expected)"
    else
        echo -e "${YELLOW}⚠${NC}  Port $PORT: NetBox/HNP service not detected (may not be running)"
        NETBOX_HEALTHY=false
    fi
done

echo ""
echo "Checking new platform ports (must be available)..."
echo "------------------------------------------------"

CONFLICTS_FOUND=false
AVAILABLE_PORTS=()
CONFLICTED_PORTS=()

for PORT in "${NEW_PLATFORM_PORTS[@]}"; do
    if lsof -Pi :$PORT -sTCP:LISTEN -t >/dev/null 2>&1 || netstat -tuln 2>/dev/null | grep -q ":$PORT "; then
        echo -e "${RED}✗${NC} Port $PORT: CONFLICT DETECTED - Already in use!"
        CONFLICTED_PORTS+=($PORT)
        CONFLICTS_FOUND=true
        
        # Try to identify what's using the port
        if command -v lsof >/dev/null 2>&1; then
            PROCESS=$(lsof -i :$PORT 2>/dev/null | grep LISTEN | awk '{print $1}' | head -1)
            if [ ! -z "$PROCESS" ]; then
                echo "    └─ Used by: $PROCESS"
            fi
        fi
    else
        echo -e "${GREEN}✓${NC} Port $PORT: Available"
        AVAILABLE_PORTS+=($PORT)
    fi
done

echo ""
echo "=================================================="
echo "Summary Report"
echo "=================================================="

# NetBox status
if [ "$NETBOX_HEALTHY" = true ]; then
    echo -e "${GREEN}✓${NC} Existing NetBox/HNP: Detected and running"
else
    echo -e "${YELLOW}⚠${NC}  Existing NetBox/HNP: May not be running (verify if needed)"
fi

# New platform port status
echo -e "\nNew Platform Ports:"
echo "  Available: ${#AVAILABLE_PORTS[@]}/${#NEW_PLATFORM_PORTS[@]}"
echo "  Conflicts: ${#CONFLICTED_PORTS[@]}"

if [ "$CONFLICTS_FOUND" = false ]; then
    echo -e "\n${GREEN}✓ SUCCESS:${NC} All new platform ports are available!"
    echo "  You can proceed with parallel deployment."
    
    # Create port mapping file for docker-compose
    cat > /tmp/platform_ports.env << EOF
# Auto-generated port configuration
# Created: $(date)
PLATFORM_WEB_PORT=8100
PLATFORM_API_PORT=8101
PLATFORM_GRAPHQL_PORT=8102
PLATFORM_WEBSOCKET_PORT=8103
RUV_SWARM_PORT=8200
AGENT_MEMORY_PORT=8201
QUALITY_GATE_PORT=8202
WASMCLOUD_CONTROL_PORT=8300
WASMCLOUD_ACTORS_PORT=8301
WASMCLOUD_CAPABILITY_PORT=8302
K8S_API_PROXY_PORT=8400
GITOPS_WEBHOOK_PORT=8401
FABRIC_SYNC_PORT=8402
DEV_SERVER_PORT=3100
STORYBOOK_PORT=6100
PROMETHEUS_PORT=9191
GRAFANA_PORT=3200
POSTGRES_NEW_PORT=5433
REDIS_NEW_PORT=6380
MONGODB_PORT=27017
EOF
    echo -e "\n${GREEN}ℹ${NC}  Port configuration saved to: /tmp/platform_ports.env"
    exit 0
else
    echo -e "\n${RED}✗ FAILURE:${NC} Port conflicts detected!"
    echo "  Conflicted ports: ${CONFLICTED_PORTS[@]}"
    echo ""
    echo "Resolution options:"
    echo "  1. Stop the conflicting services"
    echo "  2. Modify the platform port configuration"
    echo "  3. Use the port reassignment script (./reassign-ports.sh)"
    exit 1
fi