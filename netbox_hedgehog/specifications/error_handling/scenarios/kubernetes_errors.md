# Kubernetes Error Scenarios

## Overview

This document covers all error scenarios related to Kubernetes API operations, CRD management, and cluster connectivity in the NetBox Hedgehog Plugin. These scenarios are based on analysis of Kubernetes integration patterns throughout the codebase.

## Kubernetes Error Categories

### Error Types
1. **Cluster Connectivity Errors**: API server access, network, authentication
2. **CRD Operation Errors**: Custom Resource Definition management
3. **Resource Management Errors**: CRUD operations on Kubernetes resources
4. **RBAC & Permission Errors**: Service account and role-based access control

## Cluster Connectivity Error Scenarios

### Scenario: HH-K8S-001 - Cluster Connection Failed

**Description**: Cannot establish connection to Kubernetes API server.

**Common Triggers**:
- Kubernetes API server is down or unreachable
- Network connectivity issues between NetBox and cluster
- Incorrect API server endpoint configuration
- Load balancer or proxy issues

**Error Detection Patterns**:
```python
import kubernetes
from kubernetes.client.exceptions import ApiException

try:
    config = kubernetes.client.Configuration()
    config.host = fabric.kubernetes_server
    config.api_key['authorization'] = f'Bearer {fabric.kubernetes_token}'
    
    api_client = kubernetes.client.ApiClient(config)
    v1 = kubernetes.client.CoreV1Api(api_client)
    
    # Test connection with timeout
    namespaces = v1.list_namespace(_request_timeout=30)
    
except kubernetes.client.exceptions.ApiException as e:
    if e.status == 0:  # Connection failed
        raise KubernetesConnectivityError('HH-K8S-001', 'Cluster connection failed')
except requests.exceptions.ConnectionError as e:
    raise KubernetesConnectivityError('HH-K8S-001', f'Connection error: {str(e)}')
except socket.timeout:
    raise KubernetesConnectivityError('HH-K8S-001', 'Connection timeout')
```

**Typical Error Messages**:
- "Connection refused: connect"
- "Name or service not known"  
- "Connection timed out"
- "No route to host"

**Context Information**:
```json
{
    "error_code": "HH-K8S-001",
    "cluster_endpoint": "https://k8s-api.example.com:6443",
    "fabric_id": 123,
    "operation": "list_namespaces",
    "timeout": 30,
    "timestamp": "2024-01-15T10:30:00Z"
}
```

**Automatic Recovery**:
```python
def recover_cluster_connection_failed(fabric, error_context):
    """Multi-strategy cluster connection recovery"""
    
    recovery_strategies = [
        {
            'name': 'extended_timeout',
            'action': lambda: test_connection_with_timeout(fabric, 120),
            'description': 'Try with extended timeout'
        },
        {
            'name': 'alternative_endpoint', 
            'action': lambda: try_alternative_endpoints(fabric),
            'description': 'Try alternative API endpoints'
        },
        {
            'name': 'network_diagnostics',
            'action': lambda: perform_network_diagnostics(fabric),
            'description': 'Run network connectivity tests'
        }
    ]
    
    for strategy in recovery_strategies:
        try:
            logger.info(f"Attempting recovery strategy: {strategy['name']}")
            result = strategy['action']()
            
            if result.get('success'):
                return {
                    'success': True,
                    'recovery_type': 'automatic',
                    'strategy': strategy['name'],
                    'message': f"Connection restored via {strategy['description']}"
                }
                
        except Exception as e:
            logger.warning(f"Recovery strategy {strategy['name']} failed: {e}")
            continue
    
    return {
        'success': False,
        'escalate': 'manual',
        'reason': 'all_recovery_strategies_failed'
    }

def try_alternative_endpoints(fabric):
    """Try common alternative endpoints"""
    
    base_url = fabric.kubernetes_server
    alternatives = []
    
    # Parse current endpoint
    from urllib.parse import urlparse
    parsed = urlparse(base_url)
    
    # Generate alternatives
    alternatives.extend([
        f"https://{parsed.hostname}:6443",  # Standard port
        f"https://{parsed.hostname}:443",   # HTTPS port
        f"https://{parsed.hostname}:8443",  # Alternative port
        f"http://{parsed.hostname}:8080"    # HTTP port (dev)
    ])
    
    for endpoint in alternatives:
        if endpoint != base_url:
            try:
                if test_kubernetes_endpoint(endpoint, fabric.kubernetes_token):
                    fabric.kubernetes_server = endpoint
                    fabric.save()
                    return {'success': True, 'new_endpoint': endpoint}
            except Exception:
                continue
    
    return {'success': False}
```

