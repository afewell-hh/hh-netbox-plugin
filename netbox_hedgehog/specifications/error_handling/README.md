# Error Handling Catalog for NetBox Hedgehog Plugin

## Overview

This directory contains comprehensive error scenario catalogs for all major failure modes in the NetBox Hedgehog Plugin. The documentation enables agents to understand, detect, and appropriately handle failures with structured error responses and automated recovery procedures.

## Problem Statement

The NetBox Hedgehog Plugin manages complex GitOps workflows with multiple failure modes:
- Git/GitHub synchronization failures
- Kubernetes API connectivity and CRD validation errors  
- Authentication and authorization failures
- Network timeouts and connectivity issues
- Data validation and state transition errors

Without centralized error handling catalogs, agents struggle with:
- Inconsistent error responses across components
- Unclear recovery procedures for different failure types
- Missing automated error detection and resolution
- Poor error escalation and notification strategies

## Directory Structure

```
error_handling/
├── README.md                    # This overview and usage guide
├── error_taxonomy.md           # Complete error classification system
├── recovery_procedures.md      # Standard recovery workflows  
├── error_codes.md              # Structured error code definitions
├── scenarios/                  # Detailed scenario documentation
│   ├── git_sync_errors.md      # Git/GitHub integration failures
│   ├── kubernetes_errors.md    # K8s API and CRD failures
│   ├── authentication_errors.md # Auth and permission failures  
│   ├── validation_errors.md    # Data validation failures
│   └── network_errors.md       # Connectivity and timeout failures
└── examples/                   # Code examples and test cases
    ├── error_detection.py      # Error detection patterns
    ├── error_handlers.py       # Exception handling templates
    ├── recovery_workflows.py   # Automated recovery examples
    └── test_scenarios.py       # Error scenario test cases
```

## Error Code System

The plugin uses a structured error code system with prefixes:

| Prefix | Category | Example |
|--------|----------|---------|
| **HH-AUTH-xxx** | Authentication/Authorization | HH-AUTH-001: Invalid GitHub token |
| **HH-GIT-xxx** | Git/GitHub Operations | HH-GIT-003: Repository not found |
| **HH-K8S-xxx** | Kubernetes API | HH-K8S-005: CRD validation failed |
| **HH-VAL-xxx** | Data Validation | HH-VAL-002: Invalid YAML structure |
| **HH-NET-xxx** | Network/Connectivity | HH-NET-001: Connection timeout |
| **HH-STATE-xxx** | State Transitions | HH-STATE-004: Invalid transition |

## Integration with SPARC Infrastructure

This error catalog integrates with the broader SPARC Agent Infrastructure:

### Phase 0.1: Machine-Readable Contracts (Issue #19)
- Error types defined in service contracts
- Structured error responses in OpenAPI specifications
- Pydantic models for error validation

### Phase 0.2: State Transition Documentation (Issue #20)  
- Error conditions documented for each state transition
- State-specific error recovery procedures
- Invalid transition error scenarios

### Phase 0.3: Error Scenario Catalogs (This Phase)
- Comprehensive failure mode documentation
- Structured error codes and recovery procedures
- Agent-readable error handling patterns

## Agent Usage Guidelines

### 1. Error Detection

Agents should use structured error detection patterns:

```python
from netbox_hedgehog.specifications.error_handling.examples.error_detection import (
    detect_error_type,
    get_error_context
)

# Detect error type from exception
error_info = detect_error_type(exception)
error_code = error_info['code']  # e.g., 'HH-GIT-001'
category = error_info['category']  # e.g., 'git_sync'
severity = error_info['severity']  # e.g., 'high'

# Get contextual information
context = get_error_context(error_code, entity, operation)
```

### 2. Structured Error Handling

Use consistent error handling patterns:

```python
from netbox_hedgehog.specifications.error_handling.examples.error_handlers import (
    GitSyncErrorHandler,
    KubernetesErrorHandler
)

# Git sync error handling
git_handler = GitSyncErrorHandler()
try:
    result = perform_git_sync(fabric)
except Exception as e:
    error_response = git_handler.handle_error(e, context={
        'fabric_id': fabric.id,
        'operation': 'sync',
        'user': 'system'
    })
    
    if error_response['recoverable']:
        # Attempt automatic recovery
        recovery_result = git_handler.attempt_recovery(error_response)
    else:
        # Escalate for manual intervention
        create_alert(error_response)
```

