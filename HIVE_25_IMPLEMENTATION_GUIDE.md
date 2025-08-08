# 🎯 HIVE 25 IMPLEMENTATION GUIDE - Periodic Sync Scheduler

## 📋 EXECUTIVE SUMMARY

**TASK**: Implement the periodic sync scheduler based on comprehensive test suite created by Hive 24  
**STATUS**: ✅ TESTS COMPLETE - READY FOR IMPLEMENTATION  
**ESTIMATED EFFORT**: ~50 lines of code + Celery configuration  
**SUCCESS CRITERIA**: All 24+ test cases pass  

---

## 🧪 WHAT HIVE 24 DELIVERED

### Complete Test Suite (4 Files)
1. **`test_periodic_sync_scheduler.py`** - Core timing logic tests
2. **`test_sync_configuration_states.py`** - Configuration state tests  
3. **`test_scheduler_execution_states.py`** - Scheduler execution tests
4. **`test_sync_error_handling.py`** - Error handling tests

### Validation Evidence
- **24+ Test Cases** - All validated using 5-phase TDD protocol
- **100% State Coverage** - All timing, configuration, scheduler, and error states
- **Test Validity Proven** - Every test fails appropriately (scheduler doesn't exist)
- **Implementation Specifications** - Exact requirements documented

---

## 🎯 YOUR IMPLEMENTATION TASKS

### CRITICAL: You are implementing against validated tests
- Tests already exist and prove their validity by failing
- Your job is to make the tests pass
- Follow TDD: Red → Green → Refactor

### Task 1: Create Periodic Scheduler Task (PRIMARY)

**File**: `netbox_hedgehog/tasks/git_sync_tasks.py`  
**Function**: `periodic_fabric_sync_scheduler`

```python
@shared_task(name='netbox_hedgehog.tasks.periodic_fabric_sync_scheduler')
def periodic_fabric_sync_scheduler():
    """
    Periodic task that checks all enabled fabrics and triggers sync for expired ones.
    
    Runs every 60 seconds via Celery Beat.
    
    Logic:
    1. Get all fabrics where sync_enabled=True and status='active'
    2. For each fabric, check if sync is due:
       - last_sync is None (never synced) → trigger sync
       - sync_interval <= 0 → skip (disabled)
       - last_sync + sync_interval <= current_time → trigger sync
    3. Call git_sync_fabric.delay(fabric_id) for expired fabrics
    4. Handle errors gracefully, continue processing other fabrics
    5. Use cache-based locking to prevent concurrent execution
    
    Returns:
        dict: Execution summary with counts and any errors
    """
```

**Key Implementation Points:**
- Use `cache.set('periodic_fabric_sync_running', True, timeout=300)` for concurrency control
- Query: `HedgehogFabric.objects.filter(sync_enabled=True, status='active')`
- Handle `sync_interval <= 0` as disabled
- Handle `last_sync=None` as "needs sync"
- Use `git_sync_fabric.delay(fabric_id)` to trigger individual syncs
- Wrap in try/except to handle individual fabric failures
- Log errors without exposing sensitive data

### Task 2: Add Celery Beat Configuration

**File**: `netbox_hedgehog/celery.py`  
**Location**: Add to `app.conf.beat_schedule` dictionary

```python
# Add this to the existing beat_schedule dictionary
'periodic-fabric-sync': {
    'task': 'netbox_hedgehog.tasks.periodic_fabric_sync_scheduler',
    'schedule': 60.0,  # 60 seconds
    'options': {
        'queue': 'git_sync',
        'priority': 6
    }
},
```

### Task 3: Add Import Statement

**File**: `netbox_hedgehog/tasks/git_sync_tasks.py`  
**Add**: Import the HedgehogFabric model at the top

```python
# Add to existing imports
from ..models.fabric import HedgehogFabric
from django.core.cache import cache
from django.utils import timezone
```

---

## 🧪 TESTING YOUR IMPLEMENTATION

### Step 1: Verify Tests Currently Fail
```bash
cd /home/ubuntu/cc/hedgehog-netbox-plugin
python manage.py test netbox_hedgehog.tests.test_periodic_sync_scheduler
```
Expected: Tests should fail with ImportError (scheduler doesn't exist)

### Step 2: Implement Scheduler Task
- Add the `periodic_fabric_sync_scheduler` function
- Follow the specification above

### Step 3: Add Celery Beat Config
- Add beat schedule entry
- Verify 60-second interval

### Step 4: Verify Tests Now Pass
```bash
python manage.py test netbox_hedgehog.tests.test_periodic_sync_scheduler
python manage.py test netbox_hedgehog.tests.test_sync_configuration_states
python manage.py test netbox_hedgehog.tests.test_scheduler_execution_states
python manage.py test netbox_hedgehog.tests.test_sync_error_handling
```
Expected: All tests should pass

### Step 5: Integration Testing
```bash
# Test scheduler in development
python manage.py shell
>>> from netbox_hedgehog.tasks.git_sync_tasks import periodic_fabric_sync_scheduler
>>> result = periodic_fabric_sync_scheduler.apply()
>>> print(result.get())
```

---

## 📊 IMPLEMENTATION REQUIREMENTS CHECKLIST

### Core Functionality
- [ ] `periodic_fabric_sync_scheduler` task function created
- [ ] Celery Beat schedule configured (60 seconds)
- [ ] Fabric filtering logic (sync_enabled=True, status='active')
- [ ] Sync timing logic (last_sync + sync_interval vs current_time)
- [ ] Task triggering (git_sync_fabric.delay calls)
- [ ] Concurrency prevention (cache-based locking)

### Error Handling
- [ ] Individual fabric failure isolation
- [ ] Database connection error handling
- [ ] Cache unavailable fallback
- [ ] Network timeout handling
- [ ] Resource exhaustion protection
- [ ] Comprehensive error logging
- [ ] Sensitive data redaction

### Performance
- [ ] Efficient database queries
- [ ] Batch processing support
- [ ] Resource usage monitoring
- [ ] Graceful degradation under load

### Configuration Support
- [ ] sync_enabled=False fabric exclusion
- [ ] sync_interval=0 disable logic
- [ ] Large sync_interval support
- [ ] Git repository configuration validation
- [ ] Multi-fabric scenario handling

---

## 🔍 VALIDATION CRITERIA

### Test Success Criteria
- ✅ All 24+ test cases pass
- ✅ No test failures or errors
- ✅ Coverage remains 100%
- ✅ Performance tests pass (100+ fabrics)

### Functional Success Criteria  
- ✅ Scheduler runs every 60 seconds
- ✅ Only enabled, active fabrics processed
- ✅ Correct sync timing calculations
- ✅ Individual sync tasks triggered appropriately
- ✅ Errors handled gracefully
- ✅ No concurrent scheduler execution

### Integration Success Criteria
- ✅ Celery Beat schedules task correctly
- ✅ Task appears in Celery monitoring tools
- ✅ Git sync tasks triggered appropriately
- ✅ Database performance acceptable
- ✅ Error logging works correctly

---

## 🚨 COMMON IMPLEMENTATION PITFALLS

### Pitfall 1: Incorrect Timing Logic
**Wrong**: `last_sync + sync_interval > current_time`  
**Right**: `current_time >= last_sync + sync_interval`

### Pitfall 2: Missing Concurrency Control
- MUST use cache locking to prevent multiple scheduler instances
- Handle cache unavailable gracefully

### Pitfall 3: Not Handling Individual Failures
- One fabric failure should NOT stop processing others
- Use try/except around each fabric's processing

### Pitfall 4: Incorrect Query Filtering
- MUST filter by `sync_enabled=True` AND `status='active'`
- Don't forget to exclude `sync_interval <= 0`

### Pitfall 5: Sensitive Data in Logs
- Never log git tokens, passwords, or connection strings
- Use '[REDACTED]' for sensitive fields

---

## 📁 REFERENCE FILES

### Test Files to Understand Requirements
```
netbox_hedgehog/tests/test_periodic_sync_scheduler.py      - Core logic tests
netbox_hedgehog/tests/test_sync_configuration_states.py   - Config handling tests
netbox_hedgehog/tests/test_scheduler_execution_states.py  - Execution tests
netbox_hedgehog/tests/test_sync_error_handling.py         - Error handling tests
```

### Implementation Files to Modify
```
netbox_hedgehog/tasks/git_sync_tasks.py    - Add scheduler function
netbox_hedgehog/celery.py                  - Add beat schedule
```

### Reference Architecture Files
```
netbox_hedgehog/models/fabric.py           - HedgehogFabric model
netbox_hedgehog/tasks/git_sync_tasks.py    - git_sync_fabric task
TEST_COVERAGE_MATRIX.md                    - Complete coverage analysis
```

---

## ✅ SUCCESS DEFINITION

**You will know you're successful when:**

1. **All Tests Pass**: Every test case in the 4 test files passes
2. **Scheduler Runs**: Celery Beat schedules the task every 60 seconds
3. **Fabrics Sync**: Enabled fabrics with expired intervals trigger git_sync_fabric
4. **Errors Handled**: Individual failures don't crash the scheduler
5. **Performance Good**: Handles 100+ fabrics efficiently
6. **No Side Effects**: Doesn't interfere with existing functionality

**Estimated Implementation Time**: 2-4 hours  
**Lines of Code**: ~50 lines + configuration

---

## 🎯 FINAL NOTES

### Architecture Decisions Already Made
- Use cache-based concurrency control (not database locks)  
- 60-second execution interval (not configurable)
- Process all enabled fabrics on each run (not incremental)
- Use git_sync queue with priority 6
- Graceful error handling with continue-on-failure

### Implementation Philosophy
- **Follow the tests**: Tests define exact behavior expected
- **TDD approach**: Make tests pass, don't modify tests
- **Minimal implementation**: Don't over-engineer
- **Error resilience**: Individual failures shouldn't crash scheduler
- **Performance conscious**: Efficient queries and processing

### Post-Implementation
- Run all tests to verify success
- Test in development environment  
- Monitor Celery Beat scheduling
- Validate fabric sync behavior
- Update documentation if needed

**GOOD LUCK HIVE 25! The tests are your specification. Make them pass! 🚀**