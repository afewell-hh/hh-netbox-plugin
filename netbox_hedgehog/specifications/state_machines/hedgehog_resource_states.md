# HedgehogResource State Management Documentation

## Overview

HedgehogResource implements a **6-state GitOps lifecycle management system** that tracks the complete resource journey from draft creation through production deployment. This state machine handles the complex interaction between desired state (Git), actual state (Kubernetes), and draft state (uncommitted changes).

## Six-State Model

### Core States

1. **`DRAFT`** - Resource has uncommitted changes (local modifications)
2. **`COMMITTED`** - Resource changes committed to Git repository  
3. **`SYNCED`** - Resource is deployed and matches desired state
4. **`DRIFTED`** - Resource deployed but differs from desired state
5. **`ORPHANED`** - Resource exists in cluster but not in Git
6. **`PENDING`** - Resource exists in Git but not yet deployed

## State Transition Matrix

| From State | To State | Trigger | Required Conditions | Side Effects |
|-----------|----------|---------|-------------------|--------------|
| `DRAFT` | `COMMITTED` | Commit to Git | Draft changes exist, Git accessible | Clear draft_spec, update desired_spec |
| `COMMITTED` | `PENDING` | Git sync completed | Desired state updated from Git | Set desired_commit, desired_updated |
| `PENDING` | `SYNCED` | Kubernetes deployment | Resource deployed successfully | Set actual_spec, actual_status |
| `SYNCED` | `DRIFTED` | Drift detected | Actual ≠ Desired state | Update drift_details, drift_score |
| `DRIFTED` | `SYNCED` | Reconciliation completed | Drift resolved | Clear drift_details |
| `SYNCED` | `PENDING` | Git changes | New desired state from Git | Update desired_commit |
| `ORPHANED` | `COMMITTED` | Import to Git | Actual state imported to Git | Create desired_spec from actual_spec |
| `ORPHANED` | `DRAFT` | Begin editing | Start managing orphaned resource | Create draft_spec from actual_spec |
| Any | `ORPHANED` | Orphan detection | Resource in cluster, not in Git | Clear desired_spec |

## Advanced State Transitions

### Multi-Step Transitions

**Full GitOps Workflow**:
```
DRAFT → COMMITTED → PENDING → SYNCED
```

**Drift Resolution Workflow**:
```
DRIFTED → COMMITTED → PENDING → SYNCED
```

**Orphan Adoption Workflow**:
```
ORPHANED → DRAFT → COMMITTED → SYNCED
```

### Parallel State Updates

**Simultaneous Git and Cluster Changes**:
- Git update while in `SYNCED` → `PENDING`
- Cluster drift while transitioning → `DRIFTED` 
- Handle race conditions with timestamps

## State Triggers

### Automatic Triggers (System Actions)

1. **Git Repository Sync**:
   - `sync_desired_state()` → Updates from Git repository
   - New commits detected → `SYNCED` to `PENDING`
   - File deletions → Resource to `ORPHANED` (if still in cluster)

2. **Kubernetes Cluster Sync**:
   - `sync_actual_state()` → Updates from cluster
   - Resource deployment → `PENDING` to `SYNCED`
   - Resource deletion → Any state to removal

3. **Drift Detection**:
   - `calculate_drift()` → Compare desired vs actual
   - Periodic drift monitoring → `SYNCED` to `DRIFTED`
   - Real-time watch events → Immediate drift detection

4. **Reconciliation Operations**:
   - GitOps sync triggered → `PENDING` to `SYNCED`
   - Manual sync → `DRIFTED` to `SYNCED`
   - Conflict resolution → State based on outcome

### Manual Triggers (User Actions)

1. **Draft Management**:
   - User edits resource → Any state to `DRAFT`
   - Save draft changes → Update draft_spec
   - Discard draft → Return to previous state

2. **Git Operations**:
   - Commit changes → `DRAFT` to `COMMITTED`
   - Push to repository → Trigger Git sync
   - Import orphaned resource → `ORPHANED` to `COMMITTED`

3. **Kubernetes Operations**:
   - Manual deployment → Apply desired state
   - Resource deletion → Remove from cluster
   - Force reconciliation → Resolve drift

## Drift Analysis System

### Drift Status Types

**Within HedgehogResource**:
- `in_sync` - Desired and actual states match
- `spec_drift` - Specifications differ
- `desired_only` - Resource in Git but not cluster  
- `actual_only` - Resource in cluster but not Git
- `creation_pending` - Waiting for deployment
- `deletion_pending` - Waiting for removal

### Drift Calculation

