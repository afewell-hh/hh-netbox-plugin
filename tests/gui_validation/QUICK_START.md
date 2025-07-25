# Quick Start Guide for GUI Testing Specialist

**Framework Version**: 1.0.0  
**Ready for**: Days 3-4 Implementation  

## 🚀 Quick Setup (2 minutes)

```bash
# 1. Navigate to project root
cd /home/ubuntu/cc/hedgehog-netbox-plugin

# 2. Check environment is ready
python3 run_demo_tests.py --check-env

# 3. See what tests exist
python3 run_demo_tests.py --list-tests

# 4. Run sample tests
python3 run_demo_tests.py --quick
```

## 📝 Create Your First Test (5 minutes)

Create `/tests/gui_validation/test_navigation.py`:

```python
from tests.gui_validation.base_test import DemoValidationTestCase

class NavigationTests(DemoValidationTestCase):
    """Basic navigation tests for demo scenarios"""
    
    def test_plugin_homepage_loads(self):
        """Test that plugin homepage loads successfully"""
        response = self.get_plugin_page()
        self.assertResponseOK(response)
        self.assert_no_error_indicators(response)
    
    def test_fabric_list_loads(self):
        """Test that fabric list page loads"""
        response = self.get_fabric_list_page()
        self.assertResponseOK(response)
        self.assert_crd_count_reasonable(response)
```

## 🧪 Test Your Implementation

```bash
# Run your new test
python3 run_demo_tests.py --modules tests.gui_validation.test_navigation

# Run with details
python3 run_demo_tests.py --modules tests.gui_validation.test_navigation --verbose

# Run all tests
python3 run_demo_tests.py
```

## 📊 Required Test Coverage

Create these 4 test files:

| File | Purpose | Priority |
|------|---------|----------|
| `test_navigation.py` | Basic page loads | HIGH |
| `test_demo_elements.py` | Demo features | HIGH |  
| `test_crd_operations.py` | CRUD operations | HIGH |
| `test_performance.py` | Speed validation | MEDIUM |

## 🛠️ Helper Methods Available

```python
# Page access
self.get_plugin_page('fabric/')           # Any plugin page
self.get_fabric_list_page()               # Fabric list
self.get_crd_list_page('vpc')             # CRD type list

# Assertions  
self.assertResponseOK(response)           # 200 status
self.assertResponseContains(response, 'Test Connection')
self.assertPageLoadsQuickly(response)     # < 2 seconds

# Demo-specific
self.assert_demo_workflow_elements(response)
self.assert_no_error_indicators(response)
self.assert_crd_count_reasonable(response)

# Performance
self.measure_page_load_time('fabric/')
self.assert_fast_page_load('fabric/', max_time=2.0)
```

## 🎯 Success Criteria

- [ ] All demo workflows have test coverage
- [ ] Tests run in < 2 minutes total  
- [ ] No false positives on current functionality
- [ ] Clear pass/fail output for agents
- [ ] Framework overhead < 30 seconds

## 🆘 Need Help?

1. **Documentation**: `/tests/gui_validation/README.md`
2. **Examples**: `/tests/gui_validation/test_smoke.py`
3. **Test Pattern**: See sample code above
4. **Framework Code**: `/tests/gui_validation/test_runner.py`

## 🔧 Common Commands

```bash
# Environment check
python3 run_demo_tests.py --check-env

# List available tests  
python3 run_demo_tests.py --list-tests

# Run quick tests only
python3 run_demo_tests.py --quick

# Run all tests with details
python3 run_demo_tests.py --verbose

# Run specific test file
python3 run_demo_tests.py --modules tests.gui_validation.test_navigation

# Check performance
python3 run_demo_tests.py | grep "Duration:"
```

---

**Time Estimate**: 2 days to implement all required tests  
**Next Phase**: Integration Specialist (Days 5-6)  
**Framework Status**: ✅ Ready for implementation