#!/bin/bash
# Parallel Platform Startup Script
# Starts new platform alongside existing NetBox/HNP

set -euo pipefail

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/../.." && pwd )"

echo "=========================================="
echo "Parallel Platform Deployment"
echo "=========================================="
echo ""

# Color codes
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# Step 1: Check existing NetBox status
echo "Step 1: Verifying existing NetBox/HNP status..."
echo "----------------------------------------------"

if curl -s -o /dev/null -w "%{http_code}" http://localhost:8000 2>/dev/null | grep -q "200\|302"; then
    echo -e "${GREEN}✓${NC} Existing NetBox/HNP is running on port 8000"
else
    echo -e "${YELLOW}⚠${NC}  Warning: NetBox/HNP not responding on port 8000"
    echo "    The existing system may not be running."
    read -p "Continue anyway? (y/n): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Step 2: Check port availability
echo ""
echo "Step 2: Checking port availability..."
echo "-------------------------------------"

if ! "$SCRIPT_DIR/check-ports.sh"; then
    echo -e "${RED}✗${NC} Port conflicts detected. Cannot proceed."
    exit 1
fi

# Step 3: Create necessary directories
echo ""
echo "Step 3: Creating project directories..."
echo "---------------------------------------"

mkdir -p "$PROJECT_ROOT"/{src,deployment,monitoring,agent_coordination}
mkdir -p "$PROJECT_ROOT"/src/{frontend,backend,shared}
mkdir -p "$PROJECT_ROOT"/monitoring/{prometheus,grafana/{dashboards,datasources}}
echo -e "${GREEN}✓${NC} Directories created"

# Step 4: Initialize configuration files if not present
echo ""
echo "Step 4: Initializing configuration..."
echo "-------------------------------------"

# Create basic package.json for frontend if not exists
if [ ! -f "$PROJECT_ROOT/src/frontend/package.json" ]; then
    cat > "$PROJECT_ROOT/src/frontend/package.json" << 'EOF'
{
  "name": "hedgehog-platform-frontend",
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "vite build",
    "preview": "vite preview"
  },
  "dependencies": {
    "react": "^18.2.0",
    "react-dom": "^18.2.0"
  },
  "devDependencies": {
    "vite": "^5.0.0",
    "@vitejs/plugin-react": "^4.2.0"
  }
}
EOF
    echo -e "${GREEN}✓${NC} Frontend package.json created"
fi

# Create basic package.json for backend if not exists
if [ ! -f "$PROJECT_ROOT/src/backend/package.json" ]; then
    cat > "$PROJECT_ROOT/src/backend/package.json" << 'EOF'
{
  "name": "hedgehog-platform-backend",
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "dev": "node index.js",
    "start": "node index.js"
  },
  "dependencies": {
    "express": "^4.18.0",
    "graphql": "^16.8.0",
    "ws": "^8.16.0"
  }
}
EOF
    echo -e "${GREEN}✓${NC} Backend package.json created"
fi

# Create Prometheus configuration
if [ ! -f "$PROJECT_ROOT/monitoring/prometheus.yml" ]; then
    cat > "$PROJECT_ROOT/monitoring/prometheus.yml" << 'EOF'
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'platform-api'
    static_configs:
      - targets: ['platform_api:8101']
  
  - job_name: 'ruv-swarm'
    static_configs:
      - targets: ['ruv_swarm:8200']
  
  - job_name: 'existing-netbox'
    static_configs:
      - targets: ['host.docker.internal:8000']
EOF
    echo -e "${GREEN}✓${NC} Prometheus configuration created"
fi

# Step 5: Start the new platform
echo ""
echo "Step 5: Starting new platform containers..."
echo "------------------------------------------"

cd "$PROJECT_ROOT/phase2a/deployment"

# Use docker-compose or docker compose based on what's available
if command -v docker-compose &> /dev/null; then
    DOCKER_COMPOSE="docker-compose"
else
    DOCKER_COMPOSE="docker compose"
fi

# Start containers
if $DOCKER_COMPOSE -f docker-compose.new-platform.yml up -d; then
    echo -e "${GREEN}✓${NC} Containers starting..."
else
    echo -e "${RED}✗${NC} Failed to start containers"
    exit 1
fi

# Step 6: Wait for services to be healthy
echo ""
echo "Step 6: Waiting for services to be healthy..."
echo "--------------------------------------------"

# Function to check service health
check_service() {
    local service=$1
    local url=$2
    local max_attempts=30
    local attempt=1
    
    while [ $attempt -le $max_attempts ]; do
        if curl -s -o /dev/null -w "%{http_code}" "$url" 2>/dev/null | grep -q "200\|404"; then
            echo -e "${GREEN}✓${NC} $service is ready"
            return 0
        fi
        echo -n "."
        sleep 2
        attempt=$((attempt + 1))
    done
    
    echo -e "${RED}✗${NC} $service failed to start"
    return 1
}

# Check each service
check_service "Platform Web" "http://localhost:8100"
check_service "Platform API" "http://localhost:8101"
check_service "ruv-swarm" "http://localhost:8200"
check_service "Grafana" "http://localhost:3200"

# Step 7: Verify parallel deployment
echo ""
echo "Step 7: Verifying parallel deployment..."
echo "----------------------------------------"

DEPLOYMENT_SUCCESS=true

# Check existing NetBox still works
if curl -s -o /dev/null -w "%{http_code}" http://localhost:8000 2>/dev/null | grep -q "200\|302"; then
    echo -e "${GREEN}✓${NC} Existing NetBox/HNP still running (port 8000)"
else
    echo -e "${RED}✗${NC} Existing NetBox/HNP not responding"
    DEPLOYMENT_SUCCESS=false
fi

# Check new platform is running
if curl -s -o /dev/null -w "%{http_code}" http://localhost:8100 2>/dev/null | grep -q "200\|404"; then
    echo -e "${GREEN}✓${NC} New platform running (port 8100)"
else
    echo -e "${RED}✗${NC} New platform not responding"
    DEPLOYMENT_SUCCESS=false
fi

# Final status
echo ""
echo "=========================================="
if [ "$DEPLOYMENT_SUCCESS" = true ]; then
    echo -e "${GREEN}SUCCESS: Parallel deployment complete!${NC}"
    echo ""
    echo "Access points:"
    echo "  Existing NetBox/HNP: http://localhost:8000"
    echo "  New Platform Web:    http://localhost:8100"
    echo "  New Platform API:    http://localhost:8101"
    echo "  ruv-swarm Console:   http://localhost:8200"
    echo "  Grafana Dashboard:   http://localhost:3200 (admin/admin)"
    echo ""
    echo "To stop the new platform:"
    echo "  $DOCKER_COMPOSE -f docker-compose.new-platform.yml down"
else
    echo -e "${RED}FAILURE: Deployment encountered issues${NC}"
    echo ""
    echo "Check logs with:"
    echo "  $DOCKER_COMPOSE -f docker-compose.new-platform.yml logs"
    exit 1
fi