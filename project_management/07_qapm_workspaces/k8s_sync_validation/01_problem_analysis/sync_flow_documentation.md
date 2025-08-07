# Synchronization Flow Documentation

**Analysis Date**: July 31, 2025  
**Analyst**: Architecture Review Specialist  
**Focus**: Complete synchronization workflows and status validation points

## Synchronization Architecture Overview

HNP implements three primary synchronization flows:
1. **GitOps Sync Flow** (Git → NetBox): Primary operational workflow
2. **Kubernetes Apply Flow** (NetBox → K8s): Direct resource application  
3. **Drift Detection Flow** (Git ⟷ K8s): Bidirectional state comparison

## Primary GitOps Synchronization Flow

### User-Initiated Sync Workflow
```
User Action (Fabric Detail Page)
├── "Trigger Sync" button click
├── fabric_views.py: trigger_sync_view()  
├── fabric.trigger_gitops_sync()
└── git_directory_sync.sync_fabric_from_git()
```

### Detailed GitOps Sync Flow
```python
# Step 1: Validation and Configuration Resolution
def sync_from_git(self) -> Dict[str, Any]:
    """Main sync method - clones/pulls repo and syncs all CRs"""
    
    # 1.1 Validate fabric configuration
    if not self.fabric.git_repository and not self.fabric.git_repository_url:
        return {'success': False, 'error': 'No Git repository configured'}
    
    # 1.2 Handle both new and legacy Git configuration
    if self.fabric.git_repository:
        # NEW: Separated authentication architecture
        git_repo = self.fabric.git_repository
        repo_url = git_repo.url
        branch = git_repo.default_branch or 'main'
        credentials = git_repo.get_credentials()  # Encrypted retrieval
        token = credentials.get('token') or credentials.get('access_token')
    else:
        # LEGACY: Direct fabric fields (deprecated)
        repo_url = self.fabric.git_repository_url
        branch = self.fabric.git_branch or 'main'
        token = None
```

```python
# Step 2: Repository Cloning with Authentication
def _clone_repository(self, url: str, path: Path, branch: str, token: Optional[str]):
    """Clone Git repository with authentication if needed"""
    
    # 2.1 Prepare authenticated URL
    if token and 'github.com' in url:
        url_parts = url.replace('https://', '').replace('http://', '')
        auth_url = f"https://{token}@{url_parts}"
    else:
        auth_url = url
    
    # 2.2 Execute git clone operation
    cmd = ['git', 'clone', '--depth', '1', '--branch', branch, auth_url, str(path)]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    
    # 2.3 Extract commit SHA for tracking
    commit_cmd = ['git', '-C', str(path), 'rev-parse', 'HEAD']
    commit_result = subprocess.run(commit_cmd, capture_output=True, text=True)
    commit_sha = commit_result.stdout.strip()
    
    return {'success': True, 'commit_sha': commit_sha}
```

```python
# Step 3: GitOps Directory Processing
def _process_directory(self, directory: Path):
    """Recursively process all YAML files in directory"""
    
    # 3.1 Resolve GitOps directory path
    gitops_path = repo_path / (self.fabric.gitops_directory or 'hedgehog')
    # Current operational: "gitops/hedgehog/fabric-1/"
    
    # 3.2 Scan for YAML files
    for yaml_file in directory.rglob('*.yaml'):
        self._process_yaml_file(yaml_file)
    for yml_file in directory.rglob('*.yml'):
        self._process_yaml_file(yml_file)
    
    # Current files processed: prepop.yaml, test-vpc.yaml, test-vpc-2.yaml
```