### Scenario: HH-K8S-002 - Cluster Authentication Failed

**Description**: Kubernetes credentials are invalid, expired, or insufficient.

**Common Triggers**:
- Service account token expired
- Invalid kubeconfig configuration
- Token permissions revoked
- Service account deleted

**Error Detection Patterns**:
```python
try:
    v1 = kubernetes.client.CoreV1Api(api_client)
    namespaces = v1.list_namespace()
except kubernetes.client.exceptions.ApiException as e:
    if e.status == 401:
        raise KubernetesAuthenticationError('HH-K8S-002', 'Authentication failed')
    elif e.status == 403:
        if 'token' in e.reason.lower():
            raise KubernetesAuthenticationError('HH-K8S-002', 'Token authentication failed')
```

**Automatic Recovery**:
```python
def recover_kubernetes_authentication_failed(fabric, error_context):
    """Attempt authentication recovery"""
    
    # Strategy 1: Token refresh if supported
    if hasattr(fabric, 'kubernetes_refresh_token'):
        try:
            new_token = refresh_kubernetes_token(fabric.kubernetes_refresh_token)
            if new_token and validate_kubernetes_token(new_token, fabric.kubernetes_server):
                fabric.kubernetes_token = new_token
                fabric.save()
                return {
                    'success': True,
                    'recovery_type': 'automatic',
                    'action': 'token_refreshed'
                }
        except Exception as e:
            logger.error(f"Token refresh failed: {e}")
    
    # Strategy 2: Service account recreation
    if fabric.kubernetes_namespace:
        try:
            result = recreate_service_account(fabric)
            if result.get('success'):
                return {
                    'success': True,
                    'recovery_type': 'automatic', 
                    'action': 'service_account_recreated'
                }
        except Exception as e:
            logger.error(f"Service account recreation failed: {e}")
    
    return {
        'success': False,
        'escalate': 'manual',
        'reason': 'authentication_not_recoverable'
    }
```

### Scenario: HH-K8S-004 - Cluster Network Timeout

**Description**: Requests to Kubernetes API server are timing out.

**Common Triggers**:
- High cluster load causing slow responses
- Network latency or intermittent connectivity
- API server performance issues
- Resource constraints on API server

**Recovery Implementation**:
```python
def recover_cluster_timeout(fabric, error_context):
    """Progressive timeout recovery"""
    
    timeout_progression = [30, 60, 120, 300, 600]  # seconds
    
    for timeout in timeout_progression:
        try:
            logger.info(f"Testing cluster connection with {timeout}s timeout")
            
            config = kubernetes.client.Configuration()
            config.host = fabric.kubernetes_server
            config.api_key['authorization'] = f'Bearer {fabric.kubernetes_token}'
            config.timeout = timeout
            
            api_client = kubernetes.client.ApiClient(config)
            v1 = kubernetes.client.CoreV1Api(api_client)
            
            # Simple test operation
            result = v1.list_namespace(_request_timeout=timeout)
            
            # Success - update fabric with working timeout
            fabric.kubernetes_timeout = timeout
            fabric.save()
            
            return {
                'success': True,
                'recovery_type': 'automatic',
                'effective_timeout': timeout,
                'message': f'Cluster connection restored with {timeout}s timeout'
            }
            
        except Exception as e:
            if timeout == timeout_progression[-1]:
                # Last attempt failed
                return {
                    'success': False,
                    'escalate': 'manual',
                    'reason': 'all_timeouts_failed',
                    'max_timeout_tested': timeout
                }
            continue
    
    return {'success': False, 'escalate': 'manual'}
```

## CRD Operation Error Scenarios

### Scenario: HH-K8S-010 - CRD Not Found

**Description**: Required Custom Resource Definition does not exist in the cluster.

**Common Triggers**:
- CRDs not installed during cluster setup
- CRDs deleted accidentally
- Wrong CRD version or API group
- CRDs in different namespace than expected

**Error Detection Patterns**:
```python
try:
    api_extensions = kubernetes.client.ApiextensionsV1Api(api_client)
    crd = api_extensions.read_custom_resource_definition(crd_name)
except kubernetes.client.exceptions.ApiException as e:
    if e.status == 404:
        raise KubernetesCRDError('HH-K8S-010', f'CRD not found: {crd_name}')

# When creating resources
try:
    custom_api = kubernetes.client.CustomObjectsApi(api_client)
    result = custom_api.create_namespaced_custom_object(
        group='vpc.githedgehog.com',
        version='v1alpha2', 
        namespace='default',
        plural='vpcs',
        body=resource_spec
    )
except kubernetes.client.exceptions.ApiException as e:
    if e.status == 404 and 'no matches for kind' in e.body:
        raise KubernetesCRDError('HH-K8S-010', 'Required CRD not installed')
```

