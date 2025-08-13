# Kubernetes Sync TDD Test Suite

This comprehensive test suite implements **London School Test-Driven Development** for the Kubernetes synchronization functionality in the Hedgehog NetBox Plugin.

## 🎯 TDD Philosophy: Tests MUST Fail Initially

**CRITICAL**: These tests are designed to FAIL when first run. This is the core principle of TDD - failing tests drive implementation.

### London School TDD Approach

- **Outside-in development**: Start from user behavior, work down to implementation
- **Mock-driven development**: Use mocks to isolate units and define contracts  
- **Behavior verification**: Focus on interactions between objects, not internal state
- **Contract definition**: Tests define the exact behavior contracts through mock expectations

## 📁 Test Structure

```
tests/k8s_sync/
├── __init__.py                     # Test configuration and constants
├── README.md                       # This documentation
├── conftest.py                     # Pytest configuration and fixtures
├── test_runner.py                  # Comprehensive test runner with reporting
├── unit/                           # Unit tests (London School TDD)
│   ├── test_sync_state_calculation.py     # 7 sync states with exact timing
│   ├── test_gui_state_validation.py       # HTML output validation
│   └── test_error_injection.py            # Error scenarios and recovery
├── integration/                    # Integration tests
│   └── test_real_k8s_cluster.py          # Real cluster connectivity
├── performance/                    # Performance benchmarks
│   └── test_sync_performance.py          # Load testing and optimization
├── mocks/                          # Mock implementations
│   └── k8s_client_mocks.py              # K8s API mocks with scenarios
└── utils/                          # Test utilities
    ├── test_factories.py              # Factory pattern for test data
    ├── timing_helpers.py              # Precision timing validation
    └── gui_validators.py              # HTML/CSS validation helpers
```

## 🧪 Test Categories

### 1. State Calculation Tests (MUST FAIL)
**File**: `unit/test_sync_state_calculation.py`

Tests the 7 sync states with precise timing requirements:
- `not_configured`: kubernetes_server empty/null/whitespace
- `disabled`: sync_enabled = False
- `never_synced`: No sync history
- `in_sync`: Within sync interval (±5 seconds)
- `out_of_sync`: Beyond sync interval
- `syncing`: Active sync task present
- `error`: Connection or sync errors

**Expected Failures**: All tests will fail initially since `calculated_sync_status` property logic needs implementation.

### 2. GUI State Validation Tests (MUST FAIL)
**File**: `unit/test_gui_state_validation.py`

Validates exact HTML output for each sync state:
- CSS classes: `bg-success`, `bg-warning`, `bg-danger`, etc.
- Icons: `mdi-check-circle`, `mdi-sync-alert`, etc.  
- Colors: #198754 (green), #ffc107 (yellow), #dc3545 (red)
- Responsive behavior at different viewport sizes
- WCAG 2.1 AA accessibility compliance

**Expected Failures**: Template rendering doesn't exist with state-specific styling.

### 3. Real K8s Integration Tests (MUST FAIL)
**File**: `integration/test_real_k8s_cluster.py`

Tests actual cluster connectivity:
- Connects to `vlab-art.l.hhdev.io:6443`
- Uses `hnp-sync` service account
- Tests real CRD operations
- End-to-end sync workflows
- Network error handling with actual conditions

**Expected Failures**: K8s client implementation doesn't exist yet.

### 4. Error Injection Tests (MUST FAIL)
**File**: `unit/test_error_injection.py`

Comprehensive error scenario testing:
- Network failures (timeout, refused, DNS)
- Authentication failures (invalid token, expired, permissions)
- API server errors (500, 503, rate limiting)
- Circuit breaker patterns
- Exponential backoff retry logic

**Expected Failures**: Error handling and recovery logic not implemented.

### 5. Performance Benchmarks (MUST FAIL)
**File**: `performance/test_sync_performance.py`

Performance requirements validation:
- State calculation: < 5ms per operation
- GUI updates: < 2 seconds from state change
- API responses: < 200ms (status), < 500ms (sync trigger)
- Memory efficiency: < 1KB per fabric, no leaks
- Concurrent operations: 100+ fabrics

**Expected Failures**: Optimized implementations don't exist yet.

## 🚀 Running the Tests

### Quick Start
```bash
# Run the comprehensive test runner
cd /home/ubuntu/cc/hedgehog-netbox-plugin
python tests/k8s_sync/test_runner.py

# Expected output: All tests should FAIL (this is correct for TDD!)
```

### Specific Test Categories
```bash
# Run only unit tests
python tests/k8s_sync/test_runner.py --category state_calculation

# Run with integration tests (requires K8s cluster access)
python tests/k8s_sync/test_runner.py --integration

# Run with performance tests (slow)
python tests/k8s_sync/test_runner.py --performance

# Run everything
python tests/k8s_sync/test_runner.py --all
```

### Using Pytest Directly
```bash
# Run specific test file
pytest tests/k8s_sync/unit/test_sync_state_calculation.py -v

# Run with markers
pytest tests/k8s_sync/ -m "not integration" -v

# Run integration tests only
pytest tests/k8s_sync/ -m integration -v
```

## 📊 Expected Test Results

