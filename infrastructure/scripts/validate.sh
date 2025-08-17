#!/bin/bash
# HNP Modernization Infrastructure Validation Script

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
ENVIRONMENT=${1:-dev}
PROJECT_NAME="hnp-modernization"

echo -e "${GREEN}=== HNP Modernization Infrastructure Validation ===${NC}"
echo -e "${YELLOW}Environment: ${ENVIRONMENT}${NC}"

# Validation functions
validate_cluster_connectivity() {
    echo -e "${BLUE}Validating cluster connectivity...${NC}"
    
    if kubectl cluster-info &>/dev/null; then
        echo -e "${GREEN}✓ Cluster connectivity: OK${NC}"
    else
        echo -e "${RED}✗ Cluster connectivity: FAILED${NC}"
        exit 1
    fi
}

validate_nodes() {
    echo -e "${BLUE}Validating cluster nodes...${NC}"
    
    NODE_COUNT=$(kubectl get nodes --no-headers | wc -l)
    READY_NODES=$(kubectl get nodes --no-headers | grep -c " Ready ")
    
    echo -e "${YELLOW}Total nodes: ${NODE_COUNT}${NC}"
    echo -e "${YELLOW}Ready nodes: ${READY_NODES}${NC}"
    
    if [ "$NODE_COUNT" -eq "$READY_NODES" ] && [ "$NODE_COUNT" -gt 0 ]; then
        echo -e "${GREEN}✓ All nodes are ready${NC}"
    else
        echo -e "${RED}✗ Some nodes are not ready${NC}"
        kubectl get nodes
        exit 1
    fi
}

validate_namespaces() {
    echo -e "${BLUE}Validating required namespaces...${NC}"
    
    REQUIRED_NAMESPACES=("hnp-modernization" "observability" "argocd" "monitoring")
    
    for ns in "${REQUIRED_NAMESPACES[@]}"; do
        if kubectl get namespace "$ns" &>/dev/null; then
            echo -e "${GREEN}✓ Namespace ${ns}: EXISTS${NC}"
        else
            echo -e "${RED}✗ Namespace ${ns}: MISSING${NC}"
            exit 1
        fi
    done
}

validate_storage_classes() {
    echo -e "${BLUE}Validating storage classes...${NC}"
    
    REQUIRED_STORAGE_CLASSES=("gp3" "gp3-retain" "efs-sc")
    
    for sc in "${REQUIRED_STORAGE_CLASSES[@]}"; do
        if kubectl get storageclass "$sc" &>/dev/null; then
            echo -e "${GREEN}✓ StorageClass ${sc}: EXISTS${NC}"
        else
            echo -e "${RED}✗ StorageClass ${sc}: MISSING${NC}"
            exit 1
        fi
    done
}

validate_argocd() {
    echo -e "${BLUE}Validating ArgoCD deployment...${NC}"
    
    # Check ArgoCD namespace
    if ! kubectl get namespace argocd &>/dev/null; then
        echo -e "${RED}✗ ArgoCD namespace not found${NC}"
        exit 1
    fi
    
    # Check ArgoCD pods
    ARGOCD_PODS=$(kubectl get pods -n argocd --no-headers | grep -v Completed)
    TOTAL_PODS=$(echo "$ARGOCD_PODS" | wc -l)
    RUNNING_PODS=$(echo "$ARGOCD_PODS" | grep -c "Running")
    
    echo -e "${YELLOW}ArgoCD pods - Total: ${TOTAL_PODS}, Running: ${RUNNING_PODS}${NC}"
    
    if [ "$TOTAL_PODS" -eq "$RUNNING_PODS" ]; then
        echo -e "${GREEN}✓ ArgoCD: All pods running${NC}"
    else
        echo -e "${RED}✗ ArgoCD: Some pods not running${NC}"
        kubectl get pods -n argocd
        exit 1
    fi
    
    # Check ArgoCD server accessibility
    if kubectl get svc argocd-server -n argocd &>/dev/null; then
        echo -e "${GREEN}✓ ArgoCD server service: EXISTS${NC}"
    else
        echo -e "${RED}✗ ArgoCD server service: MISSING${NC}"
        exit 1
    fi
}

validate_observability_stack() {
    echo -e "${BLUE}Validating observability stack...${NC}"
    
    # Check observability namespace
    if ! kubectl get namespace observability &>/dev/null; then
        echo -e "${RED}✗ Observability namespace not found${NC}"
        exit 1
    fi
    
    # Check Prometheus
    if kubectl get deployment prometheus-kube-prometheus-prometheus-operator -n observability &>/dev/null; then
        echo -e "${GREEN}✓ Prometheus operator: DEPLOYED${NC}"
    else
        echo -e "${RED}✗ Prometheus operator: NOT FOUND${NC}"
        exit 1
    fi
    
    # Check Grafana
    if kubectl get deployment prometheus-grafana -n observability &>/dev/null; then
        echo -e "${GREEN}✓ Grafana: DEPLOYED${NC}"
    else
        echo -e "${RED}✗ Grafana: NOT FOUND${NC}"
        exit 1
    fi
    
    # Check Elasticsearch
    if kubectl get statefulset elasticsearch-master -n observability &>/dev/null; then
        echo -e "${GREEN}✓ Elasticsearch: DEPLOYED${NC}"
    else
        echo -e "${YELLOW}! Elasticsearch: NOT FOUND (may not be deployed yet)${NC}"
    fi
    
    # Check Jaeger
    if kubectl get deployment jaeger-query -n observability &>/dev/null; then
        echo -e "${GREEN}✓ Jaeger: DEPLOYED${NC}"
    else
        echo -e "${YELLOW}! Jaeger: NOT FOUND (may not be deployed yet)${NC}"
    fi
}

