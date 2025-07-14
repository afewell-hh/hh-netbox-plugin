# HEMK Architecture Specification
## Hedgehog External Management Kubernetes

**Document Type**: Comprehensive Architecture Specification  
**Version**: 1.0  
**Date**: July 13, 2025  
**Author**: Senior Systems Architect  
**Target Audience**: Implementation teams, DevOps engineers, Network engineers  

---

## Executive Summary

The Hedgehog External Management Kubernetes (HEMK) architecture provides a comprehensive, production-ready platform that enables traditional network engineers to deploy and manage external infrastructure required for Hedgehog ONF fabric operations. This specification addresses the critical gap where customers need GitOps tools, monitoring infrastructure, and operational tooling but lack Kubernetes expertise.

### Key Architectural Decisions

1. **k3s-Based Foundation**: Lightweight, production-ready Kubernetes distribution optimized for edge deployments
2. **Modular Component Design**: Independent HEMC installation enabling customer choice and selective deployment
3. **Opinionated Simplicity**: Reduced choice paralysis with sensible defaults and escape hatches for customization
4. **HNP Integration First**: Seamless integration with Hedgehog NetBox Plugin GitOps workflows
5. **Progressive Disclosure**: Simple setup with advanced options available for expert users

### Critical Success Factors

- **<30 minute deployment** for core components on single-node VM
- **Zero-downtime operations** for production multi-node deployments
- **Seamless HNP integration** with automatic component discovery
- **Enterprise-grade security** with comprehensive compliance support
- **Non-expert friendly** with guided setup and troubleshooting

---

## System Architecture Overview

### High-Level Architecture Diagram

```
┌─────────────────────┐    ┌─────────────────────┐    ┌─────────────────────┐
│ Traditional Network │    │    Git Ecosystem    │    │   Customer Choice   │
│     Engineer        │    │                     │    │                     │
│                     │    │ ┌─────────────────┐ │    │ ┌─────────────────┐ │
│ • VLAN/Routing      │◄──►│ │ GitHub/GitLab   │ │◄──►│ │ Existing K8s    │ │
│ • CLI/GUI familiar  │    │ │ Multi-repo auth │ │    │ │ Infrastructure  │ │
│ • Enterprise needs  │    │ └─────────────────┘ │    │ └─────────────────┘ │
└─────────────────────┘    └─────────────────────┘    └─────────────────────┘
           │                           │                           │
           │                           │                           │
           └───────────────┬───────────┴───────────────┬───────────┘
                           │                           │
                ┌─────────────────────┐    ┌─────────────────────┐
                │ HNP (NetBox Plugin) │    │    HEMK Platform    │
                │                     │    │                     │
                │ • GitOps workflows  │◄──►│ • Core HEMCs        │
                │ • Fabric management │    │ • Supporting tools  │
                │ • Drift detection   │    │ • Security/Ops      │
                │ • Multi-cluster API │    │ • k3s foundation    │
                └─────────────────────┘    └─────────────────────┘
                           │                           │
                           │                           │
                ┌─────────────────────┐    ┌─────────────────────┐
                │ HCKC (Per Fabric)   │    │  Deployment Options │
                │                     │    │                     │
                │ • Hedgehog Control  │    │ • Single-node VM    │
                │ • k3s cluster       │    │ • Multi-node k3s    │
                │ • Fabric CRDs       │    │ • Cloud K8s (EKS)   │
                │ • Local operations  │    │ • Bare metal        │
                └─────────────────────┘    └─────────────────────┘
```

### Component Relationship Matrix

| Component Category | Primary Function | HNP Integration | User Interface | Operational Complexity |
|-------------------|------------------|-----------------|----------------|----------------------|
| **GitOps Engine** | ArgoCD/Flux | Direct API | Web UI + CLI | Medium |
| **Monitoring Stack** | Prometheus/Grafana | Metrics API | Web UI | Low |
| **Certificate Mgmt** | cert-manager | Service Certs | CLI + Dashboard | Low |
| **Ingress Control** | NGINX/Traefik | External Access | Config files | Medium |
| **Storage Layer** | Longhorn/Local | Persistent Data | Web UI + CLI | Medium |
| **Security Tools** | Network Policies | Traffic Control | Policy files | High |
| **Backup Systems** | Velero/k3s backup | Data Protection | CLI + Schedules | Medium |
| **Operational Tools** | Logging/Alerting | Health Monitoring | Dashboards | Low |

---

## Core HEMC Components Specification

### Primary HEMCs (Essential Components)

#### 1. GitOps Engine - ArgoCD Primary, Flux Alternative

**Purpose**: Automated GitOps deployment and synchronization engine

**ArgoCD Configuration**:
```yaml
argocd:
  global:
    image:
      repository: quay.io/argoproj/argocd
      tag: v2.8.4
  controller:
    resources:
      requests:
        cpu: 250m
        memory: 512Mi
      limits:
        cpu: 500m
        memory: 1Gi
  server:
    service:
      type: ClusterIP
    ingress:
      enabled: true
      annotations:
        cert-manager.io/cluster-issuer: letsencrypt-prod
        nginx.ingress.kubernetes.io/ssl-redirect: "true"
  dex:
    enabled: false  # Simplified auth for initial deployment
  configs:
    repositories:
      - url: https://github.com/customer/hedgehog-config
        type: git
        name: hedgehog-primary
```

**HNP Integration APIs**:
- Application Status: `GET /api/v1/applications/{name}`
- Sync Trigger: `POST /api/v1/applications/{name}/sync`
- Repository Validation: `POST /api/v1/repositories`
- Health Status: `GET /api/v1/applications/{name}/resource-tree`

**Resource Requirements**:
- CPU: 500m (1 core for multi-node)
- Memory: 1Gi (2Gi for production)
- Storage: 10Gi persistent volume
- Network: Ports 80, 443, 2746

#### 2. Monitoring Stack - Prometheus + Grafana

**Purpose**: Hedgehog fabric metrics collection and visualization

**Prometheus Configuration**:
```yaml
prometheus:
  retention: 30d
  storage:
    volumeClaimTemplate:
      spec:
        accessModes: ["ReadWriteOnce"]
        resources:
          requests:
            storage: 50Gi
  resources:
    requests:
      cpu: 500m
      memory: 2Gi
    limits:
      cpu: 1000m
      memory: 4Gi
  serviceMonitor:
    enabled: true
    additionalLabels:
      hedgehog.io/fabric: "true"
```

**Grafana Configuration**:
```yaml
grafana:
  persistence:
    enabled: true
    size: 10Gi
  dashboardProviders:
    hedgehog:
      name: hedgehog
      folder: "Hedgehog ONF"
      type: file
      disableDeletion: false
      updateIntervalSeconds: 30
      options:
        path: /var/lib/grafana/dashboards/hedgehog
  dashboards:
    hedgehog:
      fabric-overview:
        url: https://raw.githubusercontent.com/hedgehog-onf/dashboards/main/fabric-overview.json
      switch-health:
        url: https://raw.githubusercontent.com/hedgehog-onf/dashboards/main/switch-health.json
```

**HNP Integration APIs**:
- Metrics Query: `GET /api/v1/query?query={promql}`
- Dashboard Access: `GET /api/dashboards/uid/{uid}`
- Alert Rules: `POST /api/v1/rules`
- Health Check: `GET /api/v1/targets`

**Resource Requirements**:
- Prometheus: 1 CPU, 4Gi RAM, 50Gi storage
- Grafana: 500m CPU, 1Gi RAM, 10Gi storage
- Network: Ports 3000, 9090

#### 3. Certificate Management - cert-manager

**Purpose**: Automated TLS certificate lifecycle management

**Configuration**:
```yaml
cert-manager:
  global:
    leaderElection:
      namespace: cert-manager
  installCRDs: true
  resources:
    requests:
      cpu: 100m
      memory: 128Mi
    limits:
      cpu: 200m
      memory: 256Mi
  clusterIssuers:
    - name: letsencrypt-prod
      acme:
        server: https://acme-v02.api.letsencrypt.org/directory
        email: admin@customer.com
        privateKeySecretRef:
          name: letsencrypt-prod
        solvers:
        - http01:
            ingress:
              class: nginx
    - name: ca-issuer
      ca:
        secretName: ca-key-pair
```

**Integration Points**:
- Automatic certificate provisioning for all HEMK services
- Integration with cloud DNS providers for domain validation
- Certificate rotation automation with 30-day renewal
- Webhook notifications for certificate events

#### 4. Ingress Controller - NGINX Primary

**Purpose**: External access and traffic routing for HEMK services

**Configuration**:
```yaml
nginx-ingress:
  controller:
    kind: Deployment
    replicaCount: 2  # HA for multi-node
    resources:
      requests:
        cpu: 250m
        memory: 256Mi
      limits:
        cpu: 500m
        memory: 512Mi
    service:
      type: LoadBalancer  # NodePort for single-node
      annotations:
        service.beta.kubernetes.io/aws-load-balancer-type: nlb
    config:
      ssl-protocols: "TLSv1.2 TLSv1.3"
      ssl-ciphers: "ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256"
      force-ssl-redirect: "true"
```

**Security Policies**:
- Default deny-all network policies
- Rate limiting: 100 requests/minute per IP
- Geographic IP filtering (configurable)
- DDoS protection with fail2ban integration

### Supporting HEMCs (Operational Excellence)

#### 5. Storage Management - Longhorn

**Purpose**: Distributed storage for persistent workloads

**Configuration**:
```yaml
longhorn:
  persistence:
    defaultClass: true
    defaultClassReplicaCount: 2  # Single replica for single-node
    reclaimPolicy: Retain
  csi:
    nodeSelector:
      node-role.kubernetes.io/worker: "true"
  defaultSettings:
    backupTarget: s3://hemk-backups@us-west-2/
    defaultReplicaCount: 2
    guaranteedEngineManagerCPU: 12
    guaranteedReplicaManagerCPU: 12
```

**Features**:
- Automatic backup to cloud storage
- Volume snapshots and cloning
- Disaster recovery with cross-region replication
- Performance monitoring and alerting

#### 6. Backup and Recovery - Velero

**Purpose**: Cluster-level backup and disaster recovery

**Configuration**:
```yaml
velero:
  configuration:
    provider: aws
    backupStorageLocation:
      bucket: hemk-cluster-backups
      config:
        region: us-west-2
    volumeSnapshotLocation:
      config:
        region: us-west-2
  schedules:
    daily:
      schedule: "0 2 * * *"
      template:
        ttl: "720h"  # 30 days retention
    weekly:
      schedule: "0 3 * * 0"
      template:
        ttl: "2160h"  # 90 days retention
```

#### 7. Security Framework

**Network Policies**:
```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: hemk-default-deny
spec:
  podSelector: {}
  policyTypes:
  - Ingress
  - Egress
---
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: hemk-allow-ingress
spec:
  podSelector:
    matchLabels:
      hemk.io/ingress: "true"
  policyTypes:
  - Ingress
  ingress:
  - from:
    - namespaceSelector:
        matchLabels:
          name: ingress-nginx
```

**Pod Security Standards**:
```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: hemk-production
  labels:
    pod-security.kubernetes.io/enforce: restricted
    pod-security.kubernetes.io/audit: restricted
    pod-security.kubernetes.io/warn: restricted
```

#### 8. Operational Monitoring

**Node Exporter Configuration**:
```yaml
prometheus-node-exporter:
  resources:
    requests:
      cpu: 50m
      memory: 64Mi
    limits:
      cpu: 100m
      memory: 128Mi
  service:
    annotations:
      prometheus.io/scrape: "true"
```

