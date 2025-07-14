#!/bin/bash
# HEMK PoC Installation Script
# Deploys k3s with ArgoCD, Prometheus, and HNP integration in <30 minutes

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_FILE="/tmp/hemk-install-$(date +%Y%m%d-%H%M%S).log"
START_TIME=$(date +%s)

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log() {
    echo -e "${GREEN}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} $1" | tee -a "$LOG_FILE"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1" | tee -a "$LOG_FILE" >&2
    exit 1
}

warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1" | tee -a "$LOG_FILE"
}

# Pre-flight checks
log "Starting HEMK PoC Installation..."
log "Log file: $LOG_FILE"
log "Running pre-flight checks..."

# Check Docker
if ! command -v docker &> /dev/null; then
    error "Docker is required but not installed"
fi

# Check if we can run Docker commands
if ! docker info &> /dev/null; then
    if ! sudo docker info &> /dev/null; then
        error "Cannot connect to Docker daemon"
    else
        DOCKER_CMD="sudo docker"
    fi
else
    DOCKER_CMD="docker"
fi

log "Docker command: $DOCKER_CMD"

# Check for existing HEMK container
if $DOCKER_CMD ps -a | grep -q hemk-poc-k3s; then
    warning "Existing HEMK container found. Removing..."
    $DOCKER_CMD compose -f docker-compose.hemk-poc.yml down -v
fi

# Start k3s container
log "Starting k3s container..."
cd "$SCRIPT_DIR"
$DOCKER_CMD compose -f docker-compose.hemk-poc.yml up -d

# Wait for k3s to be ready
log "Waiting for k3s to be ready..."
RETRIES=30
for i in $(seq 1 $RETRIES); do
    if $DOCKER_CMD exec hemk-poc-k3s kubectl get nodes 2>/dev/null | grep -q "Ready"; then
        log "k3s is ready!"
        break
    fi
    if [ $i -eq $RETRIES ]; then
        error "k3s failed to become ready after $RETRIES attempts"
    fi
    echo -n "."
    sleep 10
done

# Get kubeconfig
log "Extracting kubeconfig..."
mkdir -p "$SCRIPT_DIR/kubeconfig"
$DOCKER_CMD exec hemk-poc-k3s cat /etc/rancher/k3s/k3s.yaml | sed "s/127.0.0.1/localhost/g" | sed "s/6443/16443/g" > "$SCRIPT_DIR/kubeconfig/kubeconfig.yaml"
export KUBECONFIG="$SCRIPT_DIR/kubeconfig/kubeconfig.yaml"

# Connect to NetBox network
log "Connecting to NetBox network..."
$DOCKER_CMD network connect netbox-docker_default hemk-poc-k3s 2>/dev/null || true

# Get NetBox IP
NETBOX_IP=$($DOCKER_CMD inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' netbox-docker-netbox-1 | head -n1)
log "NetBox IP: $NETBOX_IP"

# Install cert-manager
log "Installing cert-manager..."
$DOCKER_CMD exec hemk-poc-k3s kubectl apply -f https://github.com/cert-manager/cert-manager/releases/download/v1.13.0/cert-manager.yaml

# Wait for cert-manager
log "Waiting for cert-manager to be ready..."
$DOCKER_CMD exec hemk-poc-k3s kubectl wait --for=condition=Available --timeout=300s deployment/cert-manager -n cert-manager
$DOCKER_CMD exec hemk-poc-k3s kubectl wait --for=condition=Available --timeout=300s deployment/cert-manager-webhook -n cert-manager
$DOCKER_CMD exec hemk-poc-k3s kubectl wait --for=condition=Available --timeout=300s deployment/cert-manager-cainjector -n cert-manager

# Create self-signed issuer
log "Creating self-signed certificate issuer..."
$DOCKER_CMD exec hemk-poc-k3s kubectl apply -f - <<EOF
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: selfsigned-cluster-issuer
spec:
  selfSigned: {}
EOF

# Install NGINX ingress
log "Installing NGINX ingress controller..."
$DOCKER_CMD exec hemk-poc-k3s kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/controller-v1.8.1/deploy/static/provider/baremetal/deploy.yaml

# Wait for ingress
log "Waiting for NGINX ingress to be ready..."
$DOCKER_CMD exec hemk-poc-k3s kubectl wait --for=condition=Available --timeout=300s deployment/ingress-nginx-controller -n ingress-nginx

# Patch ingress service to use NodePort on specific ports
log "Configuring ingress NodePort services..."
$DOCKER_CMD exec hemk-poc-k3s kubectl patch svc ingress-nginx-controller -n ingress-nginx --type='json' -p='[
  {"op": "replace", "path": "/spec/type", "value": "NodePort"},
  {"op": "add", "path": "/spec/ports/0/nodePort", "value": 30080},
  {"op": "add", "path": "/spec/ports/1/nodePort", "value": 30443}
]'

