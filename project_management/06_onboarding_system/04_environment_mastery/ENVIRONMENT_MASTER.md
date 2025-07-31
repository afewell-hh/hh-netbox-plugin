# HNP Environment Master Reference

**CRITICAL**: This document eliminates environment discovery cycles. All agents must internalize this setup.

## Development Environment Stack

### NetBox Docker Setup
- **Location**: `/home/ubuntu/gitignore/netbox-docker/`
- **Access**: `${NETBOX_URL}` (${NETBOX_USERNAME}/${NETBOX_PASSWORD})
- **Plugin**: HNP integrated at startup
- **Database**: PostgreSQL shared with NetBox core
- **Status Check**: `docker ps | grep netbox`

### HCKC Kubernetes Cluster
- **Type**: K3s cluster
- **Endpoint**: `${K8S_API_SERVER}`
- **Config**: `~/.kube/config` (default kubeconfig)
- **Access Test**: `kubectl get nodes`
- **CRDs Location**: 12 types operational (VPC + Wiring APIs)

### ArgoCD GitOps Integration  
- **Config**: `/hemk/poc_development/kubeconfig/kubeconfig.yaml`
- **Repository**: `${GITOPS_REPOSITORY_URL}`
- **Sync Pattern**: CRD changes → Git commits → ArgoCD deployment
- **Access**: Standard kubectl with proper kubeconfig

### File System Navigation
```
${PROJECT_ROOT}/  (Project Root)
├── netbox_hedgehog/                     (Plugin Core)
│   ├── models/                          (12 CRD Django models)
│   ├── views/                           (UI views with Bootstrap 5)
│   ├── api/                             (REST endpoints)
│   └── sync/                            (KubernetesSync class)
├── project_management/                  (Coordination hub)
└── architecture_specifications/         (Technical docs)
```

### Development Tools
- **IDE Integration**: VSCode with Django/Python extensions
- **Testing**: Django test framework + pytest
- **Git Workflow**: Feature branches → testing → PR → merge
- **Debug Port**: NetBox Django on 8000, plugin debugging enabled

### Database Operations
- **PostgreSQL**: Shared with NetBox (docker-managed)
- **Migrations**: Standard Django migration process
- **Schema**: NetBox + HNP plugin tables
- **Backup**: Handled by NetBox Docker configuration

## Critical Environment Commands

```bash
# Environment Status Check
docker ps | grep netbox                    # NetBox running
kubectl get nodes                          # HCKC cluster accessible  
git status                                 # Repository clean
python manage.py check                     # Django health

# Quick Setup Validation
curl http://${NETBOX_URL}/admin          # NetBox access
kubectl get crds | grep hedgehog           # CRDs installed
ls ~/.kube/config                          # K8s config exists
```

## Failure Recovery
- **NetBox Docker**: `cd /home/ubuntu/gitignore/netbox-docker && docker-compose up -d`
- **Kubernetes**: Verify kubeconfig, restart K3s if needed
- **Plugin**: Django restart via docker-compose restart
- **Database**: Automatic recovery via Docker volumes

**SUCCESS METRIC**: Agent knows environment without discovery → immediate productive work.