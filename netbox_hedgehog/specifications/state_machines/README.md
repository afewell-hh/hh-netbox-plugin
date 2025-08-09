# State Machine Documentation for NetBox Hedgehog Plugin

## Overview

This directory contains comprehensive state transition documentation for all NetBox Hedgehog Plugin entities with complex state management. The documentation is designed to eliminate agent confusion about state management and provide clear guidance for automated operations.

## Problem Statement

The NetBox Hedgehog Plugin manages complex GitOps workflows with multiple interacting state dimensions:

- **HedgehogFabric**: Three independent status fields (configuration, connection, sync)  
- **GitRepository**: Authentication and connection lifecycle management
- **HedgehogResource**: Six-state GitOps workflow (draft → committed → synced)
- **ReconciliationAlert**: Drift detection and remediation workflow management

Without clear state documentation, agents struggle with:
- Invalid state transitions
- Missing required conditions 
- Unclear error recovery paths
- Inconsistent state management

## Documentation Structure

### Core State Documentation

| File | Purpose | Agent Use Case |
|------|---------|---------------|
| [`hedgehog_fabric_states.md`](hedgehog_fabric_states.md) | Three-dimensional fabric state management | Understand fabric lifecycle, connection health, sync status |
| [`git_repository_states.md`](git_repository_states.md) | Git authentication and connection states | Handle repository authentication, credential rotation |
| [`hedgehog_resource_states.md`](hedgehog_resource_states.md) | Six-state GitOps resource lifecycle | Manage complete resource deployment workflow |
| [`reconciliation_states.md`](reconciliation_states.md) | Drift detection and alert workflow | Handle automated drift detection and remediation |

### Visual Diagrams

| File | Purpose | Agent Use Case |
|------|---------|---------------|
| [`state_diagrams/hedgehog_fabric_diagram.md`](state_diagrams/hedgehog_fabric_diagram.md) | Fabric state visualization | Visual understanding of fabric state interactions |
| [`state_diagrams/git_repository_diagram.md`](state_diagrams/git_repository_diagram.md) | Repository authentication flows | Visual guide to git connection management |
| [`state_diagrams/hedgehog_resource_diagram.md`](state_diagrams/hedgehog_resource_diagram.md) | GitOps resource workflow diagrams | Visual GitOps lifecycle understanding |
| [`state_diagrams/reconciliation_diagram.md`](state_diagrams/reconciliation_diagram.md) | Alert workflow visualizations | Visual drift detection and resolution workflows |

### Reference Materials

| File | Purpose | Agent Use Case |
|------|---------|---------------|
| [`state_transition_matrices.md`](state_transition_matrices.md) | Comprehensive transition tables | Authoritative reference for valid transitions |

## Agent Implementation Guidelines

### 1. State Validation Before Transitions

**Always validate state transitions before execution**:

```python
def validate_transition(entity, from_state, to_state):
    """Validate state transition is allowed"""
    # Check state transition matrices
    valid_transitions = get_valid_transitions(entity.__class__, from_state)
    
    if to_state not in valid_transitions:
        raise InvalidTransitionError(
            f"Cannot transition {entity} from {from_state} to {to_state}"
        )
    
    # Check required conditions
    conditions = get_transition_conditions(entity.__class__, from_state, to_state)
    for condition in conditions:
        if not condition.check(entity):
            raise TransitionConditionError(
                f"Condition not met for {from_state} → {to_state}: {condition.description}"
            )
```

### 2. Atomic State Changes

**Use database transactions for state changes**:

```python
from django.db import transaction

@transaction.atomic
def execute_state_transition(entity, new_state, trigger, context=None):
    """Execute state transition atomically"""
    old_state = entity.get_current_state()
    
    # Validate transition
    validate_transition(entity, old_state, new_state)
    
    # Update state
    entity.update_state(new_state, trigger, context)
    
    # Log transition
    log_state_transition(entity, old_state, new_state, trigger, context)
    
    # Execute side effects
    execute_transition_side_effects(entity, old_state, new_state, context)
```

### 3. Error Recovery Patterns

