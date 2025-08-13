# NetBox Hedgehog Plugin - Sync Architecture Analysis Report

## Executive Summary

This analysis reveals critical architectural inconsistencies in the NetBox Hedgehog Plugin's sync system that cause periodic sync failures. The system has **two competing sync implementations** running simultaneously, creating timing conflicts and import errors.

## Root Cause Analysis

### 1. Dual Sync Architecture Conflict

**Problem**: The system has two parallel sync implementations:

1. **RQ-based System** (`jobs/fabric_sync.py`)
   - Uses `FabricSyncJob.execute_fabric_sync()` 
   - Scheduled via `django-rq-scheduler`
   - Works with NetBox's native RQ task system

2. **Celery-based System** (`tasks/sync_tasks.py` + `celery.py`)
   - Uses `master_sync_scheduler()` and `sync_fabric_task()`
   - Scheduled via Celery Beat (60-second intervals)
   - **Not compatible with NetBox's architecture**

**Impact**: Both systems are active, causing:
- Race conditions in `fabric.last_sync` updates
- Duplicate sync executions
- Timing confusion in `needs_sync()` logic

### 2. Import Error Root Cause

**Error**: `cannot import name 'ensure_gitops_structure' from 'netbox_hedgehog.signals'`

**Cause**: Views try to import `ensure_gitops_structure` directly from signals module:
```python
# Line 238 in fabric_views.py
from ..signals import ensure_gitops_structure, ingest_fabric_raw_files
```

**Reality**: The function exists but is not exposed in the module's `__all__` list or module-level imports.

### 3. Missing scheduler_enabled Field

**Problem**: The `master_sync_scheduler()` requires a `scheduler_enabled` field:
```python
# Line 45 in sync_tasks.py
fabrics = HedgehogFabric.objects.filter(
    sync_enabled=True,
    scheduler_enabled=True  # This field exists but may not be populated
)
```

**Impact**: Even enabled fabrics may be skipped if `scheduler_enabled=False`.

## Architecture Analysis

### Current Sync Flow (Conflicted)

```
Manual Sync:
User → fabric_views.py → FabricSyncJob.execute_fabric_sync() → KubernetesSync

Periodic Sync (RQ):
django-rq-scheduler → FabricSyncJob.execute_fabric_sync() → KubernetesSync

Periodic Sync (Celery - PROBLEMATIC):
Celery Beat → master_sync_scheduler() → sync_fabric_task() → KubernetesSync
```

### Timing Logic Issues

The `fabric.needs_sync()` method works correctly:
```python
def needs_sync(self):
    if not self.sync_enabled:
        return False
    if self.sync_interval <= 0:
        return False
    if not self.last_sync:
        return True  # Never synced
    
    time_since_last_sync = timezone.now() - self.last_sync
    sync_interval_timedelta = timedelta(seconds=self.sync_interval)
    
    return time_since_last_sync >= sync_interval_timedelta
```

**Problem**: Both sync systems update `last_sync`, causing timing conflicts.

## Specific Issues Identified

### Issue 1: Celery vs RQ Conflict

**NetBox Architecture**: NetBox uses RQ (Redis Queue) for background tasks, not Celery.

**Current Problem**: The system tries to run both:
- `celery.py` configures Celery Beat with 60-second `master-sync-scheduler`
- `jobs/fabric_sync.py` uses RQ scheduler
- **Both are active simultaneously**

### Issue 2: Sync Status Contradictions

**Scenario**: 
1. Manual sync works (updates `last_sync`)
2. RQ scheduler sees `needs_sync()` = False, skips
3. Celery scheduler runs independently, may conflict
4. Status shows "Out of Sync" due to conflicting updates

### Issue 3: Database Field Dependencies

Missing or unpopulated fields:
- `scheduler_enabled` field exists but may not be set to `True`
- RQ jobs need proper scheduling registration

## Architectural Fixes Required

### Fix 1: Choose Single Sync System (Recommended: RQ)

**Action**: Disable Celery, use only RQ-based system

**Rationale**: 
- NetBox natively supports RQ
- `jobs/fabric_sync.py` is properly implemented
- Avoids dual-system conflicts

