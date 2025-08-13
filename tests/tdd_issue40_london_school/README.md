# TDD London School Test Suite for Issue #40

## Test-Driven Development Approach

This comprehensive test suite follows the **London School TDD methodology** to fix Issue #40: "Periodic sync not triggering despite sync_enabled=Yes and sync_interval=60 seconds."

### London School TDD Principles Applied

1. **Mock-Driven Development**: All external dependencies are mocked extensively
2. **Outside-In Design**: Start with acceptance tests, work inward to implementation
3. **Behavior Focus**: Test HOW objects collaborate, not what they contain
4. **Contract Testing**: Verify interactions between components
5. **Red-Green-Refactor**: All tests FAIL initially, proving the broken state

## Test Structure

### 1. Acceptance Tests (`test_acceptance_failing.py`)
**Purpose**: Capture the exact user observation and prove the system is broken

**Key Tests**:
- `test_user_observation_never_synced_despite_enabled_config()`: Proves user's reported issue
- `test_periodic_sync_timer_not_triggering_60_second_intervals()`: Verifies timer failure
- `test_celery_beat_schedule_configuration_broken()`: Checks Celery Beat config
- `test_real_netbox_environment_broken_state()`: Integration with real NetBox

**Expected Result**: ALL TESTS FAIL initially, proving Issue #40 is real

### 2. Mock-Driven Component Tests (`test_mock_driven_components.py`)
**Purpose**: Test object interactions and collaborations using extensive mocking

**Key Tests**:
- `TestSchedulerFabricCollaboration`: How Scheduler talks to Fabric objects
- `TestCelerySchedulerIntegration`: Contract between Celery and Scheduler
- `TestNetBoxRQIntegration`: Integration with NetBox's RQ system
- `TestSyncTaskExecutorCollaboration`: How sync tasks collaborate

**London School Focus**: 
- Mock ALL external dependencies
- Test message passing between objects
- Verify contracts are honored
- Focus on behavior, not state

### 3. Integration & Timing Tests (`test_integration_timing.py`)
**Purpose**: Verify end-to-end functionality and precise 60-second timing

**Key Tests**:
- `test_60_second_periodic_sync_timer_precision()`: Precise timing verification
- `test_celery_beat_process_running_and_scheduling()`: Infrastructure validation
- `test_real_fabric_sync_state_changes()`: Database state change verification
- `test_multiple_fabrics_sync_coordination()`: Multi-fabric coordination

**Expected Result**: FAIL due to broken periodic sync infrastructure

### 4. Behavior Verification Tests (`test_behavior_verification.py`)
**Purpose**: Verify object behavior patterns and collaboration protocols

**Key Tests**:
- `TestSchedulerBehaviorVerification`: Scheduler behavior patterns
- `TestFabricSyncBehaviorVerification`: How fabrics respond to sync requests
- `TestTaskExecutionBehaviorVerification`: Task collaboration patterns
- `TestErrorHandlingBehaviorVerification`: Error handling and recovery behavior

**London School Focus**: 
- Extensive mocking of collaborators
- Verification of method calls and message passing
- Behavior assertions, not state checks
- Protocol compliance testing

## Test Execution

### Running All Tests
```bash
# Run the full TDD suite
pytest tests/tdd_issue40_london_school/ -v

# Run with real environment integration
pytest tests/tdd_issue40_london_school/ -v --real-env

# Run specific test categories
pytest tests/tdd_issue40_london_school/ -v -m acceptance
pytest tests/tdd_issue40_london_school/ -v -m mock_driven
pytest tests/tdd_issue40_london_school/ -v -m integration
pytest tests/tdd_issue40_london_school/ -v -m behavior
```

### Expected Initial Results
**ALL TESTS SHOULD FAIL** - This proves Issue #40 is real and the system is broken.

Common failure patterns expected:
- `ImportError`: Scheduler modules not properly importable
- `AssertionError`: Periodic sync not triggering
- `ConnectionError`: Celery/RQ integration issues
- `AttributeError`: Missing scheduler_enabled field
- Timing failures: 60-second intervals not working