**Implement automatic error recovery where possible**:

```python
def handle_state_error(entity, error):
    """Handle state-related errors with recovery"""
    if isinstance(error, InvalidTransitionError):
        # Attempt to find valid transition path
        suggested_path = find_transition_path(
            entity.get_current_state(), 
            error.target_state
        )
        if suggested_path:
            return execute_transition_sequence(entity, suggested_path)
        else:
            raise error
    
    elif isinstance(error, TransitionConditionError):
        # Attempt to resolve condition
        if error.condition.can_auto_resolve():
            error.condition.resolve(entity)
            # Retry original transition
            return execute_state_transition(entity, error.target_state, error.trigger)
        else:
            # Escalate for manual resolution
            create_manual_resolution_alert(entity, error)
```

### 4. State Consistency Monitoring

**Implement periodic state consistency checks**:

```python
def monitor_state_consistency():
    """Monitor and fix state inconsistencies"""
    # Check for invalid state combinations
    inconsistencies = validate_system_state_consistency()
    
    for inconsistency in inconsistencies:
        if inconsistency.can_auto_fix():
            fix_state_inconsistency(inconsistency)
            log_state_fix(inconsistency)
        else:
            create_consistency_alert(inconsistency)
```

## Integration with Contracts (Issue #19)

This state documentation integrates seamlessly with the component contracts created in Issue #19:

### Pydantic Model Integration

**State validation uses contract models**:

```python
from netbox_hedgehog.contracts.models.gitops import HedgehogResourceContract

def validate_resource_state_transition(resource, new_state):
    """Validate resource state using contracts"""
    contract = HedgehogResourceContract.from_orm(resource)
    
    # Use contract validation
    if not contract.can_transition_to(new_state):
        raise InvalidTransitionError(
            f"Resource {resource.name} cannot transition to {new_state}"
        )
    
    # Validate required fields for new state
    required_fields = get_state_required_fields(new_state)
    contract.validate_fields_present(required_fields)
```

### Service Interface Integration

**State management through service interfaces**:

```python
from netbox_hedgehog.contracts.services.gitops import GitOpsService

class StatefulGitOpsService(GitOpsService):
    """GitOps service with state management"""
    
    def deploy_resource(self, resource: HedgehogResourceContract):
        """Deploy resource with proper state management"""
        # Validate current state allows deployment
        if resource.resource_state != 'PENDING':
            raise InvalidStateError("Resource must be PENDING to deploy")
        
        # Execute deployment
        result = super().deploy_resource(resource)
        
        # Update state based on result
        if result.success:
            resource.transition_to('SYNCED', 'deployment_success')
        else:
            # Handle deployment failure
            resource.add_error(result.error)
```

## Error Scenarios Documentation (Issue #21)

This state documentation provides the foundation for Issue #21 error scenarios by:

1. **Identifying Error Conditions**: Each state document lists error conditions and recovery paths
2. **Defining Recovery Actions**: Clear recovery procedures for each error type  
3. **Providing Error Context**: Detailed error classification and handling strategies

### Integration with Error Handling System

The comprehensive error handling system created in Issue #21 integrates with state management through:

**State Transition Errors (HH-STATE-xxx)**:
```python
from netbox_hedgehog.specifications.error_handling import detect_error_type, execute_recovery_workflow

def safe_state_transition(entity, target_state, trigger, context=None):
    """Execute state transition with comprehensive error handling"""
    try:
        return execute_state_transition(entity, target_state, trigger, context)
    except Exception as e:
        # Detect specific error type using error catalog
        error_info = detect_error_type(e, {
            'entity_type': entity.__class__.__name__,
            'entity_id': getattr(entity, 'id', None),
            'current_state': entity.get_current_state(),
            'target_state': target_state,
            'trigger': trigger
        })
        
        if error_info.get('detected'):
            # Execute automated recovery if available
            recovery_result = execute_recovery_workflow(
                error_info['code'], 
                error_info.get('context', {})
            )
            
            if recovery_result.success:
                # Retry transition after recovery
                return execute_state_transition(entity, target_state, trigger, context)
        
        # Re-raise with enhanced error information
        raise StateTransitionError(
            code=error_info.get('code', 'HH-STATE-999'),
            message=error_info.get('message', str(e)),
            entity=entity,
            transition=f"{entity.get_current_state()} → {target_state}"
        )
```

