# HEMK PoC Technical Requirements
## Implementation Specifications and Validation Procedures

**Document Type**: Technical Requirements and Validation Procedures  
**Version**: 1.0  
**Date**: July 13, 2025  
**Author**: Senior PoC Development Lead  
**Target Audience**: PoC Development Team, Technical Implementers  

---

## Executive Summary

This document provides comprehensive technical requirements and validation procedures for the HEMK PoC implementation. With Docker available for testing and HNP NetBox running locally, we can perform realistic integration testing to validate the core architecture and user experience.

### Testing Environment Overview

**Local Environment Capabilities**:
- Docker available for containerized testing
- HNP NetBox instance running on port 8000
- Network connectivity between containers via Docker networks
- Resource-conscious container deployment for k3s testing

---

## Technical Implementation Requirements

### 1. Container-Based k3s Testing Environment

#### 1.1 k3s Docker Container Specification

**Base Container Configuration**:
```dockerfile
# Dockerfile.k3s-poc
FROM rancher/k3s:v1.27.3-k3s1

# Install required tools
RUN apk add --no-cache \
    curl \
    bash \
    git \
    openssl \
    ca-certificates

# k3s configuration
ENV K3S_NODE_NAME=hemk-poc
ENV K3S_KUBECONFIG_MODE=644
ENV INSTALL_K3S_EXEC="--disable traefik --disable servicelb"

# Health check
HEALTHCHECK --interval=30s --timeout=3s \
  CMD kubectl get nodes || exit 1

EXPOSE 6443 80 443 30080 30443
```

**Docker Compose Configuration**:
```yaml
# docker-compose.hemk-poc.yml
version: '3.8'

services:
  k3s-server:
    image: rancher/k3s:v1.27.3-k3s1
    container_name: hemk-poc-k3s
    privileged: true
    networks:
      - netbox-docker_default
    volumes:
      - k3s-server:/var/lib/rancher/k3s
      - ./kubeconfig:/output
    environment:
      - K3S_NODE_NAME=hemk-poc
      - K3S_KUBECONFIG_OUTPUT=/output/kubeconfig.yaml
      - K3S_KUBECONFIG_MODE=666
    command: server --disable traefik --disable servicelb
    ports:
      - "6443:6443"
      - "30080:30080"
      - "30443:30443"
    healthcheck:
      test: ["CMD", "kubectl", "get", "nodes"]
      interval: 30s
      timeout: 10s
      retries: 5

volumes:
  k3s-server:

networks:
  netbox-docker_default:
    external: true
```

#### 1.2 Resource Requirements and Constraints

**Container Resource Limits**:
```yaml
resources:
  limits:
    cpu: "2"
    memory: "4Gi"
  requests:
    cpu: "1"
    memory: "2Gi"
```

**Host System Requirements**:
- Available CPU: 2+ cores for k3s container
- Available Memory: 4GB minimum
- Available Storage: 20GB for container volumes
- Network: Access to netbox-docker_default network

### 2. Core HEMC Deployment Requirements

#### 2.1 ArgoCD Deployment Configuration

**Minimal ArgoCD Helm Values**:
```yaml
# argocd-poc-values.yaml
global:
  image:
    repository: quay.io/argoproj/argocd
    tag: v2.8.4

redis:
  enabled: true
  metrics:
    enabled: false

controller:
  replicas: 1
  resources:
    requests:
      cpu: 100m
      memory: 256Mi
    limits:
      cpu: 250m
      memory: 512Mi

server:
  replicas: 1
  service:
    type: ClusterIP
  ingress:
    enabled: true
    annotations:
      cert-manager.io/cluster-issuer: selfsigned-cluster-issuer
      nginx.ingress.kubernetes.io/ssl-redirect: "true"
    hosts:
      - argocd.hemk.local
    paths:
      - /
    pathType: Prefix
  extraArgs:
    - --insecure  # PoC only - TLS termination at ingress
  resources:
    requests:
      cpu: 50m
      memory: 128Mi
    limits:
      cpu: 100m
      memory: 256Mi

dex:
  enabled: false  # Simplified auth for PoC

applicationSet:
  enabled: false  # Not needed for PoC

notifications:
  enabled: false  # Not needed for PoC

configs:
  params:
    server.insecure: true
  cm:
    admin.enabled: "true"
    users.anonymous.enabled: "false"
```

#### 2.2 Monitoring Stack Configuration

