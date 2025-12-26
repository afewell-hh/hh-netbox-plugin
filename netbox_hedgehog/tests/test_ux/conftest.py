"""
Pytest configuration and fixtures for browser-based UX tests.

Provides browser instances and authenticated sessions for testing.
"""

# CRITICAL: Prevent pytest from importing parent netbox_hedgehog package
# Browser tests run on HOST (not in container) so Django/NetBox aren't available
import sys
import os

# Remove parent package paths from sys.modules to prevent import attempts
# This must happen BEFORE any other imports that might trigger parent imports
if 'netbox_hedgehog' in sys.modules:
    del sys.modules['netbox_hedgehog']
if 'netbox_hedgehog.tests' in sys.modules:
    del sys.modules['netbox_hedgehog.tests']

import pytest
from playwright.sync_api import Page, expect, Browser, BrowserContext


# NetBox connection details
NETBOX_URL = os.environ.get('NETBOX_URL', 'http://localhost:8000')
NETBOX_USERNAME = os.environ.get('NETBOX_USERNAME', 'admin')
NETBOX_PASSWORD = os.environ.get('NETBOX_PASSWORD', 'admin')
NETBOX_VIEWER_USERNAME = os.environ.get('NETBOX_VIEWER_USERNAME', 'viewer')
NETBOX_VIEWER_PASSWORD = os.environ.get('NETBOX_VIEWER_PASSWORD', 'viewer')

# IMPORTANT: Plugin URL base is /plugins/hedgehog/ (not /plugins/netbox_hedgehog/)
# This is set by base_url='hedgehog' in __init__.py:HedgehogPluginConfig
# Tests should use: f'{NETBOX_URL}/plugins/hedgehog/topology-plans/'


@pytest.fixture(scope="session")
def browser_context_args(browser_context_args):
    """
    Configure browser context for all tests.

    Sets viewport size and other browser options.
    """
    return {
        **browser_context_args,
        "viewport": {
            "width": 1920,
            "height": 1080,
        },
        "ignore_https_errors": True,  # For local development
    }


def _login(page: Page, username: str, password: str) -> None:
    page.goto(f'{NETBOX_URL}/login/')
    page.fill('input[name="username"]', username)
    page.fill('input[name="password"]', password)
    page.click('button[type="submit"]')
    page.wait_for_url(f'{NETBOX_URL}/', timeout=5000)
    expect(page.locator('text=/Logged in as/i')).to_be_visible(timeout=5000)


@pytest.fixture
def authenticated_page(page: Page) -> Page:
    """
    Fixture providing a logged-in browser session.

    This fixture:
    1. Navigates to NetBox login page
    2. Fills in username and password
    3. Submits the form
    4. Verifies successful login
    5. Returns the authenticated page

    Usage:
        def test_something(authenticated_page: Page):
            authenticated_page.goto(f'{NETBOX_URL}/plugins/hedgehog/...')
            # Test authenticated functionality
    """
    _login(page, NETBOX_USERNAME, NETBOX_PASSWORD)

    return page


@pytest.fixture
def viewer_page(page: Page) -> Page:
    """
    Fixture providing a logged-in viewer session (view-only permissions).
    """
    _login(page, NETBOX_VIEWER_USERNAME, NETBOX_VIEWER_PASSWORD)
    return page


@pytest.fixture
def unauthenticated_page(page: Page) -> Page:
    """
    Fixture providing an unauthenticated browser session.

    Use this for testing login flows, permission denied pages, etc.

    Usage:
        def test_login(unauthenticated_page: Page):
            unauthenticated_page.goto(f'{NETBOX_URL}/login/')
            # Test login functionality
    """
    return page
