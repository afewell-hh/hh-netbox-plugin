# HNP Kubernetes Synchronization Architecture Analysis

**Analysis Date**: July 31, 2025  
**Analyst**: Architecture Review Specialist  
**Scope**: Complete K8s integration architecture review for sync validation

## Executive Summary

The Hedgehog NetBox Plugin (HNP) implements a sophisticated GitOps-first Kubernetes synchronization architecture with bidirectional sync capabilities between Git repositories, NetBox database, and Kubernetes clusters. The system supports multi-fabric operations with encrypted credential management and comprehensive drift detection.

## Core Architecture Components

### 1. Fabric Model - Central Integration Hub

The `HedgehogFabric` model serves as the central coordination point for all K8s integrations:

#### Kubernetes Connection Fields
```python
# Direct K8s cluster connection
kubernetes_server = models.URLField()          # K8s API server URL
kubernetes_token = models.TextField()          # Service account token  
kubernetes_ca_cert = models.TextField()        # CA certificate
kubernetes_namespace = models.CharField()      # Default namespace

# Connection status tracking
connection_status = models.CharField()         # UNKNOWN/CONNECTED/FAILED
sync_status = models.CharField()              # NEVER_SYNCED/SYNCED/ERROR
sync_error = models.TextField()               # Last sync error
last_sync = models.DateTimeField()            # Last successful sync
```

#### GitOps Integration Fields
```python
# New architecture (separated concerns)
git_repository = models.ForeignKey('GitRepository')  # Encrypted auth repo
gitops_directory = models.CharField()                # Directory path

# Legacy fields (deprecated but maintained for migration)
git_repository_url = models.URLField()        # Direct git URL
git_branch = models.CharField()               # Git branch
git_path = models.CharField()                 # Git directory path
git_username/git_token = models.CharField()   # Legacy auth (deprecated)
```

#### Drift Detection and Status Fields
```python
# Drift detection state
drift_status = models.CharField()             # in_sync/drift_detected/conflicts
drift_count = models.PositiveIntegerField()   # Number of resources with drift
last_git_sync = models.DateTimeField()       # Last Git sync timestamp

# Cached CRD counts for performance
cached_crd_count = models.PositiveIntegerField()    # Total CRDs
cached_vpc_count = models.PositiveIntegerField()    # VPC count
cached_connection_count = models.PositiveIntegerField() # Connection count
connections_count/servers_count/switches_count/vpcs_count  # Specific counts
```

### 2. GitRepository Model - Authentication Separation

The `GitRepository` model implements separated authentication concerns:

#### Core Authentication Architecture
```python
# Repository identification
name = models.CharField()                     # User-friendly name
url = models.URLField()                      # Git repository URL
provider = models.CharField()                # GitHub/GitLab/Generic

# Authentication management
authentication_type = models.CharField()     # TOKEN/SSH_KEY/BASIC/OAUTH
encrypted_credentials = models.TextField()   # Encrypted JSON credentials
connection_status = models.CharField()       # PENDING/CONNECTED/FAILED
last_validated = models.DateTimeField()     # Last connection test
validation_error = models.TextField()        # Connection error details
```

#### Credential Encryption Implementation
```python
def set_credentials(self, credentials_dict: Dict[str, Any]):
    """Encrypt credentials using Django SECRET_KEY derived key"""
    credentials_json = json.dumps(credentials_dict)
    fernet = Fernet(self._encryption_key)
    encrypted_data = fernet.encrypt(credentials_json.encode('utf-8'))
    self.encrypted_credentials = base64.b64encode(encrypted_data)

def get_credentials(self) -> Dict[str, Any]:
    """Decrypt and return credentials for use in Git operations"""
    encrypted_data = base64.b64decode(self.encrypted_credentials)
    fernet = Fernet(self._encryption_key)
    return json.loads(fernet.decrypt(encrypted_data).decode('utf-8'))
```

### 3. Synchronization Architecture

#### GitOps Synchronization Flow (Git → NetBox)
```
1. User Trigger (fabric detail page) →
2. fabric.trigger_gitops_sync() →
3. GitDirectorySync.sync_from_git() →
4. git_repo.clone_repository(temp_dir) →
5. Scan gitops_directory for *.yaml files →
6. Parse YAML documents (yaml.safe_load_all) →
7. Process each CR document →
8. Create/update CRD model instances →
9. Update fabric.cached_crd_count →
10. Return sync results to UI
```

#### Kubernetes Synchronization Flow (NetBox → K8s)
```
1. CRD model changes trigger sync →
2. KubernetesClient(fabric) initialization →
3. fabric.get_kubernetes_config() provides auth →
4. crd_instance.to_kubernetes_manifest() →
5. CustomObjectsApi operations:
   - get_namespaced_custom_object() (check existing)
   - patch_namespaced_custom_object() (update)
   - create_namespaced_custom_object() (create)
6. Update kubernetes_status/kubernetes_uid fields
```

#### Drift Detection Architecture
```
1. fabric.calculate_drift_status() →
2. HedgehogResource.objects.filter(fabric=self) →
3. For each resource: resource.calculate_drift() →
4. DriftDetector.detect_drift(desired, actual) →
5. Update resource.drift_status/drift_score →
6. Aggregate fabric.drift_count/drift_status
```

## Data Model Integration

