# State Transition Matrices

## Overview

This document provides comprehensive state transition matrices for all NetBox Hedgehog Plugin entities with state management. These matrices serve as authoritative references for agents to understand valid transitions, required conditions, and side effects.

## HedgehogFabric State Matrices

### Configuration Status Transitions

| From State | To State | Trigger | Required Conditions | Side Effects | Agent Actions |
|-----------|----------|---------|-------------------|--------------|---------------|
| `PLANNED` | `ACTIVE` | Manual activation / ArgoCD setup complete | Valid Kubernetes config, Git repo configured | Enable sync operations | Start monitoring, enable alerts |
| `ACTIVE` | `MAINTENANCE` | Manual maintenance mode | User authorization | Suspend operations | Pause sync, alert users |
| `MAINTENANCE` | `ACTIVE` | Maintenance complete | System validation passed | Resume operations | Resume sync, clear maintenance alerts |
| `ACTIVE` | `DECOMMISSIONED` | Permanent shutdown | User confirmation | Stop all operations | Cleanup resources, final alerts |
| `MAINTENANCE` | `DECOMMISSIONED` | Shutdown during maintenance | User confirmation | Stop all operations | Cleanup resources, final alerts |

**Invalid Transitions**:
- `DECOMMISSIONED` → Any other state (permanent state)
- `PLANNED` → `MAINTENANCE` (must be active first)
- `PLANNED` → `DECOMMISSIONED` (should be deleted instead)

### Connection Status Transitions

| From State | To State | Trigger | Required Conditions | Side Effects | Agent Actions |
|-----------|----------|---------|-------------------|--------------|---------------|
| `UNKNOWN` | `TESTING` | `test_connection()` called | Valid kubernetes config | Update connection fields | Display testing status |
| `TESTING` | `CONNECTED` | Connection test succeeds | Valid auth, network access | Set `last_validated` | Enable operations |
| `TESTING` | `FAILED` | Connection test fails | Auth/network failure | Set `connection_error` | Generate alerts, disable ops |
| `CONNECTED` | `TESTING` | Scheduled retest / manual test | Test interval reached | Clear previous validation | Temporary ops suspension |
| `CONNECTED` | `FAILED` | Connection lost | Auth expiry, network issue | Set `connection_error` | Generate alerts, disable ops |
| `FAILED` | `TESTING` | Retry connection | Error addressed | Clear previous error | Attempt recovery |

**Invalid Transitions**:
- Any state → `UNKNOWN` (except initial creation)
- `TESTING` → `TESTING` (already in testing)

### Sync Status Transitions

| From State | To State | Trigger | Required Conditions | Side Effects | Agent Actions |
|-----------|----------|---------|-------------------|--------------|---------------|
| `NEVER_SYNCED` | `SYNCING` | First sync initiated | Connection established | Start sync process | Show sync progress |
| `SYNCING` | `IN_SYNC` | Sync completes successfully | No errors, data matches | Update `last_sync` | Update counters, clear alerts |
| `SYNCING` | `ERROR` | Sync fails | Errors encountered | Set `sync_error` | Generate alerts, log errors |
| `IN_SYNC` | `SYNCING` | Scheduled sync / manual sync | Sync triggered | Start sync process | Show sync progress |
| `IN_SYNC` | `OUT_OF_SYNC` | Drift detected | State differences found | Update drift counters | Generate drift alerts |
| `OUT_OF_SYNC` | `SYNCING` | Reconciliation started | User/system action | Start reconciliation | Show reconciliation progress |
| `ERROR` | `SYNCING` | Retry sync | Error resolved | Clear previous error | Attempt recovery |

**Invalid Transitions**:
- `ERROR` → `IN_SYNC` (must sync first)
- `OUT_OF_SYNC` → `IN_SYNC` (must reconcile first)

## GitRepository State Matrix

### Connection Status Transitions

