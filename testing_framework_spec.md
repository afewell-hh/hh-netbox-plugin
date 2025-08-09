# Playwright + Django Integration Specification

## Project Context
- Django application: NetBox Hedgehog Plugin
- 65 URL endpoints (from url_inventory.json)
- 16 key templates with forms/interactions (from template_inventory.json)  
- 17 Django models with complex relationships (from models_inventory.json)
- 45 JavaScript functions with AJAX calls (from javascript_behaviors.json)

## Technical Requirements

### 1. Test Environment Setup
- **Django test settings configuration**: 
  - Isolated test database using `TEST_NAME` with unique naming per test run
  - Static files served via Django's StaticFilesHandler during tests
  - CSRF middleware enabled with proper token handling
  - Session middleware configured for authentication tests
  - Custom test runner to manage NetBox plugin lifecycle
- **Database isolation strategy**: 
  - Use `pytest.mark.django_db` decorator for database access
  - `setUpTestData` for heavy, immutable data shared across test methods
  - Transaction-based test isolation with automatic rollback
  - Separate test database per test class with Django's TestCase
- **Static file handling for testing**: 
  - Configure `STATICFILES_STORAGE` for test environment
  - Use `django.contrib.staticfiles.testing.StaticLiveServerTestCase`
  - Serve static files during tests via `whitenoise` or Django's built-in handler
- **NetBox plugin test integration**: 
  - Custom pytest fixtures for NetBox configuration
  - Plugin-specific middleware and authentication handling
  - NetBox core model dependencies and relationships

### 2. Authentication Strategy  
- **User creation and permissions setup**: 
  - Factory-based user creation with `factory_boy` for consistent test data
  - Pre-created user fixtures with different permission levels
  - Authentication state saving and reuse across tests
  - CSRF token extraction and inclusion in requests
- **Session management across tests**: 
  - Save authentication state using Playwright's `context.storageState()`
  - Reuse saved authentication state to bypass repetitive login operations
  - Browser context isolation ensuring full test independence
- **NetBox authentication integration**: 
  - NetBox-specific user model and permission system
  - Custom authentication backends and middleware
  - Session-based authentication with proper cookie handling
- **Permission-based UI testing approach**: 
  - Test UI element visibility/invisibility based on user permissions
  - Dynamic form field availability based on access levels
  - Action button states reflecting user capabilities

### 3. Database Management
- **Test database creation/teardown**: 
  - Automated test database lifecycle management
  - Parallel test execution with separate database per worker
  - Database cleanup between test runs
- **Data fixture management**: 
  - JSON fixtures for stable test data
  - Factory Boy for dynamic test data generation
  - Shared fixtures via `setUpTestData` for performance
  - Fabric and GitRepository fixtures with realistic configurations
- **Transaction isolation between tests**: 
  - Each test wrapped in a database transaction
  - Automatic rollback after each test completion
  - Prevent test data contamination between runs
- **Model relationship testing strategy**: 
  - Test complex model relationships (HedgehogFabric → GitRepository → User)
  - Validate cascade operations and foreign key constraints
  - Test many-to-many relationships and through tables

### 4. Async Testing Approach
- **WebSocket connection testing**: 
  - Use `page.on('websocket')` to monitor WebSocket creation
  - Test WebSocket connection establishment and message handling
  - Validate reconnection logic and error handling
  - Mock WebSocket responses for testing error scenarios
- **AJAX call interception/mocking**: 
  - Use `page.route()` to intercept and mock network requests
  - Wait for AJAX responses using `page.waitForResponse()`
  - Test multiple concurrent AJAX requests
  - Simulate network failures and timeout scenarios
- **Real-time update verification**: 
  - Monitor DOM changes after async operations
  - Validate status badge updates and counter animations
  - Test progressive disclosure and dynamic content loading
- **Async JavaScript behavior testing**: 
  - Test 45 identified JavaScript functions and their DOM interactions
  - Verify AJAX endpoints and response handling
  - Test event listeners and user interaction flows

### 5. Browser Automation Strategy
- **Playwright configuration for Django**: 
  - Multi-browser testing (Chromium, Firefox, WebKit)
  - Browser context isolation for each test
  - Custom viewport sizes for responsive testing
  - Slow motion and debugging options for development
- **Multi-browser testing approach**: 
  - Cross-browser compatibility validation
  - Browser-specific behavior testing
  - Consistent test execution across platforms
- **Headless vs headed testing**: 
  - Headless mode for CI/CD pipelines
  - Headed mode for debugging and development
  - Configurable via environment variables
- **Screenshot and video recording**: 
  - Automatic screenshot capture on test failures
  - Video recording for complex interaction debugging
  - Visual regression testing with baseline comparisons

## Implementation Plan

### Phase 2 Dependencies
- **Required packages and versions**:
  ```
  playwright==1.41.0
  pytest-playwright==0.4.4
  pytest-django==4.8.0
  pytest-xdist==3.5.0
  factory-boy==3.3.0
  responses==0.24.0
  ```