```python
# Step 4: YAML File Processing and CRD Creation
def _process_yaml_file(self, file_path: Path):
    """Process a single YAML file containing CRs"""
    
    # 4.1 Parse multi-document YAML
    with open(file_path, 'r') as f:
        documents = list(yaml.safe_load_all(f))
    
    # 4.2 Process each document
    for doc in documents:
        if doc and isinstance(doc, dict):
            self._process_cr_document(doc, file_path)

def _process_cr_document(self, doc: Dict[str, Any], file_path: Path):
    """Process a single CR document from YAML"""
    
    # 4.3 Extract CR metadata
    kind = doc.get('kind')                    # 'VPC', 'Connection', 'Switch'
    metadata = doc.get('metadata', {})
    name = metadata.get('name')               # Resource name
    namespace = metadata.get('namespace', 'default')
    
    # 4.4 Validate supported CRD types
    if kind not in self.KIND_TO_MODEL:
        self.stats['skipped'] += 1
        return
    
    # 4.5 Get model class and create/update record
    model_path = self.KIND_TO_MODEL[kind]    # 'vpc_api.VPC'
    model_class = getattr(models.vpc_api, 'VPC')  # Dynamic import
    
    # 4.6 Database transaction for CRD creation/update
    with transaction.atomic():
        cr, created = model_class.objects.update_or_create(
            name=name,
            fabric=self.fabric,
            namespace=namespace,
            defaults={
                'spec': doc.get('spec', {}),
                'raw_spec': doc.get('spec', {}),
                'annotations': metadata.get('annotations', {}),
                'labels': metadata.get('labels', {}),
                'git_file_path': self._calculate_git_file_path(file_path),
                'last_synced': timezone.now()
            }
        )
        
        # 4.7 Update statistics
        if created:
            self.stats['created'] += 1
        else:
            self.stats['updated'] += 1
```

```python
# Step 5: Fabric State Update and Result Return
# 5.1 Update fabric sync metadata
self.fabric.last_git_sync = timezone.now()
self.fabric.sync_status = 'synced' if self.stats['errors'] == 0 else 'error'
self.fabric.cached_crd_count = self.stats['created'] + self.stats['updated']
self.fabric.save()

# 5.2 Return comprehensive sync results
return {
    'success': success,
    'message': f"Sync completed: {self.stats['created']} created, {self.stats['updated']} updated",
    'commit_sha': clone_result.get('commit_sha', 'unknown'),
    'files_processed': self.stats['scanned'],         # 3 files currently
    'resources_created': self.stats['created'],       # New CRDs
    'resources_updated': self.stats['updated'],       # Updated CRDs  
    'errors': self.errors if self.stats['errors'] > 0 else [],
    'sync_time': self.fabric.last_git_sync.isoformat()
}
```

## Kubernetes Apply Synchronization Flow

### NetBox to Kubernetes Resource Application
```python
# Step 1: CRD Manifest Generation
def apply_crd(self, crd_instance) -> Dict[str, Any]:
    """Apply a CRD to Kubernetes cluster"""
    
    # 1.1 Generate Kubernetes manifest from CRD instance
    manifest = crd_instance.to_kubernetes_manifest()
    
    # Example manifest structure:
    # {
    #   'apiVersion': 'hedgehog.githedgehog.com/v1alpha1',
    #   'kind': 'VPC',
    #   'metadata': {'name': 'vpc-1', 'namespace': 'default'},
    #   'spec': {...}
    # }
```

```python
# Step 2: Kubernetes API Client Configuration
def _get_api_client(self):
    """Get configured Kubernetes API client"""
    
    # 2.1 Get fabric-specific configuration
    fabric_config = self.fabric.get_kubernetes_config()
    # Returns: {'host': 'https://127.0.0.1:6443', 'api_key': {...}, 'verify_ssl': False}
    
    # 2.2 Configure Kubernetes client
    configuration = client.Configuration()
    configuration.host = fabric_config['host']
    configuration.verify_ssl = fabric_config.get('verify_ssl', True)
    
    # 2.3 Set up bearer token authentication
    if 'api_key' in fabric_config:
        auth_header = fabric_config['api_key']['authorization']
        token = auth_header[7:] if auth_header.startswith('Bearer ') else auth_header
        configuration.api_key = {'authorization': token}
        configuration.api_key_prefix = {'authorization': 'Bearer'}
    
    return client.ApiClient(configuration)
```

```python
# Step 3: Resource Application via CustomObjectsApi
def apply_crd(self, crd_instance) -> Dict[str, Any]:
    """Apply CRD to Kubernetes cluster using CustomObjectsApi"""
    
    # 3.1 Extract CRD API details
    group, version = manifest['apiVersion'].split('/')  # 'hedgehog.githedgehog.com', 'v1alpha1'
    plural = self._get_plural_name(manifest['kind'])    # 'vpcs' from 'VPC'
    namespace = manifest['metadata']['namespace']       # 'default'
    name = manifest['metadata']['name']                 # 'vpc-1'
    
    # 3.2 Check for existing resource
    try:
        existing = custom_api.get_namespaced_custom_object(
            group=group, version=version, namespace=namespace,
            plural=plural, name=name
        )
        
        # 3.3 Update existing resource
        result = custom_api.patch_namespaced_custom_object(
            group=group, version=version, namespace=namespace,
            plural=plural, name=name, body=manifest
        )
        operation = 'updated'
        
    except ApiException as e:
        if e.status == 404:
            # 3.4 Create new resource
            result = custom_api.create_namespaced_custom_object(
                group=group, version=version, namespace=namespace,
                plural=plural, body=manifest
            )
            operation = 'created'
```