### 3. Automated Recovery

Implement recovery workflows based on error type:

```python
from netbox_hedgehog.specifications.error_handling.examples.recovery_workflows import (
    execute_recovery_workflow
)

# Execute appropriate recovery workflow
recovery_result = execute_recovery_workflow(
    error_code='HH-GIT-003',
    context={
        'fabric': fabric,
        'repository_url': fabric.git_repository_url,
        'error_details': error_details
    }
)

if recovery_result['success']:
    logger.info(f"Automatic recovery successful: {recovery_result['actions']}")
else:
    logger.error(f"Recovery failed: {recovery_result['reason']}")
    # Escalate to manual resolution
```

## Error Severity Levels

| Level | Description | Response |
|-------|-------------|----------|
| **LOW** | Minor issues, degraded functionality | Log warning, continue operation |
| **MEDIUM** | Significant issues, some features affected | Alert administrators, attempt recovery |
| **HIGH** | Major failures, core functionality affected | Immediate attention, automatic recovery |
| **CRITICAL** | System-wide failures, service disruption | Emergency response, escalate immediately |

## Recovery Strategies

### Automatic Recovery
- **Retry Logic**: Exponential backoff for transient failures
- **Fallback Operations**: Alternative approaches when primary fails
- **State Rollback**: Return to known-good state when possible
- **Resource Cleanup**: Clean up partial operations on failure

### Manual Recovery
- **Clear Instructions**: Step-by-step recovery procedures
- **Diagnostic Tools**: Commands and scripts for troubleshooting  
- **Escalation Paths**: When to involve different teams/expertise
- **Recovery Validation**: How to verify successful recovery

## Testing Error Scenarios

Use the provided test scenarios to validate error handling:

```python
from netbox_hedgehog.specifications.error_handling.examples.test_scenarios import (
    GitSyncErrorScenarios,
    KubernetesErrorScenarios
)

# Test git sync error scenarios
git_scenarios = GitSyncErrorScenarios()

# Test authentication failure
auth_result = git_scenarios.test_authentication_failure()
assert auth_result['error_code'] == 'HH-AUTH-001'
assert auth_result['recovery_attempted'] == True

# Test repository not found
repo_result = git_scenarios.test_repository_not_found()
assert repo_result['error_code'] == 'HH-GIT-003'
assert 'repository_url' in repo_result['context']
```

## Integration Points

### With Existing Components

1. **Django Models**: Error information stored in model fields
2. **Celery Tasks**: Structured error handling in async operations  
3. **API Endpoints**: Consistent error responses across REST APIs
4. **WebSocket Events**: Real-time error notifications to UI
5. **Logging System**: Structured error logging with context

### With Monitoring Systems

1. **Metrics Collection**: Error rates and types tracked
2. **Alerting Rules**: Automatic alerts based on error patterns
3. **Dashboard Visualization**: Error trends and hotspots
4. **SLA Monitoring**: Impact of errors on service levels

## Best Practices

### For Error Handling
1. **Always Use Error Codes**: Every error should have a structured code
2. **Include Context**: Provide enough information for debugging
3. **Log Appropriately**: Use correct log levels and structured data
4. **Recovery First**: Attempt automatic recovery when safe
5. **User-Friendly Messages**: Provide clear guidance to users

### For Error Documentation
1. **Keep Updated**: Regularly review and update error scenarios
2. **Real Examples**: Use actual error messages and stack traces
3. **Test Scenarios**: Validate error handling with automated tests
4. **Clear Recovery**: Provide step-by-step recovery instructions
5. **Cross-Reference**: Link to related state transitions and contracts

## Maintenance

This error catalog should be updated when:

- New error conditions are discovered
- Recovery procedures change or improve
- New components are added to the system
- Error patterns change due to infrastructure updates
- Agent feedback identifies missing or unclear scenarios

## Getting Started

1. **Review Error Taxonomy**: Start with `error_taxonomy.md` for complete classification
2. **Check Error Codes**: Reference `error_codes.md` for specific error definitions
3. **Study Scenarios**: Read relevant scenario files for your use case
4. **Implement Handlers**: Use examples to build appropriate error handling
5. **Test Thoroughly**: Validate error handling with provided test scenarios

For specific error scenarios, refer to the detailed documentation files in the `scenarios/` directory.