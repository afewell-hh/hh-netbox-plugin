# HNP Project Understanding - Onboarding Study Summary

## HNP System Architecture Overview

### Core Technology Stack
- **NetBox Plugin**: Django 4.2 plugin on NetBox 4.3.3 platform
- **Database**: PostgreSQL shared with NetBox core
- **UI**: Bootstrap 5 with NetBox theme integration
- **Kubernetes**: K3s cluster (HCKC) with 12 operational CRDs
- **GitOps**: ArgoCD integration with Git repository synchronization

### Environment Configuration
- **NetBox**: http://localhost:8000/ (accessible via .env credentials)
- **K8s API**: 172.18.0.8:6443 with service account token
- **Test GitOps Repo**: https://github.com/afewell-hh/gitops-test-1.git
- **Test Fabric Directory**: gitops/hedgehog/fabric-1
- **ArgoCD**: https://localhost:30444

### HNP CRD Architecture (12 Types)
**VPC API (6 types)**:
- VPCPeering, VPCAttachment, IPv4Namespace, Connection, SwitchPort, Location

**Wiring API (6 types)**:
- Switch, ServerFacingConnector, FabricLink, Fabric, ConnectionRequirement, PortGroup

### Key Integration Patterns
1. **Django Models ↔ Kubernetes CRDs**: Bidirectional synchronization
2. **NetBox UI ↔ CRD Management**: Progressive disclosure UI patterns
3. **Git ↔ ArgoCD ↔ K8s**: GitOps workflow for CRD deployment
4. **Real-time Sync**: Watch patterns for live cluster synchronization

### Critical File Locations
```
/home/ubuntu/cc/hedgehog-netbox-plugin/
├── netbox_hedgehog/          # Plugin core implementation
│   ├── models.py             # CRD Django models
│   ├── views/                # UI controllers
│   ├── api/                  # REST endpoints
│   └── sync/                 # K8s synchronization logic
├── architecture_specifications/  # Technical design documentation
├── project_management/           # Project coordination
└── .env                         # Environment configuration
```

## GitOps Directory Issue Context

### Problem Components Identified
1. **Fabric GitOps Directory Initialization**: When fabric added, should ingest pre-existing YAML files
2. **File Ingestion Process**: Should recreate valid CRs in opinionated directory structure
3. **Raw Directory Monitoring**: Should ingest files placed in raw/ subdirectory
4. **Directory Structure Validation**: Should validate/repair structure before each sync
5. **Invalid File Management**: Should move invalid files to unmanaged/ directory

### Current State
- ✅ Directory structure creation working
- ❌ File ingestion not working (files remain in root)
- ❓ Raw directory ingestion status unknown
- ❓ Directory validation/repair status unknown
- ❓ Invalid file management status unknown

### Test Environment Evidence
- Test fabric configured in HNP with prestaged YAML files
- Files remain in gitops directory root unchanged after fabric creation
- Directory structure created correctly but ingestion failed

## Next Steps for Investigation
1. Research architecture specifications for GitOps directory feature design
2. Analyze current implementation in codebase
3. Identify specific failure points in ingestion process
4. Design systematic approach to fix all components