**Alert Rules**:
```yaml
groups:
- name: hemk.rules
  rules:
  - alert: HEMKNodeDown
    expr: up{job="node-exporter"} == 0
    for: 5m
    labels:
      severity: critical
    annotations:
      summary: "HEMK node {{ $labels.instance }} is down"
  - alert: HEMKHighMemoryUsage
    expr: (1 - (node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes)) * 100 > 85
    for: 10m
    labels:
      severity: warning
    annotations:
      summary: "High memory usage on {{ $labels.instance }}"
```

---

## HNP Integration Architecture

### API Integration Patterns

#### GitOps Integration Layer

**HNP to ArgoCD Communication**:
```python
class HEMKGitOpsIntegration:
    def __init__(self, argocd_endpoint: str, auth_token: str):
        self.endpoint = argocd_endpoint
        self.auth_headers = {"Authorization": f"Bearer {auth_token}"}
    
    def create_application(self, fabric_id: str, repo_config: dict) -> str:
        """Create ArgoCD application for Hedgehog fabric"""
        app_spec = {
            "metadata": {
                "name": f"hedgehog-fabric-{fabric_id}",
                "namespace": "argocd"
            },
            "spec": {
                "project": "default",
                "source": {
                    "repoURL": repo_config["url"],
                    "targetRevision": repo_config.get("branch", "main"),
                    "path": repo_config["directory"]
                },
                "destination": {
                    "server": repo_config["cluster_endpoint"],
                    "namespace": "hedgehog-fabric"
                },
                "syncPolicy": {
                    "automated": {
                        "prune": True,
                        "selfHeal": True
                    }
                }
            }
        }
        
    def get_application_status(self, fabric_id: str) -> dict:
        """Get GitOps application status for fabric"""
        app_name = f"hedgehog-fabric-{fabric_id}"
        response = requests.get(
            f"{self.endpoint}/api/v1/applications/{app_name}",
            headers=self.auth_headers
        )
        return response.json()
    
    def trigger_sync(self, fabric_id: str) -> dict:
        """Trigger manual sync for fabric application"""
        app_name = f"hedgehog-fabric-{fabric_id}"
        sync_request = {
            "revision": "HEAD",
            "prune": True,
            "dryRun": False
        }
        response = requests.post(
            f"{self.endpoint}/api/v1/applications/{app_name}/sync",
            headers=self.auth_headers,
            json=sync_request
        )
        return response.json()
```

#### Monitoring Integration Layer

**HNP to Prometheus/Grafana Communication**:
```python
class HEMKMonitoringIntegration:
    def __init__(self, prometheus_endpoint: str, grafana_endpoint: str, auth_token: str):
        self.prometheus_endpoint = prometheus_endpoint
        self.grafana_endpoint = grafana_endpoint
        self.auth_headers = {"Authorization": f"Bearer {auth_token}"}
    
    def query_fabric_health(self, fabric_id: str) -> dict:
        """Query Hedgehog fabric health metrics"""
        queries = {
            "switch_status": f'hedgehog_switch_up{{fabric_id="{fabric_id}"}}',
            "bgp_sessions": f'hedgehog_bgp_session_up{{fabric_id="{fabric_id}"}}',
            "interface_status": f'hedgehog_interface_up{{fabric_id="{fabric_id}"}}'
        }
        
        results = {}
        for metric, query in queries.items():
            response = requests.get(
                f"{self.prometheus_endpoint}/api/v1/query",
                params={"query": query},
                headers=self.auth_headers
            )
            results[metric] = response.json()
        
        return results
    
    def get_dashboard_url(self, dashboard_type: str, fabric_id: str) -> str:
        """Generate Grafana dashboard URL for fabric"""
        dashboard_mapping = {
            "fabric_overview": "hedgehog-fabric-overview",
            "switch_health": "hedgehog-switch-health",
            "bgp_status": "hedgehog-bgp-monitoring"
        }
        
        dashboard_uid = dashboard_mapping.get(dashboard_type)
        if not dashboard_uid:
            raise ValueError(f"Unknown dashboard type: {dashboard_type}")
        
        return f"{self.grafana_endpoint}/d/{dashboard_uid}?var-fabric_id={fabric_id}"
```

### Authentication and Authorization Framework

#### Multi-Repository Authentication

**Git Repository Manager**:
```python
class HEMKGitRepositoryManager:
    def __init__(self, secret_store):
        self.secret_store = secret_store
        self.authenticated_repos = {}
    
    def authenticate_repository(self, repo_url: str, auth_method: str, credentials: dict) -> bool:
        """Authenticate access to a Git repository"""
        if auth_method == "ssh_key":
            return self._authenticate_ssh(repo_url, credentials["private_key"])
        elif auth_method == "token":
            return self._authenticate_token(repo_url, credentials["token"])
        elif auth_method == "app_password":
            return self._authenticate_app_password(repo_url, credentials["username"], credentials["password"])
        else:
            raise ValueError(f"Unsupported authentication method: {auth_method}")
    
    def validate_repository_access(self, repo_url: str, directory: str) -> dict:
        """Validate access to specific GitOps directory"""
        try:
            # Clone repository and check directory existence
            repo = git.Repo.clone_from(repo_url, "/tmp/repo_validation")
            directory_exists = os.path.exists(os.path.join("/tmp/repo_validation", directory))
            
            # Check for required files
            required_files = ["kustomization.yaml", "fabric.yaml"]
            files_present = []
            for file in required_files:
                file_path = os.path.join("/tmp/repo_validation", directory, file)
                if os.path.exists(file_path):
                    files_present.append(file)
            
            return {
                "accessible": True,
                "directory_exists": directory_exists,
                "required_files": files_present,
                "validation_errors": []
            }
        except Exception as e:
            return {
                "accessible": False,
                "error": str(e)
            }
```

#### Service-to-Service Authentication

**HEMK Service Account Configuration**:
```yaml
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
  resources: ["services", "endpoints"]
  verbs: ["get", "list"]
- apiGroups: ["apps"]
  resources: ["deployments", "statefulsets"]
  verbs: ["get", "list"]
- apiGroups: ["argoproj.io"]
  resources: ["applications"]
  verbs: ["get", "list", "create", "update", "patch"]
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

### Configuration Import/Export Mechanisms

#### HEMK Configuration Export

**Configuration Template**:
```yaml
# hemk-integration-config.yaml
hemk:
  cluster:
    endpoint: "https://hemk.customer.com:6443"
    ca_certificate: |
      -----BEGIN CERTIFICATE-----
      [Base64 encoded CA certificate]
      -----END CERTIFICATE-----
  
  services:
    argocd:
      endpoint: "https://argocd.hemk.customer.com"
      api_token_secret: "hnp-argocd-token"
      web_ui_url: "https://argocd.hemk.customer.com"
    
    prometheus:
      endpoint: "https://prometheus.hemk.customer.com"
      api_token_secret: "hnp-prometheus-token"
      query_url: "https://prometheus.hemk.customer.com/api/v1/query"
    
    grafana:
      endpoint: "https://grafana.hemk.customer.com"
      api_token_secret: "hnp-grafana-token"
      dashboard_base_url: "https://grafana.hemk.customer.com/d"
  
  authentication:
    service_account: "hnp-integration"
    namespace: "hemk-system"
    token_secret: "hnp-service-account-token"
  
  monitoring:
    health_check_interval: 30
    metrics_collection_enabled: true
    alert_webhook_url: "https://hnp.customer.com/api/hemk/alerts"
```

---

## User Experience Architecture

### Installation and Deployment Automation

#### Bootstrap Installation Process

**Single-Command Deployment**:
```bash
#!/bin/bash
# hemk-install.sh - One-command HEMK deployment

set -euo pipefail

# Configuration
HEMK_VERSION="v1.0.0"
K3S_VERSION="v1.28.3+k3s2"
INSTALLATION_MODE="${1:-single-node}"  # single-node, multi-node, cloud

# Pre-flight checks
echo "🔍 Running pre-flight checks..."
./scripts/preflight-check.sh

# Install k3s
echo "📦 Installing k3s..."
if [ "$INSTALLATION_MODE" = "single-node" ]; then
    curl -sfL https://get.k3s.io | INSTALL_K3S_VERSION=$K3S_VERSION sh -s - \
        --disable traefik \
        --disable servicelb \
        --write-kubeconfig-mode 644
else
    ./scripts/install-k3s-cluster.sh
fi

# Wait for k3s to be ready
echo "⏳ Waiting for k3s to be ready..."
until kubectl get nodes | grep Ready; do
    sleep 5
done

# Install Helm
echo "📦 Installing Helm..."
curl https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash

# Add Helm repositories
echo "📚 Adding Helm repositories..."
helm repo add hemk https://charts.hemk.io
helm repo add argo https://argoproj.github.io/argo-helm
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo add jetstack https://charts.jetstack.io
helm repo update

# Install HEMK platform
echo "🚀 Installing HEMK platform..."
helm install hemk-platform hemk/platform \
    --namespace hemk-system \
    --create-namespace \
    --set installation.mode=$INSTALLATION_MODE \
    --set domain=${HEMK_DOMAIN:-hemk.local} \
    --wait --timeout=600s

# Install core HEMCs
echo "🔧 Installing core HEMCs..."
./scripts/install-core-hemcs.sh $INSTALLATION_MODE

# Generate integration configuration
echo "📋 Generating HNP integration configuration..."
./scripts/generate-hnp-config.sh

