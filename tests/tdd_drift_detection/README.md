# TDD Drift Detection Test Suite

## Overview

This Test-Driven Development (TDD) test suite defines **EXACT behavioral requirements** for the drift detection GUI feature. Each test specifies precise expected behavior **BEFORE** implementation, ensuring the final implementation meets all user requirements.

## 🎯 Test Philosophy

### EXACT Specification Approach

Every test in this suite follows the pattern:

1. **SETUP**: Define initial state with specific test data
2. **ACTION**: Specify exact user interaction or system behavior  
3. **ASSERTION**: Validate precise expected results
4. **CLEANUP**: Ensure proper test isolation

### Requirements Validation

Tests validate these critical requirements from the Requirements Analyst:

✅ **Navigation Menu Integration**
- Drift detection appears in navigation menu
- Navigation links function correctly
- Menu structure is properly organized

✅ **Dashboard Hyperlink Functionality** 
- Dashboard drift count is clickable
- Hyperlink navigates to correct URL
- Drift count displays accurate values

✅ **Fabric Detail Integration**
- Fabric detail pages show drift counts
- Drift counts are hyperlinked when > 0
- Links filter to fabric-specific drift view

✅ **Drift Detection Page Functionality**
- Page loads without errors
- Shows accurate drift statistics  
- Supports fabric filtering
- Provides working action elements

## 📁 Test File Structure

```
tests/tdd_drift_detection/
├── __init__.py                          # Package initialization
├── conftest.py                          # Pytest fixtures and test utilities
├── test_runner.py                       # Test suite execution and reporting
├── README.md                            # This documentation
├── test_navigation_integration.py       # Navigation menu tests
├── test_dashboard_hyperlinks.py         # Dashboard drift count hyperlink tests  
├── test_fabric_detail_integration.py    # Fabric detail drift count tests
├── test_drift_detection_page.py         # Drift detection page functionality tests
└── test_end_to_end_workflows.py         # Complete user workflow tests
```

## 🧪 Test Categories

### 1. Navigation Integration Tests (`test_navigation_integration.py`)

**Purpose**: Verify navigation menu contains drift detection links

**Key Test Methods**:
```python
def test_drift_detection_appears_in_navigation_menu()
def test_drift_detection_navigation_link_works()  
def test_navigation_structure_includes_operations_group()
def test_navigation_link_has_correct_url_pattern()
```

**EXACT Requirements**:
- Navigation must contain 'Operations' group
- 'Drift Detection' link must appear in navigation
- Link must use URL pattern `/plugins/hedgehog/drift-detection/`
- Navigation structure must be properly organized

### 2. Dashboard Hyperlink Tests (`test_dashboard_hyperlinks.py`)

**Purpose**: Verify dashboard drift count is properly hyperlinked

**Key Test Methods**:
```python
def test_dashboard_drift_count_is_hyperlinked()
def test_dashboard_drift_count_navigates_to_correct_url()
def test_dashboard_drift_count_shows_correct_value()
def test_dashboard_drift_card_styling()
```

**EXACT Requirements**:
- Drift count must be wrapped in `<a href="/plugins/hedgehog/drift-detection/">` tag
- Dashboard must show cumulative drift count across all fabrics
- Warning card styling (`bg-warning`) must be used
- Zero drift must still be hyperlinked for consistency

### 3. Fabric Detail Integration Tests (`test_fabric_detail_integration.py`)

**Purpose**: Verify fabric detail pages have hyperlinked drift counts with filtering

**Key Test Methods**:
```python
def test_fabric_detail_shows_drift_count()
def test_fabric_drift_count_hyperlinked_when_greater_than_zero()
def test_fabric_drift_count_static_when_zero()
def test_fabric_drift_link_includes_fabric_filter()
```

**EXACT Requirements**:
- Fabric detail must show drift count in 'Drift Detection' section
- Drift count > 0 must be hyperlinked to `/plugins/hedgehog/drift-detection/fabric/{id}/`
- Zero drift count must NOT be hyperlinked
- Hyperlinks must include fabric ID for filtering

### 4. Drift Detection Page Tests (`test_drift_detection_page.py`)

**Purpose**: Verify drift detection dashboard page loads and functions

