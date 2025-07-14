#!/bin/bash
# HEMK PoC Installation Script v2.0
# Deploys k3s with ArgoCD, Prometheus, and HNP integration in <30 minutes
# Fixed based on alpha testing feedback

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_FILE="/tmp/hemk-install-$(date +%Y%m%d-%H%M%S).log"
START_TIME=$(date +%s)

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log() {
    echo -e "${GREEN}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} $1" | tee -a "$LOG_FILE"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1" | tee -a "$LOG_FILE" >&2
}

warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1" | tee -a "$LOG_FILE"
}

info() {
    echo -e "${BLUE}[INFO]${NC} $1" | tee -a "$LOG_FILE"
}

# Improved error handling
handle_error() {
    local exit_code=$?
    local line_number=$1
    error "Script failed at line $line_number with exit code $exit_code"
    error "Check log file: $LOG_FILE"
    error "For troubleshooting, see: https://docs.hemk.io/troubleshooting"
    exit $exit_code
}

trap 'handle_error $LINENO' ERR

# Helper function for kubectl commands with proper error handling
k3s_kubectl() {
    local max_retries=3
    local retry=0
    
    while [ $retry -lt $max_retries ]; do
        if $DOCKER_CMD exec hemk-poc-k3s sh -c "KUBECONFIG=/var/lib/rancher/k3s/server/cred/admin.kubeconfig kubectl $*" 2>/dev/null; then
            return 0
        fi
        retry=$((retry + 1))
        if [ $retry -lt $max_retries ]; then
            warning "kubectl command failed, retrying ($retry/$max_retries)..."
            sleep 5
        fi
    done
    
    error "kubectl command failed after $max_retries attempts: kubectl $*"
    return 1
}

# Helper function for kubectl apply with proper YAML handling
k3s_kubectl_apply_yaml() {
    local yaml_content="$1"
    local description="$2"
    
    info "Applying $description..."
    echo "$yaml_content" | $DOCKER_CMD exec -i hemk-poc-k3s sh -c "KUBECONFIG=/var/lib/rancher/k3s/server/cred/admin.kubeconfig kubectl apply -f -"
}

# Helper function for JSON patch operations
k3s_kubectl_patch() {
    local resource="$1"
    local patch="$2"
    local description="$3"
    
    info "Patching $description..."
    $DOCKER_CMD exec hemk-poc-k3s sh -c "KUBECONFIG=/var/lib/rancher/k3s/server/cred/admin.kubeconfig kubectl patch $resource --type='json' -p='$patch'"
}

# Pre-flight checks with better validation
run_preflight_checks() {
    log "Starting HEMK PoC Installation v2.0..."
    log "Log file: $LOG_FILE"
    log "Running comprehensive pre-flight checks..."

    # Check Docker
    if ! command -v docker &> /dev/null; then
        error "Docker is required but not installed. Please install Docker first."
        error "Installation guide: https://docs.docker.com/get-docker/"
        exit 1
    fi

    # Check if we can run Docker commands
    if ! docker info &> /dev/null; then
        if ! sudo docker info &> /dev/null; then
            error "Cannot connect to Docker daemon. Please ensure Docker is running."
            error "Try: sudo systemctl start docker"
            exit 1
        else
            DOCKER_CMD="sudo docker"
        fi
    else
        DOCKER_CMD="docker"
    fi

    log "✅ Docker check passed (using: $DOCKER_CMD)"

    # Check system resources
    local available_memory=$(free -m | awk '/^Mem:/{print $7}')
    if [ "$available_memory" -lt 2048 ]; then
        warning "Available memory is ${available_memory}MB. Recommend at least 2GB for stable operation."
    fi

    local available_disk=$(df "$SCRIPT_DIR" | awk 'NR==2{print int($4/1024)}')
    if [ "$available_disk" -lt 5120 ]; then
        warning "Available disk space is ${available_disk}MB. Recommend at least 5GB for installation."
    fi

    log "✅ System resources check passed"

    # Check for existing HEMK container
    if $DOCKER_CMD ps -a | grep -q hemk-poc-k3s; then
        warning "Existing HEMK container found. Cleaning up..."
        $DOCKER_CMD compose -f docker-compose.hemk-poc.yml down -v || true
        sleep 2
    fi

    log "✅ Pre-flight checks completed successfully"
}

