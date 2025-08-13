# TDD London School Test Suite for Periodic Sync Timer

## Overview

This test suite uses the **London School (mockist) approach** to Test-Driven Development to expose critical failures in the fabric periodic sync functionality. The current implementation claims to work but is completely broken.

## Critical Issues Detected

The fabric shows:
- `sync_enabled=Yes` 
- `sync_interval=60s`
- `last_sync="Never Synced"` despite time passing

This indicates the periodic timer system is fundamentally broken.

## London School TDD Approach

### Why London School?

1. **Mock ALL external dependencies** - Isolates units under test
2. **Focus on object interactions** - Tests HOW objects collaborate
3. **Define contracts through mocks** - Specifies exact expected behavior
4. **Red-Green-Refactor cycle** - Tests MUST fail first

### Test Structure

```
tests/tdd_periodic_sync_london_school/
├── __init__.py                           # Package initialization
├── conftest.py                          # Test fixtures and mocks
├── test_timer_interval_precision.py    # Timer precision tests
├── test_sync_execution_behavior.py     # Sync execution tests  
├── test_integration_end_to_end.py      # E2E integration tests
├── test_validation_suite.py            # Meta-tests (validate TDD)
├── test_mock_strategy_document.py      # Mock strategy documentation
├── test_runner_script.py               # Test execution script
└── README.md                           # This documentation
```

## Expected Test Results

**ALL TESTS SHOULD FAIL** against the current broken implementation.

This is not a bug - it's the correct TDD approach:

### Red Phase (Current)
- ❌ All tests fail
- ✅ Proves tests detect real problems  
- ✅ Defines correct behavior through mocks

### Green Phase (Next)
- 🔄 Implement minimal code to make tests pass
- ✅ Focus on making tests green, not perfect code

### Refactor Phase (Final)
- 🔧 Improve code quality
- ✅ Keep tests green during refactoring

## Running the Tests

### Quick Test Execution
```bash
# Run all tests (should fail)
cd /home/ubuntu/cc/hedgehog-netbox-plugin
python -m pytest tests/tdd_periodic_sync_london_school/ -v

# Run with the test runner script
python tests/tdd_periodic_sync_london_school/test_runner_script.py
```

### Individual Test Categories
```bash
# Timer precision tests
python -m pytest tests/tdd_periodic_sync_london_school/test_timer_interval_precision.py -v

# Sync execution tests  
python -m pytest tests/tdd_periodic_sync_london_school/test_sync_execution_behavior.py -v

# Integration tests
python -m pytest tests/tdd_periodic_sync_london_school/test_integration_end_to_end.py -v

# Validation tests (meta-tests)
python -m pytest tests/tdd_periodic_sync_london_school/test_validation_suite.py -v
```

## Test Categories

### 1. Timer Interval Precision Tests
**File:** `test_timer_interval_precision.py`

**Purpose:** Verify 60-second timer triggers exactly on schedule

**Key Tests:**
- `test_timer_triggers_exactly_every_60_seconds` - Core timer functionality
- `test_timer_handles_interval_changes_immediately` - Configuration changes
- `test_timer_stops_when_sync_disabled` - Disable behavior
- `test_bootstrap_initializes_all_enabled_fabrics` - System startup

**Expected Failures:**
- RQ scheduler not configured
- Timer calculations incorrect
- No automatic rescheduling
- Bootstrap never called automatically

### 2. Sync Execution Behavior Tests
**File:** `test_sync_execution_behavior.py`

**Purpose:** Verify sync process state management and execution

**Key Tests:**
- `test_sync_execution_follows_proper_state_transitions` - State machine
- `test_sync_execution_handles_kubernetes_failure` - Error handling
- `test_sync_execution_transaction_rollback_on_failure` - Transaction safety
- `test_kubernetes_sync_operations_called_correctly` - Integration contracts

**Expected Failures:**
- State transitions not atomic
- last_sync updated at wrong time
- Error handling incomplete
- K8s sync is mocked stub only

