# Kubernetes Cluster Information

## HCKC (Hedgehog Kubernetes Cluster)

**Type**: K3s Local Cluster  
**API Server**: 127.0.0.1:6443  
**Kubeconfig**: ~/.kube/config  
**Context**: default

### Cluster Access
```bash
# Verify connectivity
kubectl cluster-info

# Check CRDs
kubectl get crds | grep fabric8s.com
```

### Hedgehog CRDs Present
- connections.vpc.fabric8s.com
- externals.vpc.fabric8s.com
- racks.wiring.fabric8s.com
- servers.wiring.fabric8s.com
- switches.wiring.fabric8s.com
- switchgroups.wiring.fabric8s.com
- vpcs.vpc.fabric8s.com
- vpcattachments.wiring.fabric8s.com
- vpcvrfs.wiring.fabric8s.com
- vrfvlanattachments.wiring.fabric8s.com
- vlannamespaces.vpc.fabric8s.com
- ipv4namespaces.vpc.fabric8s.com

### Test Fabric Resources
Located in namespace: default
- 49 total CRD instances deployed
- 26 Connections
- 10 Servers  
- 7 Switches
- 3 SwitchGroups
- 1 each: VPC, VLANNamespace, IPv4Namespace

## ArgoCD Integration

**Status**: Planned for GitOps workflows  
**Repository**: https://github.com/afewell-hh/gitops-test-1.git

### Future Integration Points
- Fabric configuration deployment
- CRD synchronization
- GitOps workflow management

## Python Kubernetes Client

### Configuration in Code
```python
from kubernetes import client, config

# Load from default kubeconfig
config.load_kube_config()

# Create API client
v1 = client.CoreV1Api()
custom_api = client.CustomObjectsApi()
```

### CRD Access Pattern
```python
# List CRDs of specific type
custom_api.list_cluster_custom_object(
    group="vpc.fabric8s.com",
    version="v1alpha1", 
    plural="connections"
)
```

## Important Notes

1. **Local Development Only**: Current K3s cluster is for development
2. **No Authentication**: Using default kubeconfig without additional auth
3. **Single Namespace**: All test resources in 'default' namespace
4. **Direct API Access**: Plugin uses Python client, not kubectl