**Automatic Recovery**:
```python
def recover_crd_not_found(fabric, crd_name, error_context):
    """Automatic CRD installation"""
    
    # Map of CRD names to installation sources
    crd_sources = {
        'vpcs.vpc.githedgehog.com': 'https://raw.githubusercontent.com/githedgehog/vpc-crd/main/config/crd/bases/vpc.githedgehog.com_vpcs.yaml',
        'connections.wiring.githedgehog.com': 'https://raw.githubusercontent.com/githedgehog/wiring-crd/main/config/crd/bases/wiring.githedgehog.com_connections.yaml',
        'switches.wiring.githedgehog.com': 'https://raw.githubusercontent.com/githedgehog/wiring-crd/main/config/crd/bases/wiring.githedgehog.com_switches.yaml'
    }
    
    if crd_name in crd_sources:
        try:
            # Download CRD manifest
            crd_url = crd_sources[crd_name]
            response = requests.get(crd_url, timeout=30)
            response.raise_for_status()
            
            # Parse and install CRD
            crd_manifest = yaml.safe_load(response.content)
            
            api_extensions = kubernetes.client.ApiextensionsV1Api(
                kubernetes.client.ApiClient(fabric.get_kubernetes_config())
            )
            
            result = api_extensions.create_custom_resource_definition(crd_manifest)
            
            # Wait for CRD to be established
            if wait_for_crd_established(crd_name, timeout=120):
                return {
                    'success': True,
                    'recovery_type': 'automatic',
                    'action': 'crd_installed',
                    'crd_name': crd_name
                }
            
        except Exception as e:
            logger.error(f"CRD installation failed: {e}")
    
    return {
        'success': False,
        'escalate': 'manual',
        'reason': 'crd_installation_failed',
        'available_sources': list(crd_sources.keys())
    }

def wait_for_crd_established(crd_name, timeout=120):
    """Wait for CRD to become established"""
    
    import time
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        try:
            api_extensions = kubernetes.client.ApiextensionsV1Api()
            crd = api_extensions.read_custom_resource_definition(crd_name)
            
            # Check if CRD is established
            conditions = crd.status.conditions or []
            for condition in conditions:
                if condition.type == 'Established' and condition.status == 'True':
                    return True
                    
        except Exception as e:
            logger.debug(f"CRD establishment check failed: {e}")
        
        time.sleep(5)
    
    return False
```

### Scenario: HH-K8S-011 - CRD Validation Failed

**Description**: Resource specification doesn't match the CRD schema validation rules.

**Common Triggers**:
- Missing required fields in resource spec
- Field values outside allowed ranges
- Invalid enum values
- Schema version mismatch

**Error Detection Patterns**:
```python
try:
    custom_api = kubernetes.client.CustomObjectsApi(api_client)
    result = custom_api.create_namespaced_custom_object(
        group='vpc.githedgehog.com',
        version='v1alpha2',
        namespace=namespace,
        plural='vpcs',
        body=resource_spec
    )
except kubernetes.client.exceptions.ApiException as e:
    if e.status == 422:  # Unprocessable Entity
        validation_errors = parse_kubernetes_validation_errors(e.body)
        raise KubernetesCRDValidationError('HH-K8S-011', 'CRD validation failed', 
                                         context={'validation_errors': validation_errors})
```

**Automatic Recovery**:
```python
def recover_crd_validation_failed(fabric, resource_spec, error_context):
    """Automatic CRD validation repair"""
    
    validation_errors = error_context.get('validation_errors', [])
    fixed_spec = resource_spec.copy()
    fixes_applied = []
    
    for error in validation_errors:
        field_path = error.get('field', '')
        error_type = error.get('type', '')
        error_message = error.get('message', '')
        
        # Apply common fixes
        if error_type == 'required':
            fix = add_required_field(fixed_spec, field_path, error_message)
            if fix:
                fixes_applied.append(fix)
                
        elif error_type == 'type':
            fix = fix_field_type(fixed_spec, field_path, error_message)
            if fix:
                fixes_applied.append(fix)
                
        elif error_type == 'enum':
            fix = fix_enum_value(fixed_spec, field_path, error_message)
            if fix:
                fixes_applied.append(fix)
    
    if fixes_applied:
        # Validate fixed spec
        try:
            validate_resource_spec(fixed_spec, fabric)
            return {
                'success': True,
                'recovery_type': 'automatic',
                'fixes_applied': fixes_applied,
                'fixed_spec': fixed_spec
            }
        except Exception as e:
            logger.error(f"Fixed spec still invalid: {e}")
    
    return {
        'success': False,
        'escalate': 'manual',
        'validation_errors': validation_errors,
        'original_spec': resource_spec
    }

def add_required_field(spec, field_path, error_message):
    """Add missing required fields with sensible defaults"""
    
    defaults = {
        'apiVersion': 'vpc.githedgehog.com/v1alpha2',
        'kind': 'VPC',
        'metadata.name': 'default-vpc',
        'metadata.namespace': 'default',
        'spec.subnets': ['10.0.0.0/24']
    }
    
    if field_path in defaults:
        set_nested_field(spec, field_path, defaults[field_path])
        return {
            'field': field_path,
            'action': 'added_default',
            'value': defaults[field_path]
        }
    
    return None
```

