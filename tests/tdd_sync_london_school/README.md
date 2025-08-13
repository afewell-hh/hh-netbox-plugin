# TDD London School Comprehensive Sync Testing Strategy

## Overview
This testing suite implements the London School (mockist) approach to Test-Driven Development for comprehensive sync functionality validation. The focus is on **behavior verification** and **contract testing** through mocks.

## Testing Philosophy: London School Mockist TDD

### Key Principles
1. **Outside-In Development** - Start with acceptance tests and work inward
2. **Mock-Driven Design** - Use mocks to define contracts between objects  
3. **Behavior Verification** - Test HOW objects collaborate, not just state
4. **Interaction Testing** - Focus on message passing between collaborators
5. **Contract Evolution** - Evolve designs through mock-driven feedback

### Test Structure
```
tests/tdd_sync_london_school/
├── conftest.py                    # Test configuration and fixtures
├── test_sync_failures_exposed.py  # Failing tests that expose current bugs
├── test_kubernetes_mock_contracts.py  # K8s client mock contracts
├── test_sync_orchestration.py     # Sync workflow behavior testing
├── test_ui_integration_mocks.py   # Frontend/backend interaction tests
├── test_periodic_sync_behavior.py # Timer and scheduling behavior
├── test_error_recovery_scenarios.py # Error handling and retry logic
├── test_sync_state_transitions.py # State machine behavior
├── mocks/                         # Mock implementations
│   ├── kubernetes_mocks.py
│   ├── fabric_mocks.py
│   ├── api_mocks.py
│   └── ui_mocks.py
└── contracts/                     # Contract definitions
    ├── kubernetes_contracts.py
    ├── sync_contracts.py
    └── ui_contracts.py
```

## Test Categories

### 1. Failure Reproduction Tests (`test_sync_failures_exposed.py`)
These tests MUST FAIL initially to reproduce the current sync issues:
- Manual sync button not triggering backend
- Periodic sync timer not executing
- Kubernetes connection failures
- API endpoint inconsistencies

### 2. Mock Contract Tests (`test_kubernetes_mock_contracts.py`)
Define and test contracts for external dependencies:
- Kubernetes client API contracts
- HTTP request/response contracts
- Database interaction contracts

### 3. Behavior Integration Tests (`test_sync_orchestration.py`)
Test how components collaborate:
- Sync workflow orchestration
- Error propagation between layers
- State synchronization across components

### 4. UI Integration Tests (`test_ui_integration_mocks.py`)
Test frontend/backend interaction:
- Button click event handling
- AJAX request/response cycles
- UI state updates after sync operations

## Mock Strategy

### Kubernetes Client Mocking
```python
# Contract-first approach
class KubernetesClientContract:
    """Defines expected behavior of K8s client"""
    def test_connection(self) -> Dict[str, Any]: ...
    def apply_crd(self, manifest: Dict) -> Dict[str, Any]: ...
    def fetch_crds(self) -> Dict[str, Any]: ...

# Mock implementation
class MockKubernetesClient:
    """Mock that implements the contract"""
    def __init__(self):
        self.test_connection = Mock()
        self.apply_crd = Mock()
        self.fetch_crds = Mock()
```

### Fabric Model Mocking
```python
class MockFabricService:
    """Mock fabric operations"""
    def __init__(self):
        self.get_kubernetes_config = Mock()
        self.trigger_gitops_sync = Mock()
        self.needs_sync = Mock()
```

## Test Execution Strategy

### Phase 1: Expose Current Failures
1. Write failing tests that reproduce sync button issues
2. Write failing tests that expose periodic sync problems
3. Write failing tests that reveal API inconsistencies

### Phase 2: Mock-Driven Design
1. Define contracts for all external dependencies
2. Create mock implementations that satisfy contracts
3. Test contract compliance with real implementations

### Phase 3: Behavior Verification
1. Test sync workflow orchestration
2. Test error handling and recovery
3. Test state transitions and consistency

### Phase 4: Integration Validation
1. Test UI/API integration with mocks
2. Test periodic sync with time mocking
3. Test end-to-end workflows with all mocks

## Running Tests

### Individual Test Categories
```bash
# Run failure reproduction tests (should FAIL initially)
pytest tests/tdd_sync_london_school/test_sync_failures_exposed.py -v

# Run mock contract tests
pytest tests/tdd_sync_london_school/test_kubernetes_mock_contracts.py -v

# Run behavior tests
pytest tests/tdd_sync_london_school/test_sync_orchestration.py -v
```

### Full Test Suite
```bash
# Run all London School TDD tests
pytest tests/tdd_sync_london_school/ -v --tb=short
```

### Continuous Testing
```bash
# Watch mode for TDD workflow
pytest tests/tdd_sync_london_school/ -v --tb=short -f
```

## Expected Outcomes

### Initial State (Tests Should FAIL)
- Manual sync tests fail due to button/API disconnect
- Periodic sync tests fail due to timer issues
- K8s integration tests fail due to connection problems

### After Implementation (Tests Should PASS)
- All sync workflows pass with proper behavior verification
- Mock contracts are satisfied by real implementations
- Integration tests pass with proper coordination

## Mock Evolution Strategy

### Contract Discovery Phase
1. Identify all external dependencies
2. Define minimal contracts for each dependency
3. Create failing tests that expose missing contracts

### Contract Implementation Phase  
1. Implement mocks that satisfy contracts
2. Test real implementations against contracts
3. Evolve contracts based on discovered needs

### Contract Validation Phase
1. Verify mocks behave identically to real implementations
2. Test edge cases and error scenarios
3. Validate contract completeness

## Success Criteria

### Test Coverage Metrics
- 100% of sync workflow paths tested
- All external dependencies mocked with contracts
- All error scenarios covered with recovery tests
- All UI interactions tested with mock backends

### Behavior Verification
- Sync button triggers correct API calls
- Periodic sync executes on proper schedule
- Error states propagate correctly through layers
- State consistency maintained across operations

### Contract Compliance
- All mocks satisfy their defined contracts
- Real implementations pass contract tests
- Contract evolution is tracked and documented