echo "✅ HEMK installation complete!"
echo "📊 ArgoCD UI: https://argocd.${HEMK_DOMAIN:-hemk.local}"
echo "📈 Grafana UI: https://grafana.${HEMK_DOMAIN:-hemk.local}"
echo "🔧 Integration config: ./output/hnp-integration-config.yaml"
```

#### Guided Configuration Wizard

**Interactive Setup Process**:
```python
class HEMKConfigurationWizard:
    def __init__(self):
        self.config = {}
        self.deployment_mode = None
        self.domain = None
        self.components = {}
    
    def run_wizard(self):
        """Run interactive configuration wizard"""
        print("🎯 HEMK Configuration Wizard")
        print("═" * 50)
        
        # Step 1: Deployment mode
        self.deployment_mode = self._select_deployment_mode()
        
        # Step 2: Domain configuration
        self.domain = self._configure_domain()
        
        # Step 3: Component selection
        self.components = self._select_components()
        
        # Step 4: Security configuration
        security_config = self._configure_security()
        
        # Step 5: Git repository setup
        git_config = self._configure_git_repositories()
        
        # Step 6: Generate configuration
        self._generate_configuration()
        
        # Step 7: Pre-flight validation
        self._validate_configuration()
        
        print("✅ Configuration wizard complete!")
        return self.config
    
    def _select_deployment_mode(self):
        """Select deployment mode with guidance"""
        print("\n📦 Deployment Mode Selection")
        print("─" * 30)
        
        modes = {
            1: {
                "name": "Single-node VM",
                "description": "Best for: Development, evaluation, small environments",
                "requirements": "1 VM: 4 CPU, 8GB RAM, 100GB storage",
                "complexity": "Low"
            },
            2: {
                "name": "Multi-node cluster",
                "description": "Best for: Production, high availability",
                "requirements": "3+ VMs: 4 CPU, 8GB RAM, 100GB storage each",
                "complexity": "Medium"
            },
            3: {
                "name": "Cloud Kubernetes",
                "description": "Best for: Existing cloud infrastructure",
                "requirements": "Existing EKS/AKS/GKE cluster",
                "complexity": "Medium"
            }
        }
        
        for i, mode in modes.items():
            print(f"{i}. {mode['name']}")
            print(f"   {mode['description']}")
            print(f"   Requirements: {mode['requirements']}")
            print(f"   Complexity: {mode['complexity']}\n")
        
        while True:
            try:
                choice = int(input("Select deployment mode (1-3): "))
                if choice in modes:
                    selected_mode = modes[choice]["name"].lower().replace(" ", "-").replace("-kubernetes", "")
                    print(f"✅ Selected: {modes[choice]['name']}")
                    return selected_mode
                else:
                    print("❌ Invalid choice. Please select 1, 2, or 3.")
            except ValueError:
                print("❌ Please enter a valid number.")
    
    def _configure_domain(self):
        """Configure domain with validation"""
        print("\n🌐 Domain Configuration")
        print("─" * 25)
        
        print("HEMK services will be accessible at:")
        print("• ArgoCD: https://argocd.{domain}")
        print("• Grafana: https://grafana.{domain}")
        print("• Prometheus: https://prometheus.{domain}")
        
        while True:
            domain = input("\nEnter your domain (e.g., hemk.company.com): ").strip()
            if self._validate_domain(domain):
                print(f"✅ Domain: {domain}")
                return domain
            else:
                print("❌ Invalid domain format. Please try again.")
    
    def _select_components(self):
        """Select HEMC components with recommendations"""
        print("\n🔧 Component Selection")
        print("─" * 22)
        
        components = {
            "gitops": {
                "name": "GitOps Engine",
                "options": ["argocd", "flux"],
                "recommended": "argocd",
                "required": True,
                "description": "Required for Hedgehog GitOps workflows"
            },
            "monitoring": {
                "name": "Monitoring Stack",
                "options": ["full", "prometheus-only", "none"],
                "recommended": "full",
                "required": False,
                "description": "Hedgehog fabric monitoring and alerting"
            },
            "certificates": {
                "name": "Certificate Management",
                "options": ["letsencrypt", "internal-ca", "manual"],
                "recommended": "letsencrypt",
                "required": True,
                "description": "Automated TLS certificate management"
            },
            "backup": {
                "name": "Backup Solution",
                "options": ["velero", "k3s-backup", "none"],
                "recommended": "velero",
                "required": False,
                "description": "Cluster and data backup automation"
            }
        }
        
        selected = {}
        for key, component in components.items():
            print(f"\n📋 {component['name']}")
            print(f"   {component['description']}")
            print(f"   Required: {'Yes' if component['required'] else 'No'}")
            print(f"   Recommended: {component['recommended']}")
            
            if component["required"]:
                if len(component["options"]) == 1:
                    selected[key] = component["options"][0]
                    print(f"   ✅ Auto-selected: {selected[key]}")
                else:
                    for i, option in enumerate(component["options"], 1):
                        marker = " (recommended)" if option == component["recommended"] else ""
                        print(f"   {i}. {option}{marker}")
                    
                    while True:
                        try:
                            choice = int(input(f"   Select option (1-{len(component['options'])}): "))
                            if 1 <= choice <= len(component["options"]):
                                selected[key] = component["options"][choice - 1]
                                print(f"   ✅ Selected: {selected[key]}")
                                break
                            else:
                                print(f"   ❌ Please select 1-{len(component['options'])}")
                        except ValueError:
                            print("   ❌ Please enter a valid number")
            else:
                enable = input(f"   Enable {component['name']}? [Y/n]: ").strip().lower()
                if enable in ['y', 'yes', '']:
                    selected[key] = component["recommended"]
                    print(f"   ✅ Enabled: {selected[key]}")
                else:
                    selected[key] = "disabled"
                    print(f"   ⏸️  Disabled")
        
        return selected
```

### Monitoring Dashboard Integration

#### Hedgehog-Specific Dashboards

**Fabric Overview Dashboard**:
```json
{
  "dashboard": {
    "title": "Hedgehog Fabric Overview",
    "tags": ["hedgehog", "fabric", "overview"],
    "templating": {
      "list": [
        {
          "name": "fabric_id",
          "type": "query",
          "query": "label_values(hedgehog_fabric_info, fabric_id)",
          "refresh": 1
        }
      ]
    },
    "panels": [
      {
        "title": "Fabric Health Score",
        "type": "stat",
        "targets": [
          {
            "expr": "hedgehog_fabric_health_score{fabric_id=\"$fabric_id\"}",
            "legendFormat": "Health Score"
          }
        ],
        "fieldConfig": {
          "defaults": {
            "min": 0,
            "max": 100,
            "unit": "percent",
            "thresholds": {
              "steps": [
                {"color": "red", "value": 0},
                {"color": "yellow", "value": 70},
                {"color": "green", "value": 90}
              ]
            }
          }
        }
      },
      {
        "title": "Switch Status",
        "type": "table",
        "targets": [
          {
            "expr": "hedgehog_switch_up{fabric_id=\"$fabric_id\"}",
            "format": "table",
            "instant": true
          }
        ],
        "transformations": [
          {
            "id": "organize",
            "options": {
              "excludeByName": {"__name__": true, "job": true},
              "renameByName": {
                "switch_name": "Switch",
                "Value": "Status"
              }
            }
          }
        ]
      },
      {
        "title": "BGP Session Status",
        "type": "timeseries",
        "targets": [
          {
            "expr": "sum by (switch_name) (hedgehog_bgp_session_up{fabric_id=\"$fabric_id\"})",
            "legendFormat": "{{switch_name}}"
          }
        ]
      }
    ]
  }
}
```

### Troubleshooting and Support System

#### Self-Diagnostic Framework

**HEMK Health Check System**:
```bash
#!/bin/bash
# hemk-health-check.sh - Comprehensive health check script

echo "🏥 HEMK Health Check Starting..."
echo "═════════════════════════════════"

# Track overall health
OVERALL_HEALTH=0
TOTAL_CHECKS=0

# Function to run health check
run_check() {
    local check_name="$1"
    local check_command="$2"
    local critical="${3:-false}"
    
    echo -n "🔍 $check_name... "
    TOTAL_CHECKS=$((TOTAL_CHECKS + 1))
    
    if eval "$check_command" &>/dev/null; then
        echo "✅ PASS"
        OVERALL_HEALTH=$((OVERALL_HEALTH + 1))
    else
        if [ "$critical" = "true" ]; then
            echo "❌ FAIL (CRITICAL)"
        else
            echo "⚠️  FAIL (WARNING)"
        fi
        # Show troubleshooting guidance
        show_troubleshooting "$check_name"
    fi
}

# Show troubleshooting guidance
show_troubleshooting() {
    local check_name="$1"
    
    case "$check_name" in
        "k3s cluster health")
            echo "   💡 Try: sudo systemctl status k3s"
            echo "   📖 Docs: https://docs.hemk.io/troubleshooting/k3s"
            ;;
        "ArgoCD availability")
            echo "   💡 Try: kubectl get pods -n argocd"
            echo "   📖 Docs: https://docs.hemk.io/troubleshooting/argocd"
            ;;
        "Prometheus metrics")
            echo "   💡 Try: kubectl port-forward -n monitoring svc/prometheus 9090:9090"
            echo "   📖 Docs: https://docs.hemk.io/troubleshooting/monitoring"
            ;;
        *)
            echo "   📖 General troubleshooting: https://docs.hemk.io/troubleshooting"
            ;;
    esac
    echo ""
}

# Core infrastructure checks
echo "🏗️  Infrastructure Checks"
echo "─────────────────────────"
run_check "k3s cluster health" "kubectl cluster-info" true
run_check "Node readiness" "kubectl get nodes | grep -q Ready" true
run_check "System resources" "[ \$(free -m | awk 'NR==2{print \$7}') -gt 1000 ]"
run_check "Disk space" "[ \$(df / | awk 'NR==2{print \$4}') -gt 10000000 ]"

# Core HEMC checks
echo ""
echo "🔧 Core HEMC Checks"
echo "───────────────────"
run_check "ArgoCD availability" "kubectl get pods -n argocd | grep -q Running" true
run_check "Prometheus metrics" "kubectl get pods -n monitoring | grep prometheus | grep -q Running"
run_check "Grafana dashboard" "kubectl get pods -n monitoring | grep grafana | grep -q Running"
run_check "cert-manager" "kubectl get pods -n cert-manager | grep -q Running"

# Connectivity checks
echo ""
echo "🌐 Connectivity Checks"
echo "─────────────────────"
run_check "External DNS resolution" "nslookup google.com"
run_check "Internet connectivity" "curl -s --connect-timeout 5 https://google.com"
run_check "Container registry access" "docker pull alpine:latest"

# Security checks
echo ""
echo "🔒 Security Checks"
echo "─────────────────"
run_check "Network policies active" "kubectl get networkpolicies --all-namespaces | grep -q ."
run_check "Pod security standards" "kubectl get ns hemk-system -o yaml | grep -q pod-security"
run_check "TLS certificates valid" "kubectl get certificates --all-namespaces | grep -q True"

# HNP integration checks
echo ""
echo "🔗 HNP Integration Checks"
echo "─────────────────────────"
run_check "Service account exists" "kubectl get sa hnp-integration -n hemk-system"
run_check "RBAC permissions" "kubectl auth can-i get applications --as=system:serviceaccount:hemk-system:hnp-integration"
run_check "API endpoints accessible" "curl -k -s https://localhost:6443/api/v1"

# Calculate health percentage
HEALTH_PERCENTAGE=$((OVERALL_HEALTH * 100 / TOTAL_CHECKS))

echo ""
echo "📊 Health Summary"
echo "════════════════"
echo "✅ Passed: $OVERALL_HEALTH/$TOTAL_CHECKS checks"
echo "📈 Health Score: $HEALTH_PERCENTAGE%"

if [ $HEALTH_PERCENTAGE -ge 90 ]; then
    echo "🎉 System status: EXCELLENT"
elif [ $HEALTH_PERCENTAGE -ge 75 ]; then
    echo "👍 System status: GOOD"
elif [ $HEALTH_PERCENTAGE -ge 50 ]; then
    echo "⚠️  System status: NEEDS ATTENTION"
else
    echo "🚨 System status: CRITICAL - Contact support"
fi

echo ""
echo "📚 Additional Resources:"
echo "• Full documentation: https://docs.hemk.io"
echo "• Support portal: https://support.hemk.io"
echo "• Community forum: https://community.hemk.io"
```

---

## Implementation Specifications

### Phased Deployment Strategy

#### Phase 1: Core Infrastructure (Week 1-2)

**Deliverables**:
1. **k3s Bootstrap Automation**
   - Single-node and multi-node installation scripts
   - Automated system requirement validation
   - Network and storage configuration
   - Basic security hardening

2. **Base Platform Components**
   - Helm chart repository setup
   - Namespace and RBAC configuration
   - Network policies foundation
   - Ingress controller deployment

3. **Certificate Management**
   - cert-manager installation and configuration
   - LetsEncrypt integration for public certificates
   - Internal CA setup for private certificates
   - Automated certificate rotation

**Success Criteria**:
- ✅ k3s cluster operational in <15 minutes
- ✅ Basic ingress and TLS working
- ✅ All pods in Running state
- ✅ Health check script passes 100%

#### Phase 2: Core HEMCs (Week 3-4)

**Deliverables**:
1. **ArgoCD Deployment**
   - Production-ready ArgoCD installation
   - Multi-repository authentication setup
   - Application template configuration
   - HNP integration API implementation

2. **Monitoring Stack**
   - Prometheus server deployment with retention policies
   - Grafana installation with Hedgehog dashboards
   - Alert rule configuration
   - Metrics collection from Hedgehog components

3. **Storage Management**
   - Longhorn distributed storage (multi-node)
   - Local storage optimization (single-node)
   - Backup integration setup
   - Performance monitoring

**Success Criteria**:
- ✅ ArgoCD accessible and functional
- ✅ Monitoring dashboards operational
- ✅ Storage provisioning working
- ✅ HNP can connect to all APIs

#### Phase 3: Operational Excellence (Week 5-6)

**Deliverables**:
1. **Backup and Recovery**
   - Velero deployment and configuration
   - Automated backup scheduling
   - Disaster recovery procedures
   - Recovery testing framework

2. **Security Hardening**
   - Pod Security Standards enforcement
   - Network policy implementation
   - Secret management best practices
   - Security scanning integration

3. **User Experience**
   - Configuration wizard implementation
   - Health check and diagnostic tools
   - Documentation and troubleshooting guides
   - Support system integration

**Success Criteria**:
- ✅ Automated backups completing successfully
- ✅ Security policies enforced
- ✅ User can deploy HEMK without assistance
- ✅ Recovery procedures tested and documented

### Helm Chart Architecture

#### Chart Structure and Dependencies

```
hemk-platform/
├── Chart.yaml                 # Main platform chart
├── values.yaml               # Default configuration values
├── values-examples/          # Example configurations
│   ├── single-node.yaml      # Single-node deployment
│   ├── multi-node.yaml       # Multi-node deployment
│   └── cloud.yaml            # Cloud deployment
├── charts/                   # Subchart dependencies
│   ├── argocd/               # ArgoCD subchart
│   ├── prometheus-stack/     # Monitoring subchart
│   ├── cert-manager/         # Certificate management
│   ├── longhorn/             # Storage management
│   └── velero/               # Backup solution
├── templates/                # Platform templates
│   ├── namespace.yaml        # Core namespaces
│   ├── rbac.yaml            # RBAC configuration
│   ├── network-policies.yaml # Security policies
│   ├── ingress.yaml         # Ingress configuration
│   └── configmap.yaml       # Platform configuration
└── scripts/                 # Helper scripts
    ├── install.sh           # Installation script
    ├── upgrade.sh           # Upgrade procedures
    └── health-check.sh      # Health validation