### 3. Integration End-to-End Tests
**File:** `test_integration_end_to_end.py`

**Purpose:** Verify complete workflow from configuration to execution

**Key Tests:**
- `test_fabric_configuration_triggers_immediate_reschedule` - Config changes
- `test_system_recovery_after_scheduler_restart` - Failure recovery
- `test_scheduled_jobs_status_provides_complete_visibility` - Monitoring
- `test_sync_failure_preserves_scheduling` - Error resilience

**Expected Failures:**
- No Django signal handlers for config changes
- No recovery after scheduler restart
- Monitoring incomplete
- No failure recovery mechanism

### 4. Validation Suite (Meta-Tests)
**File:** `test_validation_suite.py`

**Purpose:** Validate that TDD process is working correctly

**Key Tests:**
- `test_all_timer_precision_tests_fail` - Confirms tests detect problems
- `test_mock_strategy_defines_all_critical_dependencies` - Mock completeness
- `test_tests_fail_before_implementation_changes` - TDD process validation

**Expected Results:**
- Validates other tests are failing correctly
- Ensures TDD approach is sound
- Prevents false confidence in broken code

## Mock Strategy

### External Dependencies Mocked

1. **django_rq** - Redis Queue system
   - Mock scheduler, queue operations
   - Verify job scheduling contracts

2. **rq_scheduler** - Periodic job scheduling
   - Mock schedule/cancel operations  
   - Verify timing precision

3. **HedgehogFabric** - Django model
   - Mock database operations
   - Verify state transitions

4. **transaction** - Django transactions
   - Mock atomic context managers
   - Verify rollback behavior

5. **timezone** - Time utilities
   - Mock now() for deterministic tests
   - Verify timing calculations

### Mock Interaction Patterns

#### Successful Sync Pattern
```python
get_current_job() -> job
fabric.select_for_update().get() -> fabric  
fabric.needs_sync() -> True
timezone.now() -> fixed_time
fabric.save(update_fields=['last_sync', 'sync_status'])
perform_sync_operations() -> success
fabric.save(update_fields=['sync_status', 'sync_error']) 
scheduler.schedule(next_time, func, args)
```

#### Timer Scheduling Pattern
```python
fabric.sync_enabled -> True
fabric.sync_interval -> 60
scheduler.cancel(job_id)
timezone.now() + 60s -> next_time
scheduler.schedule(next_time, func, args, job_id)
```

## Behavioral Contracts

### Timer Precision Contract
- Timer must trigger at exact intervals (±1 second tolerance)
- Configuration changes trigger immediate reschedule
- Disabled fabrics have jobs cancelled

### State Transition Contract  
- States follow: never → syncing → synced/error
- last_sync updated BEFORE sync work begins
- Errors preserved in sync_error field

### Concurrency Contract
- select_for_update() used for fabric locking
- needs_sync() prevents duplicate work
- Transactions protect critical sections

### Scheduler Integration Contract
- RQ scheduler properly configured
- Job IDs follow fabric_sync_{id} pattern
- Error handling for unavailable scheduler

## Implementation Guidance

When tests fail (they should), implement in this order:

### 1. Fix RQ Integration
```python
# Django settings.py
RQ_QUEUES = {
    'hedgehog_sync': {
        'HOST': 'redis',
        'PORT': 6379,
        'DB': 0,
    }
}

# Install django-rq-scheduler
pip install django-rq-scheduler
```

### 2. Implement Proper Timing
```python
def _schedule_next_sync(self, fabric):
    scheduler = django_rq.get_scheduler('hedgehog_sync')
    next_run = timezone.now() + timedelta(seconds=fabric.sync_interval)
    scheduler.schedule(
        scheduled_time=next_run,
        func=FabricSyncJob.execute_fabric_sync,
        args=[fabric.id],
        job_id=f"fabric_sync_{fabric.id}",
        queue_name='hedgehog_sync'
    )
```

