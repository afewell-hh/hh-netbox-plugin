# End-to-End (E2E) Tests

## Overview

E2E tests use **Playwright** to test the plugin in a real browser, including:
- Client-side JavaScript execution
- CSS rendering and active states
- Navigation highlighting behavior
- Full user interaction flows

These tests complement Django integration tests by verifying browser-based behavior that cannot be tested with Django's test client.

## Why E2E Tests?

NetBox uses client-side JavaScript for navigation highlighting. Backend integration tests cannot verify:
- JavaScript execution
- CSS active states
- Client-side routing logic
- Browser rendering

E2E tests fill this gap by running tests in an actual browser.

## Setup

### 1. Install Playwright

```bash
# Install Python package
pip install playwright

# Install browser binaries (Chromium, Firefox, WebKit)
playwright install chromium
```

### 2. Ensure NetBox is Running

E2E tests need a running NetBox instance. Use the docker-compose setup:

```bash
cd /path/to/netbox-docker
docker compose up -d
```

## Running E2E Tests

### Run All E2E Tests

```bash
# From the plugin root directory
cd /home/ubuntu/afewell-hh/hh-netbox-plugin

# Run with visible browser (for debugging)
PLAYWRIGHT_HEADLESS=false python manage.py test netbox_hedgehog.tests.test_e2e

# Run headless (for CI/automation)
PLAYWRIGHT_HEADLESS=true python manage.py test netbox_hedgehog.tests.test_e2e
```

### Run Specific E2E Test

```bash
# Run only navigation highlighting tests
python manage.py test netbox_hedgehog.tests.test_e2e.test_navigation_highlighting

# Run a specific test method
python manage.py test netbox_hedgehog.tests.test_e2e.test_navigation_highlighting.NavigationHighlightingE2ETestCase.test_dashboard_not_highlighted_on_topology_plans_page
```

### Run from Docker Container

**Note**: The default NetBox container may not have Playwright installed. E2E tests are typically run:
- **Locally** on your development machine
- **In CI/CD** with a properly configured environment

If you need to run in the container:

1. **Option A - Extend the Dockerfile** (recommended for regular E2E testing):
   ```dockerfile
   # In netbox-docker/Dockerfile-Plugins
   RUN /opt/netbox/venv/bin/pip install playwright && \
       /opt/netbox/venv/bin/playwright install chromium chromium-dependencies
   ```

2. **Option B - One-time installation** (for ad-hoc testing):
   ```bash
   docker compose exec netbox bash
   # Inside container:
   /opt/netbox/venv/bin/pip install playwright
   /opt/netbox/venv/bin/playwright install chromium
   exit

   # Then run tests:
   docker compose exec netbox python manage.py test netbox_hedgehog.tests.test_e2e
   ```

## Environment Variables

- `PLAYWRIGHT_HEADLESS`: Set to `false` to see browser UI (default: `true`)
  - Useful for debugging test failures
  - Example: `PLAYWRIGHT_HEADLESS=false python manage.py test ...`

## Test Coverage

### Navigation Highlighting (`test_navigation_highlighting.py`)

| Test | What It Verifies |
|------|------------------|
| `test_dashboard_highlighted_only_on_dashboard_page` | Dashboard link exists and page loads correctly |
| `test_dashboard_not_highlighted_on_topology_plans_page` | Dashboard is NOT current page when viewing Topology Plans |
| `test_navigation_between_pages_updates_state` | Navigation state changes when moving between pages |
| `test_url_path_components_are_distinct` | URLs don't share ambiguous path components (empty string) |

## Troubleshooting

### Playwright Not Installed

```
ModuleNotFoundError: No module named 'playwright'
```

**Solution**: Install Playwright:
```bash
pip install playwright
playwright install chromium
```

### Browser Binary Missing

```
Executable doesn't exist at /path/to/chromium
```

**Solution**: Install browser binaries:
```bash
playwright install chromium
```

### Tests Skip with "Playwright not available"

The tests will auto-skip if Playwright is not installed. Install it per the instructions above.

### Port Already in Use

```
Error: Address already in use
```

**Solution**: The `StaticLiveServerTestCase` starts a test server. Ensure no other NetBox instances are running on conflicting ports, or use `--keepdb` to reuse the test database.

## CI/CD Integration

### GitHub Actions Example

```yaml
name: E2E Tests

on: [push, pull_request]

jobs:
  e2e:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install playwright
          playwright install chromium
      - name: Run E2E tests
        run: |
          PLAYWRIGHT_HEADLESS=true python manage.py test netbox_hedgehog.tests.test_e2e
```

## Performance

E2E tests are slower than integration tests:
- Integration test: ~0.1-0.5 seconds
- E2E test: ~2-5 seconds (includes browser startup, page load, JS execution)

**Best Practice**: Use E2E tests for critical UI behavior only. Use integration tests for most CRUD/validation testing.

## Writing New E2E Tests

### Example: Test a Button Click

```python
def test_button_click_shows_modal(self):
    """Test that clicking a button opens a modal"""
    # Navigate to page
    self.page.goto(f"{self.live_server_url}/plugins/hedgehog/topology-plans/")

    # Click button
    self.page.click('button:has-text("Generate Devices")')

    # Wait for modal
    modal = self.page.locator('.modal:has-text("Confirm")')
    expect(modal).to_be_visible()
```

### Best Practices

1. **Use `wait_for_load_state('networkidle')`** after navigation
2. **Use locators** instead of raw XPath when possible
3. **Keep tests focused** - one behavior per test
4. **Clean up resources** in `tearDown()`
5. **Handle async JavaScript** with appropriate waits

## References

- [Playwright Python Docs](https://playwright.dev/python/docs/intro)
- [Django StaticLiveServerTestCase](https://docs.djangoproject.com/en/stable/topics/testing/tools/#liveservertestcase)
- [NetBox Plugin Development](https://docs.netbox.dev/en/stable/plugins/development/)