```

#### Configuration Management

**Main Values File Structure**:
```yaml
# values.yaml - Main configuration
global:
  domain: "hemk.local"
  storageClass: "longhorn"
  ingressClass: "nginx"
  
  # Deployment mode: single-node, multi-node, cloud
  deploymentMode: "single-node"
  
  # Security settings
  security:
    podSecurityStandards: "restricted"
    networkPolicies: true
    tlsOnly: true
  
  # Resource limits
  resources:
    small:
      cpu: "500m"
      memory: "1Gi"
    medium:
      cpu: "1000m"
      memory: "2Gi"
    large:
      cpu: "2000m"
      memory: "4Gi"

# Core HEMCs configuration
argocd:
  enabled: true
  size: "medium"
  server:
    ingress:
      enabled: true
      hostname: "argocd.{{ .Values.global.domain }}"
      tls: true
  configs:
    repositories: []  # Configured post-deployment

prometheus:
  enabled: true
  size: "large"
  retention: "30d"
  storage: "50Gi"
  ingress:
    enabled: true
    hostname: "prometheus.{{ .Values.global.domain }}"

grafana:
  enabled: true
  size: "medium"
  ingress:
    enabled: true
    hostname: "grafana.{{ .Values.global.domain }}"
  dashboards:
    hedgehog:
      enabled: true
      provider: "git"
      repository: "https://github.com/hedgehog-onf/dashboards"

certManager:
  enabled: true
  clusterIssuers:
    - name: "letsencrypt-prod"
      acme:
        server: "https://acme-v02.api.letsencrypt.org/directory"
        email: "admin@{{ .Values.global.domain }}"
    - name: "ca-issuer"
      ca:
        secretName: "ca-key-pair"

longhorn:
  enabled: true
  defaultClass: true
  replicaCount: 2
  backupTarget: ""  # Configured post-deployment

velero:
  enabled: false  # Optional component
  configuration:
    provider: "aws"
    backupStorageLocation:
      bucket: ""
      config:
        region: "us-west-2"

# Networking configuration
networking:
  ingress:
    controller: "nginx"
    class: "nginx"
    annotations:
      nginx.ingress.kubernetes.io/ssl-redirect: "true"
      nginx.ingress.kubernetes.io/force-ssl-redirect: "true"
  
  networkPolicies:
    defaultDeny: true
    allowIngress: true
    allowEgress: false

# Operational configuration
operations:
  monitoring:
    nodeExporter: true
    kubeStateMetrics: true
    alerting: true
  
  backup:
    enabled: false
    schedule: "0 2 * * *"
    retention: "30d"
  
  logging:
    enabled: false
    aggregation: "none"  # none, loki, elasticsearch

# HNP integration
hnp:
  integration:
    enabled: true
    serviceAccount: "hnp-integration"
    rbac: true
    webhook:
      enabled: false
      url: ""
```

### Testing and Validation Framework

#### Automated Testing Pipeline

**Test Categories and Coverage**:

1. **Unit Tests (Helm Templates)**
```bash
#!/bin/bash
# test-templates.sh - Helm template unit tests

echo "🧪 Running Helm template tests..."

# Test 1: Valid template rendering
helm template hemk-platform ./charts/hemk-platform \
    --values ./test-values/single-node.yaml \
    --dry-run > /tmp/rendered-templates.yaml

if [ $? -eq 0 ]; then
    echo "✅ Template rendering: PASS"
else
    echo "❌ Template rendering: FAIL"
    exit 1
fi

# Test 2: Resource validation
kubectl apply --dry-run=client -f /tmp/rendered-templates.yaml

if [ $? -eq 0 ]; then
    echo "✅ Resource validation: PASS"
else
    echo "❌ Resource validation: FAIL"
    exit 1
fi

# Test 3: Security policy compliance
echo "🔒 Checking security compliance..."

# Check for privileged containers
if grep -q "privileged: true" /tmp/rendered-templates.yaml; then
    echo "❌ Security: Found privileged containers"
    exit 1
fi

# Check for hostNetwork usage
if grep -q "hostNetwork: true" /tmp/rendered-templates.yaml; then
    echo "❌ Security: Found hostNetwork usage"
    exit 1
fi

echo "✅ Security compliance: PASS"
```

2. **Integration Tests (Component Interaction)**
```python
#!/usr/bin/env python3
# test-integration.py - Integration test suite

import requests
import subprocess
import time
import yaml
from pathlib import Path

