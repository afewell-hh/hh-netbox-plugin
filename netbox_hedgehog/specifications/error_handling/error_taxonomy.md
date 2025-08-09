# Error Taxonomy for NetBox Hedgehog Plugin

## Overview

This document provides a comprehensive taxonomy of all error conditions in the NetBox Hedgehog Plugin. The taxonomy enables agents to understand error relationships, implement appropriate handling strategies, and maintain consistency across error scenarios.

## Error Classification Hierarchy

### 1. Authentication & Authorization Errors (HH-AUTH-xxx)

#### Authentication Failures
- **Invalid Credentials**: Wrong username/password, expired tokens
- **Missing Credentials**: No authentication provided where required  
- **Credential Format Errors**: Malformed tokens, invalid certificate formats
- **Credential Expiry**: Expired tokens, certificates, or passwords

#### Authorization Failures
- **Insufficient Permissions**: Missing required permissions for operation
- **Resource Access Denied**: User cannot access specific resource
- **Role Restrictions**: User role doesn't allow operation
- **Namespace Restrictions**: Access denied to specific Kubernetes namespace

#### Token Management Errors
- **Token Generation Failed**: Cannot create new authentication tokens
- **Token Validation Failed**: Invalid token format or signature
- **Token Rotation Failed**: Cannot update expired tokens
- **Token Storage Failed**: Cannot securely store token information

### 2. Git & GitHub Integration Errors (HH-GIT-xxx)

#### Repository Access Errors
- **Repository Not Found**: Repository URL invalid or inaccessible
- **Authentication Failed**: Git credentials invalid or insufficient  
- **Permission Denied**: User lacks push/pull permissions
- **Repository Locked**: Repository temporarily unavailable

#### Git Operation Errors
- **Clone Failed**: Cannot clone repository to local filesystem
- **Fetch Failed**: Cannot fetch latest changes from remote
- **Push Failed**: Cannot push local changes to remote
- **Merge Conflicts**: Conflicting changes prevent automatic merge

#### GitHub API Errors  
- **Rate Limit Exceeded**: Too many API requests in time window
- **API Authentication Failed**: GitHub token invalid or expired
- **Resource Not Found**: Requested GitHub resource doesn't exist
- **API Version Mismatch**: Using unsupported GitHub API version

#### File Operation Errors
- **File Not Found**: Referenced file doesn't exist in repository
- **File Write Failed**: Cannot write to file due to permissions/locks
- **File Format Invalid**: File content doesn't match expected format
- **Directory Structure Invalid**: Required directory structure missing

### 3. Kubernetes API Errors (HH-K8S-xxx)

#### Cluster Connectivity Errors
- **Connection Failed**: Cannot connect to Kubernetes API server
- **Authentication Failed**: Invalid kubeconfig or service account
- **Certificate Errors**: TLS certificate validation failed
- **Network Timeout**: Request to K8s API timed out

#### CRD Operation Errors
- **CRD Not Found**: Custom Resource Definition doesn't exist
- **CRD Validation Failed**: Resource spec doesn't match CRD schema
- **Resource Creation Failed**: Cannot create Kubernetes resource
- **Resource Update Failed**: Cannot update existing resource

#### Resource Management Errors
- **Namespace Not Found**: Target namespace doesn't exist
- **Resource Conflicts**: Resource name conflicts with existing resource
- **Resource Quota Exceeded**: Request exceeds namespace resource limits
- **Finalizer Blocking**: Resource deletion blocked by finalizers

#### RBAC & Permission Errors
- **Service Account Missing**: Required service account doesn't exist
- **RBAC Denied**: Service account lacks required permissions
- **Cluster Role Missing**: Required cluster role not found
- **Role Binding Failed**: Cannot bind role to service account

### 4. Data Validation Errors (HH-VAL-xxx)

#### Schema Validation Errors
- **Invalid YAML Structure**: YAML syntax errors or invalid structure
- **JSON Schema Validation Failed**: Data doesn't match required schema
- **Field Type Mismatch**: Field value type doesn't match expected type
- **Required Field Missing**: Mandatory field not provided

#### Business Logic Validation Errors
- **Invalid State Transition**: Attempted transition not allowed
- **Dependency Violation**: Required dependency not met
- **Constraint Violation**: Data violates business rule constraints
- **Relationship Integrity**: Foreign key or relationship constraint failed

