#!/bin/bash
# HNP Modernization Infrastructure Deployment Script

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
ENVIRONMENT=${1:-dev}
AWS_REGION=${AWS_REGION:-us-west-2}
PROJECT_NAME="hnp-modernization"

echo -e "${GREEN}=== HNP Modernization Infrastructure Deployment ===${NC}"
echo -e "${YELLOW}Environment: ${ENVIRONMENT}${NC}"
echo -e "${YELLOW}Region: ${AWS_REGION}${NC}"

# Check prerequisites
check_prerequisites() {
    echo -e "${GREEN}Checking prerequisites...${NC}"
    
    # Check if required tools are installed
    for tool in terraform kubectl helm aws; do
        if ! command -v $tool &> /dev/null; then
            echo -e "${RED}Error: $tool is not installed${NC}"
            exit 1
        fi
    done
    
    # Check AWS credentials
    if ! aws sts get-caller-identity &> /dev/null; then
        echo -e "${RED}Error: AWS credentials not configured${NC}"
        exit 1
    fi
    
    echo -e "${GREEN}Prerequisites check passed${NC}"
}

# Deploy Terraform infrastructure
deploy_terraform() {
    echo -e "${GREEN}Deploying Terraform infrastructure...${NC}"
    
    cd terraform
    
    # Initialize Terraform
    terraform init -backend-config="environments/${ENVIRONMENT}/backend.hcl"
    
    # Plan and apply
    terraform plan -var-file="environments/${ENVIRONMENT}/terraform.tfvars" -out=tfplan
    terraform apply tfplan
    
    # Get cluster name
    CLUSTER_NAME=$(terraform output -raw cluster_name)
    echo -e "${GREEN}Cluster created: ${CLUSTER_NAME}${NC}"
    
    # Update kubeconfig
    aws eks update-kubeconfig --region ${AWS_REGION} --name ${CLUSTER_NAME}
    
    cd ..
}

# Deploy Kubernetes base configuration
deploy_kubernetes_base() {
    echo -e "${GREEN}Deploying Kubernetes base configuration...${NC}"
    
    # Apply namespaces
    kubectl apply -f kubernetes/base/namespace.yaml
    
    # Apply RBAC
    kubectl apply -f kubernetes/rbac/
    
    # Apply network policies
    kubectl apply -f kubernetes/network-policies/
    
    # Apply storage classes (substitute EFS ID)
    EFS_ID=$(cd terraform && terraform output -raw efs_file_system_id)
    sed "s/\${EFS_FILE_SYSTEM_ID}/${EFS_ID}/g" kubernetes/storage/storage-classes.yaml | kubectl apply -f -
    
    echo -e "${GREEN}Kubernetes base configuration deployed${NC}"
}

# Install ArgoCD
install_argocd() {
    echo -e "${GREEN}Installing ArgoCD...${NC}"
    
    # Install ArgoCD operator
    kubectl create namespace argocd --dry-run=client -o yaml | kubectl apply -f -
    kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml
    
    # Wait for ArgoCD to be ready
    kubectl wait --for=condition=available --timeout=300s deployment/argocd-server -n argocd
    
    # Apply ArgoCD configuration
    kubectl apply -f gitops/argocd/
    kubectl apply -f gitops/repositories/
    
    echo -e "${GREEN}ArgoCD installed and configured${NC}"
}

# Deploy observability stack
deploy_observability() {
    echo -e "${GREEN}Deploying observability stack...${NC}"
    
    # Add Helm repositories
    helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
    helm repo add grafana https://grafana.github.io/helm-charts
    helm repo add jaegertracing https://jaegertracing.github.io/helm-charts
    helm repo add elastic https://helm.elastic.co
    helm repo update
    
    # Install Prometheus stack
    helm upgrade --install prometheus prometheus-community/kube-prometheus-stack \
        --namespace observability \
        --create-namespace \
        --values observability/prometheus/values.yaml \
        --wait --timeout=10m
    
    # Install Elasticsearch
    helm upgrade --install elasticsearch elastic/elasticsearch \
        --namespace observability \
        --values observability/logging/elasticsearch-values.yaml \
        --wait --timeout=10m
    
    # Install Jaeger
    helm upgrade --install jaeger jaegertracing/jaeger \
        --namespace observability \
        --values observability/jaeger/values.yaml \
        --wait --timeout=10m
    
    echo -e "${GREEN}Observability stack deployed${NC}"
}

# Validate deployment
validate_deployment() {
    echo -e "${GREEN}Validating deployment...${NC}"
    
    # Check cluster status
    kubectl cluster-info
    
    # Check nodes
    kubectl get nodes
    
    # Check ArgoCD
    kubectl get pods -n argocd
    
    # Check observability stack
    kubectl get pods -n observability
    
    # Get service URLs
    echo -e "${GREEN}Service URLs:${NC}"
    
    # ArgoCD URL
    ARGOCD_LB=$(kubectl get svc argocd-server -n argocd -o jsonpath='{.status.loadBalancer.ingress[0].hostname}')
    if [ -n "$ARGOCD_LB" ]; then
        echo -e "${YELLOW}ArgoCD: https://${ARGOCD_LB}${NC}"
    fi
    
    # Grafana URL
    GRAFANA_LB=$(kubectl get svc prometheus-grafana -n observability -o jsonpath='{.status.loadBalancer.ingress[0].hostname}')
    if [ -n "$GRAFANA_LB" ]; then
        echo -e "${YELLOW}Grafana: http://${GRAFANA_LB}${NC}"
    fi
    
    # Get admin passwords
    echo -e "${GREEN}Admin credentials:${NC}"
    echo -e "${YELLOW}ArgoCD admin password:${NC}"
    kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath="{.data.password}" | base64 -d
    echo
    
    echo -e "${YELLOW}Grafana admin password: admin123${NC}"
    
    echo -e "${GREEN}Deployment validation completed${NC}"
}

# Main execution
main() {
    check_prerequisites
    deploy_terraform
    deploy_kubernetes_base
    install_argocd
    deploy_observability
    validate_deployment
    
    echo -e "${GREEN}=== HNP Modernization Infrastructure Deployment Complete ===${NC}"
}

# Run main function
main "$@"