class HEMKIntegrationTests:
    def __init__(self, kubeconfig_path):
        self.kubeconfig = kubeconfig_path
        self.test_results = []
    
    def test_argocd_api(self):
        """Test ArgoCD API connectivity and basic functionality"""
        try:
            # Get ArgoCD admin password
            result = subprocess.run([
                "kubectl", "get", "secret", "argocd-initial-admin-secret",
                "-n", "argocd", "-o", "jsonpath={.data.password}"
            ], capture_output=True, text=True)
            
            if result.returncode != 0:
                raise Exception("Failed to get ArgoCD admin password")
            
            password = result.stdout
            
            # Test API endpoint
            response = requests.get(
                "https://argocd.hemk.local/api/v1/session",
                auth=("admin", password),
                verify=False,
                timeout=10
            )
            
            if response.status_code == 200:
                self.test_results.append(("ArgoCD API", "PASS"))
            else:
                self.test_results.append(("ArgoCD API", f"FAIL: {response.status_code}"))
                
        except Exception as e:
            self.test_results.append(("ArgoCD API", f"FAIL: {str(e)}"))
    
    def test_prometheus_metrics(self):
        """Test Prometheus metrics collection"""
        try:
            # Port-forward to Prometheus
            port_forward = subprocess.Popen([
                "kubectl", "port-forward", "-n", "monitoring",
                "svc/prometheus-server", "9090:80"
            ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            
            time.sleep(5)  # Wait for port-forward to establish
            
            # Test metrics endpoint
            response = requests.get(
                "http://localhost:9090/api/v1/targets",
                timeout=10
            )
            
            port_forward.terminate()
            
            if response.status_code == 200:
                targets = response.json()
                active_targets = len([t for t in targets["data"]["activeTargets"] 
                                    if t["health"] == "up"])
                if active_targets > 0:
                    self.test_results.append(("Prometheus Metrics", "PASS"))
                else:
                    self.test_results.append(("Prometheus Metrics", "FAIL: No active targets"))
            else:
                self.test_results.append(("Prometheus Metrics", f"FAIL: {response.status_code}"))
                
        except Exception as e:
            self.test_results.append(("Prometheus Metrics", f"FAIL: {str(e)}"))
    
    def test_certificate_management(self):
        """Test cert-manager certificate issuance"""
        try:
            # Check for ready certificates
            result = subprocess.run([
                "kubectl", "get", "certificates", "--all-namespaces",
                "-o", "jsonpath={.items[*].status.conditions[?(@.type=='Ready')].status}"
            ], capture_output=True, text=True)
            
            if "True" in result.stdout:
                self.test_results.append(("Certificate Management", "PASS"))
            else:
                self.test_results.append(("Certificate Management", "FAIL: No ready certificates"))
                
        except Exception as e:
            self.test_results.append(("Certificate Management", f"FAIL: {str(e)}"))
    
    def run_all_tests(self):
        """Run all integration tests"""
        print("🧪 Running HEMK Integration Tests")
        print("=" * 40)
        
        tests = [
            self.test_argocd_api,
            self.test_prometheus_metrics,
            self.test_certificate_management
        ]
        
        for test in tests:
            test()
        
        # Print results
        print("\n📊 Test Results:")
        print("-" * 25)
        passed = 0
        for test_name, result in self.test_results:
            status_icon = "✅" if result == "PASS" else "❌"
            print(f"{status_icon} {test_name}: {result}")
            if result == "PASS":
                passed += 1
        
        print(f"\n📈 Summary: {passed}/{len(self.test_results)} tests passed")
        
        if passed == len(self.test_results):
            print("🎉 All integration tests passed!")
            return True
        else:
            print("🚨 Some tests failed - check configuration")
            return False

if __name__ == "__main__":
    tester = HEMKIntegrationTests("~/.kube/config")
    success = tester.run_all_tests()
    exit(0 if success else 1)
```

3. **End-to-End Tests (Full Workflow)**
```bash
#!/bin/bash
# test-e2e.sh - End-to-end workflow testing

echo "🎯 HEMK End-to-End Testing"
echo "════════════════════════"

# Test scenario: Complete HNP-HEMK integration workflow
E2E_PASSED=0
E2E_TOTAL=0

run_e2e_test() {
    local test_name="$1"
    local test_command="$2"
    
    echo -n "🔄 $test_name... "
    E2E_TOTAL=$((E2E_TOTAL + 1))
    
    if eval "$test_command"; then
        echo "✅ PASS"
        E2E_PASSED=$((E2E_PASSED + 1))
    else
        echo "❌ FAIL"
        return 1
    fi
}

# E2E Test 1: Fresh HEMK deployment
run_e2e_test "Fresh HEMK deployment" "
    # Clean previous installation
    helm uninstall hemk-platform -n hemk-system || true
    kubectl delete namespace hemk-system || true
    
    # Deploy HEMK
    ./scripts/hemk-install.sh single-node
    
    # Wait for all pods to be ready
    kubectl wait --for=condition=ready pod --all -n hemk-system --timeout=300s
    kubectl wait --for=condition=ready pod --all -n argocd --timeout=300s
    kubectl wait --for=condition=ready pod --all -n monitoring --timeout=300s
"

# E2E Test 2: HNP integration configuration
run_e2e_test "HNP integration setup" "
    # Generate integration config
    ./scripts/generate-hnp-config.sh > /tmp/hnp-config.yaml
    
    # Validate config structure
    python3 -c \"
import yaml
with open('/tmp/hnp-config.yaml') as f:
    config = yaml.safe_load(f)
    assert 'hemk' in config
    assert 'services' in config['hemk']
    assert 'argocd' in config['hemk']['services']
    assert 'prometheus' in config['hemk']['services']
\"
"

# E2E Test 3: GitOps application deployment
run_e2e_test "GitOps application deployment" "
    # Create test application
    kubectl apply -f - <<EOF
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: test-hedgehog-fabric
  namespace: argocd
spec:
  project: default
  source:
    repoURL: https://github.com/hedgehog-onf/test-configs
    targetRevision: main
    path: fabric-minimal
  destination:
    server: https://kubernetes.default.svc
    namespace: hedgehog-test
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
    syncOptions:
    - CreateNamespace=true
EOF
    
    # Wait for application to sync
    timeout 120s bash -c 'until kubectl get application test-hedgehog-fabric -n argocd -o jsonpath=\"{.status.sync.status}\" | grep -q Synced; do sleep 5; done'
"

# E2E Test 4: Monitoring data collection
run_e2e_test "Monitoring data collection" "
    # Check if metrics are being collected
    kubectl port-forward -n monitoring svc/prometheus-server 9090:80 &
    PF_PID=\$!
    sleep 5
    
    # Query for HEMK metrics
    curl -s 'http://localhost:9090/api/v1/query?query=up{job=\"kubernetes-nodes\"}' | grep -q '\"result\"'
    METRICS_RESULT=\$?
    
    kill \$PF_PID
    [ \$METRICS_RESULT -eq 0 ]
"

# E2E Test 5: Certificate automation
run_e2e_test "Certificate automation" "
    # Check for automatically issued certificates
    kubectl get certificates --all-namespaces -o jsonpath='{.items[*].status.conditions[?(@.type==\"Ready\")].status}' | grep -q True
"

# E2E Test 6: Backup functionality
run_e2e_test "Backup functionality" "
    # Create a test backup (if Velero enabled)
    if kubectl get deployment velero -n velero &>/dev/null; then
        velero backup create test-backup --wait
        velero backup describe test-backup | grep -q 'Phase: Completed'
    else
        # Test k3s etcd backup
        sudo k3s etcd-snapshot save test-snapshot
        [ -f /var/lib/rancher/k3s/server/db/snapshots/test-snapshot ]
    fi
"

# Calculate E2E success rate
E2E_SUCCESS_RATE=$((E2E_PASSED * 100 / E2E_TOTAL))

echo ""
echo "📊 End-to-End Test Summary"
echo "═════════════════════════"
echo "✅ Passed: $E2E_PASSED/$E2E_TOTAL tests"
echo "📈 Success Rate: $E2E_SUCCESS_RATE%"

if [ $E2E_SUCCESS_RATE -eq 100 ]; then
    echo "🎉 All E2E tests passed! HEMK is ready for production."
elif [ $E2E_SUCCESS_RATE -ge 80 ]; then
    echo "👍 Most E2E tests passed. Minor issues may need attention."
else
    echo "🚨 E2E tests failed. HEMK requires troubleshooting before use."
    exit 1
fi
```

---

## Operational Procedures

### Installation and Deployment Procedures

#### Production Deployment Checklist

**Pre-Deployment Requirements**:
- [ ] Infrastructure provisioned (VMs, network, storage)
- [ ] DNS records configured for HEMK services
- [ ] Firewall rules configured (ports 80, 443, 6443, 22)
- [ ] SSL certificates planned (LetsEncrypt or internal CA)
- [ ] Backup storage configured (S3, NFS, or local)
- [ ] Admin access credentials prepared
- [ ] Network time synchronization configured

**Deployment Steps**:
1. **Infrastructure Validation**
   ```bash
   # Run pre-flight checks
   ./scripts/preflight-check.sh production
   
   # Validate network connectivity
   ./scripts/network-validation.sh
   
   # Check system resources
   ./scripts/resource-check.sh
   ```

2. **Core Platform Installation**
   ```bash
   # Install k3s cluster
   ./scripts/install-k3s.sh --mode=multi-node --ha=true
   
   # Install Helm and add repositories
   ./scripts/setup-helm.sh
   
   # Deploy HEMK platform
   helm install hemk-platform hemk/platform \
     --namespace hemk-system \
     --create-namespace \
     --values ./config/production-values.yaml \
     --wait --timeout=900s
   ```

3. **HEMC Component Installation**
   ```bash
   # Install core HEMCs in sequence
   ./scripts/install-argocd.sh --production
   ./scripts/install-monitoring.sh --production
   ./scripts/install-cert-manager.sh --production
   ./scripts/install-storage.sh --production
   
   # Validate all components
   ./scripts/validate-installation.sh
   ```

4. **Security Configuration**
   ```bash
   # Apply security policies
   kubectl apply -f ./config/security/network-policies.yaml
   kubectl apply -f ./config/security/pod-security-standards.yaml
   
   # Configure RBAC
   kubectl apply -f ./config/security/rbac.yaml
   
   # Validate security compliance
   ./scripts/security-audit.sh
   ```

5. **HNP Integration Setup**
   ```bash
   # Generate integration configuration
   ./scripts/generate-hnp-config.sh --output=./output/hnp-integration.yaml
   
   # Create service accounts and tokens
   ./scripts/setup-hnp-integration.sh
   
   # Test API connectivity
   ./scripts/test-hnp-connectivity.sh
   ```

### Monitoring and Alerting Procedures

#### Health Monitoring Framework

**Key Performance Indicators (KPIs)**:
```yaml
# hemk-kpis.yaml - Key metrics to monitor
kpis:
  infrastructure:
    - name: "Node CPU Utilization"
      query: "100 - (avg by (instance) (irate(node_cpu_seconds_total{mode='idle'}[5m])) * 100)"
      warning_threshold: 80
      critical_threshold: 90
    
    - name: "Node Memory Utilization"
      query: "(1 - (node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes)) * 100"
      warning_threshold: 85
      critical_threshold: 95
    
    - name: "Disk Space Utilization"
      query: "100 - ((node_filesystem_avail_bytes * 100) / node_filesystem_size_bytes)"
      warning_threshold: 80
      critical_threshold: 90
  
  application:
    - name: "ArgoCD Application Sync Status"
      query: "argocd_app_info{sync_status!='Synced'}"
      warning_threshold: 1
      critical_threshold: 5
    
    - name: "Pod Restart Rate"
      query: "increase(kube_pod_container_status_restarts_total[1h])"
      warning_threshold: 5
      critical_threshold: 10
    
    - name: "Certificate Expiry"
      query: "(cert_manager_certificate_expiration_timestamp_seconds - time()) / 86400"
      warning_threshold: 30
      critical_threshold: 7
  
  business:
    - name: "Hedgehog Fabric Health Score"
      query: "avg(hedgehog_fabric_health_score)"
      warning_threshold: 80
      critical_threshold: 70
    
    - name: "GitOps Sync Success Rate"
      query: "rate(argocd_app_reconcile_count{operation='sync',phase='Succeeded'}[5m]) * 100"
      warning_threshold: 95
      critical_threshold: 90
```

**Alert Rule Configuration**:
```yaml
# alerts.yaml - Production alert rules
groups:
- name: hemk.critical
  rules:
  - alert: HEMKNodeDown
    expr: up{job="node-exporter"} == 0
    for: 1m
    labels:
      severity: critical
      component: infrastructure
    annotations:
      summary: "HEMK node {{ $labels.instance }} is down"
      description: "Node {{ $labels.instance }} has been down for more than 1 minute"
      runbook_url: "https://docs.hemk.io/runbooks/node-down"
      action: "Check node status and restart if necessary"
  
  - alert: HEMKHighMemoryUsage
    expr: (1 - (node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes)) * 100 > 95
    for: 5m
    labels:
      severity: critical
      component: infrastructure
    annotations:
      summary: "Critical memory usage on {{ $labels.instance }}"
      description: "Memory usage is {{ $value }}% on {{ $labels.instance }}"
      runbook_url: "https://docs.hemk.io/runbooks/high-memory"
      action: "Investigate memory usage and scale resources"
  
  - alert: ArgoCDApplicationNotSynced
    expr: argocd_app_info{sync_status!="Synced"} > 0
    for: 10m
    labels:
      severity: warning
      component: gitops
    annotations:
      summary: "ArgoCD application {{ $labels.name }} not synced"
      description: "Application {{ $labels.name }} has been out of sync for more than 10 minutes"
      runbook_url: "https://docs.hemk.io/runbooks/argocd-sync"
      action: "Check application status and resolve sync issues"
  
  - alert: CertificateExpiringSoon
    expr: (cert_manager_certificate_expiration_timestamp_seconds - time()) / 86400 < 30
    labels:
      severity: warning
      component: security
    annotations:
      summary: "Certificate {{ $labels.name }} expiring soon"
      description: "Certificate {{ $labels.name }} will expire in {{ $value }} days"
      runbook_url: "https://docs.hemk.io/runbooks/certificate-renewal"
      action: "Verify certificate renewal process"

- name: hemk.performance
  rules:
  - alert: HEMKHighCPUUsage
    expr: 100 - (avg by (instance) (irate(node_cpu_seconds_total{mode="idle"}[5m])) * 100) > 80
    for: 15m
    labels:
      severity: warning
      component: infrastructure
    annotations:
      summary: "High CPU usage on {{ $labels.instance }}"
      description: "CPU usage is {{ $value }}% on {{ $labels.instance }}"
      runbook_url: "https://docs.hemk.io/runbooks/high-cpu"
      action: "Investigate CPU usage patterns and optimize"
  
  - alert: HEMKLowDiskSpace
    expr: 100 - ((node_filesystem_avail_bytes * 100) / node_filesystem_size_bytes) > 80
    for: 5m
    labels:
      severity: warning
      component: infrastructure
    annotations:
      summary: "Low disk space on {{ $labels.instance }}"
      description: "Disk usage is {{ $value }}% on {{ $labels.instance }}"
      runbook_url: "https://docs.hemk.io/runbooks/disk-space"
      action: "Clean up disk space or expand storage"
```

#### Notification and Escalation

**Alert Routing Configuration**:
```yaml
# alertmanager.yaml - Alert routing and notification
global:
  smtp_smarthost: 'smtp.company.com:587'
  smtp_from: 'hemk-alerts@company.com'

route:
  group_by: ['alertname', 'cluster', 'service']
  group_wait: 30s
  group_interval: 5m
  repeat_interval: 24h
  receiver: 'default'
  routes:
  - match:
      severity: critical
    receiver: 'critical-alerts'
    group_wait: 10s
    repeat_interval: 5m
  - match:
      component: infrastructure
    receiver: 'infrastructure-team'
  - match:
      component: gitops
    receiver: 'devops-team'

receivers:
- name: 'default'
  email_configs:
  - to: 'hemk-admins@company.com'
    subject: 'HEMK Alert: {{ .GroupLabels.alertname }}'
    body: |
      {{ range .Alerts }}
      Alert: {{ .Annotations.summary }}
      Description: {{ .Annotations.description }}
      Severity: {{ .Labels.severity }}
      Action: {{ .Annotations.action }}
      Runbook: {{ .Annotations.runbook_url }}
      {{ end }}

- name: 'critical-alerts'
  email_configs:
  - to: 'hemk-oncall@company.com'
    subject: 'CRITICAL HEMK Alert: {{ .GroupLabels.alertname }}'
  slack_configs:
  - api_url: 'https://hooks.slack.com/services/...'
    channel: '#hemk-critical'
    title: 'CRITICAL: {{ .GroupLabels.alertname }}'
    text: '{{ range .Alerts }}{{ .Annotations.summary }}{{ end }}'

- name: 'infrastructure-team'
  email_configs:
  - to: 'infrastructure@company.com'
    subject: 'HEMK Infrastructure Alert: {{ .GroupLabels.alertname }}'

- name: 'devops-team'
  email_configs:
  - to: 'devops@company.com'
    subject: 'HEMK GitOps Alert: {{ .GroupLabels.alertname }}'
```

### Backup and Disaster Recovery

#### Backup Strategy Implementation

**Comprehensive Backup Plan**:
```bash
#!/bin/bash
# backup-strategy.sh - Comprehensive HEMK backup

BACKUP_DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/var/backups/hemk"
S3_BUCKET="s3://company-hemk-backups"

echo "🔄 Starting HEMK backup: $BACKUP_DATE"

# 1. etcd snapshot (k3s cluster state)
echo "📸 Creating etcd snapshot..."
sudo k3s etcd-snapshot save "hemk-etcd-$BACKUP_DATE"
if [ $? -eq 0 ]; then
    echo "✅ etcd snapshot created"
    # Upload to S3
    aws s3 cp "/var/lib/rancher/k3s/server/db/snapshots/hemk-etcd-$BACKUP_DATE" \
              "$S3_BUCKET/etcd/hemk-etcd-$BACKUP_DATE"
else
    echo "❌ etcd snapshot failed"
    exit 1
fi

# 2. Kubernetes resource backup (Velero)
echo "📦 Creating Velero backup..."
velero backup create "hemk-full-$BACKUP_DATE" \
    --include-namespaces "hemk-system,argocd,monitoring,cert-manager" \
    --wait

if velero backup describe "hemk-full-$BACKUP_DATE" | grep -q "Phase: Completed"; then
    echo "✅ Velero backup completed"
else
    echo "❌ Velero backup failed"
    exit 1
fi

# 3. Persistent volume snapshots
echo "💾 Creating volume snapshots..."
kubectl get pv -o jsonpath='{.items[*].metadata.name}' | xargs -n1 -I {} \
    kubectl patch pv {} -p '{"metadata":{"annotations":{"backup.longhorn.io/snapshot":"'$BACKUP_DATE'"}}}'

# 4. Application data backup
echo "🗃️  Backing up application data..."

# ArgoCD configuration
kubectl get secret argocd-secret -n argocd -o yaml > "$BACKUP_DIR/argocd-secret-$BACKUP_DATE.yaml"
kubectl get configmap argocd-cm -n argocd -o yaml > "$BACKUP_DIR/argocd-config-$BACKUP_DATE.yaml"

# Grafana dashboards and configuration
kubectl exec -n monitoring deployment/grafana -- \
    tar czf - /var/lib/grafana/dashboards > "$BACKUP_DIR/grafana-dashboards-$BACKUP_DATE.tar.gz"

# Prometheus configuration
kubectl get configmap prometheus-config -n monitoring -o yaml > "$BACKUP_DIR/prometheus-config-$BACKUP_DATE.yaml"

# 5. Upload application backups to S3
echo "☁️  Uploading to S3..."
aws s3 sync "$BACKUP_DIR" "$S3_BUCKET/application-data/"

# 6. Cleanup old backups (retain 30 days)
echo "🧹 Cleaning old backups..."
find "$BACKUP_DIR" -name "*.yaml" -mtime +30 -delete
find "$BACKUP_DIR" -name "*.tar.gz" -mtime +30 -delete
find "/var/lib/rancher/k3s/server/db/snapshots" -name "hemk-etcd-*" -mtime +30 -delete

echo "✅ HEMK backup completed: $BACKUP_DATE"
echo "📊 Backup summary:"
echo "   - etcd snapshot: hemk-etcd-$BACKUP_DATE"
echo "   - Velero backup: hemk-full-$BACKUP_DATE"
echo "   - Application data: $BACKUP_DIR/*-$BACKUP_DATE.*"
echo "   - S3 location: $S3_BUCKET"
```

#### Disaster Recovery Procedures

**Recovery Runbook**:
```bash
#!/bin/bash
# disaster-recovery.sh - HEMK disaster recovery

RECOVERY_MODE="${1:-full}"  # full, partial, data-only
BACKUP_DATE="${2:-latest}"

echo "🚨 HEMK Disaster Recovery Started"
echo "Mode: $RECOVERY_MODE"
echo "Backup Date: $BACKUP_DATE"
echo "═════════════════════════════════"

# Function to validate prerequisites
validate_prerequisites() {
    echo "🔍 Validating recovery prerequisites..."
    
    # Check if backup exists
    if [ "$BACKUP_DATE" != "latest" ]; then
        aws s3 ls "$S3_BUCKET/etcd/hemk-etcd-$BACKUP_DATE" || {
            echo "❌ Backup not found: $BACKUP_DATE"
            exit 1
        }
    fi
    
    # Check system resources
    ./scripts/resource-check.sh || {
        echo "❌ Insufficient system resources"
        exit 1
    }
    
    # Check network connectivity
    curl -s https://google.com || {
        echo "❌ No internet connectivity"
        exit 1
    }
    
    echo "✅ Prerequisites validated"
}

# Full disaster recovery
full_recovery() {
    echo "🔄 Starting full disaster recovery..."
    
    # 1. Restore k3s cluster from etcd snapshot
    echo "📸 Restoring etcd snapshot..."
    
    # Stop k3s
    sudo systemctl stop k3s
    
    # Download latest etcd snapshot
    if [ "$BACKUP_DATE" = "latest" ]; then
        LATEST_SNAPSHOT=$(aws s3 ls "$S3_BUCKET/etcd/" | sort | tail -n 1 | awk '{print $4}')
    else
        LATEST_SNAPSHOT="hemk-etcd-$BACKUP_DATE"
    fi
    
    aws s3 cp "$S3_BUCKET/etcd/$LATEST_SNAPSHOT" "/var/lib/rancher/k3s/server/db/snapshots/"
    
    # Restore from snapshot
    sudo k3s server --cluster-reset --cluster-reset-restore-path="/var/lib/rancher/k3s/server/db/snapshots/$LATEST_SNAPSHOT"
    
    # Start k3s
    sudo systemctl start k3s
    
    # Wait for cluster to be ready
    until kubectl get nodes | grep Ready; do
        echo "Waiting for cluster to be ready..."
        sleep 10
    done
    
    echo "✅ Cluster restored from etcd snapshot"
    
    # 2. Restore application data with Velero
    echo "📦 Restoring application data..."
    
    # Install Velero (if not present)
    if ! kubectl get deployment velero -n velero &>/dev/null; then
        ./scripts/install-velero.sh
    fi
    
    # Find latest Velero backup
    if [ "$BACKUP_DATE" = "latest" ]; then
        LATEST_BACKUP=$(velero backup get | grep hemk-full | sort | tail -n 1 | awk '{print $1}')
    else
        LATEST_BACKUP="hemk-full-$BACKUP_DATE"
    fi
    
    # Restore from Velero backup
    velero restore create "recovery-$BACKUP_DATE" --from-backup "$LATEST_BACKUP" --wait
    
    echo "✅ Application data restored"
    
    # 3. Validate recovery
    validate_recovery
}

# Partial recovery (specific components)
partial_recovery() {
    echo "🔧 Starting partial recovery..."
    
    # Restore specific namespaces or applications
    # This would be customized based on what needs recovery
    
    # Example: Restore only ArgoCD
    velero restore create "argocd-recovery-$BACKUP_DATE" \
        --from-backup "hemk-full-$BACKUP_DATE" \
        --include-namespaces argocd \
        --wait
    
    echo "✅ Partial recovery completed"
}

# Data-only recovery
data_only_recovery() {
    echo "🗃️  Starting data-only recovery..."
    
    # Download and restore application configurations
    mkdir -p "/tmp/recovery-$BACKUP_DATE"
    aws s3 sync "$S3_BUCKET/application-data/" "/tmp/recovery-$BACKUP_DATE/"
    
    # Restore ArgoCD configuration
    kubectl apply -f "/tmp/recovery-$BACKUP_DATE/argocd-secret-$BACKUP_DATE.yaml"
    kubectl apply -f "/tmp/recovery-$BACKUP_DATE/argocd-config-$BACKUP_DATE.yaml"
    
    # Restore Grafana dashboards
    kubectl exec -n monitoring deployment/grafana -- \
        tar xzf - -C / < "/tmp/recovery-$BACKUP_DATE/grafana-dashboards-$BACKUP_DATE.tar.gz"
    
    # Restart services to pick up new configuration
    kubectl rollout restart deployment/argocd-server -n argocd
    kubectl rollout restart deployment/grafana -n monitoring
    
    echo "✅ Data recovery completed"
}

# Validate recovery
validate_recovery() {
    echo "🔍 Validating recovery..."
    
    # Run comprehensive health check
    ./scripts/hemk-health-check.sh
    
    # Check specific services
    echo "Checking ArgoCD..."
    kubectl wait --for=condition=ready pod -l app.kubernetes.io/name=argocd-server -n argocd --timeout=300s
    
    echo "Checking Grafana..."
    kubectl wait --for=condition=ready pod -l app.kubernetes.io/name=grafana -n monitoring --timeout=300s
    
    echo "Checking Prometheus..."
    kubectl wait --for=condition=ready pod -l app.kubernetes.io/name=prometheus -n monitoring --timeout=300s
    
    # Test API endpoints
    ./scripts/test-api-endpoints.sh
    
    echo "✅ Recovery validation completed"
}

# Main recovery logic
case "$RECOVERY_MODE" in
    "full")
        validate_prerequisites
        full_recovery
        ;;
    "partial")
        validate_prerequisites
        partial_recovery
        ;;
    "data-only")
        validate_prerequisites
        data_only_recovery
        ;;
    *)
        echo "❌ Invalid recovery mode: $RECOVERY_MODE"
        echo "Valid modes: full, partial, data-only"
        exit 1
        ;;