## TDD Implementation Cycle

### Phase 1: RED (Failing Tests) ✅
All tests fail, proving the broken state. This phase is COMPLETE.

### Phase 2: GREEN (Minimal Implementation)
Implement just enough code to make tests pass:

1. Fix import issues and missing fields
2. Implement basic periodic sync infrastructure
3. Ensure 60-second timing works
4. Fix fabric discovery and sync execution
5. Implement proper error handling

### Phase 3: REFACTOR (Improve Design)
Once tests pass, refactor for better design:

1. Optimize performance
2. Improve error handling
3. Add comprehensive logging
4. Enhance monitoring and metrics
5. Document the solution

## Mock Architecture

### Comprehensive Mocking Strategy

**External Dependencies Mocked**:
- Django ORM (`HedgehogFabric.objects`)
- Celery application and tasks
- Redis/RQ connections
- Kubernetes API clients
- Git repositories
- Event services
- File system operations

**Mock Fixtures Available**:
- `mock_hedgehog_fabric`: Complete fabric mock with behavior
- `mock_fabric_manager`: Django ORM manager mock
- `mock_celery_app`: Celery application mock
- `mock_rq_queue`: NetBox RQ queue mock
- `mock_enhanced_sync_scheduler`: Scheduler behavior mock

### Contract Testing Approach

Each test verifies:
1. **Method calls made**: What methods were called with what arguments
2. **Collaboration sequences**: Order of interactions between objects
3. **Contract compliance**: Objects honor their expected interfaces
4. **Behavior responses**: How objects respond to different stimuli

## Key Insights for Implementation

### Root Cause Hypotheses (From Tests)

1. **Celery Beat Not Running**: Tests verify Celery Beat process status
2. **NetBox RQ Integration Missing**: NetBox uses RQ, but sync might use Celery
3. **scheduler_enabled Field Missing**: Tests check for missing database field
4. **Fabric Discovery Broken**: Tests verify fabric query logic
5. **Task Registration Issues**: Tests verify Celery task registration

### Critical Implementation Requirements

1. **60-Second Precision**: Master scheduler MUST run every 60 seconds
2. **Fabric Discovery**: MUST find sync-enabled fabrics correctly
3. **Task Orchestration**: MUST execute sync tasks through proper queuing
4. **Error Handling**: MUST handle errors gracefully without stopping scheduler
5. **State Updates**: MUST update fabric.last_sync and sync_status correctly

## Test-Driven Implementation Guide

Follow this TDD cycle strictly:

1. **Run Tests**: Verify they FAIL for the right reasons
2. **Write Minimal Code**: Just enough to make ONE test pass
3. **Run Tests Again**: Verify the test now passes
4. **Refactor**: Improve code quality while keeping tests green
5. **Repeat**: Move to next failing test

### Implementation Priority Order

1. Fix Django app registration and imports
2. Implement missing database fields (scheduler_enabled)
3. Create basic scheduler task structure
4. Implement Celery Beat configuration
5. Add fabric discovery logic
6. Implement task orchestration
7. Add timing precision controls
8. Implement error handling and recovery
9. Add comprehensive logging and monitoring

## Success Criteria

The implementation is complete when:

1. **All tests pass**: Every test in this suite runs successfully
2. **60-second precision**: Periodic sync triggers every 60 seconds (±5s tolerance)
3. **Real environment works**: Tests pass against real NetBox with `--real-env`
4. **User observation resolved**: Fabrics no longer show "Never Synced" with proper config
5. **Behavioral contracts honored**: All mock-driven tests verify proper object interactions

## Next Steps After Tests Pass

1. **Performance Testing**: Ensure scheduler scales with many fabrics
2. **Production Deployment**: Deploy with proper monitoring
3. **User Acceptance Testing**: Verify user's original issue is resolved
4. **Documentation**: Update user guides and operational procedures
5. **Monitoring Setup**: Add alerts for scheduler health and timing

---

**Remember**: This is TRUE test-driven development. Every line of implementation code should be written to make a failing test pass. No code should exist without a test that drove its creation.