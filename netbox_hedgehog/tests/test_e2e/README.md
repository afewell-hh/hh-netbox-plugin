# End-to-End (E2E) Tests

## Overview

E2E tests use **Playwright** with **Django StaticLiveServerTestCase** to test the plugin in a real browser, including:
- Client-side JavaScript execution
- CSS rendering and active states
- Navigation highlighting behavior
- Full user interaction flows
- Form submissions and validation
- File downloads (YAML exports)
- Permission enforcement
- Multi-step workflows (generate devices, CRUD operations)

These tests complement Django integration tests by verifying browser-based behavior that cannot be tested with Django's test client.

## Why E2E Tests?

NetBox uses client-side JavaScript and complex forms. Backend integration tests cannot verify:
- JavaScript execution (dynamic forms, navigation highlighting)
- CSS active states and visual feedback
- Actual button clicks and form interactions
- File downloads
- Browser rendering and layout
- Real user workflows end-to-end

E2E tests fill this gap by running tests in an actual browser with a real test server.

## Setup

### 1. Install Playwright in Container

Per AGENTS.md, all setup must be done inside the NetBox container:

```bash
# Navigate to netbox-docker directory
cd /home/ubuntu/afewell-hh/netbox-docker

# Install Playwright in the container
docker compose exec netbox bash -c "/opt/netbox/venv/bin/pip install playwright"

# Install Chromium browser in the container
docker compose exec netbox bash -c "/opt/netbox/venv/bin/playwright install chromium chromium-dependencies"
```

**Note**: For persistent setup across container rebuilds, add to your Dockerfile:
```dockerfile
RUN /opt/netbox/venv/bin/pip install playwright && \
    /opt/netbox/venv/bin/playwright install chromium chromium-dependencies
```

### 2. Ensure NetBox is Running

E2E tests need a running NetBox instance:

```bash
cd /home/ubuntu/afewell-hh/netbox-docker
docker compose up -d
```

## Running E2E Tests

**IMPORTANT**: Per AGENTS.md, always run Django/NetBox commands inside the container using `docker compose exec netbox`.

**NOTE**: E2E tests are opt-in and require setting `RUN_E2E_TESTS=true` to prevent database setup issues when Playwright is not available.

### Run All E2E Tests

```bash
# Navigate to netbox-docker directory
cd /home/ubuntu/afewell-hh/netbox-docker

# Run with visible browser (for debugging)
docker compose exec -e RUN_E2E_TESTS=true -e PLAYWRIGHT_HEADLESS=false netbox python manage.py test netbox_hedgehog.tests.test_e2e

# Run headless (for CI/automation)
docker compose exec -e RUN_E2E_TESTS=true -e PLAYWRIGHT_HEADLESS=true netbox python manage.py test netbox_hedgehog.tests.test_e2e --keepdb
```

### Run Specific E2E Test

```bash
# Navigate to netbox-docker directory
cd /home/ubuntu/afewell-hh/netbox-docker

# Run only navigation highlighting tests
docker compose exec -e RUN_E2E_TESTS=true netbox python manage.py test netbox_hedgehog.tests.test_e2e.test_navigation_highlighting --keepdb

# Run a specific test method
docker compose exec -e RUN_E2E_TESTS=true netbox python manage.py test \
  netbox_hedgehog.tests.test_e2e.test_navigation_highlighting.NavigationHighlightingE2ETestCase.test_dashboard_not_highlighted_on_topology_plans_page \
  --keepdb
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

- `RUN_E2E_TESTS`: Set to `true` to enable E2E tests (default: `false`)
  - **REQUIRED** to run E2E tests - prevents database setup issues when disabled
  - Example: `RUN_E2E_TESTS=true python manage.py test ...`

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

### Topology Plan CRUD (`test_topology_plan_crud.py`)

| Test | What It Verifies |
|------|------------------|
| `test_create_topology_plan_via_add_button` | Users can create plans via Add button and form |
| `test_create_topology_plan_form_validation` | Form validation works for required fields |
| `test_topology_plan_list_page_loads` | List page loads correctly |
| `test_topology_plan_detail_page_loads` | Detail page displays plan information |
| `test_edit_topology_plan_via_edit_button` | Users can edit existing plans |
| `test_delete_topology_plan_with_confirmation` | Delete workflow with confirmation works |
| `test_topology_plan_list_shows_multiple_plans` | List view shows all plans |
| `test_add_button_not_visible_without_permission` | Permission enforcement for add operations |

### Generate Devices Workflow (`test_generate_devices.py`)

| Test | What It Verifies |
|------|------------------|
| `test_generate_button_visible_on_plan_detail` | Generate button exists on detail page |
| `test_generate_preview_page_loads_with_counts` | Preview page shows accurate device counts |
| `test_generate_preview_shows_warnings_for_empty_plan` | Warnings appear for empty plans |
| `test_generate_confirm_creates_devices` | Complete workflow creates devices in NetBox |
| `test_regeneration_shows_warning` | Regeneration shows appropriate warnings |
| `test_plan_scoped_regeneration_isolation` | Regenerating Plan A doesn't affect Plan B (multi-tenant safety) |
| `test_permission_denied_without_change_permission` | Users without permissions see access denied |

### Export YAML Workflow (`test_export_yaml.py`)

| Test | What It Verifies |
|------|------------------|
| `test_export_yaml_button_exists` | Export button exists on plan detail page |
| `test_export_yaml_triggers_download` | Clicking button triggers file download |
| `test_exported_yaml_is_valid` | Downloaded file is valid parseable YAML |
| `test_exported_yaml_contains_connection_crds` | YAML contains proper Hedgehog Connection CRDs |
| `test_exported_yaml_filename_convention` | File naming follows conventions |
| `test_export_yaml_permission_enforcement` | Permission enforcement for exports |

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
