"""
Browser UX tests for authentication (login/logout).

These tests validate that users can actually log in and out of NetBox
using a real browser, ensuring the login form works as expected.
"""

import pytest
import re
from playwright.sync_api import Page, expect
from .conftest import NETBOX_URL, NETBOX_USERNAME, NETBOX_PASSWORD


class TestAuthentication:
    """Test suite for login/logout functionality"""

    def test_login_page_loads(self, unauthenticated_page: Page):
        """Test that the login page loads correctly"""
        page = unauthenticated_page

        # Navigate to login page
        page.goto(f'{NETBOX_URL}/login/')

        # Verify page loaded
        expect(page).to_have_url(f'{NETBOX_URL}/login/')

        # Verify login form elements exist
        expect(page.locator('input[name="username"]')).to_be_visible()
        expect(page.locator('input[name="password"]')).to_be_visible()
        expect(page.locator('button[type="submit"]')).to_be_visible()

    def test_successful_login(self, unauthenticated_page: Page):
        """Test that user can successfully log in with valid credentials"""
        page = unauthenticated_page

        # Navigate to login page
        page.goto(f'{NETBOX_URL}/login/')

        # Fill in credentials
        page.fill('input[name="username"]', NETBOX_USERNAME)
        page.fill('input[name="password"]', NETBOX_PASSWORD)

        # Submit form
        page.click('button[type="submit"]')

        # Wait for redirect to home page
        page.wait_for_url(f'{NETBOX_URL}/', timeout=5000)

        # Verify we're logged in by checking for login success message
        expect(page.locator('text=/Logged in as/i')).to_be_visible(timeout=5000)

    def test_failed_login_invalid_password(self, unauthenticated_page: Page):
        """Test that login fails with invalid password"""
        page = unauthenticated_page

        # Navigate to login page
        page.goto(f'{NETBOX_URL}/login/')

        # Fill in invalid credentials
        page.fill('input[name="username"]', NETBOX_USERNAME)
        page.fill('input[name="password"]', 'wrongpassword')

        # Submit form
        page.click('button[type="submit"]')

        # Should stay on login page (not redirect to /)
        # NetBox shows error message - check that we're still on login page
        page.wait_for_timeout(1000)  # Wait for form submission
        expect(page).to_have_url(re.compile(r'.*/login/.*'))

        # Login form should still be visible
        expect(page.locator('input[name="username"]')).to_be_visible()

    def test_failed_login_invalid_username(self, unauthenticated_page: Page):
        """Test that login fails with invalid username"""
        page = unauthenticated_page

        # Navigate to login page
        page.goto(f'{NETBOX_URL}/login/')

        # Fill in invalid credentials
        page.fill('input[name="username"]', 'nonexistentuser')
        page.fill('input[name="password"]', NETBOX_PASSWORD)

        # Submit form
        page.click('button[type="submit"]')

        # Should stay on login page (not redirect to /)
        page.wait_for_timeout(1000)  # Wait for form submission
        expect(page).to_have_url(re.compile(r'.*/login/.*'))

        # Login form should still be visible
        expect(page.locator('input[name="username"]')).to_be_visible()

    def test_logout(self, authenticated_page: Page):
        """Test that user can log out successfully"""
        page = authenticated_page

        # We're already logged in via the fixture
        # Verify we're logged in
        expect(page.locator('text=/Logged in as/i')).to_be_visible(timeout=5000)

        # Prefer clicking a logout link if visible; otherwise use the logout URL directly.
        logout_link = page.locator('a[href*="logout"]').first
        if logout_link.count() > 0 and logout_link.is_visible():
            logout_link.click()
        else:
            # Logout link exists but is hidden (in dropdown) or doesn't exist
            # Navigate directly to logout URL which is more reliable
            page.goto(f'{NETBOX_URL}/logout/')

        # Should redirect to login page
        page.wait_for_url(re.compile(r'.*/login/.*'), timeout=5000)

        # Verify we see the login form again
        expect(page.locator('input[name="username"]')).to_be_visible()

    def test_authenticated_page_fixture_works(self, authenticated_page: Page):
        """Test that the authenticated_page fixture provides a logged-in session"""
        page = authenticated_page

        # Fixture should have already logged us in
        # Verify we're on the home page
        expect(page).to_have_url(f'{NETBOX_URL}/')

        # Verify we're logged in
        expect(page.locator('text=/Logged in as/i')).to_be_visible(timeout=5000)

    def test_unauthenticated_access_redirects(self, unauthenticated_page: Page):
        """Test that accessing protected pages redirects to login"""
        page = unauthenticated_page

        # Try to access a protected page without logging in
        # NetBox should redirect to login
        # NOTE: Plugin base URL is /plugins/hedgehog/ (not /plugins/netbox_hedgehog/)
        page.goto(f'{NETBOX_URL}/plugins/hedgehog/topology-plans/')

        # Should be redirected to login page
        # NetBox typically adds a ?next= parameter
        expect(page).to_have_url(re.compile(r'.*/login/.*'))

        # Login form should be visible
        expect(page.locator('input[name="username"]')).to_be_visible()
