"""
Pytest configuration and fixtures for browser-based UX tests.

Provides browser instances and authenticated sessions for testing.
"""

import pytest
from playwright.sync_api import Page, expect, Browser, BrowserContext
import os


# NetBox connection details
NETBOX_URL = os.environ.get('NETBOX_URL', 'http://localhost:8000')
NETBOX_USERNAME = os.environ.get('NETBOX_USERNAME', 'admin')
NETBOX_PASSWORD = os.environ.get('NETBOX_PASSWORD', 'admin')

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
    # Navigate to login page
    page.goto(f'{NETBOX_URL}/login/')

    # Fill in login form
    page.fill('input[name="username"]', NETBOX_USERNAME)
    page.fill('input[name="password"]', NETBOX_PASSWORD)

    # Submit form
    page.click('button[type="submit"]')

    # Wait for navigation to complete and verify we're logged in
    # NetBox redirects to home page after login
    page.wait_for_url(f'{NETBOX_URL}/', timeout=5000)

    # Verify we see the logged-in user indicator
    # NetBox shows username in the navbar when logged in
    expect(page.locator('text=' + NETBOX_USERNAME)).to_be_visible(timeout=5000)

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