**Drift Score Calculation**:
```python
def calculate_drift_score(desired_spec, actual_spec):
    """Calculate numerical drift score (0.0 = perfect match, 1.0 = completely different)"""
    if not desired_spec and not actual_spec:
        return 0.0  # Both missing = no drift
    
    if not desired_spec or not actual_spec:
        return 1.0  # One missing = complete drift
    
    # Field-by-field comparison
    all_keys = set(desired_spec.keys()) | set(actual_spec.keys())
    different_keys = []
    
    for key in all_keys:
        if key not in desired_spec or key not in actual_spec:
            different_keys.append(key)
        elif desired_spec[key] != actual_spec[key]:
            different_keys.append(key)
    
    # Calculate percentage difference
    if all_keys:
        return len(different_keys) / len(all_keys)
    return 0.0
```

**Drift Severity Classification**:
- `drift_score` 0.0-0.1 → `low` severity
- `drift_score` 0.1-0.5 → `medium` severity  
- `drift_score` 0.5-0.8 → `high` severity
- `drift_score` 0.8-1.0 → `critical` severity

## Error Conditions and Recovery

### Invalid State Transitions

**Detection**:
```python
INVALID_TRANSITIONS = {
    'DRAFT': ['SYNCED', 'DRIFTED', 'ORPHANED'],  # Cannot skip commit
    'COMMITTED': ['DRIFTED', 'ORPHANED'],        # Must deploy first
    'PENDING': ['DRAFT', 'COMMITTED'],           # Must resolve deployment
    'SYNCED': ['PENDING'],                       # Need new desired state
    'DRIFTED': ['PENDING'],                      # Must reconcile first
    'ORPHANED': ['SYNCED', 'PENDING']            # Must import or edit first
}
```

**Recovery Actions**:
- Validate transition before execution
- Reject invalid transitions with explanation
- Suggest correct transition path

### State Inconsistencies

**Common Issues**:
1. **Missing Required Data**:
   - `COMMITTED` without `desired_spec`
   - `SYNCED` without `actual_spec`
   - `DRIFTED` without `drift_details`

2. **Timestamp Inconsistencies**:
   - `actual_updated` newer than `desired_updated` in `SYNCED`
   - Missing `last_state_change` timestamp

3. **Drift Score Mismatches**:
   - `SYNCED` state with non-zero drift score
   - `DRIFTED` state with zero drift score

**Automatic Recovery**:
```python
def validate_and_fix_resource_state(resource):
    """Validate resource state and attempt automatic fixes"""
    fixes_applied = []
    
    # Fix missing drift calculation
    if resource.resource_state in ['SYNCED', 'DRIFTED']:
        if not resource.drift_details:
            resource.calculate_drift()
            fixes_applied.append('recalculated_drift')
    
    # Fix inconsistent drift status
    if resource.resource_state == 'SYNCED' and resource.drift_score > 0.1:
        resource.resource_state = 'DRIFTED'
        resource.state_change_reason = 'Auto-corrected: drift detected'
        fixes_applied.append('corrected_to_drifted')
    
    # Fix missing timestamps
    if not resource.last_state_change:
        resource.last_state_change = timezone.now()
        fixes_applied.append('added_timestamp')
    
    if fixes_applied:
        resource.save()
        log_state_fixes(resource, fixes_applied)
    
    return len(fixes_applied) > 0
```

## State Persistence and History

### StateTransitionHistory Tracking

**Transition Logging**:
```python
def log_state_transition(resource, old_state, new_state, trigger, user=None, context=None):
    """Log resource state transition with full context"""
    StateTransitionHistory.objects.create(
        resource=resource,
        from_state=old_state,
        to_state=new_state,
        trigger=trigger,
        reason=context.get('reason', '') if context else '',
        context=context or {},
        user=user
    )
```

**History Analysis**:
- State transition patterns
- Time spent in each state
- Failure rate analysis
- User behavior tracking

### Dependency Tracking

**Resource Dependencies**:
```python
def update_dependency_chain(resource):
    """Update dependent resources when this resource changes state"""
    dependents = resource.dependency_of.all()
    
    for dependent in dependents:
        if resource.resource_state == 'DRIFTED':
            # Mark dependent as potentially affected
            dependent.recalculate_dependencies()
        elif resource.resource_state == 'SYNCED':
            # Check if dependent can now proceed
            check_dependent_readiness(dependent)
```

## Agent Implementation Guidelines

### State Transition Execution

