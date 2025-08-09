# Error Codes for NetBox Hedgehog Plugin

## Overview

This document defines all structured error codes used in the NetBox Hedgehog Plugin. Each error code provides a unique identifier for specific error conditions, enabling consistent error handling, monitoring, and automated recovery across all system components.

## Error Code Format

All error codes follow the format: `HH-<CATEGORY>-<NUMBER>`

- **HH**: NetBox Hedgehog Plugin prefix
- **CATEGORY**: Error category (AUTH, GIT, K8S, VAL, NET, STATE)  
- **NUMBER**: Three-digit sequential number within category

## Authentication & Authorization Errors (HH-AUTH-xxx)

### Authentication Failures

| Code | Name | Description | Severity | Recovery |
|------|------|-------------|----------|----------|
| HH-AUTH-001 | Invalid GitHub Token | GitHub authentication token is invalid or malformed | High | Prompt for new token |
| HH-AUTH-002 | Expired GitHub Token | GitHub token has expired | High | Refresh token automatically |
| HH-AUTH-003 | Missing GitHub Token | No GitHub token provided where required | High | Request token from user |
| HH-AUTH-004 | Invalid Kubernetes Token | Kubernetes service account token invalid | High | Update kubeconfig |
| HH-AUTH-005 | Expired Kubernetes Token | Kubernetes token has expired | High | Renew service account token |
| HH-AUTH-006 | Missing Kubernetes Credentials | No Kubernetes credentials configured | High | Configure cluster access |
| HH-AUTH-007 | Invalid SSH Key | SSH key for Git access is invalid or corrupted | High | Generate new SSH key pair |
| HH-AUTH-008 | SSH Key Permission Denied | SSH key lacks permission for repository | High | Add key to repository |

### Authorization Failures

| Code | Name | Description | Severity | Recovery |
|------|------|-------------|----------|----------|
| HH-AUTH-010 | Insufficient GitHub Permissions | GitHub token lacks required repository permissions | High | Grant push permissions |
| HH-AUTH-011 | Repository Access Denied | User cannot access Git repository | High | Add user to repository |
| HH-AUTH-012 | Kubernetes RBAC Denied | Service account lacks required Kubernetes permissions | High | Update cluster roles |
| HH-AUTH-013 | Namespace Access Denied | Cannot access specified Kubernetes namespace | Medium | Grant namespace access |
| HH-AUTH-014 | Resource Access Denied | Cannot access specific Kubernetes resource | Medium | Update resource permissions |
| HH-AUTH-015 | Admin Rights Required | Operation requires administrative privileges | High | Contact administrator |

### Token Management Errors

| Code | Name | Description | Severity | Recovery |
|------|------|-------------|----------|----------|
| HH-AUTH-020 | Token Generation Failed | Cannot generate new authentication token | High | Retry with backoff |
| HH-AUTH-021 | Token Validation Failed | Token format validation failed | Medium | Regenerate token |
| HH-AUTH-022 | Token Storage Failed | Cannot securely store authentication token | High | Check storage permissions |
| HH-AUTH-023 | Token Rotation Failed | Cannot update expired token | High | Manual token update |
| HH-AUTH-024 | Token Encryption Failed | Cannot encrypt token for storage | High | Check encryption keys |

## Git & GitHub Integration Errors (HH-GIT-xxx)

### Repository Access Errors

| Code | Name | Description | Severity | Recovery |
|------|------|-------------|----------|----------|
| HH-GIT-001 | Repository Not Found | Git repository URL is invalid or inaccessible | High | Verify repository URL |
| HH-GIT-002 | Repository Authentication Failed | Cannot authenticate with Git repository | High | Check credentials |
| HH-GIT-003 | Repository Permission Denied | User lacks required repository permissions | High | Grant repository access |
| HH-GIT-004 | Repository Temporarily Unavailable | Repository service temporarily down | Medium | Retry with exponential backoff |
| HH-GIT-005 | Repository Locked | Repository is locked for maintenance | Medium | Wait and retry |
| HH-GIT-006 | Invalid Repository URL | Repository URL format is invalid | High | Correct URL format |