#### Format Validation Errors
- **Invalid Format**: Data format doesn't match expected pattern
- **Range Validation Failed**: Value outside acceptable range
- **Length Validation Failed**: String too long or short
- **Pattern Mismatch**: Value doesn't match required regex pattern

#### Cross-Resource Validation Errors
- **Reference Not Found**: Referenced resource doesn't exist
- **Circular Dependency**: Resources create circular reference
- **Version Mismatch**: Resource versions incompatible
- **Namespace Mismatch**: Resources in incompatible namespaces

### 5. Network & Connectivity Errors (HH-NET-xxx)

#### Connection Errors
- **Connection Timeout**: Request timed out waiting for response
- **Connection Refused**: Target service refused connection
- **DNS Resolution Failed**: Cannot resolve hostname to IP address
- **Network Unreachable**: Network routing issue prevents connection

#### Protocol Errors
- **TLS Handshake Failed**: SSL/TLS negotiation failed
- **HTTP Error**: HTTP request returned error status code
- **WebSocket Connection Failed**: Cannot establish WebSocket connection
- **Protocol Version Mismatch**: Unsupported protocol version

#### Service Availability Errors
- **Service Unavailable**: Target service temporarily unavailable
- **Load Balancer Error**: Load balancer cannot route request
- **Circuit Breaker Open**: Circuit breaker preventing requests
- **Health Check Failed**: Service health check indicates problem

### 6. State Transition Errors (HH-STATE-xxx)

#### Invalid Transition Errors
- **Transition Not Allowed**: Source state cannot transition to target state
- **Condition Not Met**: Required condition for transition not satisfied
- **Lock Conflict**: Another process holds state transition lock
- **Version Conflict**: State changed since last read (optimistic locking)

#### State Consistency Errors
- **Inconsistent State**: Entity in inconsistent internal state
- **State Synchronization Failed**: Cannot sync state across components
- **State Persistence Failed**: Cannot save state changes to database
- **State Recovery Failed**: Cannot recover from corrupted state

#### Workflow State Errors
- **Workflow Step Failed**: Individual workflow step failed
- **Workflow Timeout**: Workflow exceeded maximum execution time
- **Workflow Rollback Failed**: Cannot rollback partial workflow
- **Workflow Dependency Failed**: Dependent workflow step failed

## Error Relationships and Dependencies

### Error Cascading
Some errors trigger secondary errors:

```
HH-AUTH-001 (Invalid GitHub Token)
    ↓
HH-GIT-002 (Repository Authentication Failed)
    ↓
HH-STATE-003 (Sync State Transition Failed)
```

### Error Recovery Dependencies
Some recovery operations depend on resolving other errors first:

```
HH-K8S-001 (Connection Failed) 
    ↓ (must resolve before)
HH-K8S-005 (CRD Creation Failed)
    ↓ (must resolve before) 
HH-STATE-001 (Resource State Invalid)
```

## Error Context Information

Each error type includes standardized context information:

### Required Context Fields
- **error_code**: Structured error identifier (e.g., HH-GIT-001)
- **category**: Error category (auth, git, k8s, validation, network, state)
- **severity**: Error severity level (low, medium, high, critical)
- **message**: Human-readable error description
- **timestamp**: When error occurred (ISO 8601 format)

### Optional Context Fields
- **entity_type**: Type of entity involved (Fabric, GitRepository, etc.)
- **entity_id**: Unique identifier of affected entity
- **operation**: Operation being performed when error occurred
- **user**: User or system account that triggered operation
- **stack_trace**: Full exception stack trace for debugging
- **related_errors**: List of related or causative error codes

### Component-Specific Context

#### Git Operations Context
- **repository_url**: Git repository URL
- **branch**: Git branch being operated on
- **commit_sha**: Relevant commit SHA
- **file_path**: File path for file-specific errors

#### Kubernetes Operations Context
- **cluster_url**: Kubernetes API server URL
- **namespace**: Kubernetes namespace
- **resource_name**: Name of Kubernetes resource
- **resource_kind**: Type of Kubernetes resource

#### State Transition Context
- **current_state**: Current state before transition
- **target_state**: Intended state after transition
- **trigger**: Event or action that triggered transition
- **conditions**: List of conditions required for transition

## Error Pattern Analysis

### Common Error Patterns

#### Transient vs Persistent Errors
- **Transient**: Network timeouts, temporary service unavailability
- **Persistent**: Invalid credentials, missing resources, configuration errors