**Error Recovery Integration**:
- **HH-STATE-001**: Invalid transition detection uses state matrices for recovery path finding
- **HH-STATE-010**: Inconsistent state recovery uses state consistency rules  
- **HH-STATE-020**: Workflow step failures integrate with entity state rollback procedures
- **HH-AUTH-xxx**: Authentication errors during state sync trigger credential refresh
- **HH-K8S-xxx**: Kubernetes errors during resource deployment update resource states appropriately

## Usage Examples

### Example 1: Fabric Lifecycle Management

```python
# Create new fabric
fabric = HedgehogFabric.objects.create(name="test-fabric")
# Initial state: status=PLANNED, connection_status=UNKNOWN, sync_status=NEVER_SYNCED

# Configure and activate
fabric.kubernetes_server = "https://k8s.example.com"
fabric.set_kubernetes_credentials(token="...")

# Test connection
connection_result = fabric.test_connection()
if connection_result['success']:
    # State: connection_status=CONNECTED
    
    # Activate fabric
    fabric.transition_status('ACTIVE', 'manual_activation')
    # State: status=ACTIVE
    
    # Perform first sync
    sync_result = fabric.sync_actual_state()
    if sync_result['success']:
        # State: sync_status=IN_SYNC
        pass
```

### Example 2: Resource GitOps Workflow

```python
# Create draft resource
resource = HedgehogResource.objects.create(
    fabric=fabric,
    name="test-vpc",
    kind="VPC",
    draft_spec={"subnets": ["10.1.0.0/24"]}
)
# Initial state: resource_state=DRAFT

# Commit to Git
commit_result = resource.commit_to_git(user=request.user)
if commit_result['success']:
    # State: resource_state=COMMITTED
    
    # Git sync occurs (automated)
    # State: resource_state=PENDING
    
    # GitOps deployment occurs (automated)  
    # State: resource_state=SYNCED
    
    # Monitor for drift
    drift_result = resource.calculate_drift()
    if drift_result.get('has_drift'):
        # State: resource_state=DRIFTED
        # Automatic alert generation occurs
```

### Example 3: Alert Resolution Workflow

```python
# Drift alert created automatically
alert = ReconciliationAlert.objects.get(
    resource=resource,
    alert_type='drift_detected',
    status='ACTIVE'
)

# User acknowledges alert
alert.acknowledge(user=request.user)
# State: status=ACKNOWLEDGED

# Execute resolution
resolution_result = alert.execute_resolution_action('update_git', user=request.user)
if resolution_result['success']:
    # State: status=RESOLVED
    # Resource state updated accordingly
```

## Best Practices for Agents

1. **Always Check Current State**: Never assume state, always check current values
2. **Validate Before Transition**: Use state matrices to verify transitions are valid
3. **Handle Errors Gracefully**: Implement comprehensive error handling with recovery
4. **Log All Transitions**: Maintain audit trail for debugging and compliance
5. **Monitor Consistency**: Implement periodic consistency checks
6. **Use Atomic Operations**: Ensure state changes are transactional
7. **Respect Dependencies**: Consider cross-entity state dependencies

## Integration Points

This state documentation integrates with:

- **Issue #19 Contracts**: Type-safe state management through Pydantic models
- **Issue #21 Error Scenarios**: Foundation for comprehensive error handling
- **Monitoring Systems**: State transition metrics and alerting
- **User Interface**: State-aware UI components and user guidance
- **API Endpoints**: RESTful state transition endpoints with validation

## Maintenance

This documentation should be updated when:

- New states are added to any entity
- State transition logic changes
- New error conditions are identified  
- Integration requirements change
- Agent feedback identifies unclear areas

For questions or clarifications about state management, refer to the detailed entity-specific documentation or consult the state transition matrices for authoritative transition rules.