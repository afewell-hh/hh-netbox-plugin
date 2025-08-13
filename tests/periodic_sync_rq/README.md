# TDD Tests for RQ-based Periodic Sync

## Overview

This test suite implements **comprehensive TDD (Test-Driven Development) tests** for migrating the Hedgehog NetBox Plugin's periodic sync system from Celery Beat to NetBox's native RQ (Redis Queue) system.

## Root Cause Analysis

**Problem**: The sync system was designed to use Celery Beat for periodic scheduling, but NetBox uses RQ for background job processing. This architectural mismatch causes the user-reported issue where sync intervals (e.g., 60 seconds) never trigger actual sync operations.

**Evidence**:
- Celery configuration exists in `netbox_hedgehog/celery.py`
- User reports fabric `sync_interval=60` but sync never executes after minutes
- NetBox uses `django-rq` for background jobs, not Celery
- No RQ-based periodic scheduling integration exists

## TDD Methodology

These tests follow strict TDD principles:

### 1. RED Phase (Current State)
- **ALL TESTS MUST FAIL INITIALLY**
- Tests define specifications for non-existent functionality
- Failures guide implementation requirements
- Each test failure represents a missing component

### 2. GREEN Phase (Implementation)
- Implement minimal code to make tests pass
- Focus on core RQ integration functionality
- Replace Celery Beat with RQ Scheduler
- Integrate with NetBox's existing RQ configuration

### 3. REFACTOR Phase (Optimization)
- Improve code quality while keeping tests passing
- Optimize timing precision and reliability
- Enhance error handling and edge cases

## Test Architecture

### Test Pyramid Structure

```
         /\
        /E2E\      <- 10%: End-to-end workflows
       /------\
      /Integr. \   <- 30%: RQ + Django + NetBox integration
     /----------\
    /   Unit     \ <- 60%: Individual RQ components
   /--------------\
```

### Test Categories

#### 1. RQ Scheduler Integration (`test_rq_scheduler_integration.py`)
**Purpose**: Test RQ job registration and scheduling mechanics

**Key Tests**:
- `test_rq_periodic_sync_job_registered_in_netbox_queues()`
- `test_rq_scheduler_integration_with_django_rq()`
- `test_rq_job_execution_at_specified_interval()`
- `test_netbox_rq_queue_configuration_includes_hedgehog_tasks()`

**Expected Failures** (RED Phase):
- `ImportError: No module named 'netbox_hedgehog.rq_jobs.periodic_sync'`
- `ImportError: No module named 'netbox_hedgehog.rq_jobs.scheduler'`
- NetBox `RQ_QUEUES` doesn't include Hedgehog queues

#### 2. Fabric Sync State Transitions (`test_fabric_sync_state_transitions.py`)
**Purpose**: Test sync state lifecycle management in RQ system

**Key Tests**:
- `test_sync_state_never_synced_to_syncing_transition()`
- `test_sync_state_syncing_to_in_sync_on_success()`
- `test_sync_state_syncing_to_error_on_failure()`
- `test_sync_state_atomic_transitions_prevent_race_conditions()`

**Expected Failures** (RED Phase):
- `ImportError: No module named 'netbox_hedgehog.rq_jobs.fabric_sync'`
- `ImportError: No module named 'netbox_hedgehog.rq_jobs.state_manager'`
- No atomic transaction handling for state transitions

#### 3. RQ Job Timing Precision (`test_rq_job_timing_precision.py`)
**Purpose**: Test precise timing for user's 60-second interval requirement

**Key Tests**:
- `test_60_second_interval_triggers_within_tolerance()`
- `test_rq_scheduler_handles_missed_execution_recovery()`
- `test_rq_scheduler_prevents_execution_drift()`
- `test_rq_scheduler_timing_under_system_load()`

**Expected Failures** (RED Phase):
- `ImportError: No module named 'netbox_hedgehog.rq_jobs.timing_scheduler'`
- No RQ scheduler timing mechanism exists
- No interval-based job scheduling exists

#### 4. NetBox RQ Integration (`test_netbox_rq_integration.py`)
**Purpose**: Test integration with NetBox's existing RQ infrastructure

