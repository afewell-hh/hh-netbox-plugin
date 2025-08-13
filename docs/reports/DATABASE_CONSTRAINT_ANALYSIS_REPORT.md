# Database Schema Constraint Violations Analysis Report

**Generated:** 2025-08-11  
**Issue:** K8s sync fails with "null value in column 'managed_file_path' violates not-null constraint"

## Executive Summary

The sync process is failing due to database constraint violations. The root cause is that migration 0021 added new NOT NULL fields to the HedgehogResource table, but existing code creating HedgehogResource records doesn't populate these fields.

## Critical Findings

### 1. Migration State Analysis
- ✅ All migrations are applied (including 0021_bidirectional_sync_extensions)
- ✅ Database schema is up to date
- ❌ Code is not compatible with the new schema requirements

### 2. Primary Constraint Violation
**Field:** `managed_file_path`  
**Type:** `character varying`  
**Constraint:** NOT NULL, no default value  
**Impact:** CRITICAL - Prevents any HedgehogResource creation

### 3. Complete List of Potentially Problematic Fields

The following 32 fields are NOT NULL without defaults and could cause constraint violations:

#### **Immediate Risk (Missing in existing code):**
1. `managed_file_path` - **CRITICAL** (causing current failure)
2. `file_hash` - **HIGH RISK**  
3. `sync_direction` - **HIGH RISK**  
4. `conflict_status` - **HIGH RISK**  
5. `conflict_details` - **MEDIUM RISK**  
6. `sync_metadata` - **MEDIUM RISK**  
7. `external_modifications` - **MEDIUM RISK**

#### **Lower Risk (May have defaults in Django model):**
8. `actual_resource_version` - Usually empty string
9. `annotations` - Usually empty dict {}
10. `api_version` - Usually has default  
11. `custom_field_data` - Usually empty dict {}
12. `dependency_score` - Usually 0.0
13. `desired_commit` - Usually empty string
14. `desired_file_path` - Usually empty string
15. `drift_details` - Usually empty dict {}
16. `drift_score` - Usually 0.0
17. `drift_severity` - Usually empty string
18. `drift_status` - Has default in model
19. `labels` - Usually empty dict {}
20. `last_sync_error` - Usually empty string
21. `last_synced_commit` - Usually empty string
22. `reconciliation_attempts` - Usually 0
23. `relationship_metadata` - Usually empty dict {}
24. `resource_state` - Has default in model
25. `state_change_reason` - Usually empty string
26. `sync_attempts` - Usually 0

#### **Auto-populated (Should work):**
27. `first_seen` - Auto-populated timestamp
28. `last_state_change` - Auto-populated timestamp
29. `kind` - Required parameter (should always be provided)
30. `name` - Required parameter (should always be provided) 
31. `namespace` - Has default 'default'

## Root Cause Analysis

### Problem Location 1: `/netbox_hedgehog/models/fabric.py:1816-1828`
```python
# Resource exists in cluster but not in GitOps - create orphaned resource
HedgehogResource.objects.create(
    fabric=self,
    kind=kind,
    name=name,
    namespace=namespace,
    api_version=resource.get('apiVersion', ''),
    actual_spec=resource.get('spec', {}),
    actual_status=resource.get('status', {}),
    actual_resource_version=metadata.get('resourceVersion', ''),
    actual_updated=timezone.now(),
    labels=metadata.get('labels', {}),
    annotations=metadata.get('annotations', {})
    # MISSING: managed_file_path, file_hash, sync_direction, conflict_status, etc.
)
```

### Problem Location 2: `/netbox_hedgehog/models/fabric.py:893-903`  
```python
resource, created = HedgehogResource.objects.get_or_create(
    fabric=self,
    kind=kind,
    name=name,
    namespace=namespace,
    defaults={
        'desired_spec': doc,
        'api_version': api_version,
        'desired_commit': commit_sha
        # MISSING: managed_file_path, file_hash, sync_direction, conflict_status, etc.
    }
)
```

## Impact Assessment

### Current State
- ❌ **K8s sync completely broken** - Cannot create any new HedgehogResource records
- ❌ **Transaction rollback** - No data saved when sync fails
- ❌ **Cascading failures** - All dependent sync processes fail

### Severity
- **CRITICAL:** Production system cannot sync with K8s clusters
- **BLOCKING:** Prevents all GitOps functionality
- **DATA LOSS RISK:** Failed transactions may lose partial sync data

## Fix Strategy Options

### Option 1: Database Migration (RECOMMENDED)
**Approach:** Create migration to add default values or make fields nullable

**Advantages:**
- ✅ Backward compatible
- ✅ No code changes required
- ✅ Immediate fix

