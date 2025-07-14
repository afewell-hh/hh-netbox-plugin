#!/bin/bash
# HEMK PoC Environment Cleanup Script
# Thoroughly removes all HEMK components and frees up ports

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

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

echo "🧹 Starting HEMK PoC environment cleanup..."

# Stop and remove containers using docker-compose
echo "Stopping containers with docker-compose..."
cd "$SCRIPT_DIR"
$DOCKER_CMD compose -f docker-compose.hemk-poc.yml down -v || true

# Force remove any remaining HEMK containers
echo "Removing any remaining HEMK containers..."
for container in $($DOCKER_CMD ps -aq --filter "name=hemk-poc" 2>/dev/null || true); do
    echo "Removing container: $container"
    $DOCKER_CMD rm -f "$container" || true
done

# Remove any orphaned containers
echo "Cleaning up orphaned containers..."
$DOCKER_CMD container prune -f || true

# Remove any orphaned volumes
echo "Cleaning up orphaned volumes..."
$DOCKER_CMD volume prune -f || true

# Remove any orphaned networks (be careful not to remove netbox network)
echo "Cleaning up orphaned networks..."
for network in $($DOCKER_CMD network ls --filter "name=poc_development" -q 2>/dev/null || true); do
    echo "Removing network: $network"
    $DOCKER_CMD network rm "$network" || true
done

# Wait for ports to be fully released
echo "Waiting for ports to be released..."
sleep 5

# Check if ports are now available
echo "Checking port availability..."
for port in 30080 30443 30444 30090 16443; do
    if ss -tuln | grep -q ":$port "; then
        echo "⚠️  Port $port is still in use"
    else
        echo "✅ Port $port is available"
    fi
done

# Clean up kubeconfig directory
if [ -d "$SCRIPT_DIR/kubeconfig" ]; then
    echo "Removing kubeconfig directory..."
    chmod -R 755 "$SCRIPT_DIR/kubeconfig" 2>/dev/null || true
    rm -rf "$SCRIPT_DIR/kubeconfig" || true
fi

# Clean up HNP integration config
if [ -f "$SCRIPT_DIR/hnp-integration.yaml" ]; then
    echo "Removing HNP integration config..."
    rm -f "$SCRIPT_DIR/hnp-integration.yaml"
fi

echo ""
echo "✅ HEMK PoC environment cleanup completed!"
echo "You can now run the installation script again for a clean test."
echo ""
echo "To verify cleanup was successful:"
echo "  docker ps | grep hemk-poc"
echo "  ss -tuln | grep -E ':(30080|30443|30444|30090|16443) '"