**Key Tests**:
- `test_netbox_rq_queues_includes_hedgehog_sync_queues()`
- `test_hedgehog_sync_tasks_discoverable_by_netbox_rq_workers()`
- `test_netbox_rq_redis_connection_compatibility()`
- `test_netbox_rq_worker_can_process_hedgehog_tasks()`

**Expected Failures** (RED Phase):
- `ImportError: No module named 'netbox_hedgehog.rq_tasks'`
- NetBox RQ configuration doesn't include Hedgehog queues
- No integration with NetBox's RQ worker management

## Test Execution

### Running the Full Test Suite

```bash
# Execute TDD test runner
cd /home/ubuntu/cc/hedgehog-netbox-plugin/tests/periodic_sync_rq
python test_runner.py
```

### Running Individual Test Categories

```bash
# Test RQ scheduler integration
python -m pytest test_rq_scheduler_integration.py -v

# Test state transitions
python -m pytest test_fabric_sync_state_transitions.py -v

# Test timing precision
python -m pytest test_rq_job_timing_precision.py -v

# Test NetBox integration
python -m pytest test_netbox_rq_integration.py -v
```

### Running with Specific Markers

```bash
# Run only RQ integration tests
python -m pytest -m rq_integration -v

# Run only timing precision tests
python -m pytest -m timing_precision -v

# Run only state transition tests
python -m pytest -m state_transitions -v
```

## Expected Test Results (RED Phase)

### ✅ SUCCESS CRITERIA for RED Phase
- **High Failure Rate**: >80% of tests should FAIL initially
- **Import Errors**: Missing modules indicate implementation needs
- **Configuration Errors**: Missing NetBox RQ queue configuration
- **Specification Clarity**: Test failures clearly indicate what to implement

### ❌ FAILURE CRITERIA for RED Phase
- Tests pass without implementation (indicates incomplete test specification)
- Low failure rate (<50%) suggests tests aren't comprehensive enough
- Unclear error messages that don't guide implementation

## Implementation Requirements (From Test Failures)

### Critical Components to Implement

#### 1. RQ Task Modules
```
netbox_hedgehog/rq_tasks/
├── __init__.py
├── fabric_sync.py          # Core fabric sync tasks
├── git_sync.py            # GitOps sync tasks
├── queue_manager.py       # Queue management utilities
└── worker_config.py       # Worker configuration
```

#### 2. RQ Scheduler Integration
```
netbox_hedgehog/rq_scheduler/
├── __init__.py
├── timing_scheduler.py    # Precise interval scheduling
├── persistence.py         # Job persistence across restarts
└── recovery.py           # Missed execution recovery
```

#### 3. NetBox Configuration Updates
```python
# In NetBox settings
RQ_QUEUES = {
    # ... existing NetBox queues ...
    'hedgehog_sync': {
        'HOST': 'redis',
        'PORT': 6379,
        'DB': 0,
        'DEFAULT_TIMEOUT': 360,
    },
    'hedgehog_git': {
        'HOST': 'redis', 
        'PORT': 6379,
        'DB': 0,
        'DEFAULT_TIMEOUT': 360,
    },
    'hedgehog_fabric': {
        'HOST': 'redis',
        'PORT': 6379,
        'DB': 0,
        'DEFAULT_TIMEOUT': 360,
    }
}
```

#### 4. State Management
```
netbox_hedgehog/rq_jobs/
├── state_manager.py       # Atomic state transitions
├── state_validator.py     # State consistency validation
└── monitoring.py         # Sync execution monitoring
```

## User Issue Resolution

### Specific Problem
- User sets `fabric.sync_interval = 60` seconds
- Sync never executes after several minutes
- Status remains "Never Synced" indefinitely

### TDD Solution Approach
1. **Tests Define Behavior**: Tests specify exactly how 60-second intervals should work
2. **Timing Precision**: Tests validate sync triggers within 58-65 second tolerance
3. **State Transitions**: Tests ensure proper status updates during sync lifecycle
4. **Error Recovery**: Tests handle connection failures gracefully
5. **NetBox Integration**: Tests ensure RQ jobs work within NetBox ecosystem