# Install ArgoCD
log "Installing ArgoCD..."
$DOCKER_CMD exec hemk-poc-k3s kubectl create namespace argocd || true
$DOCKER_CMD exec hemk-poc-k3s kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/v2.8.4/manifests/install.yaml

# Wait for ArgoCD
log "Waiting for ArgoCD to be ready..."
$DOCKER_CMD exec hemk-poc-k3s kubectl wait --for=condition=Available --timeout=300s deployment/argocd-server -n argocd

# Patch ArgoCD service to NodePort
log "Configuring ArgoCD NodePort service..."
$DOCKER_CMD exec hemk-poc-k3s kubectl patch svc argocd-server -n argocd --type='json' -p='[
  {"op": "add", "path": "/spec/type", "value": "NodePort"},
  {"op": "add", "path": "/spec/ports/0/nodePort", "value": 30443}
]'

# Install Prometheus (minimal configuration)
log "Installing Prometheus..."
$DOCKER_CMD exec hemk-poc-k3s kubectl create namespace monitoring || true

# Create minimal Prometheus deployment
$DOCKER_CMD exec hemk-poc-k3s kubectl apply -f - <<'EOF'
apiVersion: v1
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
    - job_name: 'kubernetes-nodes'
      kubernetes_sd_configs:
      - role: node
      scheme: https
      tls_config:
        ca_file: /var/run/secrets/kubernetes.io/serviceaccount/ca.crt
      bearer_token_file: /var/run/secrets/kubernetes.io/serviceaccount/token
      relabel_configs:
      - action: labelmap
        regex: __meta_kubernetes_node_label_(.+)
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
    app: prometheus
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
- apiGroups: [""]
  resources:
  - nodes
  - nodes/proxy
  - services
  - endpoints
  - pods
  verbs: ["get", "list", "watch"]
- apiGroups:
  - extensions
  resources:
  - ingresses
  verbs: ["get", "list", "watch"]
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
EOF

# Create HNP integration namespace and service account
log "Creating HNP integration service account..."
$DOCKER_CMD exec hemk-poc-k3s kubectl apply -f - <<'EOF'
apiVersion: v1
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
- apiGroups: [""]
  resources: ["services", "endpoints", "pods"]
  verbs: ["get", "list", "watch"]
- apiGroups: ["apps"]
  resources: ["deployments", "replicasets"]
  verbs: ["get", "list", "watch"]
- apiGroups: ["argoproj.io"]
  resources: ["applications", "appprojects"]
  verbs: ["get", "list", "watch", "create", "update", "patch", "delete"]
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
  namespace: hemk-system
EOF

# Get ArgoCD admin password
log "Retrieving ArgoCD admin password..."
ARGOCD_PASSWORD=$($DOCKER_CMD exec hemk-poc-k3s kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath="{.data.password}" | base64 -d)

# Calculate installation time
END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))
MINUTES=$((DURATION / 60))
SECONDS=$((DURATION % 60))

# Generate HNP integration configuration
log "Generating HNP integration configuration..."
K3S_IP=$($DOCKER_CMD inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' hemk-poc-k3s | head -n1)

cat > "$SCRIPT_DIR/hnp-integration.yaml" <<EOF
# HNP Integration Configuration
# Generated: $(date)
# Installation time: ${MINUTES}m ${SECONDS}s

hemk:
  cluster:
    endpoint: "https://localhost:16443"
    container_ip: "${K3S_IP}"
    
  services:
    argocd:
      endpoint: "https://localhost:30443"
      admin_username: "admin"
      admin_password: "${ARGOCD_PASSWORD}"
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

# Final validation
log "Running installation validation..."
"$SCRIPT_DIR/scripts/validate-installation.sh" || warning "Some validation checks failed"

# Success message
echo ""
log "==============================================="
log "HEMK PoC Installation Complete!"
log "Installation time: ${MINUTES} minutes ${SECONDS} seconds"
log "==============================================="
echo ""
log "Access points:"
log "  ArgoCD UI: https://localhost:30443"
log "  ArgoCD Password: ${ARGOCD_PASSWORD}"
log "  Prometheus: http://localhost:30090"
log "  Kubeconfig: ${SCRIPT_DIR}/kubeconfig/kubeconfig.yaml"
echo ""
log "Next steps:"
log "  1. Review the HNP integration configuration: ${SCRIPT_DIR}/hnp-integration.yaml"
log "  2. Run './scripts/test-hnp-integration.sh' to validate HNP connectivity"
log "  3. Access ArgoCD UI to deploy your first application"
echo ""

if [ $MINUTES -lt 30 ]; then
    log "✅ SUCCESS: Installation completed in under 30 minutes!"
else
    warning "⚠️  Installation took longer than 30 minutes. Review logs for optimization opportunities."
fi