# HEMK Architecture Requirements & Technical Specifications

**Document Type**: Technical Architecture Specification  
**Target Audience**: Technical implementers, system architects, DevOps engineers  
**Related Documents**: PROJECT_BRIEF.md, RESEARCH_OBJECTIVES.md

---

## Technical Architecture Overview

### System Context Diagram

```
┌─────────────────────┐    ┌─────────────────────┐    ┌─────────────────────┐
│ Hedgehog Controller │    │      Git Repos      │    │   Customer K8s      │
│   (HCKC - k3s)     │    │  (Multiple repos,   │    │   (Existing infra)  │
│                     │    │   any-to-any with   │    │                     │
│ - Hedgehog CRDs     │    │   GitOps dirs)      │    │ - Customer choice   │
│ - Fabric Control    │    │                     │    │ - Own HEMCs         │
└─────────────────────┘    └─────────────────────┘    └─────────────────────┘
           │                           │                           │
           │                           │                           │
           └───────────────┬───────────┴───────────────┬───────────┘
                           │                           │
                ┌─────────────────────┐    ┌─────────────────────┐
                │   HNP (NetBox)      │    │   HEMK (k3s)        │
                │                     │    │                     │
                │ - GitOps workflows  │    │ - ArgoCD/Flux       │
                │ - Multi-repo auth   │    │ - Prometheus/Graf   │
                │ - Fabric management │    │ - LetsEncrypt       │
                │ - HEMC integration  │    │ - Ingress           │
                └─────────────────────┘    └─────────────────────┘
```

### Core Architectural Principles

1. **Loose Coupling**: HNP depends only on HEMC availability, not deployment location
2. **Modular Design**: Each HEMC can be independently installed and configured
3. **Configuration Flexibility**: Support multiple deployment patterns while remaining opinionated
4. **Security by Default**: Enterprise-grade security configurations out of the box
5. **Operational Simplicity**: Optimize for non-Kubernetes expert operational experience

---

## Component Architecture

### HEMK Core Platform

**Base Infrastructure**:
- **Kubernetes Distribution**: k3s (lightweight, production-ready)
- **Node Configuration**: Single-node or simple multi-node cluster
- **Storage**: Local storage with optional distributed storage for multi-node
- **Networking**: Default CNI with ingress controller for external access
- **Security**: Pod Security Standards, Network Policies, RBAC

**Management Layer**:
- **Package Manager**: Helm 3 for HEMC installation
- **Configuration Management**: Environment-specific ConfigMaps and Secrets
- **Backup/Recovery**: Automated backup of cluster state and persistent data
- **Monitoring**: Basic cluster health monitoring (separate from Hedgehog monitoring)
- **Logging**: Centralized logging for troubleshooting

### HEMC Integration Framework

**Primary HEMCs**:
1. **GitOps Tools**
   - ArgoCD (web UI, CLI, API)
   - Flux (optional alternative)
   - Git provider authentication
   - Repository access management

2. **Hedgehog Monitoring Stack**
   - Prometheus server
   - Grafana dashboards
   - Hedgehog-specific metrics collection
   - Alert management integration

**Supporting Tools**:
1. **Certificate Management**
   - cert-manager for automated TLS certificates
   - LetsEncrypt integration for public certificates
   - Internal CA for private certificates

2. **Ingress and Networking**
   - Ingress controller (nginx or traefik)
   - External DNS integration (optional)
   - Load balancer configuration

3. **Security Tools**
   - Network policies for micro-segmentation
   - Pod security policies/standards
   - Secret management integration

4. **Operational Tools**
   - Backup solutions (Velero or k3s backup)
   - Log aggregation (lightweight solution)
   - Basic alerting for cluster health

---

## Integration Specifications

### HNP to HEMK Communication

**API Integration Points**:
- **ArgoCD API**: Application deployment and status monitoring
- **Prometheus API**: Metrics queries for Hedgehog fabric health
- **Grafana API**: Dashboard integration and alerting

**Authentication & Authorization**:
- Service account-based authentication
- Token-based API access with rotation
- RBAC configurations for least-privilege access
- Secure credential storage in HNP

**Network Connectivity**:
- HTTPS-only communication
- Network policy enforcement
- Optional VPN/private network connectivity
- Firewall rule documentation

