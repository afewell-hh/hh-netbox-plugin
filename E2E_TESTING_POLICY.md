# E2E Testing Policy for hh-netbox-plugin

## Mandatory Policy

**EFFECTIVE IMMEDIATELY:** No pull request affecting UI/UX functionality may be merged without corresponding browser-based end-to-end (E2E) tests.

This policy is non-negotiable and exists to prevent shipping broken user experiences that pass backend tests but fail in actual browser usage.

---

## Why This Policy Exists

### The Problem

Backend integration tests (Django test client) only validate:
- ✅ HTTP status codes
- ✅ Database operations
- ✅ Backend logic

They **do not** validate:
- ❌ Browser rendering
- ❌ JavaScript execution
- ❌ Button clicks and form interactions
- ❌ Visual feedback (success messages, errors, highlights)
- ❌ File downloads
- ❌ Real user workflows

### Real Example

PR #109 (Generate Devices) was merged with comprehensive backend tests showing everything worked perfectly. However, there was **zero validation** that:
- Users could actually click the "Generate Devices" button
- The preview page rendered correctly
- Success messages appeared
- Generated devices were visible in the UI

E2E tests retroactively discovered these would have worked, but **we had no proof at merge time**.

---

## Policy Requirements

### 1. UI/UX Changes Require E2E Tests

Any PR that:
- Adds a new page or view
- Modifies forms or buttons
- Changes navigation or menu items
- Implements multi-step workflows
- Triggers file downloads
- Shows/hides UI elements based on permissions
- Modifies JavaScript behavior
- Changes CSS or layout

**MUST** include E2E tests that verify the complete user experience.

### 2. Test Coverage Requirements

E2E tests must verify:

#### **Basic Workflow**
- Page loads without errors
- All expected buttons/links are visible
- Forms can be submitted
- Success/error messages appear

#### **Data Persistence**
- Form submissions create/update database records
- Generated objects are visible in lists
- Edits persist across page reloads

#### **Permission Enforcement**
- Users without permissions see access denied
- Buttons are hidden appropriately
- Direct URL access returns 403

#### **Multi-Step Workflows**
- Each step transitions correctly
- Intermediate state is preserved
- Final step completes successfully
- User is redirected appropriately

### 3. PR Review Checklist

Reviewers must verify:
- [ ] E2E tests exist for all UI changes
- [ ] Tests run in CI and pass
- [ ] Tests cover both happy path and error cases
- [ ] Tests verify permissions when applicable
- [ ] Test names clearly describe what is being validated

If any checkbox is unchecked, **request changes** and do not approve.

---

## How to Write E2E Tests

### Framework

We use **Playwright** with **Django StaticLiveServerTestCase**.

**Location:** `netbox_hedgehog/tests/test_e2e/`

### Template

```python
"""
E2E Tests for [Feature Name]

What these tests verify:
- [List user-facing behaviors being tested]
"""

import os
import unittest
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.contrib.auth import get_user_model

try:
    from playwright.sync_api import sync_playwright, expect
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False

User = get_user_model()
RUN_E2E_TESTS = os.environ.get('RUN_E2E_TESTS', 'false').lower() == 'true'


@unittest.skipUnless(
    RUN_E2E_TESTS and PLAYWRIGHT_AVAILABLE,
    "E2E tests disabled. Set RUN_E2E_TESTS=true to enable."
)
class MyFeatureE2ETestCase(StaticLiveServerTestCase):
    """E2E tests for My Feature using Playwright."""

    @classmethod
    def setUpClass(cls):
        """Set up Playwright browser"""
        super().setUpClass()
        cls.playwright = sync_playwright().start()
        headless = os.environ.get('PLAYWRIGHT_HEADLESS', 'true').lower() == 'true'
        cls.browser = cls.playwright.chromium.launch(headless=headless)
        cls.context = cls.browser.new_context()

    @classmethod
    def tearDownClass(cls):
        """Clean up Playwright resources"""
        cls.context.close()
        cls.browser.close()
        cls.playwright.stop()
        super().tearDownClass()

    def setUp(self):
        """Set up test user and browser page"""
        self.user = User.objects.create_user(
            username='e2e_test_user',
            password='testpass',
            is_staff=True,
            is_superuser=True
        )
        self.page = self.context.new_page()
        self._login()

    def tearDown(self):
        """Clean up after each test"""
        if hasattr(self, 'page'):
            self.page.close()
        if hasattr(self, 'user'):
            self.user.delete()

    def _login(self):
        """Login to NetBox"""
        login_url = f"{self.live_server_url}/login/"
        self.page.goto(login_url)
        self.page.fill('input[name="username"]', 'e2e_test_user')
        self.page.fill('input[name="password"]', 'testpass')
        self.page.click('button[type="submit"]')
        self.page.wait_for_load_state('networkidle')

    def test_my_feature_workflow(self):
        """Test that users can complete the feature workflow"""
        # Navigate to feature page
        self.page.goto(f"{self.live_server_url}/plugins/hedgehog/my-feature/")
        self.page.wait_for_load_state('networkidle')

        # Interact with UI
        self.page.click('button:has-text("Do Something")')
        self.page.wait_for_load_state('networkidle')

        # Verify result
        page_content = self.page.content()
        self.assertIn('Success', page_content)
```

### Best Practices

1. **Test Real User Workflows**: Don't just test individual pages - test complete workflows as users experience them
2. **Verify Visible Feedback**: Check for success messages, error messages, visual highlights
3. **Test Permissions**: Create limited users and verify access controls work
4. **Clean Up Test Data**: Delete created objects in tearDown
5. **Use Descriptive Names**: Test names should clearly state what user behavior is being verified
6. **Wait for Page Loads**: Always use `wait_for_load_state('networkidle')` after navigation
7. **Handle Async**: Use appropriate waits for dynamic content