validate_networking() {
    echo -e "${BLUE}Validating networking configuration...${NC}"
    
    # Check network policies
    NETWORK_POLICIES=$(kubectl get networkpolicy -n hnp-modernization --no-headers | wc -l)
    
    if [ "$NETWORK_POLICIES" -gt 0 ]; then
        echo -e "${GREEN}✓ Network policies: ${NETWORK_POLICIES} configured${NC}"
    else
        echo -e "${YELLOW}! Network policies: None found${NC}"
    fi
    
    # Check ingress controller
    if kubectl get pods -n kube-system | grep -q "aws-load-balancer-controller"; then
        echo -e "${GREEN}✓ AWS Load Balancer Controller: RUNNING${NC}"
    else
        echo -e "${YELLOW}! AWS Load Balancer Controller: NOT FOUND${NC}"
    fi
}

validate_rbac() {
    echo -e "${BLUE}Validating RBAC configuration...${NC}"
    
    # Check cluster roles
    CLUSTER_ROLES=("hnp-admin" "hnp-developer" "hnp-readonly")
    
    for role in "${CLUSTER_ROLES[@]}"; do
        if kubectl get clusterrole "$role" &>/dev/null; then
            echo -e "${GREEN}✓ ClusterRole ${role}: EXISTS${NC}"
        else
            echo -e "${RED}✗ ClusterRole ${role}: MISSING${NC}"
            exit 1
        fi
    done
    
    # Check service accounts
    SERVICE_ACCOUNTS=("hnp-admin:kube-system" "hnp-developer:hnp-modernization" "hnp-readonly:hnp-modernization")
    
    for sa_ns in "${SERVICE_ACCOUNTS[@]}"; do
        sa=$(echo "$sa_ns" | cut -d: -f1)
        ns=$(echo "$sa_ns" | cut -d: -f2)
        
        if kubectl get serviceaccount "$sa" -n "$ns" &>/dev/null; then
            echo -e "${GREEN}✓ ServiceAccount ${sa} in ${ns}: EXISTS${NC}"
        else
            echo -e "${RED}✗ ServiceAccount ${sa} in ${ns}: MISSING${NC}"
            exit 1
        fi
    done
}

validate_persistent_volumes() {
    echo -e "${BLUE}Validating persistent storage...${NC}"
    
    # Check for PVCs
    PVC_COUNT=$(kubectl get pvc --all-namespaces --no-headers | wc -l)
    
    if [ "$PVC_COUNT" -gt 0 ]; then
        echo -e "${GREEN}✓ Persistent Volume Claims: ${PVC_COUNT} found${NC}"
        
        # Check PVC status
        BOUND_PVCS=$(kubectl get pvc --all-namespaces --no-headers | grep -c "Bound")
        echo -e "${YELLOW}Bound PVCs: ${BOUND_PVCS}/${PVC_COUNT}${NC}"
    else
        echo -e "${YELLOW}! No Persistent Volume Claims found${NC}"
    fi
}

generate_summary_report() {
    echo -e "${GREEN}=== Validation Summary Report ===${NC}"
    
    # Get cluster info
    CLUSTER_VERSION=$(kubectl version --short --client=false 2>/dev/null | grep "Server Version" | cut -d: -f2 | tr -d ' ')
    NODE_COUNT=$(kubectl get nodes --no-headers | wc -l)
    
    echo -e "${BLUE}Cluster Information:${NC}"
    echo -e "  Kubernetes Version: ${CLUSTER_VERSION}"
    echo -e "  Node Count: ${NODE_COUNT}"
    echo -e "  Environment: ${ENVIRONMENT}"
    
    echo -e "${BLUE}Service Endpoints:${NC}"
    
    # ArgoCD
    ARGOCD_LB=$(kubectl get svc argocd-server -n argocd -o jsonpath='{.status.loadBalancer.ingress[0].hostname}' 2>/dev/null || echo "Not available")
    echo -e "  ArgoCD: https://${ARGOCD_LB}"
    
    # Grafana
    GRAFANA_LB=$(kubectl get svc prometheus-grafana -n observability -o jsonpath='{.status.loadBalancer.ingress[0].hostname}' 2>/dev/null || echo "Not available")
    echo -e "  Grafana: http://${GRAFANA_LB}"
    
    echo -e "${BLUE}Next Steps:${NC}"
    echo -e "  1. Access ArgoCD UI to manage applications"
    echo -e "  2. Configure application repositories in ArgoCD"
    echo -e "  3. Deploy HNP modernization applications"
    echo -e "  4. Set up monitoring dashboards in Grafana"
    echo -e "  5. Configure alerting rules and notification channels"
}

# Main validation function
main() {
    validate_cluster_connectivity
    validate_nodes
    validate_namespaces
    validate_storage_classes
    validate_argocd
    validate_observability_stack
    validate_networking
    validate_rbac
    validate_persistent_volumes
    generate_summary_report
    
    echo -e "${GREEN}=== Infrastructure Validation Complete ===${NC}"
    echo -e "${GREEN}All critical components validated successfully!${NC}"
}

# Run validation
main "$@"