```python
def execute_state_transition(resource, new_state, trigger, user=None, context=None):
    """Execute resource state transition with validation"""
    old_state = resource.resource_state
    
    # Validate transition
    if not is_valid_transition(old_state, new_state):
        invalid_transitions = INVALID_TRANSITIONS.get(old_state, [])
        if new_state in invalid_transitions:
            raise InvalidStateTransition(
                f"Cannot transition from {old_state} to {new_state}. "
                f"Suggested path: {get_suggested_transition_path(old_state, new_state)}"
            )
    
    # Pre-transition hooks
    pre_transition_result = execute_pre_transition_hooks(resource, old_state, new_state)
    if not pre_transition_result.success:
        raise StateTransitionError(pre_transition_result.error)
    
    # Update state
    resource.resource_state = new_state
    resource.last_state_change = timezone.now()
    resource.state_change_reason = context.get('reason', f'Transitioned via {trigger}')
    
    # State-specific updates
    if new_state == 'COMMITTED':
        resource.desired_commit = context.get('commit_sha')
        resource.desired_updated = timezone.now()
        resource.draft_spec = None  # Clear draft
        
    elif new_state == 'SYNCED':
        resource.calculate_drift()  # Should result in in_sync
        
    elif new_state == 'DRIFTED':
        if not resource.drift_details:
            resource.calculate_drift()
    
    # Save changes
    resource.save()
    
    # Log transition
    log_state_transition(resource, old_state, new_state, trigger, user, context)
    
    # Post-transition hooks
    execute_post_transition_hooks(resource, old_state, new_state)
    
    # Update dependencies
    update_dependency_chain(resource)
    
    return True
```

### Drift Monitoring

```python
async def monitor_resource_drift(resource):
    """Monitor individual resource for drift"""
    if resource.resource_state not in ['SYNCED', 'DRIFTED']:
        return  # Only monitor deployed resources
    
    try:
        # Fetch current actual state
        actual_state = await fetch_kubernetes_resource_state(resource)
        
        # Update actual state
        if actual_state:
            resource.update_actual_state(
                actual_state.spec,
                actual_state.status,
                actual_state.resource_version
            )
        
        # Calculate drift
        drift_result = resource.calculate_drift()
        
        # Handle state transition based on drift
        if resource.resource_state == 'SYNCED' and drift_result.get('drift_status') != 'in_sync':
            execute_state_transition(
                resource, 'DRIFTED', 
                'drift_detected', 
                context={'drift_score': resource.drift_score}
            )
            
        elif resource.resource_state == 'DRIFTED' and drift_result.get('drift_status') == 'in_sync':
            execute_state_transition(
                resource, 'SYNCED', 
                'drift_resolved',
                context={'reconciliation_successful': True}
            )
            
    except Exception as e:
        log_drift_monitoring_error(resource, e)
        # Don't change state on monitoring errors
```

### Batch State Operations

```python
def batch_update_resource_states(resources, operation, context=None):
    """Perform batch state updates with transaction safety"""
    results = []
    
    with transaction.atomic():
        for resource in resources:
            try:
                if operation == 'sync_from_git':
                    if resource.resource_state in ['COMMITTED', 'DRIFTED']:
                        execute_state_transition(
                            resource, 'PENDING', 
                            'git_sync', context=context
                        )
                        results.append({'resource': resource.id, 'success': True})
                    else:
                        results.append({
                            'resource': resource.id, 
                            'success': False, 
                            'error': f'Invalid state for git sync: {resource.resource_state}'
                        })
                        
                elif operation == 'reconcile_drift':
                    if resource.resource_state == 'DRIFTED':
                        execute_state_transition(
                            resource, 'SYNCED', 
                            'reconciliation', context=context
                        )
                        results.append({'resource': resource.id, 'success': True})
                    else:
                        results.append({
                            'resource': resource.id,
                            'success': False, 
                            'error': f'Not in drifted state: {resource.resource_state}'
                        })
                        
            except Exception as e:
                results.append({
                    'resource': resource.id, 
                    'success': False, 
                    'error': str(e)
                })
    
    return results
```

## Integration Points

### With HedgehogFabric States
- Fabric `sync_status` aggregates resource states
- Fabric drift count reflects `DRIFTED` resources
- Fabric reconciliation triggers resource state updates

### With GitRepository States  
- Repository connection failures prevent `COMMITTED` → `PENDING`
- Git sync operations update multiple resource states
- Repository authentication affects state transitions

### With ReconciliationAlert States
- `DRIFTED` resources generate reconciliation alerts
- Alert resolution triggers state transitions
- Orphaned resources create import alerts

This comprehensive state management enables agents to handle the complete GitOps resource lifecycle with full error recovery and consistency guarantees.