# Kubernetes Integration Analysis

**Analysis Date**: July 31, 2025  
**Analyst**: Architecture Review Specialist  
**Focus**: K8s cluster integration patterns and synchronization mechanisms

## Integration Overview

HNP implements a hybrid GitOps + Direct API integration pattern with Kubernetes clusters, supporting both Git-to-NetBox synchronization and NetBox-to-Kubernetes resource management.

## Kubernetes Connection Architecture

### Fabric-Specific Configuration Model
Each `HedgehogFabric` maintains independent Kubernetes cluster configuration:

```python
# Required cluster connectivity fields
kubernetes_server: str         # "https://127.0.0.1:6443" (K3s cluster)
kubernetes_token: str          # Service account bearer token
kubernetes_ca_cert: str        # Cluster CA certificate
kubernetes_namespace: str      # Default namespace ("default")

# Connection health tracking
connection_status: str         # UNKNOWN/CONNECTED/FAILED  
connection_error: str          # Last connection error message
```

### Multi-Fabric Isolation Enforcement
The architecture enforces strict multi-fabric isolation:

```python
def _get_api_client(self):
    """Each fabric MUST have explicit K8s configuration"""
    fabric_config = self.fabric.get_kubernetes_config()
    
    if fabric_config:
        configuration = client.Configuration()
        configuration.host = fabric_config['host']
        configuration.api_key = {'authorization': token}
        configuration.api_key_prefix = {'authorization': 'Bearer'}
        # ... SSL/cert configuration
    else:
        # NO FALLBACK to default kubeconfig - strict isolation
        raise ValueError(
            f"Fabric '{self.fabric.name}' has no Kubernetes configuration. "
            f"Each fabric must have explicit kubernetes_server, kubernetes_token, "
            f"and kubernetes_ca_cert configured to maintain proper multi-fabric isolation."
        )
```

## Integration Patterns

### 1. GitOps-First Pattern (Git → NetBox)
**Primary synchronization method** - processes YAML files from Git repositories:

```python
# Synchronization workflow
def trigger_gitops_sync(self):
    """Sync CRs from Git repository directory into HNP database"""
    from ..utils.git_directory_sync import sync_fabric_from_git
    
    # Perform Git directory sync
    result = sync_fabric_from_git(self)
    
    # Updates:
    # - cached_crd_count with total synchronized records
    # - last_git_sync timestamp
    # - sync_status (synced/error)
```

#### Supported Resource Types (12 CRD Types)
```
VPC Resources:
├── VPC                    # Virtual Private Cloud definitions
├── External               # External connectivity
├── ExternalAttachment     # External attachment configurations  
├── ExternalPeering        # External peering relationships
├── IPv4Namespace          # IPv4 namespace management
├── VPCAttachment          # VPC attachment specifications
└── VPCPeering            # VPC peering configurations

Wiring Resources:
├── Connection            # Physical/logical connections (26 records current)
├── Server                # Server configurations
├── Switch                # Switch definitions (8 records current) 
├── SwitchGroup          # Switch group configurations
└── VLANNamespace        # VLAN namespace management
```

### 2. Direct API Pattern (NetBox → K8s)
**Bidirectional capability** - applies CRD changes directly to Kubernetes:

```python
def apply_crd(self, crd_instance) -> Dict[str, Any]:
    """Apply CRD to Kubernetes cluster using CustomObjectsApi"""
    
    # Generate Kubernetes manifest from CRD instance
    manifest = crd_instance.to_kubernetes_manifest()
    
    # Extract CRD API details
    group, version = manifest['apiVersion'].split('/')
    plural = self._get_plural_name(manifest['kind'])
    
    # Apply using Kubernetes API (create or patch)
    if resource_exists:
        result = custom_api.patch_namespaced_custom_object(...)
    else:
        result = custom_api.create_namespaced_custom_object(...)
    
    # Update NetBox record with K8s metadata
    crd_instance.kubernetes_uid = result['metadata']['uid']
    crd_instance.kubernetes_resource_version = result['metadata']['resourceVersion'] 
    crd_instance.kubernetes_status = KubernetesStatusChoices.APPLIED
```

## Status Field Architecture

### Fabric-Level Status Tracking
```python
# Connection health
connection_status: UNKNOWN → CONNECTED → FAILED
connection_error: str     # "Connection timed out" / "Invalid token"

# Synchronization state  
sync_status: NEVER_SYNCED → SYNCED → ERROR
sync_error: str           # "Git clone failed" / "YAML parse error"
last_sync: datetime       # 2025-07-29 08:57:53+00:00

# Drift detection status
drift_status: in_sync → drift_detected → critical  
drift_count: int          # 0-N resources with detected drift
last_git_sync: datetime   # Last successful Git sync
```

### Resource-Level Status Fields
```python
# Kubernetes integration status
kubernetes_status: UNKNOWN → APPLIED → ERROR → LIVE
kubernetes_uid: str                # "abc123-def456-789ghi"
kubernetes_resource_version: str   # "12345"
kubernetes_creation_timestamp: datetime

# Synchronization timestamps
last_applied: datetime             # Last K8s apply operation
last_synced: datetime             # Last Git sync update

# Error tracking
sync_error: str                   # "Resource validation failed"
```

## Authentication Integration

