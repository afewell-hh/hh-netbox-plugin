# HNP System Overview

**Last Updated**: July 29, 2025  
**Status**: MVP Complete - 12 CRD types operational (49 CRDs synced)  
**Branch**: feature/css-consolidation-readability

## Executive Summary

The Hedgehog NetBox Plugin (HNP) has achieved MVP completion with operational GitOps fabric synchronization, comprehensive testing framework, and resolved authentication issues. The system provides self-service Kubernetes CRD management via NetBox interface with 36 CRD records synchronized from GitOps repository.

## Mission and Status
- **Mission**: Self-service Kubernetes CRD management via NetBox interface  
- **Status**: MVP Complete - 12 CRD types operational
- **Database**: 36 CRD records synchronized from GitOps repository
- **Architecture**: NetBox 4.3.3 plugin with Kubernetes integration

## Technical Stack
- **Backend**: Django 4.2, NetBox 4.3.3 plugin architecture
- **Frontend**: Bootstrap 5 with progressive disclosure UI
- **Integration**: Kubernetes Python client, ArgoCD GitOps
- **Database**: PostgreSQL (shared with NetBox core)
- **Container**: Docker-based deployment with NetBox integration

## Environment Configuration
- **NetBox Docker**: localhost:8000 with plugin integrated
- **HCKC Cluster**: K3s at 127.0.0.1:6443
- **GitOps Repository**: github.com/afewell-hh/gitops-test-1.git
- **GitOps Directory**: `gitops/hedgehog/fabric-1/`

## Current Operational Status

### Data Layer
**Primary Fabric Management**:
- HedgehogFabric(id=19, name="HCKC")
- git_repository: ForeignKey -> GitRepository(id=6)
- gitops_directory: "gitops/hedgehog/fabric-1/"
- cached_crd_count: 36
- drift_status: Available (varies based on sync state)

**Git Repository Management**:
- GitRepository(id=6, name="GitOps Test Repository 1")
- url: "https://github.com/afewell-hh/gitops-test-1"
- connection_status: "connected"
- last_validated: 2025-07-29 08:57:53+00:00
- encrypted_credentials: Configured and working

**CRD Synchronization Results**:
- VPCs: 2 records synchronized
- Connections: 26 records synchronized  
- Switches: 8 records synchronized
- Total CRDs: 36 records operational

### System Health
- Core functionality: 100% operational
- Authentication: Fully secured with LoginRequiredMixin
- UI/UX: Professional and responsive
- Data integrity: Validated and consistent
- Testing coverage: Comprehensive (10/10 tests passing)

## Data Flow Architecture

### Synchronization Data Flow
```
1. User Triggers Sync → 
2. HedgehogFabric.trigger_gitops_sync() →
3. GitRepository.clone_repository() (with encrypted auth) →
4. Access gitops_directory path →
5. Parse YAML files (prepop.yaml, test-vpc.yaml, test-vpc-2.yaml) →
6. Create/Update CRD records in database →
7. Update fabric.cached_crd_count = 36 →
8. Return sync results to user
```

### Authentication Data Flow
```
1. User Access Request →
2. LoginRequiredMixin Check →
3. If Authenticated: Allow Access →
4. If Not: HTTP 302 → /login/?next=<requested_url>
5. Git Operations: Use encrypted_credentials from GitRepository
```

## Architecture Strengths
- **GitOps Integration**: Successfully processes YAML files from git repositories
- **Security**: Comprehensive authentication with encrypted credential storage
- **User Experience**: Progressive disclosure UI with drift detection
- **Quality Assurance**: Evidence-based validation with comprehensive test suite
- **Container Architecture**: Reliable Docker-based deployment

## Known Technical Debt
1. **Repository-Fabric Coupling**: Requires separation for multi-fabric support
2. **Centralized Git Management**: Dedicated repository management interface needed
3. **Enhanced Drift Detection**: More sophisticated drift analysis capabilities
4. **API Expansion**: Additional endpoints for comprehensive git repository management

## References
- [Kubernetes Integration Details](component_architecture/kubernetes_integration.md)
- [NetBox Plugin Architecture](component_architecture/netbox_plugin_layer.md)
- [GitOps Architecture Overview](component_architecture/gitops/gitops_overview.md)
- [Architectural Decisions](../01_architectural_decisions/decision_log.md)