- **Configuration files needed**:
  - `pytest.ini`: Pytest configuration with Django settings
  - `conftest.py`: Shared fixtures and Playwright configuration
  - `test_settings.py`: Django test-specific settings
  - `.env.test`: Test environment variables
- **Directory structure requirements**:
  ```
  tests/
  ├── gui/
  │   ├── conftest.py
  │   ├── fixtures/
  │   │   ├── auth_helpers.py
  │   │   ├── test_data.py
  │   │   └── factory_fixtures.py
  │   ├── page_objects/
  │   │   ├── base.py
  │   │   ├── fabric_pages.py
  │   │   └── auth_pages.py
  │   └── test_suites/
  │       ├── test_fabric_workflows.py
  │       ├── test_auth_flows.py
  │       └── test_ajax_behaviors.py
  ```
- **Integration with existing Django test framework**: 
  - Extend Django's TestCase for database-dependent tests
  - Use pytest fixtures for Playwright browser management
  - Combine Django's `live_server` fixture with Playwright

### Test Categories
1. **Page Load Tests** - Basic navigation and content
   - Test all 65 URL endpoints for successful loading
   - Validate essential page elements and structure
   - Cross-browser compatibility validation

2. **Form Interaction Tests** - CRUD operations via UI
   - Test fabric creation, editing, and deletion workflows
   - Git repository configuration and validation
   - Form validation and error handling

3. **JavaScript Behavior Tests** - Dynamic functionality
   - Test all 45 JavaScript functions identified in inventory
   - AJAX call verification and response handling
   - DOM manipulation and event handling

4. **Authentication Tests** - Login/logout workflows
   - NetBox user authentication flows
   - Session management and persistence
   - Permission-based access control

5. **Permission Tests** - UI changes based on permissions
   - Element visibility based on user roles
   - Action availability per permission level
   - Dynamic form field access control

6. **AJAX Tests** - API calls and real-time updates
   - Fabric sync operations and status updates
   - Connection testing and validation
   - Real-time status monitoring

7. **Visual Regression Tests** - Screenshot comparison
   - Baseline screenshot generation
   - Automated visual difference detection
   - Cross-browser visual consistency

### Configuration Specifications
- **Playwright config for Django**:
  ```python
  # playwright.config.py
  import os
  from playwright.sync_api import Playwright
  
  def pytest_configure_playwright(config, playwright: Playwright):
      config.option.browser_name = ["chromium", "firefox", "webkit"]
      config.option.headed = os.getenv("HEADED", False)
      config.option.slow_mo = int(os.getenv("SLOW_MO", 0))
  ```

- **Test settings module**:
  ```python
  # test_settings.py
  from .settings import *
  
  DATABASES = {
      'default': {
          'ENGINE': 'django.db.backends.sqlite3',
          'NAME': ':memory:',
          'TEST': {'NAME': 'test_netbox_hedgehog'}
      }
  }
  
  STATICFILES_STORAGE = 'whitenoise.storage.CompressedStaticFilesStorage'
  SECRET_KEY = 'test-secret-key-for-testing-only'
  ```

- **Database configuration**: 
  - In-memory SQLite for fast test execution
  - Separate test database with predictable naming
  - Transaction isolation with automatic cleanup

- **Authentication helper utilities**:
  ```python
  # auth_helpers.py
  import json
  from playwright.sync_api import Page
  from django.contrib.auth.models import User
  
  def login_user(page: Page, username: str, password: str):
      """Login user and save authentication state"""
      page.goto("/admin/login/")
      page.fill("#id_username", username)
      page.fill("#id_password", password)
      page.click("input[type=submit]")
      return page.context.storage_state()
  ```

- **Page object model architecture**:
  ```python
  # base.py
  from playwright.sync_api import Page
  
  class BasePage:
      def __init__(self, page: Page):
          self.page = page
          
      def wait_for_ajax_complete(self):
          self.page.wait_for_load_state("networkidle")
          
      def capture_screenshot(self, name: str):
          return self.page.screenshot(path=f"screenshots/{name}.png")
  ```

## Best Practices
- **Test isolation strategies**: 
  - Browser context per test for complete isolation
  - Database transaction rollback after each test
  - Independent test data creation via factories

- **Performance optimization**: 
  - Parallel test execution with pytest-xdist
  - Authentication state reuse to avoid repetitive logins
  - Shared test data via setUpTestData for heavy operations

- **Error handling and reporting**: 
  - Automatic screenshot capture on failures
  - Detailed error messages with context
  - Network request logging for debugging

- **CI/CD integration considerations**: 
  - Headless browser execution in CI environment
  - Test result reporting in JUnit XML format
  - Artifact collection for failed tests (screenshots, videos)
  - Environment-specific configuration via environment variables