### Git Repository Integration

**Multi-Repository Authentication**:
```python
# Conceptual API for git repository management
class GitRepositoryManager:
    def authenticate_repository(self, repo_url: str, credentials: dict) -> bool
    def list_authenticated_repositories(self) -> List[str]
    def validate_repository_access(self, repo_url: str) -> dict
    def revoke_repository_access(self, repo_url: str) -> bool

class FabricGitOpsMapping:
    def set_fabric_gitops_directory(self, fabric_id: str, repo_url: str, directory: str) -> bool
    def get_fabric_gitops_directory(self, fabric_id: str) -> tuple[str, str]
    def validate_gitops_directory(self, repo_url: str, directory: str) -> dict
```

**GitOps Directory Management**:
- Fabric-to-directory mapping storage
- Directory structure validation
- YAML file discovery and parsing
- Change detection and synchronization

---

## Deployment Architecture

### Target Deployment Patterns

**Pattern 1: Single-Node VM (Primary)**
- **Target**: Small environments, evaluation, development
- **Infrastructure**: Single VM (4 cores, 8GB RAM, 100GB storage minimum)
- **Deployment**: Automated k3s installation with HEMC Helm charts
- **Networking**: Host networking with port forwarding for external access
- **Storage**: Local storage with backup to external location

**Pattern 2: Multi-Node Simple Cluster**
- **Target**: Production environments, high availability requirements
- **Infrastructure**: 3-node cluster (load balancer, shared storage)
- **Deployment**: k3s cluster installation with distributed HEMC deployment
- **Networking**: Cluster networking with ingress controller
- **Storage**: Distributed storage (Longhorn) with automated backup

**Pattern 3: Cloud Kubernetes (Limited Support)**
- **Target**: Customers with existing cloud K8s services
- **Infrastructure**: AWS EKS, Azure AKS, GCP GKE (basic configurations)
- **Deployment**: HEMC Helm charts only (customer manages cluster)
- **Networking**: Cloud provider ingress solutions
- **Storage**: Cloud provider storage classes

### Infrastructure Prerequisites

**Minimum System Requirements**:
- **CPU**: 4 cores per node
- **Memory**: 8GB RAM per node
- **Storage**: 100GB available space per node
- **Network**: Internet connectivity for package downloads
- **OS**: Ubuntu 20.04+ or equivalent systemd-based Linux

**Network Requirements**:
- **Inbound**: Ports 80, 443 for web UIs
- **Outbound**: Ports 443 (HTTPS), 22 (Git SSH), 6443 (K8s API)
- **Internal**: Cluster networking ports (varies by CNI)
- **DNS**: Resolvable hostnames for external access

**Security Requirements**:
- **TLS**: All external communication encrypted
- **Authentication**: Multi-factor authentication for admin access
- **Authorization**: Role-based access control (RBAC)
- **Secrets**: Encrypted secret storage with rotation
- **Networking**: Network policies for traffic isolation

---

## Configuration Management

### Environment Configuration

**Environment Types**:
1. **Development**: Minimal security, easy access, verbose logging
2. **Staging**: Production-like security, moderate access, standard logging
3. **Production**: Maximum security, restricted access, minimal logging

**Configuration Sources**:
- **Base Configuration**: Default values in Helm charts
- **Environment Overrides**: Environment-specific value files
- **Customer Customization**: Customer-provided configuration files
- **Runtime Configuration**: ConfigMaps and Secrets in cluster

### HEMC Selection Framework

**Installation Profiles**:
1. **Full HEMK**: All HEMCs installed on dedicated cluster
2. **GitOps Only**: Only GitOps tools, customer provides monitoring
3. **Monitoring Only**: Only Hedgehog monitoring, customer provides GitOps
4. **Custom**: Customer selects specific HEMCs to install

**Selection Mechanism**:
```yaml
# hemk-config.yaml example
profile: "full-hemk"
components:
  gitops:
    enabled: true
    tool: "argocd"  # or "flux"
    web_ui: true
    ssl_certificates: "letsencrypt"
  monitoring:
    enabled: true
    prometheus: true
    grafana: true
    alerting: true
  operational:
    ingress_controller: "nginx"
    certificate_manager: true
    backup_solution: "velero"
    log_aggregation: false
```

