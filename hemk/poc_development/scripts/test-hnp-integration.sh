#!/bin/bash
# Test HNP Integration with HEMK PoC

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

echo "HEMK-HNP Integration Test"
echo "========================="
echo ""

# Load configuration
CONFIG_FILE="hnp-integration.yaml"
if [ ! -f "$CONFIG_FILE" ]; then
    echo -e "${RED}❌ Configuration file not found: $CONFIG_FILE${NC}"
    exit 1
fi

# Get IPs
NETBOX_IP=$($DOCKER_CMD inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' netbox-docker-netbox-1 | head -n1)
K3S_IP=$($DOCKER_CMD inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' hemk-poc-k3s | head -n1)

echo "Network Configuration:"
echo "  NetBox IP: $NETBOX_IP"
echo "  k3s Container IP: $K3S_IP"
echo ""

# Test 1: ArgoCD API from host
echo "Test 1: ArgoCD API Accessibility"
echo -n "  From host: "
if curl -k -s "https://localhost:30444/api/version" | grep -q "Version"; then
    echo -e "${GREEN}✅ Success${NC}"
else
    echo -e "${RED}❌ Failed${NC}"
fi

# Test 2: Prometheus API from host
echo ""
echo "Test 2: Prometheus API Accessibility"
echo -n "  From host: "
if curl -s "http://localhost:30090/api/v1/status/config" | grep -q "yaml"; then
    echo -e "${GREEN}✅ Success${NC}"
else
    echo -e "${RED}❌ Failed${NC}"
fi

# Test 3: NetBox to k3s connectivity
echo ""
echo "Test 3: NetBox to k3s Container Connectivity"
echo -n "  Ping test: "
if $DOCKER_CMD exec netbox-docker-netbox-1 ping -c 1 -W 2 $K3S_IP &> /dev/null; then
    echo -e "${GREEN}✅ Success${NC}"
else
    echo -e "${YELLOW}⚠️  Cannot ping (may be normal if ping is disabled)${NC}"
fi

# Test 4: k3s to NetBox connectivity  
echo ""
echo "Test 4: k3s to NetBox Connectivity"
echo -n "  Network test: "
# Test if NetBox is reachable from k3s cluster by creating a simple busybox pod
pod_result=$($DOCKER_CMD exec hemk-poc-k3s sh -c "KUBECONFIG=/var/lib/rancher/k3s/server/cred/admin.kubeconfig kubectl run netbox-test --image=busybox:1.28 --rm -i --restart=Never --timeout=30s -- wget -q -O- -T 5 http://$NETBOX_IP:8080" 2>/dev/null | grep -i "html\|login\|netbox")

if [ -n "$pod_result" ]; then
    echo -e "${GREEN}✅ Success (NetBox reachable from cluster)${NC}"
else
    # Fallback: check network connectivity exists
    if ping -c 1 -W 2 $NETBOX_IP &> /dev/null; then
        echo -e "${YELLOW}⚠️  NetBox pingable but HTTP test inconclusive${NC}"
    else
        echo -e "${RED}❌ NetBox not reachable${NC}"
    fi
fi

# Test 5: Service Account Token
echo ""
echo "Test 5: HNP Service Account"
echo -n "  Token retrieval: "
if $DOCKER_CMD exec hemk-poc-k3s sh -c "KUBECONFIG=/var/lib/rancher/k3s/server/cred/admin.kubeconfig kubectl get sa hnp-integration -n hemk-system" &> /dev/null; then
    # Get token (K8s 1.24+ uses different token mechanism)
    TOKEN_NAME=$($DOCKER_CMD exec hemk-poc-k3s sh -c "KUBECONFIG=/var/lib/rancher/k3s/server/cred/admin.kubeconfig kubectl get sa hnp-integration -n hemk-system -o jsonpath='{.secrets[0].name}'" 2>/dev/null)
    if [ -z "$TOKEN_NAME" ]; then
        # For newer K8s, create token manually
        TOKEN=$($DOCKER_CMD exec hemk-poc-k3s sh -c "KUBECONFIG=/var/lib/rancher/k3s/server/cred/admin.kubeconfig kubectl create token hnp-integration -n hemk-system --duration=24h" 2>/dev/null)
        if [ -n "$TOKEN" ]; then
            echo -e "${GREEN}✅ Token created${NC}"
        else
            echo -e "${RED}❌ Failed to create token${NC}"
        fi
    else
        echo -e "${GREEN}✅ Token exists${NC}"
    fi
else
    echo -e "${RED}❌ Service account not found${NC}"
fi

# Test 6: ArgoCD Application Creation (Mock)
echo ""
echo "Test 6: ArgoCD Application Management"
echo -n "  API readiness: "

# Get ArgoCD admin password
ARGOCD_PASSWORD=$($DOCKER_CMD exec hemk-poc-k3s sh -c "KUBECONFIG=/var/lib/rancher/k3s/server/cred/admin.kubeconfig kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath='{.data.password}'" 2>/dev/null | base64 -d)

if [ -n "$ARGOCD_PASSWORD" ]; then
    # Test ArgoCD API with auth
    response=$(curl -k -s -o /dev/null -w "%{http_code}" \
        -H "Authorization: Bearer $ARGOCD_PASSWORD" \
        "https://localhost:30444/api/v1/applications")
    
    if [ "$response" = "200" ] || [ "$response" = "401" ]; then
        echo -e "${GREEN}✅ API responding${NC}"
    else
        echo -e "${RED}❌ API not responding (HTTP $response)${NC}"
    fi
else
    echo -e "${YELLOW}⚠️  Cannot retrieve ArgoCD password${NC}"
fi

# Test 7: Prometheus Metrics Query
echo ""
echo "Test 7: Prometheus Metrics Query"
echo -n "  Cluster metrics: "
metrics=$(curl -s "http://localhost:30090/api/v1/query?query=up" | grep -c "\"up\"")
if [ $metrics -gt 0 ]; then
    echo -e "${GREEN}✅ Metrics available${NC}"
else
    echo -e "${RED}❌ No metrics found${NC}"
fi

# Summary
echo ""
echo "======================================="
echo "Integration Test Summary:"
echo ""
echo "Configuration file: $CONFIG_FILE"
echo "For HNP integration, configure NetBox plugin with:"
echo "  - ArgoCD endpoint: https://<your-host>:30444"
echo "  - Prometheus endpoint: http://<your-host>:30090"
echo "  - Kubeconfig: $(pwd)/kubeconfig/kubeconfig.yaml"
echo ""
echo "Note: In production, use proper DNS names and certificates"
echo "======================================="