**Prometheus Minimal Configuration**:
```yaml
# prometheus-poc-values.yaml
prometheus:
  prometheusSpec:
    replicas: 1
    retention: 7d
    resources:
      requests:
        cpu: 100m
        memory: 512Mi
      limits:
        cpu: 200m
        memory: 1Gi
    storageSpec:
      volumeClaimTemplate:
        spec:
          accessModes: ["ReadWriteOnce"]
          resources:
            requests:
              storage: 10Gi
    serviceMonitorSelectorNilUsesHelmValues: false
    podMonitorSelectorNilUsesHelmValues: false

  service:
    type: ClusterIP

grafana:
  enabled: true
  defaultDashboardsEnabled: true
  adminPassword: hemk-poc-admin
  persistence:
    enabled: true
    size: 5Gi
  resources:
    requests:
      cpu: 50m
      memory: 128Mi
    limits:
      cpu: 100m
      memory: 256Mi

alertmanager:
  enabled: false  # Not needed for PoC

kube-state-metrics:
  resources:
    requests:
      cpu: 10m
      memory: 32Mi
    limits:
      cpu: 20m
      memory: 64Mi

prometheus-node-exporter:
  resources:
    requests:
      cpu: 10m
      memory: 32Mi
    limits:
      cpu: 20m
      memory: 64Mi
```

### 3. HNP Integration Requirements

#### 3.1 Network Connectivity Configuration

**Docker Network Integration**:
```bash
#!/bin/bash
# connect-hemk-to-hnp.sh

# Connect k3s container to NetBox network
sudo docker network connect netbox-docker_default hemk-poc-k3s

# Verify connectivity
sudo docker exec hemk-poc-k3s ping -c 3 netbox-docker-netbox-1

# Get NetBox container IP
NETBOX_IP=$(sudo docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' netbox-docker-netbox-1)
echo "NetBox IP: $NETBOX_IP"

# Configure k3s to recognize NetBox
sudo docker exec hemk-poc-k3s kubectl create configmap netbox-config \
  --from-literal=netbox-url="http://$NETBOX_IP:8080" \
  --from-literal=netbox-api-url="http://$NETBOX_IP:8080/api"
```

#### 3.2 Service Account and RBAC Configuration

**HNP Integration Service Account**:
```yaml
# hnp-integration-rbac.yaml
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
- apiGroups: ["monitoring.coreos.com"]
  resources: ["servicemonitors", "prometheuses"]
  verbs: ["get", "list", "watch"]
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
```

#### 3.3 API Endpoint Configuration

**Service Exposure Configuration**:
```yaml
# api-endpoints.yaml
apiVersion: v1
kind: Service
metadata:
  name: argocd-server-nodeport
  namespace: argocd
spec:
  type: NodePort
  selector:
    app.kubernetes.io/name: argocd-server
  ports:
  - name: https
    port: 443
    targetPort: 8080
    nodePort: 30443
    protocol: TCP
---
apiVersion: v1
kind: Service
metadata:
  name: prometheus-nodeport
  namespace: monitoring
spec:
  type: NodePort
  selector:
    app.kubernetes.io/name: prometheus
  ports:
  - name: http
    port: 9090
    targetPort: 9090
    nodePort: 30090
    protocol: TCP
---
apiVersion: v1
kind: Service
metadata:
  name: grafana-nodeport
  namespace: monitoring
spec:
  type: NodePort
  selector:
    app.kubernetes.io/name: grafana
  ports:
  - name: http
    port: 3000
    targetPort: 3000
    nodePort: 30300
    protocol: TCP
```

### 4. Installation Automation Scripts

#### 4.1 Master Installation Script

**hemk-install.sh**:
```bash
#!/bin/bash
# HEMK PoC Installation Script

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_FILE="/tmp/hemk-install-$(date +%Y%m%d-%H%M%S).log"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

error() {
    echo "[ERROR] $1" | tee -a "$LOG_FILE" >&2
    exit 1
}

# Pre-flight checks
log "Starting HEMK PoC Installation..."
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

# Start k3s container
log "Starting k3s container..."
$DOCKER_CMD compose -f docker-compose.hemk-poc.yml up -d

# Wait for k3s to be ready
log "Waiting for k3s to be ready..."
for i in {1..30}; do
    if $DOCKER_CMD exec hemk-poc-k3s kubectl get nodes &> /dev/null; then
        log "k3s is ready!"
        break
    fi
    sleep 10
done

# Connect to NetBox network
log "Connecting to NetBox network..."
$DOCKER_CMD network connect netbox-docker_default hemk-poc-k3s 2>/dev/null || true

# Install cert-manager
log "Installing cert-manager..."
$DOCKER_CMD exec hemk-poc-k3s kubectl apply -f https://github.com/cert-manager/cert-manager/releases/download/v1.13.0/cert-manager.yaml

# Wait for cert-manager
sleep 30

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
$DOCKER_CMD exec hemk-poc-k3s kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/controller-v1.8.1/deploy/static/provider/kind/deploy.yaml

# Install ArgoCD
log "Installing ArgoCD..."
$DOCKER_CMD exec hemk-poc-k3s kubectl create namespace argocd || true
$DOCKER_CMD exec hemk-poc-k3s kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml

# Install Prometheus
log "Installing Prometheus..."
$DOCKER_CMD exec hemk-poc-k3s kubectl create namespace monitoring || true

# Apply HNP integration
log "Configuring HNP integration..."
$DOCKER_CMD exec hemk-poc-k3s kubectl apply -f hnp-integration-rbac.yaml

# Generate integration config
log "Generating HNP integration configuration..."
./scripts/generate-hnp-config.sh

log "HEMK PoC Installation Complete!"
log "Access ArgoCD at: https://localhost:30443"
log "Access Grafana at: http://localhost:30300"
log "Run './scripts/hnp-setup.sh' to configure HNP integration"
```

