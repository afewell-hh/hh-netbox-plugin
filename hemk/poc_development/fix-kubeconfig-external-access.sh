#!/bin/bash
# Fix kubeconfig for external access by embedding certificates
# This resolves the certificate path reference issue

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
KUBECONFIG_FILE="$SCRIPT_DIR/kubeconfig/kubeconfig.yaml"
# Check if sudo is needed for docker
if ! docker info &> /dev/null; then
    if sudo docker info &> /dev/null; then
        DOCKER_CMD="sudo docker"
    else
        echo "Error: Cannot connect to Docker daemon"
        exit 1
    fi
else
    DOCKER_CMD="docker"
fi

echo "Fixing kubeconfig for external access..."
echo "Using Docker command: $DOCKER_CMD"

# Check if container is running
echo "Checking if hemk-poc-k3s container is running..."
if ! $DOCKER_CMD ps | grep -q hemk-poc-k3s; then
    echo "Error: hemk-poc-k3s container is not running"
    echo "Available containers:"
    $DOCKER_CMD ps --format "table {{.Names}}\t{{.Status}}"
    exit 1
fi

echo "Container found: hemk-poc-k3s"
CONTAINER_NAME="hemk-poc-k3s"

# Extract the certificates from the container
echo "Extracting certificates from container..."

# Get the certificate files
CA_CERT=$($DOCKER_CMD exec $CONTAINER_NAME cat /var/lib/rancher/k3s/server/tls/server-ca.crt | base64 -w 0)
CLIENT_CERT=$($DOCKER_CMD exec $CONTAINER_NAME cat /var/lib/rancher/k3s/server/tls/client-admin.crt | base64 -w 0)
CLIENT_KEY=$($DOCKER_CMD exec $CONTAINER_NAME cat /var/lib/rancher/k3s/server/tls/client-admin.key | base64 -w 0)

# Create new kubeconfig with embedded certificates
echo "Creating kubeconfig with embedded certificates..."

cat > "$KUBECONFIG_FILE" <<EOF
apiVersion: v1
clusters:
- cluster:
    certificate-authority-data: $CA_CERT
    server: https://localhost:16443
  name: default
contexts:
- context:
    cluster: default
    user: default
  name: default
current-context: default
kind: Config
preferences: {}
users:
- name: default
  user:
    client-certificate-data: $CLIENT_CERT
    client-key-data: $CLIENT_KEY
EOF

echo "✅ Kubeconfig fixed! You can now use kubectl from outside the container:"
echo ""
echo "  kubectl --kubeconfig $KUBECONFIG_FILE get pods -A"
echo ""
echo "Or export the kubeconfig:"
echo ""
echo "  export KUBECONFIG=$KUBECONFIG_FILE"
echo "  kubectl get pods -A"