### Kubernetes Authentication Flow
```python
def get_kubernetes_config(self):
    """Generate K8s client configuration from fabric fields"""
    
    if self.kubernetes_server:
        # Docker network proxy detection for SSL verification
        is_docker_proxy = '://172.18.0.1:' in self.kubernetes_server
        
        config = {
            'host': self.kubernetes_server,
            'verify_ssl': bool(self.kubernetes_ca_cert) and not is_docker_proxy,
        }
        
        # Bearer token authentication
        if self.kubernetes_token:
            config['api_key'] = {'authorization': f'Bearer {self.kubernetes_token}'}
        
        # CA certificate for SSL verification
        if self.kubernetes_ca_cert and not is_docker_proxy:
            config['ssl_ca_cert'] = self.kubernetes_ca_cert
            
        return config
    
    return None  # No default kubeconfig fallback
```

### Git Authentication Integration
```python
# GitRepository provides encrypted credential storage
credentials = git_repo.get_credentials()
token = credentials.get('token') or credentials.get('access_token')

# Git clone with authentication
if token and 'github.com' in url:
    auth_url = f"https://{token}@{url_parts}"
    
cmd = ['git', 'clone', '--depth', '1', '--branch', branch, auth_url, str(path)]
```

## Performance and Caching Architecture

### CRD Count Caching System
```python
# Fabric-level cached counts (updated during sync)
cached_crd_count: int          # 36 (current operational total)
cached_vpc_count: int          # 2 (VPC resources)  
cached_connection_count: int   # 26 (Connection resources)

# Template-specific counts
connections_count: int         # Connection CRDs
servers_count: int            # Server CRDs  
switches_count: int           # Switch CRDs (8 current)
vpcs_count: int               # VPC CRDs
```

### Live Count Properties
```python
@property
def active_crd_count(self):
    """Return count of active/live CRDs in this fabric"""
    # Queries all CRD models with kubernetes_status=LIVE
    for model in [VPC, External, Connection, Server, Switch, ...]:
        total += model.objects.filter(
            fabric=self,
            kubernetes_status=KubernetesStatusChoices.LIVE
        ).count()
    return total

@property  
def error_crd_count(self):
    """Return count of CRDs with errors in this fabric"""
    # Queries all CRD models with kubernetes_status=ERROR
```

## Real-Time Monitoring Architecture 

### Watch Service Configuration
```python
# Watch service enablement
watch_enabled: bool               # Enable real-time K8s CRD watching
watch_crd_types: JSONField        # ['VPC', 'Connection', 'Switch'] or []
watch_status: str                 # inactive/starting/active/error/stopped

# Watch service metrics
watch_started_at: datetime        # When watch service started
watch_last_event: datetime       # Last received K8s event
watch_event_count: int           # Total events processed
watch_error_message: str         # Last watch error
```

### Watch Service Architecture
```python
def get_watch_configuration(self):
    """Get watch configuration for real-time monitoring"""
    
    enabled_crds = self.watch_crd_types if self.watch_crd_types else [
        'VPC', 'External', 'ExternalAttachment', 'ExternalPeering',
        'IPv4Namespace', 'VPCAttachment', 'VPCPeering', 
        'Connection', 'Server', 'Switch', 'SwitchGroup', 'VLANNamespace'
    ]
    
    return FabricConnectionInfo(
        fabric_id=self.pk,
        cluster_endpoint=self.kubernetes_server,
        token=self.kubernetes_token,
        ca_cert=self.kubernetes_ca_cert, 
        namespace=self.kubernetes_namespace,
        enabled_crds=enabled_crds
    )
```

## Operational Environment Status

### Current Environment Configuration
- **Cluster Type**: K3s at 127.0.0.1:6443
- **Network**: Docker bridge network with proxy detection
- **SSL Verification**: Disabled for Docker network (172.18.0.1:*)
- **Access Method**: GitOps repository-based (primary)
- **Direct API**: Available but not extensively used

### Current Operational Status
```
Fabric: HCKC (HedgehogFabric id=19)
├── Repository: github.com/afewell-hh/gitops-test-1
├── Directory: gitops/hedgehog/fabric-1/  
├── Files: prepop.yaml, test-vpc.yaml, test-vpc-2.yaml
├── Total CRDs: 36 records synchronized
├── Connection: CONNECTED (last validated: 2025-07-29 08:57:53+00:00)
└── Drift Status: Available (varies based on sync state)
```

## Integration Quality Assessment

### Strengths
1. **Multi-Fabric Isolation**: Strict enforcement prevents cross-fabric contamination
2. **Authentication Security**: Encrypted credential storage with no exposures
3. **Comprehensive Status Tracking**: Detailed status fields at fabric and resource levels
4. **Error Resilience**: Graceful handling of connection/authentication failures
5. **Performance Optimization**: Cached counts and efficient database queries

### Technical Debt Areas
1. **Direct API Usage**: Limited exploitation of Kubernetes API capabilities
2. **Watch Service**: Real-time monitoring framework present but not fully operational
3. **Drift Detection**: Basic implementation could be enhanced with semantic comparison
4. **Repository Migration**: Legacy git fields need migration to separated GitRepository model

### Architecture Evolution Path
The current architecture provides a solid foundation for:
- Enhanced direct Kubernetes API operations
- Real-time cluster state monitoring  
- Sophisticated drift detection and remediation
- Multi-cluster federation capabilities

## References

- **Fabric Model**: `/netbox_hedgehog/models/fabric.py` (lines 48-95, 487-509)
- **Kubernetes Client**: `/netbox_hedgehog/utils/kubernetes.py` (lines 21-200)
- **Sync Implementation**: `/netbox_hedgehog/utils/git_directory_sync.py` (lines 54-148)
- **Architecture Overview**: `/architecture_specifications/00_current_architecture/component_architecture/kubernetes_integration.md`