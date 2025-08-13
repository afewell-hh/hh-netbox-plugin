# Issue #40: Fabric Sync Status Pseudocode - Implementation Ready

## SPARC Pseudocode Phase Complete

**Date:** 2025-08-10T19:40:00Z  
**Phase:** Pseudocode Design → Ready for Refinement/Coding  
**Issue:** #40 - Fabric Sync Status Contradictions

## Evidence Summary

Based on container analysis, Fabric ID 35 exhibits **CRITICAL CONTRADICTIONS**:

- **Raw sync_status:** "synced" 
- **kubernetes_server:** EMPTY STRING
- **connection_error:** "401 Unauthorized"
- **sync_interval:** 60 seconds
- **Time since sync:** 24+ hours
- **sync_enabled:** true

**Result:** 4 contradictions violating logical consistency

## Algorithm Implementation Pseudocode

### Algorithm 1: calculated_sync_status Property

```python
@property
def calculated_sync_status(self):
    """
    Calculate actual sync status based on configuration and timing.
    FIXES: Issue #40 sync status contradictions
    """
    from django.utils import timezone
    
    # CRITICAL FIX 1: Kubernetes server validation
    if not self.kubernetes_server or not self.kubernetes_server.strip():
        return 'not_configured'
    
    # CRITICAL FIX 2: Sync enabled check
    if not self.sync_enabled:
        return 'disabled'
    
    # CRITICAL FIX 3: Never synced check
    if not self.last_sync:
        return 'never_synced'
    
    # Time-based calculations
    current_time = timezone.now()
    time_since_sync = current_time - self.last_sync
    sync_age_seconds = time_since_sync.total_seconds()
    
    # CRITICAL FIX 4: Error state checks
    if self.sync_error and self.sync_error.strip():
        return 'error'
    
    if self.connection_error and self.connection_error.strip():
        return 'error'
    
    # CRITICAL FIX 5: Sync interval validation
    if self.sync_interval > 0:
        max_acceptable_age = self.sync_interval * 2  # 2x grace period
        
        if sync_age_seconds > max_acceptable_age:
            return 'out_of_sync'
        elif sync_age_seconds <= self.sync_interval:
            return 'in_sync'
        else:
            return 'stale'  # Between 1x and 2x interval
    
    # Fallback for manual sync (interval = 0)
    if sync_age_seconds <= 3600:  # 1 hour
        return 'in_sync'
    else:
        return 'out_of_sync'
```

### Algorithm 2: calculated_sync_status_display Property

```python
@property
def calculated_sync_status_display(self):
    """
    User-friendly display text for calculated sync status.
    """
    status_map = {
        'not_configured': 'Not Configured',
        'disabled': 'Sync Disabled',
        'never_synced': 'Never Synced',
        'in_sync': 'In Sync',
        'stale': 'Sync Stale',
        'out_of_sync': 'Out of Sync',
        'error': 'Sync Error',
        'syncing': 'Syncing...'
    }
    return status_map.get(self.calculated_sync_status, 'Unknown')
```

### Algorithm 3: calculated_sync_status_badge_class Property

```python
@property
def calculated_sync_status_badge_class(self):
    """
    Bootstrap CSS classes for status badges.
    """
    status_classes = {
        'not_configured': 'bg-secondary text-white',
        'disabled': 'bg-secondary text-white', 
        'never_synced': 'bg-warning text-dark',
        'in_sync': 'bg-success text-white',
        'stale': 'bg-warning text-dark',
        'out_of_sync': 'bg-danger text-white',
        'error': 'bg-danger text-white',
        'syncing': 'bg-info text-white'
    }
    return status_classes.get(self.calculated_sync_status, 'bg-secondary text-white')
```

## Data Structure Analysis

**Time Complexity:** O(1) - All calculations use basic field access and arithmetic  
**Space Complexity:** O(1) - No additional data structures allocated  
**Database Impact:** 0 additional queries - uses existing model fields

## Edge Case Handling

### Critical Edge Cases Resolved:

1. **Empty vs Null kubernetes_server**
   ```python
   # Handles both None and empty string
   if not self.kubernetes_server or not self.kubernetes_server.strip():
   ```

2. **Timezone Awareness**
   ```python
   # Uses Django's timezone-aware datetime
   from django.utils import timezone
   current_time = timezone.now()
   ```

3. **Zero Sync Interval (Manual Mode)**
   ```python
   # Fallback logic for manual sync
   if sync_age_seconds <= 3600:  # 1 hour grace
       return 'in_sync'
   ```

4. **Multiple Error Conditions**
   ```python
   # Prioritizes configuration errors over timing errors
   # not_configured > disabled > never_synced > error > timing-based
   ```

## Validation Logic Implementation

### Pre-Save Validation Hook

