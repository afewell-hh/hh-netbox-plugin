# GUI Testing Specialist Instructions

**Agent Role**: GUI Testing Specialist  
**Agent Type**: Claude Sonnet 4  
**Manager**: GUI Test Suite Manager
**Focus**: Demo workflow test implementation

---

## IMMEDIATE TASK

Implement GUI validation tests for management demo scenarios:
- Test all pages load without errors
- Validate button functionality
- Verify data displays correctly
- Ensure workflows complete successfully

## Standard Training Modules
- **Environment**: @onboarding/04_environment_mastery/ENVIRONMENT_MASTER.md
- **Testing Authority**: @onboarding/04_environment_mastery/TESTING_AUTHORITY_MODULE.md
- **Specialist Track**: @onboarding/03_specialist_track/SPECIALIST_MASTERY.md

## SPECIFIC TEST IMPLEMENTATIONS

### 1. Page Load Tests (`/tests/gui_validation/test_page_loads.py`)
```python
Test Coverage:
- Plugin dashboard (/plugins/hedgehog/)
- Fabric list/detail pages
- All 12 CRD type list pages
- CRD detail pages (sample each type)
- Navigation menu integration
```

### 2. Button Functionality Tests (`/tests/gui_validation/test_buttons.py`)
```python
Critical Buttons:
- "Test Connection" - verify response
- "Sync from Git" - check execution
- "Create" buttons for CRDs
- "Save" on edit forms
- Navigation links
```

### 3. Data Display Tests (`/tests/gui_validation/test_data_display.py`)
```python
Validate:
- CRD "From Git" attribution shown correctly
- Sync counts match actual data
- Fabric status displays
- Error messages (if any) are helpful
- Lists show appropriate columns
```

### 4. Workflow Tests (`/tests/gui_validation/test_workflows.py`)
```python
End-to-End Scenarios:
- Create new fabric workflow
- Test connection → view results
- Sync from Git → verify attribution
- Create CRD → appears in list
- Edit CRD → changes saved
```

## TEST IMPLEMENTATION GUIDELINES

**Focus on Success Cases**:
- Test what should work for demo
- Don't test error handling extensively
- Verify happy path scenarios
- Skip edge cases for now

**Use Architecture Framework**:
- Inherit from base test class
- Follow naming conventions
- Keep tests fast and focused
- Provide clear failure messages

## SUCCESS CRITERIA

- [ ] All demo workflows have test coverage
- [ ] Each test executes in < 5 seconds
- [ ] Tests use existing GUI (no mocking)
- [ ] Failures indicate what's broken clearly
- [ ] Manager validates demo coverage complete

---

**SPECIALIST READY**: Implement demo-focused GUI tests that ensure management presentation success.