### Initial Run (Before Implementation)
```
🧪 KUBERNETES SYNC TDD TEST SUITE RESULTS
==========================================
📊 Overall Summary:
   Categories Run: 5
   Total Tests: 47
   Passed: 0
   Failed: 47 (Expected for TDD)
   Duration: 12.3s

🎯 TDD Compliance Analysis:
   ✅ state_calculation (CRITICAL): 15/15 failing
   ✅ gui_validation (CRITICAL): 12/12 failing  
   ✅ error_injection (CRITICAL): 8/8 failing
   ✅ k8s_integration: 7/7 failing
   ✅ performance: 5/5 failing

🚧 Implementation Progress: 0.0%
   ⭕ Not Started: state_calculation, gui_validation, error_injection, k8s_integration, performance

🎯 Next Implementation Priorities:
   1. state_calculation: State calculation logic for all 7 sync states (15 failing tests)
   2. gui_validation: GUI HTML output and visual representation (12 failing tests)
   3. error_injection: Error handling and recovery scenarios (8 failing tests)

🔥 TDD SUCCESS: Tests are failing as expected!
🎯 These failing tests drive the implementation requirements.
🚀 Implement features to make tests pass one by one.
```

## 🔧 Implementation Roadmap

### Phase 1: Core State Calculation (Priority 1)
**Target**: Make `test_sync_state_calculation.py` pass

1. **Implement `calculated_sync_status` property** in `HedgehogFabric` model
2. **Add precise timing logic** with ±5 second tolerance
3. **Implement state priority hierarchy** (not_configured > disabled > error > timing-based)
4. **Optimize for performance** (< 5ms per calculation)

Expected failing tests → passing tests: `15 → 0`

### Phase 2: GUI State Representation (Priority 2)  
**Target**: Make `test_gui_state_validation.py` pass

1. **Create state-specific template logic** with exact CSS classes
2. **Add responsive design** for mobile/tablet/desktop
3. **Implement progress bars** for syncing state
4. **Add accessibility features** (ARIA labels, alt text)

Expected failing tests → passing tests: `12 → 0`

### Phase 3: Error Handling & Recovery (Priority 3)
**Target**: Make `test_error_injection.py` pass

1. **Implement error categorization** (network, auth, API)
2. **Add exponential backoff retry logic** with proper limits
3. **Create circuit breaker pattern** for fault tolerance
4. **Add error-specific admin guidance** messages

Expected failing tests → passing tests: `8 → 0`

### Phase 4: K8s Integration (Priority 4)
**Target**: Make `test_real_k8s_cluster.py` pass

1. **Create K8sClient implementation** for real cluster access
2. **Add CRD operations** (list, create, update, delete)
3. **Implement sync task orchestration** with progress tracking
4. **Add authentication and RBAC validation**

Expected failing tests → passing tests: `7 → 0`

### Phase 5: Performance Optimization (Priority 5)
**Target**: Make `test_sync_performance.py` pass

1. **Optimize state calculations** for sub-5ms performance
2. **Add efficient database queries** (no N+1 problems)
3. **Implement concurrent sync handling** for 100+ fabrics
4. **Add memory leak prevention** and garbage collection

Expected failing tests → passing tests: `5 → 0`

## 🎯 Success Criteria

### Definition of Done
A test category is "complete" when:
- ✅ All tests in the category pass
- ✅ No failing tests remain
- ✅ Performance requirements met
- ✅ Error scenarios handled
- ✅ Edge cases covered

### Final Target State
```
🧪 KUBERNETES SYNC TDD TEST SUITE RESULTS
==========================================
📊 Overall Summary:
   Categories Run: 5
   Total Tests: 47
   Passed: 47
   Failed: 0
   Duration: 8.1s

🚧 Implementation Progress: 100.0%
   ✅ Completed: state_calculation, gui_validation, error_injection, k8s_integration, performance

🏆 IMPLEMENTATION COMPLETE: All TDD requirements satisfied!
```

## 📋 Test Configuration

### Environment Setup
Tests automatically configure:
- SQLite in-memory database
- Mock K8s client by default
- Django test settings
- Isolated test data

### Test Markers
- `@pytest.mark.integration`: Requires external services
- `@pytest.mark.k8s_cluster`: Requires real K8s cluster
- `@pytest.mark.performance`: Performance/load testing
- `@pytest.mark.slow`: Long-running tests
- `@pytest.mark.gui`: GUI validation tests

### Required Dependencies
```bash
pip install pytest pytest-django pytest-json-report
pip install factory-boy freezegun beautifulsoup4
pip install psutil  # For performance monitoring
```

## 🔍 Debugging Failed Tests

### Understanding Failures
When tests fail (expected initially):
1. **Read the assertion message** - it explains what's missing
2. **Check the mock interactions** - London School tests verify behavior
3. **Look at the expected vs actual** - shows exactly what needs implementation

### Example Failure Analysis
```python
# Test failure:
AssertionError: Sync state assertion failed:
   Expected state: in_sync
   Actual state: never_synced
   Fabric: test-fabric-1
   Server: https://vlab-art.l.hhdev.io:6443
   Enabled: True
   Last sync: 2025-01-10 12:34:56+00:00

# This tells you:
# 1. The calculated_sync_status property isn't working correctly
# 2. It should return 'in_sync' based on the fabric configuration
# 3. Implementation needed in fabric.py model
```

## 🏆 Benefits of This TDD Approach

### 1. **Exact Requirements Definition**
Tests define precise behavior contracts before implementation starts.

### 2. **Implementation Confidence** 
When tests pass, you know the implementation is correct and complete.

### 3. **Regression Prevention**
Tests catch any breaking changes during development.

### 4. **Documentation Through Tests**
Tests serve as executable documentation of system behavior.

### 5. **Incremental Progress**
Implement one failing test at a time, making steady progress.

---

## 🚀 Start Implementation

Ready to begin? Run the test suite and start making tests pass:

```bash
cd /home/ubuntu/cc/hedgehog-netbox-plugin
python tests/k8s_sync/test_runner.py
```

**Remember**: Failing tests are SUCCESS in TDD. They're your roadmap to implementation!

---

*This test suite follows London School TDD principles and drives implementation through behavior specification.*