**Implementation**:
```python
# 1. Comment out Celery Beat schedule in celery.py
# 2. Ensure RQ scheduler is properly configured
# 3. Use only FabricSyncJob.execute_fabric_sync()
```

### Fix 2: Fix Import Error

**Current Problem**:
```python
from ..signals import ensure_gitops_structure  # FAILS
```

**Solution**: Import the function correctly:
```python
from ..signals import ensure_gitops_structure
# OR
from netbox_hedgehog.signals import ensure_gitops_structure
```

**Root Fix**: Add to signals module `__all__` list:
```python
# In signals.py
__all__ = [
    'ensure_gitops_structure',
    'ingest_fabric_raw_files',
    # ... other exports
]
```

### Fix 3: Database Field Consistency

**Action**: Ensure `scheduler_enabled` field is populated:

```python
# Migration or management command
HedgehogFabric.objects.filter(
    sync_enabled=True
).update(scheduler_enabled=True)
```

### Fix 4: Unified Sync Entry Point

**Problem**: Multiple sync entry points create confusion

**Solution**: Standardize on single entry point:
- Manual sync: `FabricSyncJob.execute_fabric_sync(fabric_id)`
- Periodic sync: Same function, called by RQ scheduler
- Remove `master_sync_scheduler()` and `sync_fabric_task()`

## Recommended Architecture

### Simplified Sync Flow

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Manual Sync   │    │ Periodic Sync   │    │  RQ Scheduler   │
│  (UI Button)    │    │ (Scheduled)     │    │   (Background)  │
└─────────┬───────┘    └─────────┬───────┘    └─────────┬───────┘
          │                      │                      │
          └──────────────────────┼──────────────────────┘
                                 │
          ┌─────────────────────────────────────────────────┐
          │     FabricSyncJob.execute_fabric_sync()        │
          │                                                 │
          │  1. Check fabric.needs_sync()                   │
          │  2. Update fabric.last_sync = now()            │
          │  3. Call KubernetesSync.sync_all_crds()        │
          │  4. Update sync_status based on result         │
          │  5. Schedule next sync (RQ only)               │
          └─────────────────────────────────────────────────┘
```

### Database State Management

```
┌─────────────────────────────────────────────────────────────┐
│                    HedgehogFabric Model                     │
│                                                             │
│  sync_enabled: Boolean (user controlled)                   │
│  scheduler_enabled: Boolean (system controlled)            │
│  sync_interval: Integer (seconds between syncs)            │
│  last_sync: DateTime (prevents duplicate syncs)            │
│  sync_status: Choice (in_sync, out_of_sync, error, etc.)   │
│                                                             │
│  needs_sync() -> Boolean (timing logic)                    │
└─────────────────────────────────────────────────────────────┘
```

## Implementation Priority

### Immediate Fixes (Critical)

1. **Disable Celery Scheduler**: Comment out `beat_schedule` in `celery.py`
2. **Fix Import Error**: Add proper exports to `signals.py`
3. **Database Field**: Ensure `scheduler_enabled=True` for active fabrics

### Architecture Cleanup (Next)

1. **Remove Celery Tasks**: Delete `sync_tasks.py` and related Celery code
2. **Standardize Entry Points**: Use only `FabricSyncJob.execute_fabric_sync()`
3. **RQ Scheduler Configuration**: Ensure proper RQ-based periodic scheduling

### Validation Required

1. **Sync Timing**: Verify `needs_sync()` logic prevents duplicates
2. **Status Updates**: Confirm `sync_status` reflects actual state
3. **Error Handling**: Test sync failures and recovery

## Conclusion

The periodic sync failures are caused by **architectural inconsistency** - running both RQ and Celery sync systems simultaneously. The solution is to **standardize on RQ-based sync** and fix the import errors.

**Key Actions**:
1. Disable Celery Beat scheduler
2. Fix `ensure_gitops_structure` import
3. Populate `scheduler_enabled` field
4. Use only `FabricSyncJob.execute_fabric_sync()` for all sync operations

This will resolve the "manual sync works once but doesn't continue" issue and create a consistent, reliable sync architecture.