esac

echo "🎉 HEMK disaster recovery completed successfully!"
echo "📊 Recovery summary:"
echo "   - Mode: $RECOVERY_MODE"
echo "   - Backup date: $BACKUP_DATE"
echo "   - Recovery time: $(date)"
echo ""
echo "📚 Next steps:"
echo "1. Verify all applications are functioning correctly"
echo "2. Test HNP integration connectivity"
echo "3. Confirm monitoring and alerting are operational"
echo "4. Update documentation with any configuration changes"
```

### Upgrade and Maintenance Procedures

#### Rolling Update Strategy

**Zero-Downtime Upgrade Process**:
```bash
#!/bin/bash
# rolling-upgrade.sh - Zero-downtime HEMK upgrade

CURRENT_VERSION=$(helm list -n hemk-system -o json | jq -r '.[0].app_version')
TARGET_VERSION="${1:-latest}"
BACKUP_BEFORE_UPGRADE="${2:-true}"

echo "🔄 HEMK Rolling Upgrade"
echo "Current version: $CURRENT_VERSION"
echo "Target version: $TARGET_VERSION"
echo "═══════════════════════════════"

# Pre-upgrade validation
pre_upgrade_checks() {
    echo "🔍 Pre-upgrade validation..."
    
    # Check cluster health
    ./scripts/hemk-health-check.sh || {
        echo "❌ Cluster health check failed - aborting upgrade"
        exit 1
    }
    
    # Check resource availability
    kubectl top nodes || {
        echo "❌ Unable to get node metrics - check metrics server"
        exit 1
    }
    
    # Validate Helm repositories
    helm repo update
    
    echo "✅ Pre-upgrade checks passed"
}

# Create pre-upgrade backup
create_backup() {
    if [ "$BACKUP_BEFORE_UPGRADE" = "true" ]; then
        echo "📸 Creating pre-upgrade backup..."
        ./scripts/backup-strategy.sh
        echo "✅ Pre-upgrade backup completed"
    fi
}

# Upgrade core platform
upgrade_platform() {
    echo "🚀 Upgrading HEMK platform..."
    
    # Get current values
    helm get values hemk-platform -n hemk-system > /tmp/current-values.yaml
    
    # Upgrade with current values
    helm upgrade hemk-platform hemk/platform \
        --namespace hemk-system \
        --values /tmp/current-values.yaml \
        --version "$TARGET_VERSION" \
        --wait --timeout=900s
    
    if [ $? -eq 0 ]; then
        echo "✅ Platform upgrade completed"
    else
        echo "❌ Platform upgrade failed - initiating rollback"
        helm rollback hemk-platform -n hemk-system
        exit 1
    fi
}

