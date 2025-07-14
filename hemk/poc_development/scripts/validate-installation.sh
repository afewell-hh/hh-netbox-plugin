#!/bin/bash
# HEMK Installation Validation Script

# Color codes
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Determine Docker command
if docker info &> /dev/null; then
    DOCKER_CMD="docker"
elif sudo docker info &> /dev/null; then
    DOCKER_CMD="sudo docker"
else
    echo -e "${RED}❌ Cannot connect to Docker${NC}"
    exit 1
fi

echo "HEMK Installation Validation"
echo "============================"
echo ""

ERRORS=0
WARNINGS=0

# Function to check component health
check_component() {
    local name=$1
    local namespace=$2
    local check_cmd=$3
    
    echo -n "Checking $name: "
    if $DOCKER_CMD exec hemk-poc-k3s kubectl -n $namespace $check_cmd 2>/dev/null | grep -q "Running"; then
        echo -e "${GREEN}✅ Running${NC}"
        return 0
    else
        echo -e "${RED}❌ Not running${NC}"
        ((ERRORS++))
        return 1
    fi
}

# Function to check service endpoint
check_endpoint() {
    local name=$1
    local url=$2
    local expected_code=${3:-200}
    
    echo -n "Checking $name endpoint: "
    response=$(curl -s -o /dev/null -w "%{http_code}" -k "$url" 2>/dev/null)
    if [ "$response" = "$expected_code" ]; then
        echo -e "${GREEN}✅ Accessible (HTTP $response)${NC}"
        return 0
    else
        echo -e "${RED}❌ Not accessible (HTTP $response)${NC}"
        ((ERRORS++))
        return 1
    fi
}

# Check k3s cluster
echo -n "k3s cluster: "
if $DOCKER_CMD exec hemk-poc-k3s kubectl get nodes 2>/dev/null | grep -q "Ready"; then
    echo -e "${GREEN}✅ Ready${NC}"
else
    echo -e "${RED}❌ Not ready${NC}"
    ((ERRORS++))
fi

# Check core components
check_component "cert-manager" "cert-manager" "get pods"
check_component "NGINX ingress" "ingress-nginx" "get pods"
check_component "ArgoCD" "argocd" "get pods"
check_component "Prometheus" "monitoring" "get pods"

# Check service endpoints
echo ""
echo "Service Endpoints:"
check_endpoint "ArgoCD API" "https://localhost:30443/api/v1/version"
check_endpoint "Prometheus API" "http://localhost:30090/api/v1/status/config"

# Check HNP integration
echo ""
echo -n "HNP integration service account: "
if $DOCKER_CMD exec hemk-poc-k3s kubectl get sa hnp-integration -n hemk-system &> /dev/null; then
    echo -e "${GREEN}✅ Configured${NC}"
else
    echo -e "${RED}❌ Missing${NC}"
    ((ERRORS++))
fi

# Check NetBox connectivity
echo -n "NetBox connectivity: "
NETBOX_IP=$($DOCKER_CMD inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' netbox-docker-netbox-1 | head -n1)
if $DOCKER_CMD exec hemk-poc-k3s curl -s -o /dev/null -w "%{http_code}" "http://$NETBOX_IP:8080" 2>/dev/null | grep -q "200"; then
    echo -e "${GREEN}✅ Connected${NC}"
else
    echo -e "${YELLOW}⚠️  Cannot reach NetBox from k3s container${NC}"
    ((WARNINGS++))
fi

# Check resource usage
echo ""
echo "Resource Usage:"
cpu_usage=$($DOCKER_CMD stats --no-stream --format "{{.CPUPerc}}" hemk-poc-k3s | sed 's/%//')
mem_usage=$($DOCKER_CMD stats --no-stream --format "{{.MemUsage}}" hemk-poc-k3s)
echo "  CPU: $cpu_usage%"
echo "  Memory: $mem_usage"

# Convert CPU percentage to cores (assuming 2 core limit)
cpu_cores=$(echo "scale=2; $cpu_usage * 2 / 100" | bc)
if (( $(echo "$cpu_cores < 1.6" | bc -l) )); then
    echo -e "  ${GREEN}✅ CPU usage within limits${NC}"
else
    echo -e "  ${YELLOW}⚠️  High CPU usage detected${NC}"
    ((WARNINGS++))
fi

# Summary
echo ""
echo "======================================="
if [ $ERRORS -eq 0 ]; then
    if [ $WARNINGS -eq 0 ]; then
        echo -e "${GREEN}✅ All validation checks passed!${NC}"
        exit 0
    else
        echo -e "${YELLOW}⚠️  Validation completed with $WARNINGS warnings${NC}"
        exit 0
    fi
else
    echo -e "${RED}❌ Validation failed with $ERRORS errors and $WARNINGS warnings${NC}"
    exit 1
fi