```python
def clean(self):
    """
    Validate fabric configuration for consistency.
    """
    super().clean()
    
    # Validate sync status against calculated status
    calculated = self.calculated_sync_status
    
    if self.sync_status != calculated:
        from django.core.exceptions import ValidationError
        raise ValidationError({
            'sync_status': f'Status "{self.sync_status}" contradicts configuration. Should be "{calculated}"'
        })
```

### Auto-Correction Logic

```python
def save(self, *args, **kwargs):
    """
    Auto-correct contradictory sync status before save.
    """
    # Store original for logging
    original_status = self.sync_status
    
    # Apply correction
    correct_status = self.calculated_sync_status
    if self.sync_status != correct_status:
        self.sync_status = correct_status
        
        # Log correction
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(
            f"Fabric {self.name} sync status auto-corrected: "
            f"{original_status} → {correct_status}"
        )
    
    super().save(*args, **kwargs)
```

## Template Integration Pseudocode

### Status Display Pattern

```django
<!-- BEFORE (Contradictory) -->
<span class="badge bg-success">{{ fabric.get_sync_status_display }}</span>

<!-- AFTER (Accurate) -->
<span class="badge {{ fabric.calculated_sync_status_badge_class }}">
    {{ fabric.calculated_sync_status_display }}
</span>
```

### Conditional Logic Pattern

```django
<!-- BEFORE (Unreliable) -->
{% if fabric.sync_status == 'synced' %}
    <i class="fas fa-check text-success"></i>
{% endif %}

<!-- AFTER (Reliable) -->
{% if fabric.calculated_sync_status == 'in_sync' %}
    <i class="fas fa-check text-success"></i>
{% elif fabric.calculated_sync_status == 'error' %}
    <i class="fas fa-exclamation-triangle text-danger"></i>
{% endif %}
```

## Testing Strategy Pseudocode

### Unit Test Implementation

```python
def test_calculated_sync_status_contradictions(self):
    """Test all contradiction scenarios from Issue #40"""
    
    # Test Case 1: Empty kubernetes_server
    fabric = HedgehogFabric(
        sync_status='synced',
        kubernetes_server='',
        sync_enabled=True
    )
    assert fabric.calculated_sync_status == 'not_configured'
    
    # Test Case 2: Connection error
    fabric = HedgehogFabric(
        sync_status='synced',
        kubernetes_server='https://k8s.example.com',
        connection_error='401 Unauthorized',
        sync_enabled=True
    )
    assert fabric.calculated_sync_status == 'error'
    
    # Test Case 3: Stale sync
    fabric = HedgehogFabric(
        sync_status='synced',
        kubernetes_server='https://k8s.example.com',
        sync_enabled=True,
        sync_interval=60,
        last_sync=timezone.now() - timedelta(hours=24)
    )
    assert fabric.calculated_sync_status == 'out_of_sync'
```

## Migration Strategy

### Phase 1: Property Addition (No Breaking Changes)
1. Add calculated properties to model
2. Update templates gradually
3. Run parallel validation

### Phase 2: Template Migration
1. Replace sync_status references with calculated_sync_status
2. Update admin interface
3. Add validation warnings

### Phase 3: Auto-Correction (Optional)
1. Add pre-save validation
2. Implement auto-correction logic
3. Monitor correction logs

## Performance Optimization

### Efficient Field Access Pattern

```python
# Optimized property implementation
@property
def calculated_sync_status(self):
    # Cache frequently accessed fields
    k8s_server = self.kubernetes_server
    sync_enabled = self.sync_enabled
    last_sync = self.last_sync
    
    # Early returns for performance
    if not k8s_server or not k8s_server.strip():
        return 'not_configured'
    
    if not sync_enabled:
        return 'disabled'
    
    # Continue with timing calculations only if needed
    # ... rest of logic
```

## Security Considerations

1. **Error Message Sanitization:** Don't expose sensitive connection details
2. **Audit Trail:** Log all auto-corrections for security review
3. **Permission Checks:** Properties respect existing model permissions
4. **Rate Limiting:** Properties are O(1) - safe for frequent access

## Implementation Priority

### Critical Path (Issue #40 Resolution):
1. **Add calculated_sync_status property** - HIGHEST PRIORITY
2. **Add display and badge properties** - HIGH PRIORITY  
3. **Update fabric detail template** - HIGH PRIORITY
4. **Add unit tests for contradictions** - MEDIUM PRIORITY
5. **Add auto-correction logic** - LOW PRIORITY (Optional)

### Success Criteria:
- ✅ Fabric ID 35 shows "Not Configured" instead of "Synced"
- ✅ Templates display accurate status based on actual configuration
- ✅ All contradiction scenarios handled correctly
- ✅ No performance regression in fabric list views
- ✅ Backward compatibility maintained during transition

---

**PSEUDOCODE PHASE COMPLETE**  
**Status:** ✅ Ready for SPARC Refinement/Coding Phase  
**Next Phase:** Implementation and TDD validation