# Upgrade individual HEMCs
upgrade_hemcs() {
    echo "🔧 Upgrading HEMC components..."
    
    # ArgoCD upgrade
    echo "Upgrading ArgoCD..."
    helm upgrade argocd argo/argo-cd \
        --namespace argocd \
        --reuse-values \
        --wait --timeout=600s
    
    # Monitoring stack upgrade
    echo "Upgrading monitoring stack..."
    helm upgrade prometheus-stack prometheus-community/kube-prometheus-stack \
        --namespace monitoring \
        --reuse-values \
        --wait --timeout=600s
    
    # cert-manager upgrade
    echo "Upgrading cert-manager..."
    helm upgrade cert-manager jetstack/cert-manager \
        --namespace cert-manager \
        --reuse-values \
        --wait --timeout=300s
    
    echo "✅ HEMC upgrades completed"
}

# Post-upgrade validation
post_upgrade_validation() {
    echo "🔍 Post-upgrade validation..."
    
    # Wait for all pods to be ready
    echo "Waiting for pods to be ready..."
    kubectl wait --for=condition=ready pod --all -n hemk-system --timeout=300s
    kubectl wait --for=condition=ready pod --all -n argocd --timeout=300s
    kubectl wait --for=condition=ready pod --all -n monitoring --timeout=300s
    kubectl wait --for=condition=ready pod --all -n cert-manager --timeout=300s
    
    # Run comprehensive health check
    ./scripts/hemk-health-check.sh
    
    # Test HNP integration
    ./scripts/test-hnp-connectivity.sh
    
    # Run integration tests
    ./scripts/test-integration.py
    
    echo "✅ Post-upgrade validation completed"
}

# Main upgrade process
main() {
    echo "Starting HEMK upgrade process..."
    
    pre_upgrade_checks
    create_backup
    upgrade_platform
    upgrade_hemcs
    post_upgrade_validation
    
    echo "🎉 HEMK upgrade completed successfully!"
    echo "📊 Upgrade summary:"
    echo "   - Previous version: $CURRENT_VERSION"
    echo "   - Current version: $(helm list -n hemk-system -o json | jq -r '.[0].app_version')"
    echo "   - Upgrade time: $(date)"
    echo "   - Downtime: 0 minutes (rolling upgrade)"
}

# Execute main function
main "$@"
```

---

## Risk Assessment and Mitigation Strategies

### Technical Risk Analysis

#### High-Priority Risks

**1. Resource Constraints and Performance Impact**
- **Risk**: HEMK components consume significant resources, impacting host system performance
- **Probability**: High (especially on minimal hardware)
- **Impact**: High (system instability, poor user experience)
- **Mitigation Strategies**:
  - Implement comprehensive resource limits and requests in all Helm charts
  - Provide clear minimum system requirements with safety margins
  - Create resource monitoring and alerting for capacity planning
  - Offer "lightweight" deployment profiles for resource-constrained environments
  - Implement horizontal pod autoscaling for core components

**2. Network Connectivity and DNS Resolution**
- **Risk**: Complex networking requirements causing connectivity issues
- **Probability**: Medium (varied customer network environments)
- **Impact**: High (complete system inaccessibility)
- **Mitigation Strategies**:
  - Provide comprehensive networking documentation with firewall rules
  - Implement network connectivity validation scripts
  - Support multiple ingress options (LoadBalancer, NodePort, HostNetwork)
  - Create troubleshooting guides for common network issues
  - Offer offline installation packages for restricted environments

**3. Certificate Management and SSL/TLS Issues**
- **Risk**: Certificate provisioning failures causing service outages
- **Probability**: Medium (LetsEncrypt rate limits, DNS challenges)
- **Impact**: Medium (service inaccessibility, security warnings)
- **Mitigation Strategies**:
  - Support multiple certificate issuers (LetsEncrypt, internal CA, manual)
  - Implement certificate monitoring and early expiration alerts
  - Provide fallback to self-signed certificates with clear warnings
  - Create comprehensive certificate troubleshooting documentation
  - Implement automated certificate renewal testing

**4. GitOps Integration Complexity**
- **Risk**: Multi-repository authentication and configuration errors
- **Probability**: High (complex customer Git environments)
- **Impact**: High (broken GitOps workflows, fabric deployment failures)
- **Mitigation Strategies**:
  - Implement step-by-step Git repository setup wizard
  - Provide validation tools for Git connectivity and permissions
  - Support multiple authentication methods (SSH keys, tokens, app passwords)
  - Create comprehensive troubleshooting guides for Git issues
  - Implement connection testing and health monitoring

#### Medium-Priority Risks

**5. Storage and Data Persistence**
- **Risk**: Data loss due to storage configuration issues
- **Probability**: Medium (complex storage requirements)
- **Impact**: High (configuration loss, monitoring data loss)
- **Mitigation Strategies**:
  - Implement automated backup validation and testing
  - Provide multiple storage backend options
  - Create storage health monitoring and alerting
  - Implement data recovery procedures and testing
  - Offer storage migration tools for upgrades

**6. Security Policy Conflicts**
- **Risk**: Enterprise security policies conflicting with HEMK requirements
- **Probability**: Medium (varied enterprise environments)
- **Impact**: Medium (deployment failures, security compliance issues)
- **Mitigation Strategies**:
  - Provide security policy documentation and compliance guides
  - Support configurable security settings (PSPs, network policies)
  - Create enterprise integration guides for common security frameworks
  - Implement security scanning and vulnerability assessment
  - Offer "hardened" deployment profiles for high-security environments

**7. Upgrade and Migration Challenges**
- **Risk**: Failed upgrades causing system instability or downtime
- **Probability**: Medium (complex component interdependencies)
- **Impact**: High (service outages, data corruption)
- **Mitigation Strategies**:
  - Implement comprehensive pre-upgrade validation
  - Provide automated rollback capabilities
  - Create staging environment upgrade testing procedures
  - Implement blue-green deployment strategies where possible
  - Maintain detailed upgrade logs and troubleshooting guides

#### Low-Priority Risks

**8. Component Version Compatibility**
- **Risk**: Incompatible component versions causing integration failures
- **Probability**: Low (well-tested component matrix)
- **Impact**: Medium (feature degradation, integration issues)
- **Mitigation Strategies**:
  - Maintain tested component version compatibility matrix
  - Implement automated compatibility testing
  - Pin component versions in production deployments
  - Provide version upgrade guidance and compatibility notes
  - Create component isolation to minimize cross-dependencies

### Operational Risk Assessment

#### User Experience Risks

**1. Complexity Overwhelming Non-Kubernetes Users**
- **Risk**: Traditional network engineers unable to successfully deploy and operate HEMK
- **Probability**: High (target user profile limitation)
- **Impact**: High (project adoption failure)
- **Mitigation Strategies**:
  - Develop comprehensive step-by-step documentation with screenshots
  - Create interactive installation wizards with validation
  - Provide video tutorials and hands-on training materials
  - Implement guided troubleshooting with automated diagnostics
  - Offer professional services and support options

**2. Insufficient Documentation and Support**
- **Risk**: Users unable to resolve issues independently
- **Probability**: Medium (comprehensive documentation challenge)
- **Impact**: High (support burden, user frustration)
- **Mitigation Strategies**:
  - Create multi-format documentation (written, video, interactive)
  - Implement community support forums and knowledge base
  - Provide professional support tiers
  - Create comprehensive troubleshooting decision trees
  - Implement telemetry for common issue identification

#### Business and Strategic Risks

**3. HNP Integration Breaking Changes**
- **Risk**: HNP updates breaking HEMK integration compatibility
- **Probability**: Low (coordinated development)
- **Impact**: High (customer workflows disrupted)
- **Mitigation Strategies**:
  - Establish API versioning and compatibility commitments
  - Implement automated integration testing with HNP
  - Create integration deprecation and migration procedures
  - Maintain backward compatibility for critical APIs
  - Coordinate release schedules and testing

**4. Market and Technology Evolution**
- **Risk**: Kubernetes ecosystem changes obsoleting HEMK approaches
- **Probability**: Medium (rapidly evolving ecosystem)
- **Impact**: Medium (technical debt, modernization requirements)
- **Mitigation Strategies**:
  - Design modular architecture enabling component replacement
  - Monitor ecosystem trends and participate in community discussions
  - Implement gradual migration strategies for technology updates
  - Maintain vendor-neutral approaches where possible
  - Plan regular architecture reviews and updates

### Risk Monitoring and Early Warning Systems

#### Automated Risk Detection

**System Health Monitoring**:
```yaml
# risk-monitoring.yaml - Risk detection rules
risk_indicators:
  resource_exhaustion:
    - name: "Memory pressure approaching critical levels"
      query: "(1 - (node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes)) * 100 > 85"
      severity: "warning"
      action: "Scale resources or optimize workloads"
    
    - name: "Disk space approaching critical levels"
      query: "100 - ((node_filesystem_avail_bytes * 100) / node_filesystem_size_bytes) > 80"
      severity: "warning"
      action: "Clean up storage or expand capacity"
  
  connectivity_issues:
    - name: "External DNS resolution failures"
      query: "probe_success{job='dns-probe'} == 0"
      severity: "critical"
      action: "Check network connectivity and DNS configuration"
    
    - name: "Git repository connectivity failures"
      query: "argocd_git_request_duration_seconds{status_code!~'2.*'}"
      severity: "warning"
      action: "Verify Git repository access and credentials"
  
  security_compliance:
    - name: "Certificates expiring within warning period"
      query: "(cert_manager_certificate_expiration_timestamp_seconds - time()) / 86400 < 30"
      severity: "warning"
      action: "Verify certificate renewal automation"
    
    - name: "Security policy violations"
      query: "increase(kubernetes_audit_total{verb='create',objectRef_resource='pods',responseStatus_code!~'2.*'}[5m]) > 0"
      severity: "critical"
      action: "Review and remediate security policy violations"
```

**Proactive Issue Detection**:
```bash
#!/bin/bash
# risk-assessment.sh - Proactive risk assessment

echo "🔍 HEMK Risk Assessment"
echo "═════════════════════"

RISK_SCORE=0
TOTAL_CHECKS=0

assess_risk() {
    local risk_name="$1"
    local check_command="$2"
    local risk_weight="${3:-1}"
    
    echo -n "📊 $risk_name... "
    TOTAL_CHECKS=$((TOTAL_CHECKS + 1))
    
    if eval "$check_command" &>/dev/null; then
        echo "✅ LOW RISK"
    else
        echo "⚠️  ELEVATED RISK"
        RISK_SCORE=$((RISK_SCORE + risk_weight))
        
        # Provide risk mitigation guidance
        case "$risk_name" in
            "Resource availability")
                echo "   💡 Consider scaling resources or optimizing workloads"
                ;;
            "Network connectivity")
                echo "   💡 Check firewall rules and DNS configuration"
                ;;
            "Certificate health")
                echo "   💡 Verify certificate renewal automation"
                ;;
            "GitOps connectivity")
                echo "   💡 Check Git repository access and credentials"
                ;;
        esac
    fi
}

# Resource risk assessment
echo ""
echo "🏗️  Resource Risk Assessment"
echo "──────────────────────────"
assess_risk "CPU availability" "[ $(kubectl top nodes --no-headers | awk '{sum+=$3} END {print sum}' | sed 's/%//') -lt 80 ]" 3
assess_risk "Memory availability" "[ $(kubectl top nodes --no-headers | awk '{sum+=$5} END {print sum}' | sed 's/%//') -lt 85 ]" 3
assess_risk "Storage availability" "[ $(df / | awk 'NR==2{print $5}' | sed 's/%//') -lt 80 ]" 2