---

## Security Architecture

### Security Model

**Defense in Depth**:
1. **Infrastructure Security**: Host hardening, firewall configuration
2. **Cluster Security**: RBAC, Pod Security Standards, Network Policies
3. **Application Security**: TLS encryption, authentication, authorization
4. **Data Security**: Encryption at rest, secure secret management
5. **Network Security**: Traffic encryption, network isolation

**Authentication & Authorization**:
- **Admin Access**: OIDC integration with enterprise identity providers
- **Service Access**: Service account tokens with limited scope
- **API Access**: Token-based authentication with expiration
- **Inter-Service**: Mutual TLS for service-to-service communication

**Secret Management**:
- **Kubernetes Secrets**: Encrypted at rest using cluster encryption
- **External Secrets**: Integration with HashiCorp Vault or cloud secret managers
- **Certificate Management**: Automated certificate lifecycle management
- **Credential Rotation**: Automated rotation of service credentials

---

## Operational Requirements

### Monitoring & Observability

**Cluster Health Monitoring**:
- Node resource utilization
- Pod health and restart rates
- Network connectivity status
- Storage capacity and performance
- Certificate expiration tracking

**HEMC-Specific Monitoring**:
- ArgoCD sync status and application health
- Prometheus metrics collection and retention
- Grafana dashboard availability
- Backup completion status
- Security scanning results

### Backup & Recovery

**Backup Strategy**:
- **Cluster State**: etcd snapshots with automated scheduling
- **Persistent Data**: Application data backup to external storage
- **Configuration**: Git-based configuration management
- **Disaster Recovery**: Documented recovery procedures

**Recovery Requirements**:
- **RTO (Recovery Time Objective)**: 2 hours for full cluster recovery
- **RPO (Recovery Point Objective)**: 24 hours maximum data loss
- **Testing**: Monthly recovery testing procedures
- **Documentation**: Step-by-step recovery playbooks

### Maintenance & Updates

**Update Strategy**:
- **Rolling Updates**: Zero-downtime updates for multi-node clusters
- **Staged Rollouts**: Development → Staging → Production update progression
- **Rollback Capability**: Automated rollback on failure detection
- **Maintenance Windows**: Scheduled maintenance for breaking changes

**Lifecycle Management**:
- **Version Tracking**: Component version management and compatibility matrix
- **Security Updates**: Automated security patch application
- **Feature Updates**: Planned feature rollout with testing
- **End-of-Life**: Component sunset and migration planning

---

## Development Framework

### Helm Chart Architecture

**Chart Structure**:
```
hemk-charts/
├── charts/
│   ├── argocd/           # ArgoCD deployment chart
│   ├── prometheus-stack/ # Monitoring stack chart
│   ├── cert-manager/     # Certificate management chart
│   ├── ingress-nginx/    # Ingress controller chart
│   └── hemk-base/        # Base cluster configuration
├── values/
│   ├── development.yaml  # Development environment values
│   ├── staging.yaml      # Staging environment values
│   └── production.yaml   # Production environment values
└── templates/
    ├── bootstrap.yaml    # Bootstrap job template
    ├── monitoring.yaml   # Monitoring configuration
    └── networking.yaml   # Network policy templates
```

**Chart Dependencies**:
- External chart dependencies managed through Helm dependencies
- Version pinning for stability and security
- Custom charts for Hedgehog-specific configurations
- Environment-specific value overrides

### Testing Framework

**Testing Levels**:
1. **Unit Tests**: Helm chart template validation
2. **Integration Tests**: Multi-component deployment testing
3. **End-to-End Tests**: Full HEMK to HNP integration testing
4. **Performance Tests**: Load testing for HEMC components
5. **Security Tests**: Vulnerability scanning and penetration testing

**Validation Criteria**:
- All HEMCs deploy successfully
- External connectivity from HNP established
- GitOps workflows function correctly
- Monitoring data collection operational
- Security policies enforced

---

**Next Steps**: This architecture specification provides the foundation for detailed implementation planning. The research phase should validate and refine these requirements based on actual HEMC discovery and customer environment analysis.