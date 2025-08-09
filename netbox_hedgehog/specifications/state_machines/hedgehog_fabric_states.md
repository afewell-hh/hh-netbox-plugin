# HedgehogFabric State Management Documentation

## Overview

HedgehogFabric has **three independent state dimensions** that interact to provide comprehensive lifecycle management:

1. **Configuration Status** (`status`) - Business lifecycle state
2. **Connection Status** (`connection_status`) - Technical connectivity state  
3. **Sync Status** (`sync_status`) - Data synchronization state

This three-dimensional state space allows agents to understand fabric readiness and automatically handle state transitions.

## State Dimensions

### 1. Configuration Status (`status` field)

**Purpose**: Represents the business/operational lifecycle of the fabric.

**Valid States**:
- `PLANNED` - Fabric is being planned but not yet active
- `ACTIVE` - Fabric is operational and ready for use
- `MAINTENANCE` - Fabric is temporarily unavailable for maintenance
- `DECOMMISSIONED` - Fabric is permanently offline

**State Transitions**:
```
PLANNED → ACTIVE (fabric deployment complete)
ACTIVE → MAINTENANCE (planned maintenance)  
MAINTENANCE → ACTIVE (maintenance complete)
ACTIVE → DECOMMISSIONED (permanent shutdown)
MAINTENANCE → DECOMMISSIONED (shutdown during maintenance)
```

### 2. Connection Status (`connection_status` field)

**Purpose**: Represents the technical ability to connect to the Kubernetes cluster.

**Valid States**:
- `UNKNOWN` - Connection not yet tested
- `CONNECTED` - Successfully connected to Kubernetes API
- `FAILED` - Connection attempt failed
- `TESTING` - Connection test in progress

**State Transitions**:
```
UNKNOWN → TESTING (connection test initiated)
TESTING → CONNECTED (test successful)
TESTING → FAILED (test failed)
CONNECTED → TESTING (retest initiated)
FAILED → TESTING (retry connection)
CONNECTED → FAILED (connection lost)
```

### 3. Sync Status (`sync_status` field)

**Purpose**: Represents the state of data synchronization with Kubernetes cluster.

**Valid States**:
- `NEVER_SYNCED` - No synchronization attempted
- `IN_SYNC` - Data is synchronized with cluster
- `OUT_OF_SYNC` - Data diverged from cluster
- `SYNCING` - Synchronization in progress
- `ERROR` - Synchronization failed with errors

**State Transitions**:
```
NEVER_SYNCED → SYNCING (first sync initiated)
SYNCING → IN_SYNC (sync completed successfully)
SYNCING → ERROR (sync failed)
IN_SYNC → SYNCING (scheduled sync started)
IN_SYNC → OUT_OF_SYNC (drift detected)
OUT_OF_SYNC → SYNCING (reconciliation started)
ERROR → SYNCING (retry sync)
```

## State Interaction Matrix

| Config Status | Connection Status | Sync Status | Agent Action Required |
|---------------|-------------------|-------------|----------------------|
| PLANNED | UNKNOWN | NEVER_SYNCED | Test connection when ready |
| PLANNED | CONNECTED | NEVER_SYNCED | Ready for initial sync |
| ACTIVE | CONNECTED | IN_SYNC | Normal operation |
| ACTIVE | CONNECTED | OUT_OF_SYNC | Trigger reconciliation |
| ACTIVE | FAILED | ANY | Alert: Connection issue |
| MAINTENANCE | ANY | ANY | Suspend operations |
| DECOMMISSIONED | ANY | ANY | Cleanup resources |

## State Triggers

### Automatic Triggers (System Actions)

1. **Connection Status Changes**:
   - `test_connection()` → Updates `connection_status`
   - Kubernetes API errors → `CONNECTED` to `FAILED`
   - Periodic health checks → `CONNECTED` to `TESTING`

2. **Sync Status Changes**:
   - `sync_actual_state()` → Updates `sync_status`
   - Drift detection → `IN_SYNC` to `OUT_OF_SYNC`
   - Real-time watch events → State validation

3. **Configuration Status Changes**:
   - ArgoCD installation completion → `PLANNED` to `ACTIVE`
   - Manual maintenance mode → `ACTIVE` to `MAINTENANCE`