### Git Operation Errors

| Code | Name | Description | Severity | Recovery |
|------|------|-------------|----------|----------|
| HH-GIT-010 | Clone Operation Failed | Cannot clone repository to local filesystem | High | Check network and permissions |
| HH-GIT-011 | Fetch Operation Failed | Cannot fetch latest changes from remote | Medium | Retry with clean repository |
| HH-GIT-012 | Push Operation Failed | Cannot push local changes to remote | High | Check for conflicts |
| HH-GIT-013 | Pull Operation Failed | Cannot pull remote changes | Medium | Reset local changes |
| HH-GIT-014 | Merge Conflict Detected | Automatic merge failed due to conflicts | High | Manual conflict resolution |
| HH-GIT-015 | Branch Not Found | Specified Git branch does not exist | High | Create branch or use default |
| HH-GIT-016 | Commit Failed | Cannot create Git commit | Medium | Check repository state |
| HH-GIT-017 | Tag Operation Failed | Cannot create or retrieve Git tag | Low | Continue without tagging |

### GitHub API Errors

| Code | Name | Description | Severity | Recovery |
|------|------|-------------|----------|----------|
| HH-GIT-020 | GitHub API Rate Limited | Exceeded GitHub API rate limit | Medium | Wait and retry after reset |
| HH-GIT-021 | GitHub API Authentication Failed | GitHub API token invalid or expired | High | Refresh API token |
| HH-GIT-022 | GitHub Resource Not Found | Requested GitHub resource doesn't exist | Medium | Create resource if possible |
| HH-GIT-023 | GitHub API Version Mismatch | Using unsupported GitHub API version | Low | Update to supported version |
| HH-GIT-024 | GitHub Webhook Failed | Cannot create or update GitHub webhook | Medium | Manual webhook configuration |
| HH-GIT-025 | GitHub API Server Error | GitHub API returned server error | Medium | Retry with exponential backoff |

### File Operation Errors

| Code | Name | Description | Severity | Recovery |
|------|------|-------------|----------|----------|
| HH-GIT-030 | File Not Found in Repository | Referenced file doesn't exist in Git repo | Medium | Create file or use default |
| HH-GIT-031 | File Write Permission Denied | Cannot write to file in repository | High | Check file permissions |
| HH-GIT-032 | File Format Invalid | File content doesn't match expected format | High | Validate and correct format |
| HH-GIT-033 | Directory Structure Invalid | Required directory structure missing | High | Create directory structure |
| HH-GIT-034 | File Size Exceeded | File size exceeds repository limits | Medium | Compress or split file |
| HH-GIT-035 | Binary File Detected | Unexpected binary file in YAML directory | Medium | Remove or move file |

## Kubernetes API Errors (HH-K8S-xxx)

### Cluster Connectivity Errors

| Code | Name | Description | Severity | Recovery |
|------|------|-------------|----------|----------|
| HH-K8S-001 | Cluster Connection Failed | Cannot connect to Kubernetes API server | Critical | Check cluster status |
| HH-K8S-002 | Cluster Authentication Failed | Invalid kubeconfig or service account | High | Update cluster credentials |
| HH-K8S-003 | Cluster Certificate Invalid | TLS certificate validation failed | High | Update cluster certificates |
| HH-K8S-004 | Cluster Network Timeout | Request to Kubernetes API timed out | Medium | Retry with longer timeout |
| HH-K8S-005 | Cluster Version Incompatible | Kubernetes version not supported | High | Upgrade cluster or plugin |
| HH-K8S-006 | Cluster API Server Unavailable | Kubernetes API server not responding | Critical | Check cluster health |

### CRD Operation Errors