## Resource Management Error Scenarios

### Scenario: HH-K8S-020 - Resource Creation Failed

**Description**: Cannot create new Kubernetes resource due to various constraints.

**Common Triggers**:
- Resource name already exists
- Namespace doesn't exist
- Resource quotas exceeded
- Admission controller rejection

**Error Handling**:
```python
def handle_resource_creation_failed(fabric, resource_spec, error_context):
    """Handle resource creation failures"""
    
    api_exception = error_context.get('exception')
    
    if api_exception.status == 409:  # Conflict
        # Resource already exists
        return handle_resource_already_exists(fabric, resource_spec)
    elif api_exception.status == 404:
        # Namespace might not exist
        return handle_namespace_not_found(fabric, resource_spec)
    elif api_exception.status == 403:
        # Quota or admission controller
        return handle_resource_quota_exceeded(fabric, resource_spec)
    else:
        return escalate_to_manual_recovery('HH-K8S-020', str(api_exception))

def handle_resource_already_exists(fabric, resource_spec):
    """Handle existing resource scenarios"""
    
    resource_name = resource_spec['metadata']['name']
    namespace = resource_spec['metadata']['namespace']
    
    try:
        # Get existing resource
        existing_resource = get_kubernetes_resource(
            fabric, resource_spec['kind'], resource_name, namespace
        )
        
        # Compare specs to determine if update is needed
        if resources_are_equivalent(existing_resource, resource_spec):
            return {
                'success': True,
                'recovery_type': 'automatic',
                'action': 'resource_already_exists_equivalent',
                'message': 'Resource already exists with equivalent specification'
            }
        else:
            # Update existing resource
            return update_existing_resource(fabric, existing_resource, resource_spec)
            
    except Exception as e:
        return {
            'success': False,
            'escalate': 'manual',
            'reason': f'could_not_handle_existing_resource: {e}'
        }
```

### Scenario: HH-K8S-025 - Resource Quota Exceeded

**Description**: Resource creation/update exceeds namespace resource quotas.

**Common Triggers**:
- Too many resources in namespace
- CPU/memory limits exceeded
- Storage quota exceeded
- Custom resource limits exceeded

**Recovery Strategy**:
```python
def recover_resource_quota_exceeded(fabric, resource_spec, error_context):
    """Handle resource quota exceeded scenarios"""
    
    namespace = resource_spec['metadata']['namespace']
    
    try:
        # Get current quota usage
        v1 = kubernetes.client.CoreV1Api(fabric.get_kubernetes_client())
        quota_status = v1.read_namespaced_resource_quota_status(
            name='compute-quota', 
            namespace=namespace
        )
        
        # Analyze quota constraints
        quota_analysis = analyze_quota_constraints(quota_status, resource_spec)
        
        if quota_analysis['can_cleanup']:
            # Attempt cleanup of unused resources
            cleanup_result = cleanup_unused_resources(fabric, namespace)
            if cleanup_result['success']:
                return {
                    'success': True,
                    'recovery_type': 'automatic',
                    'action': 'cleaned_up_resources',
                    'resources_removed': cleanup_result['removed']
                }
        
        return {
            'success': False,
            'escalate': 'manual',
            'reason': 'quota_exceeded',
            'quota_analysis': quota_analysis,
            'suggested_actions': [
                'Increase namespace resource quota',
                'Remove unused resources',
                'Move resources to different namespace'
            ]
        }
        
    except Exception as e:
        return {
            'success': False,
            'escalate': 'manual',
            'reason': f'quota_analysis_failed: {e}'
        }
```

## RBAC & Permission Error Scenarios

### Scenario: HH-K8S-033 - RBAC Permission Denied

**Description**: Service account lacks required permissions for Kubernetes operations.

