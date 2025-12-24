# Browser UX Tests

**Browser-based end-to-end testing for NetBox Hedgehog Plugin using Playwright.**

## What These Tests Do

These tests validate the **actual user experience** by:
- Running a real browser (Chromium)
- Clicking buttons and filling forms
- Verifying pages render correctly
- Testing complete workflows end-to-end

**This is different from Django integration tests** which only test HTTP responses, not what users actually see.

## Why This Matters

**Critical Gap:** We merged PR #109 (Generate Devices) without browser testing. Our Django integration tests validated that:
- ✅ Views return 200 status codes
- ✅ Backend logic works
- ✅ Database objects are created

But did NOT validate that:
- ❌ Users can actually click the "Generate Devices" button
- ❌ The preview page renders correctly
- ❌ Forms work in a real browser
- ❌ JavaScript executes properly
- ❌ The UI layout isn't broken

**These browser tests fix that gap.**

## Prerequisites

### 1. Install Playwright (Host Machine)

```bash
# Install Playwright and pytest plugin
pip install --user playwright pytest-playwright

# Install Chromium browser
python3 -m playwright install chromium
```

**Note:** Playwright runs on the HOST, not in the NetBox container. The browser connects to NetBox via HTTP at `http://localhost:8000`.

### 2. NetBox Running

Ensure NetBox is running and accessible:

```bash
cd /home/ubuntu/afewell-hh/netbox-docker
docker compose up -d
docker compose ps  # Verify netbox container is running

# Test manually
curl http://localhost:8000/login/  # Should return HTML
```

### 3. Admin Credentials

Default credentials:
- **URL:** http://localhost:8000
- **Username:** admin
- **Password:** admin

If these don't work, reset the password:

```bash
cd /home/ubuntu/afewell-hh/netbox-docker
docker compose exec netbox python manage.py shell -c "
from django.contrib.auth import get_user_model;
User = get_user_model();
admin = User.objects.get(username='admin');
admin.set_password('admin');
admin.save();
print('Password reset to: admin')
"
```

## Running the Tests

### Quick Test (Verify Framework Works)

```bash
# Simple standalone test
python3 test_framework_simple.py
```

This should show:
```
🧪 Testing Playwright + NetBox Login
==================================================
✅ Playwright initialized
✅ Chromium browser launched (headless)
✅ Browser page created
✅ NetBox login page loaded
✅ Login form elements found
✅ Credentials entered (admin)
✅ Login submitted, redirected to home page
✅ Successfully logged in as admin
==================================================
🎉 SUCCESS! Playwright framework is working!
==================================================
```

### Run UX Test Suite (Future)

**Note:** The pytest integration is still being configured due to pytest-django conflicts.

Once working, you'll run:

```bash
# From plugin directory
python3 -m pytest netbox_hedgehog/tests/test_ux/ -v
```

## Test Coverage

### ✅ Implemented

**Authentication Tests** (`test_ux_login.py`):
- Login page loads
- Successful login with valid credentials
- Failed login with invalid password
- Failed login with invalid username
- Logout functionality
- Unauthenticated access redirects to login

**Generate Devices Tests** (`test_ux_generate.py`):
- Navigate to Topology Plans
- Generate Devices button visibility
- Generate preview page loads
- Preview shows counts (devices, interfaces, cables)
- Generate confirm creates devices
- Success message appears
- Devices visible in NetBox
- Warning for empty plans
- Regeneration workflow
- Multi-plan isolation (Plan A regen doesn't affect Plan B)
- Permission enforcement

### ⏳ Test Data Required

Many tests are currently skipped with `pytest.skip("Requires test data")` because they need:
- Topology plans with known configurations
- Multiple plans for testing isolation
- Users with limited permissions

**Next step:** Create test data fixtures.

## Test Architecture

```
Host Machine                          Docker Container
┌──────────────────────┐             ┌──────────────────┐
│                      │             │                  │
│  Playwright          │   HTTP      │     NetBox       │
│  (Chromium Browser)  │────────────>│  localhost:8000  │
│                      │             │                  │
│  Tests run here      │             │  App runs here   │
└──────────────────────┘             └──────────────────┘
```

**Key Points:**
- Browser runs on HOST (not in container)
- Browser connects to NetBox via HTTP
- No Django dependencies needed on HOST
- Tests are completely independent of NetBox code

## Troubleshooting

### "Could not connect to NetBox"

**Problem:** Playwright can't reach http://localhost:8000

**Solution:**
```bash
# Check if NetBox is running
docker compose ps

# Check if port 8000 is accessible
curl http://localhost:8000/login/

# Restart NetBox if needed
cd /home/ubuntu/afewell-hh/netbox-docker
docker compose restart netbox
```

### "Login failed"

**Problem:** Admin credentials not working

**Solution:** Reset password (see Prerequisites section above)

### "ModuleNotFoundError: No module named 'playwright'"

**Problem:** Playwright not installed on host

**Solution:**
```bash
pip install --user playwright pytest-playwright
python3 -m playwright install chromium
```

### "pytest-django errors"

**Problem:** pytest trying to load Django modules

**Solution:** We're working on this. Use `test_framework_simple.py` for now.

## CI/CD Integration (Future)

Once tests are stable, add to GitHub Actions:

```yaml
name: Browser UX Tests

on: [push, pull_request]

jobs:
  ux-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Start NetBox
        run: |
          cd netbox-docker
          docker compose up -d
          sleep 30  # Wait for NetBox to be ready

      - name: Install Playwright
        run: |
          pip install playwright pytest-playwright
          playwright install chromium

      - name: Run UX Tests
        run: |
          python3 test_framework_simple.py

      - name: Upload Screenshots on Failure
        if: failure()
        uses: actions/upload-artifact@v3
        with:
          name: test-screenshots
          path: test-screenshots/
```

## Writing New Tests

See `test_ux_login.py` and `test_ux_generate.py` for examples.

**Basic pattern:**

```python
from playwright.sync_api import Page, expect
from .conftest import NETBOX_URL

def test_my_feature(authenticated_page: Page):
    \"\"\"Test description\"\"\"
    page = authenticated_page

    # Navigate to your page
    page.goto(f'{NETBOX_URL}/plugins/netbox_hedgehog/...')

    # Click buttons, fill forms
    page.click('button:has-text(\"My Button\")')
    page.fill('input[name=\"field\"]', 'value')

    # Verify results
    expect(page.locator('text=Success')).to_be_visible()
```

## Related Issues

- **Issue #110:** Browser-Based UX Validation Testing (tracking issue)
- **PR #109:** Generate Devices (merged without browser testing - these tests retroactively validate it)

## Status

**Phase 1: COMPLETE ✅**
- [x] Playwright installed
- [x] Framework verified working
- [x] Basic test structure created
- [x] Authentication tests written
- [x] Generate Devices tests written

**Phase 2: IN PROGRESS**
- [ ] Resolve pytest-django conflicts
- [ ] Create test data fixtures
- [ ] Run full test suite
- [ ] Fix any failing tests

**Phase 3: TODO**
- [ ] Add more comprehensive tests
- [ ] CI/CD integration
- [ ] Screenshot comparison (visual regression)
- [ ] Documentation for writing tests

## Contact

Questions? See Issue #110 for discussion and updates.

---

**Remember:** These tests validate what USERS actually experience. They are critical for ensuring the UI works, not just the backend.