### 3. Add State Management
```python
def execute_fabric_sync(fabric_id):
    with transaction.atomic():
        fabric = HedgehogFabric.objects.select_for_update().get(id=fabric_id)
        if not fabric.needs_sync():
            return {'success': True, 'message': 'Sync not needed'}
        
        fabric.last_sync = timezone.now()
        fabric.sync_status = 'syncing'
        fabric.save(update_fields=['last_sync', 'sync_status'])
    
    # Perform sync work outside transaction...
```

### 4. Handle Concurrency
```python
# Use database locking
fabric = HedgehogFabric.objects.select_for_update().get(id=fabric_id)

# Check needs_sync after acquiring lock
if not fabric.needs_sync():
    return {'success': True, 'message': 'Sync not needed'}
```

### 5. Add Error Handling
```python
try:
    result = perform_sync_operations(fabric)
    if result['success']:
        fabric.sync_status = 'synced'
        fabric.sync_error = ''
    else:
        fabric.sync_status = 'error'
        fabric.sync_error = result['error']
except Exception as e:
    fabric.sync_status = 'error'
    fabric.sync_error = str(e)
finally:
    fabric.save()
```

### 6. Real Integration
Replace mocked Kubernetes and Git operations with actual implementations.

## Why Tests MUST Fail First

1. **Proves tests detect problems** - Passing tests on broken code = bad tests
2. **Defines correct behavior** - Mock expectations specify exact requirements
3. **Guides implementation** - Failing tests show exactly what to build
4. **Prevents false confidence** - Broken code + passing tests = dangerous

## Red-Green-Refactor Cycle

### Red Phase ✅ (Current)
- All tests fail against broken implementation
- Validates test quality and TDD approach
- Defines behavioral contracts through mocks

### Green Phase 🔄 (Next)
- Write minimal code to make tests pass
- Focus on correctness, not elegance
- Keep tests green while implementing

### Refactor Phase 🔧 (Final)  
- Improve code quality and design
- Maintain green tests throughout
- Add optimizations and polish

## Success Criteria

### Phase 1: Red (Current)
- ✅ All timer precision tests fail
- ✅ All sync execution tests fail  
- ✅ All integration tests fail
- ✅ Validation suite confirms TDD approach

### Phase 2: Green (Implementation)
- 🎯 All tests pass with minimal implementation
- 🎯 Real periodic timer triggers every 60 seconds
- 🎯 Fabric last_sync updates correctly
- 🎯 Configuration changes reschedule immediately

### Phase 3: Refactor (Polish)
- 🎯 Code is clean and maintainable
- 🎯 Performance optimizations added
- 🎯 Error handling comprehensive
- 🎯 Monitoring and observability complete

## Monitoring Test Results

The test runner generates detailed reports:

```
📊 TEST SUITE ANALYSIS
======================
Files run: 4
Failed: 4 ❌
Passed: 0 ✅
Missing: 0 ⚠️

TDD Validation: CORRECT
✅ All tests FAILED as expected - TDD approach working correctly
```

If any tests pass, the TDD process is compromised and needs investigation.

## Troubleshooting

### If Tests Pass Unexpectedly
1. Check if implementation was accidentally fixed
2. Verify mocks are isolating external dependencies
3. Ensure tests are running against the right code
4. Review mock contracts for correctness

### If Tests Don't Run
1. Install required dependencies: `pip install pytest freezegun`
2. Ensure PYTHONPATH includes project root
3. Check Django settings configuration
4. Verify test file permissions

### If Mocks Don't Work
1. Check import paths in patch decorators
2. Verify mock object configurations
3. Ensure fixture dependencies are correct
4. Review mock call assertions

## Next Steps

1. **Run the test suite** - Confirm all tests fail
2. **Review failure details** - Understand what needs implementation
3. **Start Green phase** - Implement minimal code to pass tests
4. **Maintain test quality** - Keep TDD discipline throughout

Remember: **Failing tests are not a problem - they're the solution!** They define exactly what correct behavior should look like.