| Code | Name | Description | Severity | Recovery |
|------|------|-------------|----------|----------|
| HH-K8S-010 | CRD Not Found | Custom Resource Definition doesn't exist | High | Install required CRDs |
| HH-K8S-011 | CRD Validation Failed | Resource spec doesn't match CRD schema | High | Correct resource specification |
| HH-K8S-012 | CRD Version Mismatch | CRD version incompatible with resource | High | Update CRD or resource |
| HH-K8S-013 | CRD Installation Failed | Cannot install Custom Resource Definition | High | Check cluster permissions |
| HH-K8S-014 | CRD Update Failed | Cannot update existing CRD | High | Manual CRD update required |

### Resource Management Errors

| Code | Name | Description | Severity | Recovery |
|------|------|-------------|----------|----------|
| HH-K8S-020 | Resource Creation Failed | Cannot create Kubernetes resource | High | Check resource specification |
| HH-K8S-021 | Resource Update Failed | Cannot update existing Kubernetes resource | High | Check resource conflicts |
| HH-K8S-022 | Resource Deletion Failed | Cannot delete Kubernetes resource | Medium | Check finalizers |
| HH-K8S-023 | Resource Not Found | Requested Kubernetes resource doesn't exist | Medium | Create resource if needed |
| HH-K8S-024 | Resource Conflict | Resource name conflicts with existing | High | Use different resource name |
| HH-K8S-025 | Resource Quota Exceeded | Request exceeds namespace quotas | Medium | Request quota increase |
| HH-K8S-026 | Resource Finalizer Blocking | Finalizers prevent resource deletion | Medium | Remove blocking finalizers |

### Namespace & RBAC Errors

| Code | Name | Description | Severity | Recovery |
|------|------|-------------|----------|----------|
| HH-K8S-030 | Namespace Not Found | Target namespace doesn't exist | High | Create namespace |
| HH-K8S-031 | Namespace Creation Failed | Cannot create new namespace | High | Check cluster permissions |
| HH-K8S-032 | Service Account Missing | Required service account doesn't exist | High | Create service account |
| HH-K8S-033 | RBAC Permission Denied | Service account lacks required permissions | High | Update cluster role bindings |
| HH-K8S-034 | Cluster Role Missing | Required cluster role not found | High | Create cluster role |
| HH-K8S-035 | Role Binding Failed | Cannot bind role to service account | High | Check RBAC configuration |

## Data Validation Errors (HH-VAL-xxx)

### Schema Validation Errors

| Code | Name | Description | Severity | Recovery |
|------|------|-------------|----------|----------|
| HH-VAL-001 | YAML Syntax Error | YAML file contains syntax errors | High | Correct YAML syntax |
| HH-VAL-002 | Invalid YAML Structure | YAML structure doesn't match expected format | High | Fix YAML structure |
| HH-VAL-003 | JSON Schema Validation Failed | Data doesn't match required JSON schema | High | Correct data format |
| HH-VAL-004 | Field Type Mismatch | Field value type doesn't match expected | High | Convert to correct type |
| HH-VAL-005 | Required Field Missing | Mandatory field not provided | High | Add required field |
| HH-VAL-006 | Invalid Field Value | Field contains invalid value | High | Provide valid value |

### Business Logic Validation Errors

| Code | Name | Description | Severity | Recovery |
|------|------|-------------|----------|----------|
| HH-VAL-010 | Invalid State Transition | Attempted state transition not allowed | High | Use valid transition path |
| HH-VAL-011 | Dependency Violation | Required dependency not met | High | Resolve dependencies first |
| HH-VAL-012 | Constraint Violation | Data violates business rule constraints | High | Correct constraint violation |
| HH-VAL-013 | Relationship Integrity Failed | Foreign key constraint violation | High | Fix relationship references |
| HH-VAL-014 | Unique Constraint Violation | Value must be unique but already exists | High | Use different unique value |

### Format Validation Errors

