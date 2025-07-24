# Kubernetes CRD Management Mastery

## HCKC Cluster Architecture
- **Type**: K3s (lightweight Kubernetes)
- **Endpoint**: `127.0.0.1:6443`
- **Access**: Standard kubectl with `~/.kube/config`
- **CRD Count**: 12 HNP CRDs operational

## HNP CRD Structure
```yaml
# VPC API CRDs (6 types)
apiVersion: vpc.githedgehog.com/v1beta1
kind: [VPCPeering|VPCAttachment|IPv4Namespace|Connection|SwitchPort|Location]

# Wiring API CRDs (6 types)
apiVersion: wiring.githedgehog.com/v1beta1  
kind: [Switch|ServerFacingConnector|FabricLink|Fabric|ConnectionRequirement|PortGroup]
```

## CRD Lifecycle Management
1. **Creation**: `kubectl apply -f crd.yaml`
2. **Validation**: Built-in OpenAPI schema validation
3. **Status Updates**: Controller updates `.status` field
4. **Deletion**: Finalizers prevent orphaned resources
5. **Versioning**: v1beta1 with future v1 migration path

## Kubernetes Python Client Integration
```python
from kubernetes import client, config, watch
from kubernetes.client.rest import ApiException

# Configuration
config.load_kube_config()  # Uses ~/.kube/config
api = client.CustomObjectsApi()

# CRD Operations
api.create_namespaced_custom_object(
    group="vpc.githedgehog.com",
    version="v1beta1", 
    namespace="default",
    plural="vpcpeerings",
    body=crd_manifest
)
```

## Watch Patterns for Real-Time Sync
```python
# Real-time sync implementation
w = watch.Watch()
for event in w.stream(api.list_cluster_custom_object,
                     group="vpc.githedgehog.com",
                     version="v1beta1",
                     plural="vpcpeerings"):
    # Handle ADDED, MODIFIED, DELETED events
    sync_to_netbox(event['type'], event['object'])
```

## CRD State Management (Six States)
1. **Pending**: Awaiting controller processing
2. **Active**: Successfully applied to cluster
3. **Updating**: Modification in progress
4. **Failed**: Controller error state
5. **Deleting**: Removal in progress  
6. **Conflict**: Manual resolution required

## GitOps Integration
- **Repository**: `https://github.com/afewell-hh/gitops-test-1.git`
- **Pattern**: NetBox changes → Git commit → ArgoCD sync → Cluster apply
- **Config**: ArgoCD watches git repo for CRD manifests
- **Validation**: ArgoCD pre-sync hooks for schema validation

## Common Operations
```bash
# List HNP CRDs
kubectl get crds | grep hedgehog

# View CRD instances
kubectl get vpcpeerings -A
kubectl get switches -A

# Debug CRD status
kubectl describe vpcpeering <name>
kubectl get events --field-selector involvedObject.kind=VPCPeering

# Schema validation
kubectl explain vpcpeering.spec
```

## Controller Integration Points
- **Admission Controllers**: Validate CRD creation/updates
- **Custom Controllers**: Business logic for CRD lifecycle
- **Webhooks**: Mutation and validation hooks
- **Status Updates**: Controller populates `.status` fields

## Development Workflow
1. **CRD Schema**: Define OpenAPI schema in YAML
2. **Controller Logic**: Implement business logic in Go/Python
3. **Testing**: Unit tests + integration tests with test cluster
4. **Deployment**: Apply CRDs → Deploy controller → Validate

## Error Patterns & Recovery
- **Schema Violations**: Fix manifest, re-apply
- **Controller Failures**: Check controller logs, restart if needed
- **Resource Conflicts**: Manual resolution of conflicting changes
- **Network Issues**: Retry with exponential backoff

**MASTERY GOAL**: Fluent CRD operations, real-time sync patterns, and GitOps integration for production Kubernetes environments.