| From State | To State | Trigger | Required Conditions | Side Effects | Agent Actions |
|-----------|----------|---------|-------------------|--------------|---------------|
| `PENDING` | `TESTING` | `test_connection()` called | URL format valid | Update status | Show test progress |
| `TESTING` | `CONNECTED` | Authentication succeeds | Valid credentials, repo access | Set `last_validated`, clear errors | Enable git operations |
| `TESTING` | `FAILED` | Authentication fails | Invalid creds, no access | Set `validation_error` | Show error, disable operations |
| `CONNECTED` | `TESTING` | Retest triggered | Manual/scheduled test | Clear validation cache | Temporary operation hold |
| `CONNECTED` | `FAILED` | Auth expires/revoked | Token expiry, permission loss | Set `validation_error` | Alert users, disable operations |
| `FAILED` | `TESTING` | Retry with fixes | Credentials updated | Clear previous error | Attempt recovery |

**Invalid Transitions**:
- `PENDING` → `CONNECTED` (must test first)
- `PENDING` → `FAILED` (cannot fail without testing)
- `TESTING` → `PENDING` (cannot go backward)

**Credential-Specific Behaviors**:

| Auth Type | Token Expiry Behavior | Rotation Required | Recovery Actions |
|-----------|----------------------|------------------|------------------|
| `TOKEN` | Auto-detect expiry → `FAILED` | Yes (periodic) | Generate new token, retest |
| `SSH_KEY` | Rarely expires | No (unless compromised) | Regenerate keypair if needed |
| `BASIC` | App password changes → `FAILED` | As needed | Update password, retest |
| `OAUTH` | Token refresh cycle | Auto-refresh | Attempt refresh, re-auth if failed |

## HedgehogResource State Matrix

### Six-State Lifecycle Transitions

| From State | To State | Trigger | Required Conditions | Side Effects | Agent Actions |
|-----------|----------|---------|-------------------|--------------|---------------|
| `DRAFT` | `COMMITTED` | Commit to Git | `draft_spec` exists, Git accessible | Move `draft_spec` → `desired_spec`, set `desired_commit` | Clear draft, update Git |
| `COMMITTED` | `PENDING` | Git sync completed | New `desired_spec` from Git | Update `desired_updated` | Prepare for deployment |
| `PENDING` | `SYNCED` | Kubernetes deployment success | Resource deployed, `actual_spec` populated | Calculate initial drift (should be 0) | Monitor for drift |
| `SYNCED` | `DRIFTED` | Drift detected | `actual_spec` ≠ `desired_spec` | Update `drift_details`, `drift_score` | Generate reconciliation alert |
| `DRIFTED` | `SYNCED` | Reconciliation completed | Drift resolved | Clear drift details | Clear alerts |
| `SYNCED` | `PENDING` | New Git changes | Updated `desired_spec` | Update `desired_updated` | Prepare for redeployment |
| `ORPHANED` | `COMMITTED` | Import to Git | `actual_spec` exported to Git | Create `desired_spec` from `actual_spec` | Create Git commit |
| `ORPHANED` | `DRAFT` | Begin editing orphan | User starts editing | Create `draft_spec` from `actual_spec` | Enter edit mode |
| Any | `ORPHANED` | Orphan detection | Resource in cluster, not in Git | Clear `desired_spec` | Generate orphan alert |

**Invalid Transitions**:

| From State | To State | Reason | Suggested Path |
|-----------|----------|--------|----------------|
| `DRAFT` | `SYNCED` | Cannot skip commit/deploy | `DRAFT` → `COMMITTED` → `PENDING` → `SYNCED` |
| `DRAFT` | `DRIFTED` | Cannot drift without deployment | `DRAFT` → `COMMITTED` → `PENDING` → `SYNCED` |
| `COMMITTED` | `SYNCED` | Cannot skip deployment | `COMMITTED` → `PENDING` → `SYNCED` |
| `COMMITTED` | `DRIFTED` | Must deploy first | `COMMITTED` → `PENDING` → `SYNCED` |
| `PENDING` | `DRAFT` | Cannot edit during deployment | Wait for `SYNCED`, then edit |
| `PENDING` | `DRIFTED` | Must complete deployment | Wait for `SYNCED` or handle deployment failure |
| `ORPHANED` | `SYNCED` | Must import or edit first | `ORPHANED` → `COMMITTED` → `PENDING` → `SYNCED` |
| `ORPHANED` | `PENDING` | Must have desired state | `ORPHANED` → `COMMITTED` → `PENDING` |