# Connectivity risk assessment
echo ""
echo "🌐 Connectivity Risk Assessment"
echo "─────────────────────────────"
assess_risk "Internet connectivity" "curl -s --connect-timeout 5 https://google.com" 2
assess_risk "DNS resolution" "nslookup kubernetes.default.svc.cluster.local" 2
assess_risk "Container registry access" "docker pull alpine:latest" 1

# Security risk assessment
echo ""
echo "🔒 Security Risk Assessment"
echo "─────────────────────────"
assess_risk "Certificate health" "kubectl get certificates --all-namespaces -o jsonpath='{.items[*].status.conditions[?(@.type==\"Ready\")].status}' | grep -q True" 3
assess_risk "Network policies active" "kubectl get networkpolicies --all-namespaces | grep -q ." 2
assess_risk "Pod security standards" "kubectl get ns hemk-system -o yaml | grep -q pod-security" 2

# Integration risk assessment
echo ""
echo "🔗 Integration Risk Assessment"
echo "────────────────────────────"
assess_risk "ArgoCD API health" "kubectl get pods -n argocd | grep argocd-server | grep -q Running" 3
assess_risk "Prometheus metrics" "kubectl get pods -n monitoring | grep prometheus | grep -q Running" 2
assess_risk "HNP service account" "kubectl get sa hnp-integration -n hemk-system" 2

# Calculate overall risk level
RISK_PERCENTAGE=$((RISK_SCORE * 100 / (TOTAL_CHECKS * 3)))

echo ""
echo "📈 Risk Assessment Summary"
echo "════════════════════════"
echo "🔢 Risk Score: $RISK_SCORE/$((TOTAL_CHECKS * 3))"
echo "📊 Risk Level: $RISK_PERCENTAGE%"

if [ $RISK_PERCENTAGE -le 20 ]; then
    echo "✅ Overall Risk: LOW"
    echo "   System is operating within acceptable risk parameters"
elif [ $RISK_PERCENTAGE -le 50 ]; then
    echo "⚠️  Overall Risk: MEDIUM"
    echo "   Some risks identified - monitor and address proactively"
else
    echo "🚨 Overall Risk: HIGH"
    echo "   Multiple risks detected - immediate attention required"
fi

echo ""
echo "📚 Risk Mitigation Resources:"
echo "• Documentation: https://docs.hemk.io/risk-management"
echo "• Support: https://support.hemk.io"
echo "• Emergency procedures: https://docs.hemk.io/emergency"
```

---

## Conclusion and Implementation Roadmap

### Executive Summary of Architecture

The HEMK (Hedgehog External Management Kubernetes) architecture provides a comprehensive, production-ready solution that addresses the critical infrastructure gap for Hedgehog ONF fabric customers. By focusing on traditional network engineers as the primary user base, this architecture prioritizes operational simplicity while maintaining enterprise-grade capabilities.

**Key Architectural Achievements**:

1. **Simplified Complexity**: Reduces Kubernetes operational complexity through opinionated defaults, automated deployment, and progressive disclosure of advanced features
2. **Seamless HNP Integration**: Provides native integration with Hedgehog NetBox Plugin GitOps workflows through well-defined APIs and configuration patterns
3. **Enterprise-Ready Security**: Implements comprehensive security frameworks including network policies, pod security standards, and automated certificate management
4. **Operational Excellence**: Includes robust monitoring, alerting, backup, and disaster recovery capabilities designed for production environments
5. **Modular Flexibility**: Enables customers to choose between full HEMK deployment or selective component installation based on their specific needs

### Implementation Roadmap

#### Phase 1: Foundation Development (Weeks 1-3)

**Sprint 1-2: Core Platform (k3s + Base Infrastructure)**
- [ ] k3s installation automation (single-node and multi-node)
- [ ] Helm chart repository setup and base platform charts
- [ ] Network policies and security framework implementation
- [ ] Basic ingress controller and certificate management
- [ ] Comprehensive testing framework establishment

**Sprint 3: Core HEMC Integration**
- [ ] ArgoCD deployment and configuration automation
- [ ] Prometheus/Grafana monitoring stack implementation
- [ ] Basic HNP integration API development
- [ ] Health check and diagnostic tooling
- [ ] Documentation framework creation

**Success Criteria**:
- ✅ <15 minute deployment time for single-node installation
- ✅ All core HEMCs operational with basic functionality
- ✅ HNP can successfully connect to deployed components
- ✅ Comprehensive health checks passing at 100%

#### Phase 2: Production Readiness (Weeks 4-6)

**Sprint 4: Advanced Features and Integration**
- [ ] Multi-repository Git authentication implementation
- [ ] Advanced monitoring dashboards and alerting rules
- [ ] Storage management (Longhorn) and backup integration
- [ ] Configuration wizard and guided setup implementation
- [ ] Advanced security hardening and compliance features

**Sprint 5: Operational Excellence**
- [ ] Automated backup and disaster recovery procedures
- [ ] Rolling upgrade and maintenance automation
- [ ] Comprehensive troubleshooting documentation
- [ ] Performance optimization and resource management
- [ ] Load testing and scalability validation

**Sprint 6: User Experience and Documentation**
- [ ] Interactive installation wizard completion
- [ ] Video tutorials and step-by-step guides
- [ ] Community support infrastructure
- [ ] Professional services integration
- [ ] Customer onboarding automation

**Success Criteria**:
- ✅ Zero-downtime upgrades for multi-node deployments
- ✅ Complete disaster recovery procedures tested and documented
- ✅ Non-Kubernetes experts can successfully deploy HEMK independently
- ✅ Integration with HNP workflows validated in customer environments

#### Phase 3: Ecosystem Integration and Advanced Features (Weeks 7-9)

**Sprint 7: Cloud and Enterprise Integration**
- [ ] AWS EKS, Azure AKS, GCP GKE integration patterns
- [ ] Enterprise identity provider integration (LDAP, SAML)
- [ ] Advanced compliance and audit capabilities
- [ ] Multi-cloud backup and disaster recovery
- [ ] Enterprise support system integration

**Sprint 8: Advanced Operational Features**
- [ ] Capacity planning and auto-scaling implementation
- [ ] Advanced security scanning and vulnerability management
- [ ] Performance analytics and optimization recommendations
- [ ] Advanced troubleshooting and diagnostic automation
- [ ] Customer environment assessment tooling

**Sprint 9: Ecosystem and Community**
- [ ] Community contribution guidelines and processes
- [ ] Third-party integration framework
- [ ] Marketplace and partner ecosystem development
- [ ] Advanced training and certification programs
- [ ] Customer success and feedback integration systems

**Success Criteria**:
- ✅ Support for all major cloud Kubernetes platforms
- ✅ Enterprise-grade security and compliance validation
- ✅ Active community adoption and contribution
- ✅ Positive customer satisfaction metrics and case studies

### Resource Requirements and Timeline

#### Development Team Structure

**Core Development Team (6-8 weeks)**:
- **Technical Lead**: Overall architecture oversight and technical decision making
- **Kubernetes Expert**: Core platform development and HEMC integration
- **DevOps Engineer**: Automation, CI/CD, and operational tooling
- **Security Specialist**: Security framework implementation and compliance
- **Documentation Engineer**: User guides, tutorials, and support materials
- **QA Engineer**: Testing automation and validation procedures

**Extended Team (Weeks 4-9)**:
- **UX Designer**: User experience optimization and interface design
- **Cloud Architect**: Multi-cloud integration and enterprise patterns
- **Support Engineer**: Customer onboarding and professional services
- **Community Manager**: Ecosystem development and user community

#### Technology Stack and Dependencies

**Core Technologies**:
- **Kubernetes**: k3s v1.28+ (lightweight, production-ready)
- **Package Management**: Helm 3.x (chart-based deployment)
- **GitOps**: ArgoCD v2.8+ (primary), Flux v2.x (alternative)
- **Monitoring**: Prometheus v2.45+, Grafana v10.x
- **Security**: cert-manager v1.13+, network policies, PSS
- **Storage**: Longhorn v1.5+ (distributed), local-path (single-node)
- **Backup**: Velero v1.12+ (cluster), cloud-native solutions

**Integration Dependencies**:
- **HNP Compatibility**: NetBox 3.5+, Django 4.x+
- **Git Providers**: GitHub, GitLab, Azure DevOps, Bitbucket
- **Cloud Platforms**: AWS EKS, Azure AKS, GCP GKE (basic integration)
- **Enterprise Systems**: LDAP, SAML, enterprise storage solutions

### Success Metrics and Validation Criteria

#### Technical Success Metrics

**Performance Targets**:
- **Installation Time**: <30 minutes for complete HEMK deployment
- **Resource Efficiency**: <4GB RAM baseline, <2 CPU cores for single-node
- **Availability**: 99.9% uptime for multi-node deployments
- **Recovery Time**: <2 hours for complete disaster recovery
- **Scalability**: Support 10+ concurrent GitOps workflows per cluster

**Quality Targets**:
- **Test Coverage**: >90% automated test coverage for core functionality
- **Security Compliance**: Pass all OWASP and Kubernetes security benchmarks
- **Documentation Quality**: <10% support ticket rate for documented procedures
- **Integration Stability**: Zero breaking changes to HNP integration APIs
- **Upgrade Success**: >95% success rate for automated upgrades

#### User Experience Success Metrics

**Adoption Metrics**:
- **Time to Value**: Non-expert users successful within 2 hours
- **Self-Service Rate**: >80% of installations completed without support
- **User Satisfaction**: >8.5/10 customer satisfaction score
- **Support Ticket Reduction**: 50% reduction in infrastructure-related tickets
- **Community Adoption**: Active community contributions and case studies

**Business Impact Metrics**:
- **HNP Adoption**: 25% increase in HNP evaluation-to-adoption rate
- **Customer Success**: Positive feedback from 90% of HEMK users
- **Ecosystem Growth**: Active partner integrations and marketplace adoption
- **Professional Services**: Viable professional services offering
- **ROI Validation**: Documented customer time and cost savings

### Long-Term Vision and Evolution

#### Architectural Evolution Path

**Year 1: Foundation and Adoption**
- Establish HEMK as the standard external infrastructure solution for Hedgehog
- Build active user community and ecosystem of integrations
- Achieve feature parity with manual deployment approaches
- Validate business model and customer success metrics

**Year 2: Enterprise and Scale**
- Advanced enterprise features and compliance frameworks
- Multi-cloud and hybrid deployment patterns
- Advanced automation and AI-driven operations
- International market expansion and localization

**Year 3: Innovation and Leadership**
- Industry leadership in network infrastructure automation
- Advanced analytics and predictive operations
- Integration with emerging technologies (edge computing, 5G)
- Ecosystem platform with third-party developer support

#### Technology Evolution Considerations

**Kubernetes Ecosystem Evolution**:
- Monitor and adapt to Kubernetes release cycles and deprecations
- Evaluate emerging CNCF projects for integration opportunities
- Plan migration strategies for evolving technology standards
- Maintain backward compatibility while adopting innovations

**Hedgehog Ecosystem Integration**:
- Deeper integration with Hedgehog ONF roadmap and features
- Support for emerging Hedgehog use cases and deployment patterns
- Integration with additional Hedgehog tools and components
- Contribution back to Hedgehog ONF community and standards

---

**Final Note**: This architecture specification provides the comprehensive foundation for implementing HEMK as a production-ready solution that transforms how traditional network engineers interact with Kubernetes infrastructure for Hedgehog operations. The emphasis on user experience, operational simplicity, and enterprise readiness positions HEMK to significantly accelerate Hedgehog adoption while maintaining the flexibility for advanced users to customize their deployments.

The implementation roadmap balances rapid time-to-market with long-term sustainability, ensuring that HEMK can evolve with both customer needs and technology advancement while maintaining its core mission of simplifying Kubernetes operations for traditional network engineers.