| Code | Name | Description | Severity | Recovery |
|------|------|-------------|----------|----------|
| HH-VAL-020 | Invalid Format | Data format doesn't match expected pattern | Medium | Correct data format |
| HH-VAL-021 | Range Validation Failed | Value outside acceptable range | Medium | Use value within range |
| HH-VAL-022 | Length Validation Failed | String length outside acceptable range | Medium | Adjust string length |
| HH-VAL-023 | Pattern Mismatch | Value doesn't match required regex | Medium | Match required pattern |
| HH-VAL-024 | Invalid Email Format | Email address format invalid | Medium | Correct email format |
| HH-VAL-025 | Invalid URL Format | URL format invalid | Medium | Correct URL format |

### Cross-Resource Validation Errors

| Code | Name | Description | Severity | Recovery |
|------|------|-------------|----------|----------|
| HH-VAL-030 | Reference Not Found | Referenced resource doesn't exist | High | Create referenced resource |
| HH-VAL-031 | Circular Dependency | Resources create circular reference | High | Break circular reference |
| HH-VAL-032 | Version Mismatch | Resource versions incompatible | High | Align resource versions |
| HH-VAL-033 | Namespace Mismatch | Resources in incompatible namespaces | Medium | Move to compatible namespace |
| HH-VAL-034 | Cross-Reference Invalid | Resource reference points to wrong type | High | Correct reference type |

## Network & Connectivity Errors (HH-NET-xxx)

### Connection Errors

| Code | Name | Description | Severity | Recovery |
|------|------|-------------|----------|----------|
| HH-NET-001 | Connection Timeout | Request timed out waiting for response | Medium | Retry with longer timeout |
| HH-NET-002 | Connection Refused | Target service refused connection | High | Check service availability |
| HH-NET-003 | DNS Resolution Failed | Cannot resolve hostname to IP address | High | Check DNS configuration |
| HH-NET-004 | Network Unreachable | Network routing prevents connection | High | Check network connectivity |
| HH-NET-005 | Port Blocked | Target port blocked by firewall | High | Configure firewall rules |
| HH-NET-006 | Proxy Configuration Error | HTTP proxy misconfigured | Medium | Fix proxy settings |

### Protocol Errors

| Code | Name | Description | Severity | Recovery |
|------|------|-------------|----------|----------|
| HH-NET-010 | TLS Handshake Failed | SSL/TLS negotiation failed | High | Check TLS configuration |
| HH-NET-011 | Certificate Verification Failed | TLS certificate validation failed | High | Update certificates |
| HH-NET-012 | HTTP Status Error | HTTP request returned error status | Medium | Handle status-specific error |
| HH-NET-013 | WebSocket Connection Failed | Cannot establish WebSocket connection | Medium | Fallback to HTTP polling |
| HH-NET-014 | Protocol Version Mismatch | Unsupported protocol version | Medium | Use compatible version |
| HH-NET-015 | Content Type Mismatch | Response content type unexpected | Low | Handle alternate content type |

### Service Availability Errors

| Code | Name | Description | Severity | Recovery |
|------|------|-------------|----------|----------|
| HH-NET-020 | Service Unavailable | Target service temporarily unavailable | Medium | Retry with exponential backoff |
| HH-NET-021 | Load Balancer Error | Load balancer cannot route request | High | Try alternate endpoints |
| HH-NET-022 | Circuit Breaker Open | Circuit breaker preventing requests | Medium | Wait for circuit breaker reset |
| HH-NET-023 | Health Check Failed | Service health check indicates problem | High | Check service health |
| HH-NET-024 | Rate Limit Exceeded | Request rate limit exceeded | Medium | Implement request throttling |
| HH-NET-025 | Bandwidth Limit Exceeded | Network bandwidth limit reached | Low | Queue requests for later |

## State Transition Errors (HH-STATE-xxx)

### Invalid Transition Errors