#### Recoverable vs Non-Recoverable Errors
- **Recoverable**: Can be resolved through automated recovery
- **Non-Recoverable**: Require manual intervention or external changes

#### System vs User Errors
- **System**: Internal failures, infrastructure issues
- **User**: Invalid input, permission issues, configuration mistakes

### Error Frequency Analysis
Track error frequency to identify:
- Hot spots needing attention
- Trends indicating systemic issues  
- Success rates for recovery attempts
- User vs system error patterns

## Error Handling Strategies by Category

### Authentication Errors
- **Immediate**: Reject request with clear error message
- **Recovery**: Attempt credential refresh if possible
- **Escalation**: Alert administrators for persistent failures
- **User Action**: Provide clear instructions for credential update

### Git Integration Errors
- **Retry Logic**: Exponential backoff for transient failures
- **Fallback**: Use cached data when repository unavailable
- **Recovery**: Attempt to resolve conflicts automatically
- **Monitoring**: Track repository availability and performance

### Kubernetes Errors
- **Validation**: Pre-validate resources before submission
- **Retry**: Retry failed operations with backoff
- **Alternative**: Use alternative clusters when available
- **Rollback**: Rollback on critical resource failures

### Validation Errors
- **Early Detection**: Validate at input boundaries
- **Clear Messages**: Provide specific validation failure details
- **Correction Hints**: Suggest corrections when possible
- **Prevent Cascade**: Stop processing to prevent cascading errors

### Network Errors
- **Circuit Breaker**: Prevent cascade failures
- **Timeout Management**: Appropriate timeout values
- **Retry Strategy**: Intelligent retry with backoff
- **Health Monitoring**: Track service health continuously

### State Transition Errors
- **Atomic Operations**: Ensure state changes are atomic
- **Consistency Checks**: Validate state before and after transitions
- **Recovery Paths**: Define clear recovery procedures
- **Audit Trail**: Maintain complete state change history

## Integration with Error Codes

Each error in the taxonomy maps to specific error codes defined in `error_codes.md`:

| Category | Code Range | Examples |
|----------|------------|----------|
| Authentication | HH-AUTH-001 to HH-AUTH-099 | HH-AUTH-001, HH-AUTH-015 |
| Git Operations | HH-GIT-001 to HH-GIT-099 | HH-GIT-003, HH-GIT-024 |
| Kubernetes | HH-K8S-001 to HH-K8S-099 | HH-K8S-005, HH-K8S-033 |
| Validation | HH-VAL-001 to HH-VAL-099 | HH-VAL-002, HH-VAL-018 |
| Network | HH-NET-001 to HH-NET-099 | HH-NET-001, HH-NET-012 |
| State Transition | HH-STATE-001 to HH-STATE-099 | HH-STATE-004, HH-STATE-027 |

## Usage in Agent Implementation

### Error Detection
Agents should classify errors using this taxonomy:

```python
def classify_error(exception, context):
    """Classify exception using error taxonomy"""
    
    if isinstance(exception, AuthenticationError):
        return classify_auth_error(exception, context)
    elif isinstance(exception, GitError):
        return classify_git_error(exception, context)
    # ... continue for other categories
    
def classify_auth_error(exception, context):
    """Classify authentication-specific errors"""
    
    if 'invalid token' in str(exception).lower():
        return {
            'category': 'authentication',
            'subcategory': 'token_management',
            'error_type': 'invalid_credentials',
            'suggested_code': 'HH-AUTH-001'
        }
    # ... continue for other auth error types
```

### Error Context Building
Build standardized error context:

```python
def build_error_context(error_type, exception, entity=None, operation=None):
    """Build standardized error context"""
    
    context = {
        'error_code': error_type['suggested_code'],
        'category': error_type['category'],
        'severity': determine_severity(error_type, exception),
        'message': build_user_message(error_type, exception),
        'timestamp': timezone.now().isoformat(),
        'stack_trace': traceback.format_exc()
    }
    
    if entity:
        context.update({
            'entity_type': entity.__class__.__name__,
            'entity_id': getattr(entity, 'id', None),
            'entity_name': getattr(entity, 'name', None)
        })
    
    if operation:
        context['operation'] = operation
    
    return context
```

This taxonomy provides the foundation for all error handling implementations and ensures consistent error management across the NetBox Hedgehog Plugin.