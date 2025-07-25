# Integration Specialist Instructions

**Agent Role**: Integration Specialist  
**Agent Type**: Claude Sonnet 4  
**Manager**: GUI Test Suite Manager
**Focus**: Test suite environment integration and agent usability

---

## IMMEDIATE TASK

Integrate the GUI test suite with HNP environment ensuring:
- Works with NetBox Docker setup
- Handles test data appropriately
- Provides excellent agent experience
- Enables regression prevention workflow

## Standard Training Modules
- **Environment**: @onboarding/04_environment_mastery/ENVIRONMENT_MASTER.md
- **Testing Authority**: @onboarding/04_environment_mastery/TESTING_AUTHORITY_MODULE.md
- **Specialist Track**: @onboarding/03_specialist_track/SPECIALIST_MASTERY.md

## SPECIFIC DELIVERABLES

### 1. Environment Integration (`/tests/gui_validation/environment.py`)
```python
Handle:
- NetBox Docker connection (localhost:8000)
- Authentication (admin/admin or token)
- Database state management
- Test isolation strategies
```

### 2. Test Data Management (`/tests/gui_validation/fixtures.py`)
```python
Provide:
- Minimal test data setup
- Safe test execution (non-destructive)
- Cleanup utilities (if needed)
- Demo-realistic data scenarios
```

### 3. Agent Usage Documentation (`/tests/gui_validation/README.md`)
```markdown
Include:
- Quick start guide for agents
- How to run before/after changes
- Interpreting results
- Adding new tests
- Troubleshooting common issues
```

### 4. Integration Scripts
```bash
# Helper scripts:
- run_demo_tests.py (main entry point)
- quick_check.sh (pre-commit hook)
- test_single_workflow.py (debugging)
```

## INTEGRATION REQUIREMENTS

**Work With Existing Setup**:
- No new dependencies
- Use current NetBox Docker
- Compatible with development workflow
- Don't modify HNP core code

**Agent Workflow Integration**:
```bash
# Before making changes:
./run_demo_tests.py  # Baseline

# After making changes:
./run_demo_tests.py  # Verify no regression

# If intentional GUI change:
# Update relevant test, document in PR
```

## SUCCESS CRITERIA

- [ ] Tests run without special setup
- [ ] Clear instructions for agents
- [ ] No interference with development
- [ ] Fast execution encourages usage
- [ ] Manager confirms integration smooth

## SPECIAL CONSIDERATIONS

**Data Safety**:
- Don't delete production-like data
- Create test-specific fabrics if needed
- Preserve existing GUI state
- Enable parallel development

**Agent Experience**:
- One command to run all tests
- Clear success/failure indicators
- Helpful error messages
- Quick execution time

---

**SPECIALIST READY**: Integrate test suite for seamless agent usage and demo confidence.