### Drift Status Sub-States

| Drift Status | Description | Resource State | Alert Generated | Recovery Action |
|-------------|-------------|----------------|-----------------|-----------------|
| `in_sync` | No differences | `SYNCED` | No | None needed |
| `spec_drift` | Configuration differs | `DRIFTED` | Yes | Reconcile or update Git |
| `desired_only` | In Git, not cluster | `PENDING` | Sometimes | Deploy to cluster |
| `actual_only` | In cluster, not Git | `ORPHANED` | Yes | Import to Git or delete |
| `creation_pending` | Deployment queued | `PENDING` | No | Wait for GitOps |
| `deletion_pending` | Removal queued | N/A | Yes | Confirm deletion |

## ReconciliationAlert State Matrix

### Alert Status Transitions

| From State | To State | Trigger | Required Conditions | Side Effects | Agent Actions |
|-----------|----------|---------|-------------------|--------------|---------------|
| `ACTIVE` | `ACKNOWLEDGED` | `acknowledge()` called | User review | Set `acknowledged_at/by` | Update UI, log action |
| `ACTIVE` | `RESOLVED` | `resolve(action)` called | Valid resolution action | Set `resolved_at/by/action` | Execute resolution, update resource |
| `ACTIVE` | `SUPPRESSED` | `suppress(reason)` called | User decision | Set suppression metadata | Log suppression, stop processing |
| `ACKNOWLEDGED` | `RESOLVED` | `resolve(action)` called | Valid resolution action | Set `resolved_at/by/action` | Execute resolution, update resource |
| `ACKNOWLEDGED` | `SUPPRESSED` | `suppress(reason)` called | User decision | Set suppression metadata | Log suppression, stop processing |

**Invalid Transitions**:
- `RESOLVED` → `ACTIVE` (create new alert if condition recurs)
- `RESOLVED` → `ACKNOWLEDGED` (already resolved)
- `SUPPRESSED` → `ACTIVE` (create new alert if needed)
- `SUPPRESSED` → `ACKNOWLEDGED` (cannot acknowledge suppressed)

### Resolution Action Matrix

| Alert Type | Primary Actions | Secondary Actions | Auto-Execute | Manual Review Required |
|-----------|----------------|-------------------|--------------|----------------------|
| `drift_detected` | `update_git`, `import_to_git` | `ignore` | Low severity only | High/Critical severity |
| `orphaned_resource` | `import_to_git`, `delete_from_cluster` | `ignore` | Never | Always |
| `creation_pending` | `manual_review` | `ignore` | Never | Always |
| `deletion_pending` | `manual_review` | `ignore` | Never | Always |
| `sync_failure` | `manual_review` | `ignore` | Never | Always |
| `validation_error` | `manual_review` | `ignore` | Never | Always |
| `conflict_detected` | `manual_review` | N/A | Never | Always |

### Priority Calculation Matrix

| Severity | Base Priority | Age Factor | Final Priority Range | Processing Order |
|----------|--------------|------------|--------------------|--------------------|
| `CRITICAL` | 10 | -min(age_hours, 20) | 1-10 | Immediate |
| `HIGH` | 30 | -min(age_hours, 20) | 10-30 | Within 1 hour |
| `MEDIUM` | 50 | -min(age_hours, 20) | 30-50 | Within 4 hours |
| `LOW` | 70 | -min(age_hours, 20) | 50-70 | Within 24 hours |

**Severity Auto-Calculation**:

| Alert Type | Conditions | Calculated Severity |
|-----------|------------|-------------------|
| `drift_detected` | `drift_score` ≥ 0.8 | `HIGH` |
| `drift_detected` | `drift_score` 0.5-0.8 | `MEDIUM` |
| `drift_detected` | `drift_score` < 0.5 | `LOW` |
| `orphaned_resource` | Always | `CRITICAL` |
| `conflict_detected` | Always | `CRITICAL` |
| `sync_failure` | Always | `HIGH` |
| `validation_error` | Always | `HIGH` |

## Cross-Entity State Dependencies

### Fabric → Repository Dependencies

| Fabric Status | Repository Status | Combined Effect | Agent Behavior |
|--------------|------------------|----------------|----------------|
| `ACTIVE` | `CONNECTED` | Normal operation | Enable all GitOps |
| `ACTIVE` | `FAILED` | Degraded operation | Alert, disable Git sync |
| `ACTIVE` | `TESTING` | Temporary hold | Suspend Git operations |
| `MAINTENANCE` | Any | Suspended | Disable all operations |
| `DECOMMISSIONED` | Any | Inactive | Cleanup, final sync |

### Fabric → Resource Dependencies

| Fabric Sync Status | Resource State | Valid Combination | Agent Action |
|-------------------|----------------|------------------|--------------|
| `IN_SYNC` | `SYNCED` | ✓ Normal | Monitor drift |
| `OUT_OF_SYNC` | `DRIFTED` | ✓ Expected | Reconcile |
| `ERROR` | Any | ✓ Degraded | Alert, attempt recovery |
| `SYNCING` | `PENDING` | ✓ In progress | Monitor progress |
| `NEVER_SYNCED` | `DRAFT` | ✓ Initial state | Await first sync |

### Resource → Alert Dependencies

| Resource State | Alert Types Generated | Alert Priority | Auto-Resolution |
|---------------|----------------------|---------------|-----------------|
| `DRIFTED` | `drift_detected` | Based on drift_score | Low severity only |
| `ORPHANED` | `orphaned_resource` | `CRITICAL` | Never |
| Deployment failure | `sync_failure` | `HIGH` | Retry only |
| Validation error | `validation_error` | `HIGH` | Never |

## State Consistency Rules

### Global Consistency Checks

1. **Fabric-Repository Consistency**:
   - If fabric has `git_repository` FK, repository must exist and be `CONNECTED` for normal ops
   - Repository `FAILED` state should propagate to fabric sync issues

2. **Fabric-Resource Consistency**:
   - Fabric `drift_count` must match count of `DRIFTED` resources
   - Fabric `IN_SYNC` requires all resources to be `SYNCED` or acceptable states

3. **Resource-Alert Consistency**:
   - `DRIFTED` resources must have corresponding `drift_detected` alerts
   - `ORPHANED` resources must have corresponding `orphaned_resource` alerts

4. **Alert-Resolution Consistency**:
   - `RESOLVED` alerts must have `resolved_action` and `resolved_at`
   - Resolution actions must be appropriate for alert type

### Validation Procedures

```python
def validate_system_state_consistency():
    """Comprehensive state consistency validation"""
    errors = []
    
    # Check fabric-repository consistency
    for fabric in HedgehogFabric.objects.all():
        if fabric.git_repository:
            if fabric.git_repository.connection_status == 'FAILED':
                if fabric.sync_status not in ['ERROR', 'NEVER_SYNCED']:
                    errors.append(f"Fabric {fabric.name} has sync status {fabric.sync_status} but git repo failed")
    
    # Check resource-alert consistency  
    drifted_resources = HedgehogResource.objects.filter(resource_state='DRIFTED')
    for resource in drifted_resources:
        active_drift_alerts = resource.reconciliation_alerts.filter(
            alert_type='drift_detected', 
            status__in=['ACTIVE', 'ACKNOWLEDGED']
        )
        if not active_drift_alerts.exists():
            errors.append(f"Drifted resource {resource.name} has no active drift alert")
    
    return errors
```

This comprehensive state transition matrix provides agents with complete guidance for managing state transitions across all NetBox Hedgehog Plugin entities with full consistency validation.