```python
# Step 4: NetBox Record Update with Kubernetes Metadata
# 4.1 Update CRD instance with Kubernetes metadata
crd_instance.kubernetes_uid = result['metadata']['uid']
crd_instance.kubernetes_resource_version = result['metadata']['resourceVersion']
crd_instance.kubernetes_status = KubernetesStatusChoices.APPLIED
crd_instance.last_applied = datetime.now()
crd_instance.sync_error = ''
crd_instance.save()

# 4.2 Return operation results
return {
    'success': True,
    'operation': operation,                    # 'created' or 'updated'
    'uid': result['metadata']['uid'],
    'resource_version': result['metadata']['resourceVersion'],
    'message': f'CRD {operation} successfully'
}
```

## Drift Detection Synchronization Flow

### Bidirectional State Comparison
```python
# Step 1: Fabric-Level Drift Detection Trigger
def calculate_drift_status(self):
    """Calculate current drift status between desired and actual state"""
    
    # 1.1 Get all resources for this fabric
    from ..models.gitops import HedgehogResource
    resources = HedgehogResource.objects.filter(fabric=self)
    
    # 1.2 Initialize drift tracking
    drift_count = 0
    resource_details = {}
```

```python
# Step 2: Resource-Level Drift Analysis
for resource in resources:
    # 2.1 Trigger drift calculation for each resource
    resource.calculate_drift()
    
    # 2.2 Check for drift status
    if resource.drift_status != 'in_sync':
        drift_count += 1
        resource_details[f"{resource.kind}/{resource.name}"] = {
            'status': resource.drift_status,      # 'drift_detected', 'git_ahead', 'cluster_ahead'
            'score': resource.drift_score,        # 0.0 - 1.0 drift severity
            'summary': resource.get_drift_summary()
        }
```

```python
# Step 3: Drift Detection Algorithm
def detect_drift(self, desired: Dict[str, Any], actual: Dict[str, Any]) -> Dict[str, Any]:
    """Detect drift between desired and actual resource states"""
    
    # 3.1 Handle missing states
    if not desired and not actual:
        return self._no_drift_result()
    if not desired:
        return self._actual_only_result(actual)  # Resource exists in cluster only
    if not actual:
        return self._desired_only_result(desired)  # Resource exists in Git only
    
    # 3.2 Deep comparison of specifications
    differences = self._deep_compare(desired, actual, path='')
    
    # 3.3 Calculate drift score based on differences
    drift_score = self._calculate_drift_score(differences)
    
    # 3.4 Categorize differences by importance
    categorized_diffs = self._categorize_differences(differences)
    
    return {
        'has_drift': True,
        'drift_score': min(drift_score, 1.0),
        'total_differences': len(differences),
        'differences': differences,
        'categorized_differences': categorized_diffs,
        'summary': self._generate_drift_summary(categorized_diffs),
        'recommendations': self._generate_recommendations(categorized_diffs)
    }
```

```python
# Step 4: Fabric Drift Status Aggregation
# 4.1 Determine overall drift status
if drift_count == 0:
    overall_status = 'in_sync'
else:
    overall_status = 'drift_detected'

# 4.2 Update fabric drift information
self.drift_status = overall_status
self.drift_count = drift_count
self.save(update_fields=['drift_status', 'drift_count'])

# 4.3 Return comprehensive drift report
return {
    'drift_status': overall_status,
    'drift_count': drift_count,
    'total_resources': resources.count(),
    'last_calculated': timezone.now(),
    'resource_details': resource_details,
    'details': f'Calculated drift for {resources.count()} resources'
}
```

## Status Validation Points

### Critical Validation Checkpoints