#### 4.2 HNP Integration Configuration Script

**generate-hnp-config.sh**:
```bash
#!/bin/bash
# Generate HNP integration configuration

DOCKER_CMD="${DOCKER_CMD:-docker}"
NETBOX_IP=$($DOCKER_CMD inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' netbox-docker-netbox-1)
K3S_IP=$($DOCKER_CMD inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' hemk-poc-k3s)

# Get service account token
SA_TOKEN=$($DOCKER_CMD exec hemk-poc-k3s kubectl -n hemk-system get secret \
  $(kubectl -n hemk-system get sa hnp-integration -o jsonpath='{.secrets[0].name}') \
  -o jsonpath='{.data.token}' | base64 -d)

# Generate configuration
cat > hnp-integration.yaml <<EOF
# HNP Integration Configuration
# Generated: $(date)

hemk:
  cluster:
    endpoint: "https://${K3S_IP}:6443"
    ca_cert: |
$(kubectl config view --raw -o jsonpath='{.clusters[0].cluster.certificate-authority-data}' | base64 -d | sed 's/^/      /')
    
  services:
    argocd:
      endpoint: "https://${K3S_IP}:30443"
      api_token: "${ARGOCD_TOKEN}"
      health_check: "/api/v1/version"
      
    prometheus:
      endpoint: "http://${K3S_IP}:30090"
      api_path: "/api/v1"
      health_check: "/api/v1/status/config"
      
    grafana:
      endpoint: "http://${K3S_IP}:30300"
      api_token: "${GRAFANA_TOKEN}"
      health_check: "/api/health"

  authentication:
    service_account_token: "${SA_TOKEN}"
    
  netbox:
    url: "http://${NETBOX_IP}:8080"
    api_url: "http://${NETBOX_IP}:8080/api"
EOF

echo "HNP integration configuration generated: hnp-integration.yaml"
```

### 5. Validation Procedures

#### 5.1 Component Health Validation

**validate-components.sh**:
```bash
#!/bin/bash
# Validate HEMK component health

DOCKER_CMD="${DOCKER_CMD:-docker}"

echo "HEMK Component Health Validation"
echo "================================"

# k3s cluster health
echo -n "k3s cluster: "
if $DOCKER_CMD exec hemk-poc-k3s kubectl get nodes | grep -q "Ready"; then
    echo "✅ Healthy"
else
    echo "❌ Unhealthy"
fi

# ArgoCD health
echo -n "ArgoCD: "
if $DOCKER_CMD exec hemk-poc-k3s kubectl -n argocd get pods | grep -q "Running"; then
    echo "✅ Running"
else
    echo "❌ Not running"
fi

# Prometheus health
echo -n "Prometheus: "
if $DOCKER_CMD exec hemk-poc-k3s kubectl -n monitoring get pods | grep prometheus | grep -q "Running"; then
    echo "✅ Running"
else
    echo "❌ Not running"
fi

# cert-manager health
echo -n "cert-manager: "
if $DOCKER_CMD exec hemk-poc-k3s kubectl -n cert-manager get pods | grep -q "Running"; then
    echo "✅ Running"
else
    echo "❌ Not running"
fi

# NGINX ingress health
echo -n "NGINX ingress: "
if $DOCKER_CMD exec hemk-poc-k3s kubectl -n ingress-nginx get pods | grep -q "Running"; then
    echo "✅ Running"
else
    echo "❌ Not running"
fi
```

#### 5.2 HNP Integration Testing

