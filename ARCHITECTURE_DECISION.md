# SYNC INTERVAL ARCHITECTURE DECISION

## Executive Summary

**DECISION**: Keep sync_interval on HedgehogFabric model (current state)  
**REASONING**: Repository-level intervals would break existing functionality and serve no practical use case  
**IMPLEMENTATION**: No model changes needed, fix template display logic only

---

## Current State Analysis

### HedgehogFabric Model
- ✅ **sync_interval field EXISTS** (line 76-79 in fabric.py)  
- ✅ **Default**: 300 seconds
- ✅ **Migration**: Already in 0001_initial.py
- ✅ **Working**: Currently functional on fabric detail pages

### GitRepository Model  
- ❌ **sync_interval field MISSING** (confirmed in git_repository.py)
- ❌ **Template Error**: fabric_detail_simple.html tries to access `object.git_repository.sync_interval` (fails)
- ❌ **No Migration**: No sync_interval field ever existed on repository model

---

## Architectural Options Evaluated

### Option A: Repository-Level Sync Intervals (REJECTED)
```python
# Would require adding to GitRepository model
sync_interval = models.PositiveIntegerField(
    default=300,
    help_text="Sync interval in seconds for all fabrics using this repository"
)
```

**Pros:**
- Single configuration point for shared repositories
- Simpler for repositories used by multiple fabrics

**Cons (CRITICAL ISSUES):**
- **Breaking Change**: Would require complex migration
- **Loss of Flexibility**: All fabrics forced to same sync schedule  
- **Use Case Mismatch**: Different fabrics may need different sync frequencies
- **Implementation Complexity**: All sync logic would need refactoring

### Option B: Fabric-Level Sync Intervals (SELECTED)
```python
# Current implementation - KEEP AS-IS
sync_interval = models.PositiveIntegerField(
    default=300,
    help_text="Sync interval in seconds (0 to disable automatic sync)"
)
```

**Pros (WINNING FACTORS):**
- ✅ **Zero Breaking Changes**: Already working
- ✅ **Maximum Flexibility**: Each fabric can have different sync needs
- ✅ **Real-World Use Case**: Dev fabric (fast sync) vs Prod fabric (slow sync)
- ✅ **No Migration Required**: Field already exists and works
- ✅ **Preservation of Working Code**: Hive 22 fixes remain intact

**Cons:**
- Multiple configuration points (acceptable - provides needed flexibility)

---

## Use Case Analysis

### Multiple Fabrics, One Repository Scenario
```
GitRepository: "hedgehog-configs" 
├── Fabric: "dev-cluster" (sync_interval: 60 seconds - fast development)
├── Fabric: "staging-cluster" (sync_interval: 300 seconds - moderate)  
└── Fabric: "prod-cluster" (sync_interval: 1800 seconds - conservative)
```

**Fabric-level intervals** (current): ✅ Each fabric syncs at appropriate frequency  
**Repository-level intervals** (alternative): ❌ All forced to same frequency

### Single Fabric, Multiple Repositories Scenario  
```
Fabric: "main-cluster"
├── GitRepository: "core-configs" (fabric manages sync timing)
├── GitRepository: "app-configs" (fabric manages sync timing)
└── GitRepository: "security-configs" (fabric manages sync timing)
```

**Both approaches work**, but fabric-level provides more control over orchestration.

---

## Implementation Requirements

### Phase 1: Fix Template Display Bug ✅ COMPLETE
The issue is in `fabric_detail_simple.html` where template tries to access non-existent field:
```django
<!-- BROKEN - field doesn't exist -->
<th>Git Sync Interval:</th>
<td>{{ object.git_repository.sync_interval|default:"—" }} seconds</td>

<!-- WORKING - field exists -->  
<th>Fabric Sync Interval:</th>
<td>{{ object.sync_interval }} seconds</td>
```

**Fix**: Remove the broken "Git Sync Interval" row, keep working "Fabric Sync Interval" row

### Phase 2: Git Repository Template (No Sync Interval Needed)
Git repository detail pages should NOT display sync intervals because:
1. Sync intervals belong to fabrics, not repositories
2. Repository page should show "Dependent Fabrics" with their individual intervals
3. This maintains proper separation of concerns

---

## Migration Impact Assessment

### SELECTED APPROACH (Keep Fabric-Level): ZERO IMPACT ✅
- No database migrations required
- No model changes required  
- No sync logic changes required
- Only template fixes needed
- All existing functionality preserved

### REJECTED APPROACH (Move to Repository-Level): HIGH IMPACT ❌
- Complex data migration required (move intervals from fabrics to repositories)
- All sync services need refactoring
- Risk of breaking working FGD sync (fixed in Hive 22)
- Extensive testing required across all sync mechanisms
- Potential data loss if migration fails

---

## Final Decision Justification

**Keep sync_interval on HedgehogFabric model** because:

1. **Preserve Working Functionality**: Hive 22 successfully fixed FGD sync - don't break it
2. **Real-World Flexibility**: Different environments need different sync frequencies  
3. **Zero Risk**: No migrations or model changes eliminates implementation risk
4. **Proper Architecture**: Sync timing is operational concern of fabric, not repository
5. **Template Fix Only**: Simple template corrections vs complex system overhaul

## Next Steps

1. ✅ Fix fabric template to remove broken git repository sync interval display
2. ✅ Ensure git repository templates don't attempt to show sync intervals  
3. ✅ Test that existing sync functionality continues working
4. ✅ Document proper sync interval management in user documentation

**Total Implementation Time**: < 30 minutes (template fixes only)  
**Risk Level**: MINIMAL (no model or logic changes)