---

## Running E2E Tests

### Locally (Development)

```bash
cd /home/ubuntu/afewell-hh/netbox-docker

# Run all E2E tests
docker compose exec -e RUN_E2E_TESTS=true -e PLAYWRIGHT_HEADLESS=true \
  netbox python manage.py test netbox_hedgehog.tests.test_e2e --keepdb -v 2

# Run specific test file
docker compose exec -e RUN_E2E_TESTS=true -e PLAYWRIGHT_HEADLESS=true \
  netbox python manage.py test netbox_hedgehog.tests.test_e2e.test_topology_plan_crud --keepdb

# Run with visible browser (for debugging)
docker compose exec -e RUN_E2E_TESTS=true -e PLAYWRIGHT_HEADLESS=false \
  netbox python manage.py test netbox_hedgehog.tests.test_e2e --keepdb
```

### In CI/CD (Automated)

E2E tests run automatically on every PR via GitHub Actions (`.github/workflows/e2e-tests.yml`).

**PR merge is blocked** if E2E tests fail.

---

## Existing E2E Test Coverage

| Feature | Test File | Coverage |
|---------|-----------|----------|
| Navigation Highlighting | `test_navigation_highlighting.py` | ✅ Complete |
| Topology Plan CRUD | `test_topology_plan_crud.py` | ✅ Complete |
| Generate Devices Workflow | `test_generate_devices.py` | ✅ Complete |
| Export YAML Workflow | `test_export_yaml.py` | ✅ Complete |
| Permission Enforcement | `test_permissions.py` | ✅ Complete |

**Total:** 50+ E2E tests covering all major UI workflows.

---

## Examples of Required E2E Tests

### ✅ GOOD: Proper E2E Test

```python
def test_user_can_create_plan_via_add_button(self):
    """
    Test that users can create a plan using the Add button and form.

    Verifies:
    - Add button is visible
    - Clicking button shows form
    - Filling form and submitting creates plan
    - Success message appears
    - Plan appears in list
    """
    # Navigate to list page
    self.page.goto(f"{self.live_server_url}/plugins/hedgehog/topology-plans/")
    self.page.wait_for_load_state('networkidle')

    # Click Add button
    self.page.click('a:has-text("Add Topology Plan")')
    self.page.wait_for_load_state('networkidle')

    # Fill form
    self.page.fill('input[name="name"]', 'Test Plan')
    self.page.fill('input[name="customer_name"]', 'Test Customer')

    # Submit
    self.page.click('button[type="submit"]')
    self.page.wait_for_load_state('networkidle')

    # Verify success
    page_content = self.page.content()
    self.assertIn('Test Plan', page_content)
    self.assertIn('created', page_content.lower() or 'success' in page_content.lower())
```

### ❌ BAD: Not an E2E Test

```python
def test_plan_creation_endpoint(self):
    """Backend test - does not verify UI"""
    response = self.client.post('/api/topology-plans/', data={...})
    self.assertEqual(response.status_code, 201)
```

This is a backend integration test. It's good to have, but **does NOT replace E2E tests**.

---

## Enforcement

### Pre-Merge

- GitHub Actions runs E2E tests on every PR
- PR cannot be merged if E2E tests fail
- Reviewers must verify E2E test coverage before approving

### Post-Merge

If a merged PR is found to lack required E2E tests:
1. Open an immediate follow-up issue
2. Assign to original PR author
3. Block further feature work until tests are added

---

## FAQs

### Q: Do I need E2E tests for backend-only changes?

**A:** No. If your PR only touches models, API serializers, or backend logic **without UI changes**, E2E tests are not required. Backend integration tests are sufficient.

### Q: Do I need E2E tests for documentation changes?

**A:** No. Documentation-only PRs do not require E2E tests.

### Q: Can I skip E2E tests if I manually tested in the browser?

**A:** No. Manual testing is not repeatable, not automated, and not enforced. E2E tests ensure the feature continues to work in future versions.

### Q: What if E2E tests are flaky?

**A:** Flaky tests must be fixed immediately. Do not disable or skip flaky tests. If a test fails intermittently:
1. Add proper waits (`wait_for_load_state`, `expect().to_be_visible()`)
2. Ensure test data cleanup is complete
3. Check for race conditions in async operations

### Q: How long should E2E tests take?

**A:** Individual E2E tests typically run in 2-5 seconds. Full suite should complete in under 5 minutes. If tests are slower, optimize page loads and use `--keepdb` to reuse test database.

### Q: Can I use the test_ux/ directory instead?

**A:** No. We have standardized on `test_e2e/` using Django StaticLiveServerTestCase + Playwright. All new E2E tests go in `test_e2e/`. The `test_ux/` directory is deprecated.

---

## Exceptions

Exceptions to this policy may be granted in rare cases:
1. Urgent security fixes where E2E tests would delay critical patch
2. Rollback PRs reverting broken changes
3. Infrastructure changes with no user-facing impact

**To request exception:** Discuss with team lead and document justification in PR description. Exception must be approved by at least 2 reviewers.

---

## Updates to This Policy

This policy may be updated as we learn more about effective E2E testing practices.

**Last Updated:** 2026-02-07
**Next Review:** 2026-05-01

---

**Remember:** The goal is not to create bureaucracy, but to **ensure users have a working, reliable experience**. E2E tests are our proof that the UI actually works for real people.