### CRD Type Support (12 Types Operational)
```python
KIND_TO_MODEL = {
    'VPC': 'vpc_api.VPC',
    'External': 'vpc_api.External', 
    'ExternalAttachment': 'vpc_api.ExternalAttachment',
    'ExternalPeering': 'vpc_api.ExternalPeering',
    'IPv4Namespace': 'vpc_api.IPv4Namespace',
    'VPCAttachment': 'vpc_api.VPCAttachment',
    'VPCPeering': 'vpc_api.VPCPeering',
    'Connection': 'wiring_api.Connection',
    'Server': 'wiring_api.Server',
    'Switch': 'wiring_api.Switch',
    'SwitchGroup': 'wiring_api.SwitchGroup',
    'VLANNamespace': 'wiring_api.VLANNamespace'
}
```

### Current Operational Status
- **Total CRDs**: 36 records synchronized
- **VPCs**: 2 records  
- **Connections**: 26 records
- **Switches**: 8 records
- **Repository**: github.com/afewell-hh/gitops-test-1
- **Directory**: gitops/hedgehog/fabric-1/
- **Files Processed**: prepop.yaml, test-vpc.yaml, test-vpc-2.yaml

## Authentication and Security Architecture

### Multi-Layer Security Implementation
1. **Credential Encryption**: Fernet encryption using Django SECRET_KEY
2. **Authentication Separation**: GitRepository handles auth independently 
3. **Connection Validation**: Real-time connectivity testing
4. **Error Isolation**: No credential exposure in logs/errors
5. **Multi-Fabric Isolation**: Each fabric maintains separate K8s config

### Authentication Flow
```python
# GitRepository credential retrieval
credentials = git_repo.get_credentials()
token = credentials.get('token')

# Git operations with authentication  
clone_url = f"https://{token}@{parsed_url.netloc}{parsed_url.path}"
repo = git.Repo.clone_from(clone_url, target_directory)

# Kubernetes authentication
config = {
    'host': fabric.kubernetes_server,
    'api_key': {'authorization': f'Bearer {fabric.kubernetes_token}'},
    'ssl_ca_cert': fabric.kubernetes_ca_cert,
    'verify_ssl': bool(fabric.kubernetes_ca_cert)
}
```

## Performance and Monitoring Architecture

### Status Tracking Fields
```python
# Fabric-level status
connection_status: UNKNOWN/CONNECTED/FAILED
sync_status: NEVER_SYNCED/SYNCED/ERROR  
drift_status: in_sync/drift_detected/critical
watch_status: inactive/starting/active/error

# Resource-level status  
kubernetes_status: UNKNOWN/APPLIED/ERROR/LIVE
kubernetes_uid: str                    # K8s resource UID
kubernetes_resource_version: str       # K8s resource version
actual_spec/desired_spec: dict        # For drift detection
```

### Real-Time Monitoring Capabilities
```python
# Watch configuration
watch_enabled = models.BooleanField()
watch_crd_types = models.JSONField()        # CRD types to monitor
watch_status = models.CharField()           # Watch service status
watch_started_at = models.DateTimeField()  # Watch start time
watch_last_event = models.DateTimeField()  # Last event received
watch_event_count = models.PositiveIntegerField() # Event counter
```

## Integration Strengths and Capabilities

### Proven Operational Capabilities
1. **Encrypted Authentication**: Working credential storage with no exposures
2. **Multi-Format YAML Processing**: Handles multi-document YAML files
3. **Transactional Consistency**: Database operations wrapped in transactions
4. **Error Resilience**: Graceful handling of authentication/processing failures
5. **Performance Optimization**: Cached CRD counts and efficient queries

### Architecture Maturity
- **GitOps-First Design**: Repository-centric workflow standardization
- **Separation of Concerns**: Authentication decoupled from fabric configuration
- **Multi-Fabric Ready**: Supports multiple fabrics per repository
- **Enterprise Security**: Encrypted credentials with rotation capabilities
- **Comprehensive Monitoring**: Real-time status tracking and drift detection

## Technical Debt and Enhancement Areas

### Current Limitations
1. **Repository-Fabric Coupling**: Migration to separated GitRepository model needed
2. **Direct Cluster API**: Limited direct Kubernetes API operations
3. **Drift Detection Sophistication**: Basic comparison algorithms
4. **Real-Time Monitoring**: Watch service not fully implemented

### Planned Enhancements (ADR-002)
1. **Complete Authentication Separation**: Centralized git repository management
2. **Enhanced Multi-Fabric Support**: Improved directory management
3. **Sophisticated Drift Detection**: Advanced comparison algorithms  
4. **API Expansion**: Comprehensive Kubernetes API integration

## References

- **System Overview**: `/architecture_specifications/00_current_architecture/system_overview.md`
- **GitOps Architecture**: `/architecture_specifications/00_current_architecture/component_architecture/gitops/gitops_overview.md`
- **Kubernetes Integration**: `/architecture_specifications/00_current_architecture/component_architecture/kubernetes_integration.md`
- **Decision Log**: `/architecture_specifications/01_architectural_decisions/decision_log.md`
- **Fabric Model**: `/netbox_hedgehog/models/fabric.py`
- **GitRepository Model**: `/netbox_hedgehog/models/git_repository.py`
- **Sync Implementation**: `/netbox_hedgehog/utils/git_directory_sync.py`
- **K8s Client**: `/netbox_hedgehog/utils/kubernetes.py`