### Manual Triggers (User Actions)

1. **Connection Management**:
   - Update Kubernetes credentials → `connection_status` to `TESTING`
   - Manual connection test → Current state to `TESTING`

2. **Sync Management**:
   - Manual sync trigger → Current state to `SYNCING`
   - Force reconciliation → `OUT_OF_SYNC` to `SYNCING`

3. **Lifecycle Management**:
   - Fabric activation → `PLANNED` to `ACTIVE`
   - Maintenance scheduling → `ACTIVE` to `MAINTENANCE`

## Error Conditions and Recovery

### Connection Failures

**Condition**: `connection_status` = `FAILED`

**Recovery Paths**:
1. **Credential Issues**: Update authentication → Retry connection
2. **Network Issues**: Wait for connectivity → Auto-retry
3. **Cluster Down**: Monitor cluster status → Retry when available

**Agent Actions**:
- Generate connectivity alert
- Suspend sync operations
- Retry with exponential backoff

### Sync Errors

**Condition**: `sync_status` = `ERROR`

**Recovery Paths**:
1. **Transient Errors**: Automatic retry with backoff
2. **Permission Issues**: Update credentials → Retry
3. **Resource Conflicts**: Manual intervention → Resume sync

**Agent Actions**:
- Log specific error details
- Create reconciliation alerts
- Attempt automated recovery

### State Inconsistencies

**Detection**: State combinations that shouldn't occur
- `ACTIVE` + `FAILED` + `IN_SYNC` (impossible combination)
- `DECOMMISSIONED` + `CONNECTED` + `SYNCING` (contradictory states)

**Recovery**: Force state validation and correction

## State Persistence

### Fields Updated During Transitions

1. **Connection State Changes**:
   - `connection_status` - New status value
   - `last_validated` - Timestamp of last successful test
   - `connection_error` - Error message if failed

2. **Sync State Changes**:
   - `sync_status` - New status value
   - `last_sync` - Timestamp of last successful sync
   - `sync_error` - Error message if failed

3. **Configuration Changes**:
   - `status` - New configuration status
   - Related timestamp fields based on transition

### State History Tracking

All state transitions are logged with:
- Previous state
- New state  
- Transition trigger
- Timestamp
- User context (if manual)

## Agent Implementation Guidelines

### State Validation

```python
def validate_fabric_state(fabric):
    """Validate fabric state consistency"""
    # Check for impossible combinations
    if fabric.status == 'DECOMMISSIONED':
        if fabric.sync_status in ['SYNCING', 'IN_SYNC']:
            return False, "Decommissioned fabric cannot be syncing"
    
    if fabric.connection_status == 'FAILED':
        if fabric.sync_status == 'IN_SYNC':
            return False, "Cannot be in sync without connection"
    
    return True, "State is consistent"
```

### State Transition Execution

```python
def execute_state_transition(fabric, new_status, trigger, user=None):
    """Execute fabric state transition with validation"""
    # Validate transition is allowed
    if not is_valid_transition(fabric.status, new_status):
        raise InvalidTransition(f"Cannot transition from {fabric.status} to {new_status}")
    
    # Update state
    old_status = fabric.status
    fabric.status = new_status
    fabric.save(update_fields=['status'])
    
    # Log transition
    log_state_transition(fabric, old_status, new_status, trigger, user)
    
    # Trigger dependent actions
    handle_state_transition_effects(fabric, old_status, new_status)
```

### Monitoring and Alerting

**Critical State Combinations**:
- `ACTIVE` + `FAILED` → High priority alert
- `ACTIVE` + `ERROR` → Medium priority alert  
- `MAINTENANCE` duration > 24h → Review required

**Automated Recovery**:
- Connection failures → Retry with backoff
- Sync errors → Attempt reconciliation
- State inconsistencies → Force validation

## Integration Points

### With GitRepository States
- `connection_status` depends on GitRepository connection health
- Git authentication failures affect fabric sync capabilities

### With HedgehogResource States  
- Fabric `sync_status` aggregates individual resource sync states
- Fabric drift detection triggers resource reconciliation

### With ReconciliationAlert States
- State inconsistencies generate alerts
- Alert resolution updates fabric states

This documentation provides agents with complete state management context for HedgehogFabric entities.