**Common Triggers**:
- Missing cluster roles or role bindings
- Service account deleted or modified
- Namespace-specific permission issues
- CRD-specific permissions missing

**Error Detection**:
```python
try:
    result = custom_api.create_namespaced_custom_object(...)
except kubernetes.client.exceptions.ApiException as e:
    if e.status == 403:
        permission_details = parse_rbac_error(e.body)
        raise KubernetesRBACError('HH-K8S-033', 'RBAC permission denied',
                                context={'permission_details': permission_details})
```

**Automatic Recovery**:
```python
def recover_rbac_permission_denied(fabric, error_context):
    """Attempt RBAC permission recovery"""
    
    permission_details = error_context.get('permission_details', {})
    missing_permissions = permission_details.get('missing_permissions', [])
    
    # Check if we can create missing RBAC resources
    if fabric.kubernetes_admin_access:
        try:
            rbac_recovery_result = create_missing_rbac_resources(
                fabric, missing_permissions
            )
            
            if rbac_recovery_result['success']:
                return {
                    'success': True,
                    'recovery_type': 'automatic',
                    'action': 'created_rbac_resources',
                    'resources_created': rbac_recovery_result['created']
                }
                
        except Exception as e:
            logger.error(f"RBAC resource creation failed: {e}")
    
    return {
        'success': False,
        'escalate': 'manual',
        'reason': 'rbac_permissions_required',
        'missing_permissions': missing_permissions,
        'required_actions': generate_rbac_fix_instructions(missing_permissions)
    }

def generate_rbac_fix_instructions(missing_permissions):
    """Generate instructions for fixing RBAC issues"""
    
    instructions = []
    
    for permission in missing_permissions:
        resource = permission.get('resource')
        verb = permission.get('verb') 
        api_group = permission.get('apiGroup', '')
        
        if api_group:
            instructions.append({
                'action': 'create_cluster_role',
                'resource': resource,
                'verb': verb,
                'api_group': api_group,
                'yaml': generate_cluster_role_yaml(resource, verb, api_group)
            })
    
    return instructions
```

## Integration Error Scenarios  

### Scenario: Multi-Component Kubernetes Failure

**Description**: Failure cascades across multiple Kubernetes components and affects state management.

**Error Chain Example**:
1. `HH-K8S-001`: Cluster connection failed
2. `HH-STATE-012`: Cannot update fabric connection status
3. `HH-K8S-020`: Resource creation queued but failing
4. `HH-VAL-010`: State validation inconsistencies

**Recovery Strategy**:
```python
def recover_kubernetes_multi_component_failure(fabric, error_chain):
    """Handle complex Kubernetes failure scenarios"""
    
    # Analyze failure pattern
    failure_analysis = analyze_kubernetes_failure_pattern(error_chain)
    
    # Generate recovery plan based on failure type
    if failure_analysis['type'] == 'connectivity_cascade':
        return recover_connectivity_cascade(fabric, error_chain)
    elif failure_analysis['type'] == 'permission_cascade':
        return recover_permission_cascade(fabric, error_chain)  
    elif failure_analysis['type'] == 'resource_cascade':
        return recover_resource_cascade(fabric, error_chain)
    else:
        return {
            'success': False,
            'escalate': 'manual',
            'reason': 'unknown_failure_pattern',
            'analysis': failure_analysis
        }
```

## Testing Kubernetes Error Scenarios

```python
class KubernetesErrorTests:
    
    def test_cluster_connection_failed(self):
        """Test HH-K8S-001 scenario"""
        fabric = self.create_test_fabric(
            kubernetes_server='https://invalid-cluster:6443'
        )
        
        with self.assertRaises(KubernetesConnectivityError) as context:
            test_kubernetes_connection(fabric)
        
        self.assertEqual(context.exception.code, 'HH-K8S-001')
    
    def test_crd_not_found_recovery(self):
        """Test HH-K8S-010 automatic recovery"""
        fabric = self.create_test_fabric()
        
        with mock.patch('kubernetes.client.ApiextensionsV1Api') as mock_api:
            # Simulate CRD not found
            mock_api.return_value.read_custom_resource_definition.side_effect = \
                kubernetes.client.exceptions.ApiException(status=404)
            
            result = recover_crd_not_found(fabric, 'vpcs.vpc.githedgehog.com', {})
            
            # Should attempt automatic installation
            self.assertEqual(result.get('action'), 'crd_installed')
```

This comprehensive Kubernetes error scenario documentation provides agents with detailed knowledge for handling all major Kubernetes-related failures in the NetBox Hedgehog Plugin.