**Key Test Methods**:
```python
def test_drift_detection_page_loads_without_error()
def test_drift_detection_page_shows_statistics()
def test_drift_detection_page_supports_fabric_filtering()
def test_drift_detection_page_has_working_actions()
```

**EXACT Requirements**:
- URL `/plugins/hedgehog/drift-detection/` must return 200 status
- Page must contain 'Drift Detection Dashboard' title
- Page must show accurate drift statistics
- Fabric filtering via `/drift-detection/fabric/{id}/` must work

### 5. End-to-End Workflow Tests (`test_end_to_end_workflows.py`)

**Purpose**: Verify complete user workflows function correctly

**Key Test Methods**:
```python
def test_complete_navigation_to_drift_detection_workflow()
def test_dashboard_to_drift_detection_workflow()
def test_fabric_detail_to_filtered_drift_workflow()
def test_complete_round_trip_navigation_workflow()
```

**EXACT Requirements**:
- Login → Dashboard → Drift Detection workflow must work
- Dashboard hyperlink → Drift page navigation must work
- Fabric detail → Filtered drift view workflow must work
- Round-trip navigation must preserve session state

## 🚀 Running the Tests

### Prerequisites

Ensure Django test environment is configured:
```bash
# Set Django settings
export DJANGO_SETTINGS_MODULE=netbox.settings

# Ensure database is ready
python manage.py migrate
```

### Execute All TDD Tests

```bash
# Run complete TDD test suite
cd /home/ubuntu/cc/hedgehog-netbox-plugin/tests/tdd_drift_detection
python test_runner.py
```

### Run Specific Test Categories

```bash
# Navigation tests only
python -m pytest test_navigation_integration.py -v

# Dashboard hyperlink tests only  
python -m pytest test_dashboard_hyperlinks.py -v

# Fabric detail integration tests only
python -m pytest test_fabric_detail_integration.py -v

# Drift detection page tests only
python -m pytest test_drift_detection_page.py -v

# End-to-end workflow tests only
python -m pytest test_end_to_end_workflows.py -v
```

### Run Individual Test Methods

```bash
# Specific test method
python -m pytest test_dashboard_hyperlinks.py::DashboardDriftHyperlinkTests::test_dashboard_drift_count_is_hyperlinked -v
```

## 📊 Expected Test Results

### ❌ BEFORE Implementation
All tests should **FAIL** initially, as they define behavior that doesn't exist yet:

```
🧪 Starting TDD Drift Detection Test Suite
============================================================

📋 Running test_navigation_integration...
   ✅ 0 passed, ❌ 8 failed
📋 Running test_dashboard_hyperlinks...
   ✅ 0 passed, ❌ 12 failed
📋 Running test_fabric_detail_integration...
   ✅ 0 passed, ❌ 15 failed
📋 Running test_drift_detection_page...
   ✅ 0 passed, ❌ 10 failed
📋 Running test_end_to_end_workflows...
   ✅ 0 passed, ❌ 8 failed

============================================================
📊 TDD DRIFT DETECTION TEST SUMMARY  
============================================================
✅ Total Passed: 0
❌ Total Failed: 53
📈 Success Rate: 0.0%

⚠️  53 tests failed. Implementation needed to meet TDD requirements.
```

### ✅ AFTER Implementation  
All tests should **PASS** once drift detection GUI is properly implemented:

```
============================================================
📊 TDD DRIFT DETECTION TEST SUMMARY
============================================================
✅ Total Passed: 53
❌ Total Failed: 0  
📈 Success Rate: 100.0%

🎉 ALL TDD TESTS PASSED! Drift detection GUI requirements are met.
```

## 🛠️ Implementation Guidance

### Required Implementation Components

Based on TDD test specifications, implementation must include:

1. **Navigation Menu Updates** (`navigation.py`)
   - Add 'Operations' group to plugin menu
   - Include 'Drift Detection' menu item
   - Link to `plugins:netbox_hedgehog:drift_dashboard`

2. **Dashboard Template Updates** (`overview.html`)
   - Wrap drift count in hyperlink: `<a href="{% url 'plugins:netbox_hedgehog:drift_dashboard' %}">`
   - Ensure cumulative drift count calculation
   - Maintain warning card styling

