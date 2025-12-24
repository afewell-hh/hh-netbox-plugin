"""
Browser UX tests for authentication (login/logout).

These tests validate that users can actually log in and out of NetBox
using a real browser, ensuring the login form works as expected.
"""

import pytest
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

        # Verify we're logged in by checking for username in navbar
        expect(page.locator(f'text={NETBOX_USERNAME}')).to_be_visible()

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

        # Should stay on login page or show error
        # NetBox typically shows an error message
        expect(page.locator('text=/incorrect|invalid|failed/i')).to_be_visible(timeout=5000)

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

        # Should show error
        expect(page.locator('text=/incorrect|invalid|failed/i')).to_be_visible(timeout=5000)

    def test_logout(self, authenticated_page: Page):
        """Test that user can log out successfully"""
        page = authenticated_page

        # We're already logged in via the fixture
        # Verify we're logged in
        expect(page.locator(f'text={NETBOX_USERNAME}')).to_be_visible()

        # Find and click logout button/link
        # NetBox typically has a user dropdown menu with logout option
        # This may need adjustment based on NetBox UI structure
        page.click(f'text={NETBOX_USERNAME}')  # Click username dropdown
        page.click('text=/logout/i')  # Click logout link

        # Should redirect to login page
        page.wait_for_url(f'{NETBOX_URL}/login/', timeout=5000)

        # Verify we see the login form again
        expect(page.locator('input[name="username"]')).to_be_visible()

    def test_authenticated_page_fixture_works(self, authenticated_page: Page):
        """Test that the authenticated_page fixture provides a logged-in session"""
        page = authenticated_page

        # Fixture should have already logged us in
        # Verify we're on the home page
        expect(page).to_have_url(f'{NETBOX_URL}/')

        # Verify username is visible (logged in)
        expect(page.locator(f'text={NETBOX_USERNAME}')).to_be_visible()

    def test_unauthenticated_access_redirects(self, unauthenticated_page: Page):
        """Test that accessing protected pages redirects to login"""
        page = unauthenticated_page

        # Try to access a protected page without logging in
        # NetBox should redirect to login
        page.goto(f'{NETBOX_URL}/plugins/netbox_hedgehog/topology-plans/')

        # Should be redirected to login page
        # NetBox typically adds a ?next= parameter
        expect(page).to_have_url(pytest.regexp(r'.*/login/.*'))

        # Login form should be visible
        expect(page.locator('input[name="username"]')).to_be_visible()