# Start k3s container with better error handling
start_k3s_container() {
    log "Starting k3s container..."
    cd "$SCRIPT_DIR"
    
    if ! $DOCKER_CMD compose -f docker-compose.hemk-poc.yml up -d; then
        error "Failed to start k3s container"
        error "Check Docker logs: $DOCKER_CMD logs hemk-poc-k3s"
        exit 1
    fi

    # Wait for k3s to be ready with better feedback
    log "Waiting for k3s cluster to initialize..."
    local retries=60
    local count=0
    
    while [ $count -lt $retries ]; do
        if $DOCKER_CMD exec hemk-poc-k3s sh -c "KUBECONFIG=/var/lib/rancher/k3s/server/cred/admin.kubeconfig kubectl get nodes" 2>/dev/null | grep -q "Ready"; then
            log "✅ k3s cluster is ready! (${count} seconds)"
            break
        fi
        
        count=$((count + 1))
        if [ $count -eq $retries ]; then
            error "k3s failed to become ready after $retries attempts"
            error "Check container logs: $DOCKER_CMD logs hemk-poc-k3s"
            exit 1
        fi
        
        if [ $((count % 10)) -eq 0 ]; then
            info "Still waiting for k3s... (${count}s elapsed)"
        fi
        
        sleep 1
    done
}

# Extract kubeconfig with validation
setup_kubeconfig() {
    log "Setting up kubeconfig access..."
    mkdir -p "$SCRIPT_DIR/kubeconfig"
    chmod 755 "$SCRIPT_DIR/kubeconfig"
    
    if ! $DOCKER_CMD exec hemk-poc-k3s cat /var/lib/rancher/k3s/server/cred/admin.kubeconfig > "$SCRIPT_DIR/kubeconfig/kubeconfig.yaml.tmp"; then
        error "Failed to extract kubeconfig from container"
        exit 1
    fi
    
    # Modify kubeconfig for external access
    sed 's/127\.0\.0\.1/localhost/g; s/:6443/:16443/g' "$SCRIPT_DIR/kubeconfig/kubeconfig.yaml.tmp" > "$SCRIPT_DIR/kubeconfig/kubeconfig.yaml"
    rm "$SCRIPT_DIR/kubeconfig/kubeconfig.yaml.tmp"
    
    export KUBECONFIG="$SCRIPT_DIR/kubeconfig/kubeconfig.yaml"
    log "✅ Kubeconfig configured for external access"
}

# Connect to NetBox network with error handling
setup_netbox_networking() {
    log "Configuring NetBox network connectivity..."
    
    if ! $DOCKER_CMD network connect netbox-docker_default hemk-poc-k3s 2>/dev/null; then
        warning "Could not connect to NetBox network. HNP integration may not work."
        warning "Ensure NetBox is running: docker compose -f netbox-docker/docker-compose.yml up -d"
        NETBOX_IP="unknown"
    else
        NETBOX_IP=$($DOCKER_CMD inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' netbox-docker-netbox-1 | head -n1)
        if [ -z "$NETBOX_IP" ]; then
            warning "Could not determine NetBox IP address"
            NETBOX_IP="unknown"
        else
            log "✅ Connected to NetBox network (IP: $NETBOX_IP)"
        fi
    fi
}

# Install cert-manager with proper validation
install_cert_manager() {
    log "Installing cert-manager..."
    
    if ! k3s_kubectl apply -f https://github.com/cert-manager/cert-manager/releases/download/v1.13.0/cert-manager.yaml; then
        error "Failed to install cert-manager"
        exit 1
    fi

    log "Waiting for cert-manager to be ready..."
    k3s_kubectl wait --for=condition=Available --timeout=300s deployment/cert-manager -n cert-manager
    k3s_kubectl wait --for=condition=Available --timeout=300s deployment/cert-manager-webhook -n cert-manager
    k3s_kubectl wait --for=condition=Available --timeout=300s deployment/cert-manager-cainjector -n cert-manager

    log "✅ cert-manager installed and ready"

    # Create self-signed issuer with proper YAML formatting
    local cluster_issuer_yaml="apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: selfsigned-cluster-issuer
spec:
  selfSigned: {}"

    k3s_kubectl_apply_yaml "$cluster_issuer_yaml" "self-signed ClusterIssuer"
    log "✅ Self-signed certificate issuer created"
}

# Install NGINX ingress with proper JSON patch handling
install_nginx_ingress() {
    log "Installing NGINX ingress controller..."
    
    if ! k3s_kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/controller-v1.8.1/deploy/static/provider/baremetal/deploy.yaml; then
        error "Failed to install NGINX ingress controller"
        exit 1
    fi

    log "Waiting for NGINX ingress to be ready..."
    k3s_kubectl wait --for=condition=Available --timeout=300s deployment/ingress-nginx-controller -n ingress-nginx

    log "✅ NGINX ingress controller installed and ready"

    # Configure NodePort services with proper JSON escaping
    local patch='[
        {"op": "replace", "path": "/spec/type", "value": "NodePort"},
        {"op": "add", "path": "/spec/ports/0/nodePort", "value": 30080},
        {"op": "add", "path": "/spec/ports/1/nodePort", "value": 30443}
    ]'
    
    k3s_kubectl_patch "svc ingress-nginx-controller -n ingress-nginx" "$patch" "ingress controller for NodePort access"
    log "✅ NGINX ingress configured for external access"
}