| Code | Name | Description | Severity | Recovery |
|------|------|-------------|----------|----------|
| HH-STATE-001 | Transition Not Allowed | Current state cannot transition to target | High | Use valid transition path |
| HH-STATE-002 | Condition Not Met | Required condition for transition not satisfied | High | Satisfy required conditions |
| HH-STATE-003 | Lock Conflict | Another process holds state transition lock | Medium | Wait for lock release |
| HH-STATE-004 | Version Conflict | State changed since last read | Medium | Refresh and retry |
| HH-STATE-005 | Transition Timeout | State transition exceeded time limit | Medium | Rollback incomplete transition |

### State Consistency Errors

| Code | Name | Description | Severity | Recovery |
|------|------|-------------|----------|----------|
| HH-STATE-010 | Inconsistent State | Entity in inconsistent internal state | High | Force state reconciliation |
| HH-STATE-011 | State Synchronization Failed | Cannot sync state across components | High | Manual state alignment |
| HH-STATE-012 | State Persistence Failed | Cannot save state changes to database | Critical | Investigate storage issues |
| HH-STATE-013 | State Recovery Failed | Cannot recover from corrupted state | Critical | Restore from backup |
| HH-STATE-014 | State Machine Invalid | State machine definition invalid | Critical | Fix state machine definition |

### Workflow State Errors

| Code | Name | Description | Severity | Recovery |
|------|------|-------------|----------|----------|
| HH-STATE-020 | Workflow Step Failed | Individual workflow step failed | High | Retry failed step |
| HH-STATE-021 | Workflow Timeout | Workflow exceeded maximum execution time | High | Cancel and rollback workflow |
| HH-STATE-022 | Workflow Rollback Failed | Cannot rollback partial workflow | Critical | Manual cleanup required |
| HH-STATE-023 | Workflow Dependency Failed | Dependent workflow step failed | High | Resolve dependency failure |
| HH-STATE-024 | Workflow Suspended | Workflow suspended awaiting external input | Medium | Resume when ready |

## Error Code Usage Patterns

### In Code Implementation

```python
from netbox_hedgehog.specifications.error_handling.error_codes import ErrorCodes

# Raise structured error
raise GitSyncError(
    code=ErrorCodes.HH_GIT_001,
    message="Repository not found: https://github.com/invalid/repo",
    context={
        'repository_url': 'https://github.com/invalid/repo',
        'operation': 'clone',
        'fabric_id': fabric.id
    }
)

# Check error type
if error.code == ErrorCodes.HH_AUTH_002:
    # Handle expired token
    attempt_token_refresh()
elif error.code in [ErrorCodes.HH_NET_001, ErrorCodes.HH_NET_002]:
    # Handle network issues
    schedule_retry_with_backoff()
```

### In Error Responses

```json
{
    "success": false,
    "error": {
        "code": "HH-GIT-001",
        "message": "Repository not found",
        "details": "The specified GitHub repository could not be accessed. Please verify the repository URL and ensure you have appropriate permissions.",
        "category": "git",
        "severity": "high",
        "recoverable": true,
        "recovery_suggestions": [
            "Verify repository URL is correct",
            "Check GitHub token permissions",
            "Ensure repository exists and is accessible"
        ]
    },
    "context": {
        "repository_url": "https://github.com/invalid/repo",
        "operation": "clone",
        "timestamp": "2024-01-15T10:30:00Z"
    }
}
```

### In Monitoring and Alerting

```yaml
# Prometheus alerting rules
groups:
  - name: hedgehog_plugin_errors
    rules:
      - alert: HighAuthFailureRate
        expr: rate(hedgehog_errors_total{code=~"HH-AUTH-.*"}[5m]) > 0.1
        for: 2m
        labels:
          severity: warning
        annotations:
          summary: High authentication failure rate detected
          
      - alert: CriticalStateErrors
        expr: hedgehog_errors_total{severity="critical"} > 0
        for: 0s
        labels:
          severity: critical
        annotations:
          summary: Critical state errors detected
```

This error code system provides a comprehensive foundation for consistent error handling, monitoring, and automated recovery across the entire NetBox Hedgehog Plugin.