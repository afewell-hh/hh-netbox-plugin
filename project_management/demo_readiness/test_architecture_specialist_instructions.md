# Test Architecture Specialist Instructions

**Agent Role**: Test Architecture Specialist  
**Agent Type**: Claude Sonnet 4  
**Manager**: GUI Test Suite Manager
**Focus**: Lightweight test framework design for demo validation

---

## IMMEDIATE TASK

Design and implement a lightweight test runner framework for GUI validation that:
- Executes all tests in < 2 minutes
- Provides clear pass/fail output for agents
- Focuses on demo workflow validation
- Enables easy test addition by other specialists

## Standard Training Modules
- **Environment**: @onboarding/04_environment_mastery/ENVIRONMENT_MASTER.md
- **Testing Authority**: @onboarding/04_environment_mastery/TESTING_AUTHORITY_MODULE.md
- **Specialist Track**: @onboarding/03_specialist_track/SPECIALIST_MASTERY.md

## SPECIFIC DELIVERABLES

### 1. Test Runner Framework (`/tests/gui_validation/test_runner.py`)
```python
# Core requirements:
- Test discovery system
- Execution orchestration  
- Time tracking per test
- Clear result reporting
- Return code for CI/CD integration
```

### 2. Base Test Class (`/tests/gui_validation/base_test.py`)
```python
# Provide common functionality:
- NetBox client setup
- Authentication handling
- Response validation helpers
- Timing utilities
- Consistent error reporting
```

### 3. CLI Interface (`run_demo_tests.py`)
```python
# Agent-friendly interface:
- Single command execution
- Progress indicators
- Summary results
- Optional verbose mode
- Exit codes for automation
```

### 4. Configuration System
- Test selection/filtering
- Timeout management
- Environment configuration
- Parallel execution options

## SUCCESS CRITERIA

- [ ] Framework executes in < 30 seconds overhead
- [ ] Other specialists can easily add tests
- [ ] Clear documentation for agent usage
- [ ] No external dependencies beyond existing HNP requirements
- [ ] Manager approves architecture design

## ARCHITECTURE CONSTRAINTS

**Keep It Simple**:
- Use Python standard library where possible
- Leverage existing Django test infrastructure
- No complex test frameworks (pytest, behave)
- Focus on demo needs, not comprehensive testing

**Performance First**:
- Minimize setup/teardown time
- Enable parallel test execution
- Cache authentication tokens
- Quick failure reporting

---

**SPECIALIST READY**: Design lightweight test architecture focused on demo validation and agent usability.