# Install ArgoCD with validation
install_argocd() {
    log "Installing ArgoCD..."
    
    k3s_kubectl create namespace argocd || true
    
    if ! k3s_kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/v2.8.4/manifests/install.yaml; then
        error "Failed to install ArgoCD"
        exit 1
    fi

    log "Waiting for ArgoCD to be ready..."
    k3s_kubectl wait --for=condition=Available --timeout=300s deployment/argocd-server -n argocd

    log "✅ ArgoCD installed and ready"

    # Configure ArgoCD for external access
    local patch='[
        {"op": "add", "path": "/spec/type", "value": "NodePort"},
        {"op": "add", "path": "/spec/ports/0/nodePort", "value": 30443}
    ]'
    
    k3s_kubectl_patch "svc argocd-server -n argocd" "$patch" "ArgoCD server for external access"
    log "✅ ArgoCD configured for external access"
}

# Install basic Prometheus monitoring
install_monitoring() {
    log "Installing basic monitoring stack..."
    
    k3s_kubectl create namespace monitoring || true

    # Create Prometheus configuration
    local prometheus_yaml="apiVersion: v1
kind: ConfigMap
metadata:
  name: prometheus-config
  namespace: monitoring
data:
  prometheus.yml: |
    global:
      scrape_interval: 30s
    scrape_configs:
    - job_name: 'kubernetes-apiservers'
      kubernetes_sd_configs:
      - role: endpoints
      scheme: https
      tls_config:
        ca_file: /var/run/secrets/kubernetes.io/serviceaccount/ca.crt
      bearer_token_file: /var/run/secrets/kubernetes.io/serviceaccount/token
      relabel_configs:
      - source_labels: [__meta_kubernetes_namespace, __meta_kubernetes_service_name, __meta_kubernetes_endpoint_port_name]
        action: keep
        regex: default;kubernetes;https
---
apiVersion: v1
kind: ServiceAccount
metadata:
  name: prometheus
  namespace: monitoring
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: prometheus
rules:
- apiGroups: [\"\"]
  resources: [\"nodes\", \"services\", \"endpoints\", \"pods\"]
  verbs: [\"get\", \"list\", \"watch\"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata:
  name: prometheus
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: ClusterRole
  name: prometheus
subjects:
- kind: ServiceAccount
  name: prometheus
  namespace: monitoring
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: prometheus
  namespace: monitoring
spec:
  replicas: 1
  selector:
    matchLabels:
      app: prometheus
  template:
    metadata:
      labels:
        app: prometheus
    spec:
      serviceAccountName: prometheus
      containers:
      - name: prometheus
        image: prom/prometheus:v2.45.0
        args:
          - '--config.file=/etc/prometheus/prometheus.yml'
          - '--storage.tsdb.path=/prometheus/'
          - '--web.console.libraries=/etc/prometheus/console_libraries'
          - '--web.console.templates=/etc/prometheus/consoles'
          - '--web.enable-lifecycle'
        ports:
        - containerPort: 9090
        resources:
          requests:
            cpu: 100m
            memory: 512Mi
          limits:
            cpu: 200m
            memory: 1Gi
        volumeMounts:
        - name: prometheus-config
          mountPath: /etc/prometheus
        - name: prometheus-storage
          mountPath: /prometheus
      volumes:
      - name: prometheus-config
        configMap:
          name: prometheus-config
      - name: prometheus-storage
        emptyDir: {}
---
apiVersion: v1
kind: Service
metadata:
  name: prometheus
  namespace: monitoring
spec:
  type: NodePort
  ports:
  - port: 9090
    targetPort: 9090
    nodePort: 30090
  selector:
    app: prometheus"

    k3s_kubectl_apply_yaml "$prometheus_yaml" "Prometheus monitoring stack"
    log "✅ Basic monitoring stack installed"
}

# Create HNP integration resources
setup_hnp_integration() {
    log "Setting up HNP integration..."
    
    local hnp_integration_yaml="apiVersion: v1
kind: Namespace
metadata:
  name: hemk-system
---
apiVersion: v1
kind: ServiceAccount
metadata:
  name: hnp-integration
  namespace: hemk-system
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: hnp-integration
rules:
- apiGroups: [\"\"]
  resources: [\"services\", \"endpoints\", \"pods\"]
  verbs: [\"get\", \"list\", \"watch\"]
- apiGroups: [\"apps\"]
  resources: [\"deployments\", \"replicasets\"]
  verbs: [\"get\", \"list\", \"watch\"]
- apiGroups: [\"argoproj.io\"]
  resources: [\"applications\", \"appprojects\"]
  verbs: [\"get\", \"list\", \"watch\", \"create\", \"update\", \"patch\", \"delete\"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata:
  name: hnp-integration
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: ClusterRole
  name: hnp-integration
subjects:
- kind: ServiceAccount
  name: hnp-integration
  namespace: hemk-system"

    k3s_kubectl_apply_yaml "$hnp_integration_yaml" "HNP integration resources"
    log "✅ HNP integration service account created"
}

# Generate configuration and validate installation
finalize_installation() {
    log "Finalizing installation and generating configuration..."

    # Get ArgoCD admin password
    local argocd_password
    if ! argocd_password=$(k3s_kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath="{.data.password}" | base64 -d 2>/dev/null); then
        warning "Could not retrieve ArgoCD admin password"
        argocd_password="unknown"
    fi

    # Calculate installation time
    local end_time=$(date +%s)
    local duration=$((end_time - START_TIME))
    local minutes=$((duration / 60))
    local seconds=$((duration % 60))

    # Generate HNP integration configuration
    local k3s_ip
    k3s_ip=$($DOCKER_CMD inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' hemk-poc-k3s | head -n1)

    cat > "$SCRIPT_DIR/hnp-integration.yaml" <<EOF
# HNP Integration Configuration
# Generated: $(date)
# Installation time: ${minutes}m ${seconds}s

hemk:
  cluster:
    endpoint: "https://localhost:16443"
    container_ip: "${k3s_ip}"
    
  services:
    argocd:
      endpoint: "https://localhost:30443"
      admin_username: "admin"
      admin_password: "${argocd_password}"
      health_check: "/api/v1/version"
      
    prometheus:
      endpoint: "http://localhost:30090"
      api_path: "/api/v1"
      health_check: "/api/v1/status/config"
      
  netbox:
    url: "http://${NETBOX_IP}:8080"
    api_url: "http://${NETBOX_IP}:8080/api"
    
  kubeconfig: "${SCRIPT_DIR}/kubeconfig/kubeconfig.yaml"
EOF

    # Run validation if script exists
    if [ -f "$SCRIPT_DIR/scripts/validate-installation.sh" ]; then
        log "Running installation validation..."
        if ! "$SCRIPT_DIR/scripts/validate-installation.sh"; then
            warning "Some validation checks failed - see logs for details"
        fi
    fi

    # Success message
    echo ""
    log "==============================================="
    log "🎉 HEMK PoC Installation Complete!"
    log "Installation time: ${minutes} minutes ${seconds} seconds"
    log "==============================================="
    echo ""
    log "Access points:"
    log "  📊 ArgoCD UI: https://localhost:30443"
    log "  🔑 ArgoCD Admin Password: ${argocd_password}"
    log "  📈 Prometheus: http://localhost:30090"
    log "  ⚙️  Kubeconfig: ${SCRIPT_DIR}/kubeconfig/kubeconfig.yaml"
    echo ""
    log "Next steps:"
    log "  1. 📋 Review HNP integration config: ${SCRIPT_DIR}/hnp-integration.yaml"
    log "  2. 🧪 Test HNP connectivity: ./scripts/test-hnp-integration.sh"
    log "  3. 🚀 Access ArgoCD UI to deploy your first application"
    echo ""

    if [ $minutes -lt 30 ]; then
        log "✅ SUCCESS: Installation completed in under 30 minutes!"
    else
        warning "⚠️  Installation took longer than 30 minutes. Check system resources."
    fi

    log "📝 Installation log saved to: $LOG_FILE"
}

# Main execution flow
main() {
    run_preflight_checks
    start_k3s_container
    setup_kubeconfig
    setup_netbox_networking
    install_cert_manager
    install_nginx_ingress
    install_argocd
    install_monitoring
    setup_hnp_integration
    finalize_installation
}

# Execute main function
main "$@"