**Migration Required:**
```python
# Migration: 0022_fix_not_null_constraints.py
operations = [
    # Option A: Add default values
    migrations.RunSQL([
        "ALTER TABLE netbox_hedgehog_hedgehogresource ALTER COLUMN managed_file_path SET DEFAULT '';",
        "ALTER TABLE netbox_hedgehog_hedgehogresource ALTER COLUMN file_hash SET DEFAULT '';", 
        "ALTER TABLE netbox_hedgehog_hedgehogresource ALTER COLUMN sync_direction SET DEFAULT 'bidirectional';",
        "ALTER TABLE netbox_hedgehog_hedgehogresource ALTER COLUMN conflict_status SET DEFAULT 'none';",
        # ... etc for all fields
    ], reverse_sql=[
        "ALTER TABLE netbox_hedgehog_hedgehogresource ALTER COLUMN managed_file_path DROP DEFAULT;",
        "ALTER TABLE netbox_hedgehog_hedgehogresource ALTER COLUMN file_hash DROP DEFAULT;",
        # ... etc
    ]),
    
    # Option B: Make fields nullable (if appropriate)
    migrations.AlterField(
        model_name='hedgehogresource',
        name='managed_file_path',
        field=models.CharField(max_length=500, blank=True, null=True, help_text="Path to managed file in GitOps repository"),
    ),
]
```

### Option 2: Code Fix (ADDITIONAL)
**Approach:** Update all HedgehogResource.objects.create() calls

**Required Changes:**
```python
# Fix 1: fabric.py:1816-1828
HedgehogResource.objects.create(
    # ... existing fields ...
    managed_file_path='',  # Add default empty string
    file_hash='',
    sync_direction='bidirectional', 
    conflict_status='none',
    conflict_details={},
    sync_metadata={},
    external_modifications=[],
)

# Fix 2: fabric.py:893-903  
defaults={
    # ... existing defaults ...
    'managed_file_path': '',
    'file_hash': '',
    'sync_direction': 'bidirectional',
    'conflict_status': 'none', 
    'conflict_details': {},
    'sync_metadata': {},
    'external_modifications': [],
}
```

### Option 3: Model Field Updates (LONG-TERM)
**Approach:** Update model definitions to have appropriate defaults

## Recommended Immediate Actions

### Phase 1: Emergency Fix (< 1 hour)
1. **Create migration 0022** with default values for critical fields
2. **Apply migration** to fix immediate constraint violations
3. **Test sync operation** to verify fix

### Phase 2: Code Hardening (< 4 hours) 
1. **Update all HedgehogResource creation code** to explicitly set required fields
2. **Add validation** to prevent future constraint violations
3. **Test all sync pathways** (Git→HNP, K8s→HNP, etc.)

### Phase 3: Architecture Review (< 1 day)
1. **Review migration 0021** - Why were these fields made NOT NULL?
2. **Evaluate field necessity** - Do all fields need to be NOT NULL?
3. **Update documentation** for future schema changes

## SQL Commands for Immediate Fix

```sql
-- IMMEDIATE FIX: Add default values to prevent constraint violations
ALTER TABLE netbox_hedgehog_hedgehogresource ALTER COLUMN managed_file_path SET DEFAULT '';
ALTER TABLE netbox_hedgehog_hedgehogresource ALTER COLUMN file_hash SET DEFAULT '';
ALTER TABLE netbox_hedgehog_hedgehogresource ALTER COLUMN sync_direction SET DEFAULT 'bidirectional';
ALTER TABLE netbox_hedgehog_hedgehogresource ALTER COLUMN conflict_status SET DEFAULT 'none';
ALTER TABLE netbox_hedgehog_hedgehogresource ALTER COLUMN conflict_details SET DEFAULT '{}';
ALTER TABLE netbox_hedgehog_hedgehogresource ALTER COLUMN sync_metadata SET DEFAULT '{}';
ALTER TABLE netbox_hedgehog_hedgehogresource ALTER COLUMN external_modifications SET DEFAULT '[]';

-- Update any existing NULL values (if any exist)
UPDATE netbox_hedgehog_hedgehogresource SET 
    managed_file_path = '' WHERE managed_file_path IS NULL,
    file_hash = '' WHERE file_hash IS NULL,
    sync_direction = 'bidirectional' WHERE sync_direction IS NULL,
    conflict_status = 'none' WHERE conflict_status IS NULL;
```

## Risk Assessment

### High Risk
- Making fields nullable may break other code expecting non-null values
- Default values may not be semantically correct for all use cases

### Medium Risk  
- Migration rollback complexity
- Performance impact of updating existing records

### Low Risk
- Adding defaults for new records (recommended approach)

## Testing Strategy

### Pre-Fix Validation
```bash
# Verify current failure
python manage.py test_k8s_sync  # Should fail with managed_file_path constraint

# Check existing data
SELECT COUNT(*) FROM netbox_hedgehog_hedgehogresource;  # Should show current record count
```

### Post-Fix Validation
```bash
# Test sync functionality
python manage.py test_k8s_sync  # Should succeed

# Verify new records have proper defaults  
SELECT managed_file_path, file_hash, sync_direction, conflict_status 
FROM netbox_hedgehog_hedgehogresource 
ORDER BY id DESC LIMIT 10;
```

## Conclusion

The database constraint violation is preventing all K8s sync functionality. The immediate fix requires either:

1. **Database migration** to add default values (RECOMMENDED - fast, safe)  
2. **Code updates** to provide all required fields (ADDITIONAL - thorough, future-proof)

**CRITICAL:** This is a production-blocking issue that requires immediate attention. The migration approach can be implemented and tested within 1 hour to restore sync functionality.