**test-hnp-integration.py**:
```python
#!/usr/bin/env python3
"""Test HNP integration with HEMK PoC"""

import requests
import json
import sys
import time

class HEMKIntegrationTest:
    def __init__(self, config_file='hnp-integration.yaml'):
        self.config = self.load_config(config_file)
        self.results = []
        
    def load_config(self, config_file):
        """Load integration configuration"""
        import yaml
        with open(config_file, 'r') as f:
            return yaml.safe_load(f)
    
    def test_argocd_api(self):
        """Test ArgoCD API connectivity"""
        print("Testing ArgoCD API...")
        try:
            url = f"{self.config['hemk']['services']['argocd']['endpoint']}/api/v1/version"
            response = requests.get(url, verify=False, timeout=5)
            if response.status_code == 200:
                print("✅ ArgoCD API accessible")
                return True
            else:
                print(f"❌ ArgoCD API returned {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ ArgoCD API error: {e}")
            return False
    
    def test_prometheus_api(self):
        """Test Prometheus API connectivity"""
        print("Testing Prometheus API...")
        try:
            url = f"{self.config['hemk']['services']['prometheus']['endpoint']}/api/v1/status/config"
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                print("✅ Prometheus API accessible")
                return True
            else:
                print(f"❌ Prometheus API returned {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ Prometheus API error: {e}")
            return False
    
    def test_netbox_connectivity(self):
        """Test connectivity from HEMK to NetBox"""
        print("Testing NetBox connectivity...")
        try:
            # This would be executed from within the k3s container
            import subprocess
            result = subprocess.run([
                'docker', 'exec', 'hemk-poc-k3s', 
                'curl', '-s', '-o', '/dev/null', '-w', '%{http_code}',
                self.config['hemk']['netbox']['url']
            ], capture_output=True, text=True)
            
            if result.stdout == '200':
                print("✅ NetBox accessible from HEMK")
                return True
            else:
                print(f"❌ NetBox returned {result.stdout}")
                return False
        except Exception as e:
            print(f"❌ NetBox connectivity error: {e}")
            return False
    
    def run_all_tests(self):
        """Run all integration tests"""
        print("\nHEMK-HNP Integration Tests")
        print("=" * 40)
        
        tests = [
            self.test_argocd_api,
            self.test_prometheus_api,
            self.test_netbox_connectivity
        ]
        
        passed = 0
        for test in tests:
            if test():
                passed += 1
            time.sleep(1)
        
        print("\n" + "=" * 40)
        print(f"Tests passed: {passed}/{len(tests)}")
        
        return passed == len(tests)

if __name__ == "__main__":
    tester = HEMKIntegrationTest()
    success = tester.run_all_tests()
    sys.exit(0 if success else 1)
```

#### 5.3 Performance Validation

**measure-performance.sh**:
```bash
#!/bin/bash
# Measure HEMK PoC performance metrics

DOCKER_CMD="${DOCKER_CMD:-docker}"

echo "HEMK Performance Metrics"
echo "======================="

# Container resource usage
echo "Container Resource Usage:"
$DOCKER_CMD stats --no-stream hemk-poc-k3s

# k3s cluster metrics
echo -e "\nCluster Resource Usage:"
$DOCKER_CMD exec hemk-poc-k3s kubectl top nodes 2>/dev/null || echo "Metrics not yet available"

echo -e "\nPod Resource Usage:"
$DOCKER_CMD exec hemk-poc-k3s kubectl top pods --all-namespaces 2>/dev/null || echo "Metrics not yet available"

# API response times
echo -e "\nAPI Response Times:"
time curl -s -o /dev/null http://localhost:30443/api/v1/version
time curl -s -o /dev/null http://localhost:30090/api/v1/status/config

# Installation time measurement
if [ -f "/tmp/hemk-install-*.log" ]; then
    echo -e "\nInstallation Time:"
    grep "Installation Complete" /tmp/hemk-install-*.log | tail -1
fi
```

---

## Success Validation Checklist

### Technical Implementation Success
- [ ] k3s container deploys and runs successfully
- [ ] All core HEMCs deploy within resource constraints
- [ ] Network connectivity between HEMK and HNP established
- [ ] API endpoints accessible from host and HNP
- [ ] Service account authentication functional

### Integration Success
- [ ] HNP can discover HEMK services
- [ ] ArgoCD API responds to HNP queries
- [ ] Prometheus metrics accessible from HNP
- [ ] Configuration export generates valid YAML
- [ ] End-to-end workflow validation passes

### Performance Success
- [ ] Container uses <2 CPU cores and <4GB RAM
- [ ] Installation completes in <30 minutes
- [ ] API response times <1 second
- [ ] All health checks pass consistently
- [ ] No resource exhaustion observed

This technical requirements document provides the foundation for implementing and validating the HEMK PoC using Docker containers and integrating with the local HNP NetBox instance.