#### 1. Pre-Sync Validation
```python
# Repository configuration validation
if not self.fabric.git_repository and not self.fabric.git_repository_url:
    return {'success': False, 'error': 'No Git repository configured'}

# Authentication validation  
try:
    credentials = git_repo.get_credentials()
    if not credentials.get('token'):
        return {'success': False, 'error': 'No authentication token available'}
except Exception as e:
    return {'success': False, 'error': f'Credential retrieval failed: {e}'}
```

#### 2. Git Operation Validation
```python
# Clone operation validation
result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
if result.returncode != 0:
    return {'success': False, 'error': f'Git clone failed: {result.stderr.strip()}'}

# Directory existence validation
if not gitops_path.exists():
    return {'success': False, 'error': f'GitOps directory {gitops_path} not found'}
```

#### 3. YAML Processing Validation
```python
# File parsing validation
try:
    documents = list(yaml.safe_load_all(f))
except Exception as e:
    self.stats['errors'] += 1
    self.errors.append(f"Error processing {file_path}: {str(e)}")

# CRD metadata validation
if not kind or not name:
    self.stats['skipped'] += 1
    return  # Skip invalid documents

# Supported kind validation
if kind not in self.KIND_TO_MODEL:
    self.stats['skipped'] += 1
    return  # Skip unsupported CRD types
```

#### 4. Database Transaction Validation
```python
# Atomic transaction for consistency
with transaction.atomic():
    cr, created = model_class.objects.update_or_create(
        name=name,
        fabric=self.fabric,
        namespace=namespace,
        defaults={...}
    )
    
    # Update statistics within transaction
    if created:
        self.stats['created'] += 1
    else:
        self.stats['updated'] += 1
```

#### 5. Kubernetes API Validation
```python
# Connection test validation
try:
    version_info = version_api.get_code()
    namespaces = v1.list_namespace(limit=1)
    return {'success': True, 'cluster_version': version_info.git_version}
except Exception as e:
    return {'success': False, 'error': str(e)}

# Resource application validation
try:
    result = custom_api.create_namespaced_custom_object(...)
    crd_instance.kubernetes_status = KubernetesStatusChoices.APPLIED
except Exception as e:
    crd_instance.kubernetes_status = KubernetesStatusChoices.ERROR
    crd_instance.sync_error = str(e)
```

## Current Operational Metrics

### Sync Performance Data
```
Repository: github.com/afewell-hh/gitops-test-1
Directory: gitops/hedgehog/fabric-1/
Files Processed: 3 (prepop.yaml, test-vpc.yaml, test-vpc-2.yaml)

Sync Results:
├── Resources Created: 0
├── Resources Updated: 48  
├── Files Processed: 3
├── Total CRD Records: 36
├── VPCs: 2 records
├── Connections: 26 records  
├── Switches: 8 records
└── Error Rate: 0% (all operations successful)
```

### Status Field States
```
Fabric Status:
├── connection_status: "connected"
├── last_validated: 2025-07-29 08:57:53+00:00
├── sync_status: "synced"
├── drift_status: "Available" (varies)
└── cached_crd_count: 36

Resource Status Distribution:
├── kubernetes_status: APPLIED/LIVE/ERROR
├── last_synced: Recent timestamps
└── sync_error: Empty (no errors)
```

## Error Handling and Recovery

### Error Classification
1. **Configuration Errors**: Missing repository/authentication configuration
2. **Network Errors**: Git clone timeouts, connection failures
3. **Authentication Errors**: Invalid tokens, permission denied
4. **Parsing Errors**: Invalid YAML, unsupported CRD types
5. **Database Errors**: Transaction failures, constraint violations
6. **Kubernetes Errors**: API timeouts, resource conflicts

### Recovery Mechanisms
- **Graceful Degradation**: Partial sync success with error reporting
- **Transaction Rollback**: Database consistency preservation
- **Error Logging**: Comprehensive error tracking and reporting  
- **Status Persistence**: Error states preserved for troubleshooting
- **Manual Retry**: User-initiated retry capability

## References

- **Sync Implementation**: `/netbox_hedgehog/utils/git_directory_sync.py`
- **Kubernetes Client**: `/netbox_hedgehog/utils/kubernetes.py`  
- **Drift Detection**: `/netbox_hedgehog/utils/drift_detection.py`
- **Fabric Model**: `/netbox_hedgehog/models/fabric.py` (sync methods)
- **GitRepository Model**: `/netbox_hedgehog/models/git_repository.py` (authentication)