### Key Test Cases for User Issue
- `test_60_second_sync_interval_triggers_within_tolerance()`: Validates user's exact scenario
- `test_sync_status_changes_from_never_synced_to_syncing()`: Ensures status updates
- `test_fabric_last_sync_timestamp_reflects_actual_execution_time()`: Provides debugging visibility

## Advanced Testing Features

### Timing Validation
- **Precision Testing**: Validates intervals within 5-second tolerance
- **Drift Prevention**: Ensures timing doesn't degrade over multiple cycles  
- **Load Testing**: Maintains timing accuracy under system load
- **Recovery Testing**: Handles missed executions after system restart

### Error Injection
- **Connection Failures**: Tests Kubernetes API unreachability
- **Redis Failures**: Tests Redis connection loss scenarios
- **Worker Failures**: Tests RQ worker process interruptions
- **Resource Exhaustion**: Tests behavior under resource constraints

### Race Condition Testing
- **Concurrent Sync Prevention**: Ensures only one sync per fabric at a time
- **Atomic State Transitions**: Prevents inconsistent database states
- **Job Queue Integrity**: Maintains job ordering and execution guarantees

## Integration with Existing Systems

### NetBox Compatibility
- Uses NetBox's existing Redis configuration
- Integrates with NetBox's RQ worker management
- Respects NetBox's logging and monitoring systems
- Maintains NetBox admin interface compatibility

### Backward Compatibility
- Existing fabric configurations continue working
- Graceful migration from Celery Beat (if any remnants exist)
- Preserves existing sync status and history
- Maintains API compatibility for external integrations

## Performance Considerations

### Scalability Testing
- **Multiple Fabrics**: Tests behavior with 10+ fabrics with different intervals
- **High Frequency**: Tests short intervals (5-30 seconds) for performance impact
- **Queue Backlog**: Tests behavior when RQ queues have job backlogs
- **Memory Usage**: Validates memory consumption patterns

### Reliability Testing  
- **Long Duration**: Tests continuous operation over hours/days
- **System Restarts**: Tests persistence across NetBox/Redis restarts
- **Network Partitions**: Tests behavior during network connectivity issues
- **Resource Limits**: Tests behavior at system resource boundaries

## Monitoring and Observability

### Test Coverage Metrics
- **Code Coverage**: Target >90% line coverage for RQ integration code
- **Branch Coverage**: Target >85% decision branch coverage
- **Integration Coverage**: All NetBox RQ integration points tested

### Performance Metrics
- **Timing Accuracy**: Measure actual vs expected execution times
- **Resource Usage**: Monitor memory, CPU, Redis connection usage
- **Throughput**: Measure jobs processed per minute under load
- **Latency**: Measure time from schedule to execution

## Documentation Integration

### Code Documentation
- All RQ task functions include comprehensive docstrings
- State transition logic clearly documented with examples
- Error handling strategies documented with recovery procedures

### User Documentation
- Update NetBox admin UI to show RQ job status
- Provide troubleshooting guide for sync timing issues
- Include configuration examples for different use cases

## Success Metrics

### Implementation Success
- **Test Pass Rate**: >95% after implementation (GREEN phase)
- **User Issue Resolution**: 60-second sync intervals work reliably
- **Performance**: Sync operations complete within expected timeframes
- **Reliability**: System handles failures gracefully without data corruption

### Production Readiness
- **Zero Downtime**: Migration doesn't require NetBox restart
- **Resource Efficiency**: RQ system uses ≤ resources compared to Celery
- **Monitoring**: Full observability into sync operations and timing
- **Scalability**: Supports 100+ fabrics with varied sync intervals

---

## Quick Start for Implementation

1. **Analyze Test Failures**: Run `python test_runner.py` to see what needs implementation
2. **Start with Core RQ Tasks**: Implement `netbox_hedgehog/rq_tasks/fabric_sync.py`
3. **Add RQ Scheduler**: Implement `netbox_hedgehog/rq_scheduler/timing_scheduler.py`  
4. **Configure NetBox RQ**: Add Hedgehog queues to NetBox `RQ_QUEUES`
5. **Test Integration**: Verify tests start passing as components are implemented
6. **Iterate**: Follow TDD cycle until all tests pass and user issue is resolved

The test failures will guide you through exactly what needs to be implemented and how it should behave. This is the power of TDD - the tests serve as both specification and validation.