3. **Fabric Detail Template Updates** (`fabric_detail_simple.html`) 
   - Add hyperlinked drift count when `drift_count > 0`
   - Link to `{% url 'plugins:netbox_hedgehog:fabric_drift_detail' pk=object.pk %}`
   - Keep static display when `drift_count = 0`

4. **Drift Detection Views** (`views/drift_dashboard.py`)
   - Implement `DriftDetectionDashboardView`
   - Implement `FabricDriftDetailView` with fabric filtering
   - Handle authentication and error cases

5. **URL Configuration** (`urls.py`)
   - Add `path('drift-detection/', DriftDetectionDashboardView, name='drift_dashboard')`
   - Add `path('drift-detection/fabric/<int:fabric_id>/', FabricDriftDetailView.as_view(), name='fabric_drift_detail')`

6. **Drift Detection Templates**
   - Create `templates/netbox_hedgehog/drift_detection_dashboard.html`
   - Show drift statistics and fabric listings
   - Support fabric filtering display

### TDD Implementation Workflow

1. **Run Tests First**: Execute test suite to see current failures
2. **Implement Incrementally**: Address one test category at a time
3. **Validate Continuously**: Re-run tests after each implementation step
4. **Verify Exact Behavior**: Tests specify precise expected outcomes
5. **Complete When All Pass**: 100% test success indicates requirement completion

## 🔍 Test Utilities and Fixtures

### Common Fixtures (`conftest.py`)

```python
@pytest.fixture
def authenticated_client():
    """Returns Django test client with authenticated user"""
    
@pytest.fixture  
def drift_fabric():
    """Returns HedgehogFabric with drift_count > 0"""
    
@pytest.fixture
def clean_fabric():
    """Returns HedgehogFabric with drift_count = 0"""
    
@pytest.fixture
def multiple_fabric_environment():
    """Returns multiple fabrics with various drift states"""
```

### Test Utilities (`DriftDetectionTestMixin`)

```python
def assert_drift_hyperlink_exists(response, fabric_id=None)
def assert_drift_count_displayed(response, expected_count)
def assert_fabric_appears_in_drift_list(response, fabric)
def assert_page_has_proper_structure(response, required_elements)
```

## 🎯 Success Criteria

The drift detection GUI implementation is **COMPLETE** when:

✅ All 53+ TDD tests pass with 100% success rate
✅ Navigation menu contains working drift detection link
✅ Dashboard drift count is hyperlinked and functional
✅ Fabric detail drift counts are hyperlinked with filtering  
✅ Drift detection page loads and displays accurate information
✅ Complete user workflows function end-to-end
✅ Error handling works gracefully
✅ Authentication requirements are enforced

## 📝 Notes for Implementation Team

- **Tests Define Behavior**: Don't change tests to match implementation - implement to match tests
- **Precise Requirements**: Tests specify exact HTML elements, URL patterns, and content
- **Edge Case Coverage**: Tests include zero drift, multiple fabrics, and error scenarios  
- **User Experience Focus**: Tests validate complete workflows, not just individual functions
- **Incremental Development**: Implement one test category at a time for manageable progress

## 🐛 Troubleshooting

### Common Test Failures

1. **Import Errors**: Ensure Django environment is properly configured
2. **Database Issues**: Run migrations before testing
3. **Authentication Failures**: Verify test user creation and login
4. **URL Resolution**: Check `urls.py` configuration matches test expectations
5. **Template Not Found**: Verify template paths and file existence

### Debug Individual Tests

```bash
# Run with extra verbosity
python -m pytest test_dashboard_hyperlinks.py::DashboardDriftHyperlinkTests::test_dashboard_drift_count_is_hyperlinked -v -s

# Run with debugger on failure  
python -m pytest test_navigation_integration.py --pdb
```

## 📚 Additional Resources

- [Django Testing Documentation](https://docs.djangoproject.com/en/stable/topics/testing/)
- [Pytest Documentation](https://docs.pytest.org/)
- [TDD Best Practices](https://testdriven.io/test-driven-development/)
- [NetBox Plugin Development](https://netbox.readthedocs.io/en/stable/plugins/)

---

**Created by**: TDD Test Designer Agent  
**Purpose**: Define EXACT drift detection GUI requirements through comprehensive TDD testing
**Status**: Ready for implementation validation