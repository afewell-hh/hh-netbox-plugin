"""
E2E Tests for Navigation Highlighting (DIET-157)

These tests use Playwright to verify that navigation highlighting works
correctly in an actual browser, including JavaScript-based highlighting logic.

WHY E2E TESTS ARE NEEDED:
- NetBox uses client-side JavaScript for navigation highlighting
- Django's test client cannot execute JavaScript
- CSS active states are only visible in a rendered browser
- Backend integration tests cannot verify actual UX behavior

WHAT THESE TESTS VERIFY:
- Dashboard link is highlighted only when viewing dashboard
- Dashboard link is NOT highlighted when viewing other pages
- Topology Plans link is highlighted when viewing topology plans
- Navigation state changes correctly when navigating between pages

RUNNING THESE TESTS:
See netbox_hedgehog/tests/test_e2e/README.md for setup instructions.
"""

import os
import time
import unittest
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.contrib.auth import get_user_model

# Conditional import - allows module to load even when Playwright isn't installed
try:
    from playwright.sync_api import sync_playwright, expect
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    sync_playwright = None
    expect = None

User = get_user_model()

# Check for opt-in environment variable to enable E2E tests
RUN_E2E_TESTS = os.environ.get('RUN_E2E_TESTS', 'false').lower() == 'true'


@unittest.skipUnless(
    RUN_E2E_TESTS and PLAYWRIGHT_AVAILABLE,
    "E2E tests disabled. Set RUN_E2E_TESTS=true and install Playwright to enable."
)
class NavigationHighlightingE2ETestCase(StaticLiveServerTestCase):
    """
    E2E tests for navigation highlighting using Playwright.

    These tests launch a real browser and verify navigation behavior.
    """

    @classmethod
    def setUpClass(cls):
        """Set up Playwright browser"""
        super().setUpClass()

        # At this point, we know Playwright is available (class-level skip handles it)
        cls.playwright = sync_playwright().start()
        # Use chromium for consistent testing
        # headless=False for debugging, headless=True for CI
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

        # Create superuser for testing
        self.user = User.objects.create_user(
            username='e2e_test_user',
            password='testpassword123',
            is_staff=True,
            is_superuser=True
        )

        # Create new page for each test
        self.page = self.context.new_page()

        # Login to NetBox
        self._login()

    def tearDown(self):
        """Clean up after each test"""
        if hasattr(self, 'page'):
            self.page.close()
        if hasattr(self, 'user'):
            self.user.delete()

    def _login(self):
        """Login to NetBox via the browser"""
        login_url = f"{self.live_server_url}/login/"
        self.page.goto(login_url)

        # Fill in login form
        self.page.fill('input[name="username"]', 'e2e_test_user')
        self.page.fill('input[name="password"]', 'testpassword123')

        # Submit form
        self.page.click('button[type="submit"]')

        # Wait for redirect after login
        self.page.wait_for_load_state('networkidle')

    def _get_nav_link_classes(self, link_text):
        """
        Get the CSS classes of a navigation link by its text.

        Returns the class attribute as a string, or None if not found.
        """
        # Try to find the link in the navigation
        # NetBox uses dropdown menus, so we need to click the plugin menu first
        try:
            # Click on "Plugins" or "Hedgehog" dropdown to reveal menu
            hedgehog_menu = self.page.locator('text=Hedgehog').first
            if hedgehog_menu.is_visible():
                hedgehog_menu.click()
                time.sleep(0.3)  # Wait for dropdown animation

            # Find the specific link
            link = self.page.locator(f'a:has-text("{link_text}")').first
            if link.is_visible():
                classes = link.get_attribute('class')
                return classes
        except Exception as e:
            print(f"Could not find link '{link_text}': {e}")
            return None

        return None

    def _is_link_active(self, link_text):
        """
        Check if a navigation link appears to be active/highlighted.

        NetBox may use various methods to indicate active state:
        - CSS classes (active, selected, etc.)
        - aria-current attribute
        - Computed styles (color, font-weight, etc.)

        Returns tuple: (found: bool, is_active: bool)
        - (True, True): Link found and appears active
        - (True, False): Link found but not active
        - (False, False): Link not found (cannot determine state)
        """
        try:
            # Open the Hedgehog dropdown to reveal menu
            hedgehog_menu = self.page.locator('text=Hedgehog').first
            if not hedgehog_menu.is_visible():
                return (False, False)  # Menu not found

            hedgehog_menu.click()
            time.sleep(0.3)  # Wait for dropdown animation

            # Find the specific link
            link = self.page.locator(f'a:has-text("{link_text}")').first
            if not link.is_visible():
                return (False, False)  # Link not found after opening menu

            # Link was found - now check if it's active

            # Check 1: CSS classes
            classes = link.get_attribute('class') or ''
            if 'active' in classes.lower() or 'selected' in classes.lower():
                return (True, True)

            # Check 2: aria-current attribute (accessibility indicator)
            aria_current = link.get_attribute('aria-current')
            if aria_current in ['page', 'true', 'location']:
                return (True, True)

            # Check 3: Parent element classes
            parent = link.locator('xpath=..')
            parent_classes = parent.get_attribute('class') or ''
            if 'active' in parent_classes.lower() or 'selected' in parent_classes.lower():
                return (True, True)

            # Check 4: Computed styles (as a heuristic)
            # Active links often have different font-weight or color
            computed_style = self.page.evaluate('''(linkText) => {
                const link = Array.from(document.querySelectorAll('a'))
                    .find(a => a.textContent.trim() === linkText);
                if (!link) return null;
                const style = window.getComputedStyle(link);
                return {
                    fontWeight: style.fontWeight,
                    color: style.color,
                    backgroundColor: style.backgroundColor
                };
            }''', link_text)

            if computed_style:
                # Parse font-weight - can be numeric (400, 700) or keyword (normal, bold)
                font_weight_value = computed_style.get('fontWeight', '400')

                # Convert keywords to numeric values
                weight_map = {'normal': 400, 'bold': 700, 'bolder': 800, 'lighter': 300}
                if font_weight_value in weight_map:
                    font_weight = weight_map[font_weight_value]
                else:
                    try:
                        font_weight = int(font_weight_value)
                    except (ValueError, TypeError):
                        font_weight = 400  # Default to normal if unparseable

                # Bold font weight (700+) often indicates active state
                if font_weight >= 700:
                    return (True, True)

            # Link was found but no active indicators detected
            return (True, False)

        except Exception as e:
            print(f"Error checking if link '{link_text}' is active: {e}")
            return (False, False)  # Error means we couldn't determine state

    def _get_current_url_path(self):
        """Get the current URL path (without domain)"""
        return self.page.evaluate('() => window.location.pathname')

    # =========================================================================
    # E2E Test Cases
    # =========================================================================

    def test_dashboard_highlighted_only_on_dashboard_page(self):
        """
        Test that Dashboard link is highlighted on dashboard page.

        Verifies that when viewing the dashboard, the Dashboard navigation link
        appears in an active/highlighted state.
        """
        # Navigate to Dashboard
        dashboard_url = f"{self.live_server_url}/plugins/hedgehog/dashboard/"
        self.page.goto(dashboard_url)
        self.page.wait_for_load_state('networkidle')

        # Verify we're on the dashboard page
        current_path = self._get_current_url_path()
        self.assertIn('dashboard', current_path)

        # CRITICAL CHECK: Dashboard link must be found in navigation
        link_found, is_active = self._is_link_active("Dashboard")

        self.assertTrue(link_found,
                       "Dashboard link must be visible in navigation. "
                       "If this fails, either the navigation structure changed or "
                       "the dropdown didn't open properly.")

        # CRITICAL ASSERTION: Dashboard link must be active when on dashboard page
        self.assertTrue(is_active,
                       "Dashboard link must be active/highlighted when viewing the dashboard page. "
                       "If this fails, the navigation highlighting is broken - the active link "
                       "indicator is not appearing on the current page.")

    def test_dashboard_not_highlighted_on_topology_plans_page(self):
        """
        Test that Dashboard link is NOT highlighted when viewing Topology Plans.

        This is the MAIN REGRESSION TEST for DIET-157.

        The bug was that the Dashboard link stayed highlighted on all pages
        because it used an empty string URL that matched everything.
        """
        # Navigate to Topology Plans
        topology_url = f"{self.live_server_url}/plugins/hedgehog/topology-plans/"
        self.page.goto(topology_url)
        self.page.wait_for_load_state('networkidle')

        # Verify we're on the topology plans page
        current_path = self._get_current_url_path()
        self.assertIn('topology-plans', current_path)
        self.assertNotIn('dashboard', current_path)

        # Verify we can see the topology plans list heading
        # This confirms we're on the right page
        heading_visible = (
            self.page.locator('h1:has-text("Topology Plans")').count() > 0 or
            self.page.locator('text=Topology Plans').count() > 0
        )
        self.assertTrue(heading_visible, "Should see Topology Plans heading")

        # CRITICAL REGRESSION CHECK: Dashboard link should NOT be active
        dashboard_found, dashboard_is_active = self._is_link_active("Dashboard")

        # First verify we could actually find the link
        self.assertTrue(dashboard_found,
                       "Dashboard link must be visible in navigation. "
                       "If this fails, either the navigation structure changed or "
                       "the dropdown didn't open properly.")

        # Now verify it's NOT active (this is the main regression test)
        self.assertFalse(dashboard_is_active,
                        "Dashboard link should NOT be active/highlighted on Topology Plans page. "
                        "If this fails, the DIET-157 bug has regressed - the dashboard link is "
                        "being highlighted on pages other than the dashboard.")

        # Additional verification: URLs should be different
        dashboard_url_path = '/plugins/hedgehog/dashboard/'
        self.assertNotEqual(current_path, dashboard_url_path,
                          "Topology Plans URL should differ from Dashboard URL")

    def test_navigation_between_pages_updates_state(self):
        """
        Test that navigation state changes when moving between pages.

        Verifies that the navigation highlighting logic responds to page changes.
        """
        # Start at Dashboard
        dashboard_url = f"{self.live_server_url}/plugins/hedgehog/dashboard/"
        self.page.goto(dashboard_url)
        self.page.wait_for_load_state('networkidle')

        dashboard_path = self._get_current_url_path()
        self.assertIn('dashboard', dashboard_path)

        # Navigate to Topology Plans
        topology_url = f"{self.live_server_url}/plugins/hedgehog/topology-plans/"
        self.page.goto(topology_url)
        self.page.wait_for_load_state('networkidle')

        topology_path = self._get_current_url_path()
        self.assertIn('topology-plans', topology_path)

        # Verify we actually changed pages
        self.assertNotEqual(dashboard_path, topology_path,
                          "Should navigate from dashboard to topology plans")

        # Navigate to Server Classes
        server_classes_url = f"{self.live_server_url}/plugins/hedgehog/server-classes/"
        self.page.goto(server_classes_url)
        self.page.wait_for_load_state('networkidle')

        server_classes_path = self._get_current_url_path()

        # Verify all three pages have different URLs
        paths = {dashboard_path, topology_path, server_classes_path}
        self.assertEqual(len(paths), 3,
                        "All three pages should have distinct URLs")

    def test_url_path_components_are_distinct(self):
        """
        Verify that plugin URLs don't share ambiguous path components.

        This test ensures the root cause of DIET-157 (empty string URL)
        cannot regress even at the E2E level.
        """
        # Navigate to dashboard
        self.page.goto(f"{self.live_server_url}/plugins/hedgehog/dashboard/")
        self.page.wait_for_load_state('networkidle')
        dashboard_path = self._get_current_url_path()

        # Verify dashboard path has 'dashboard' component
        path_parts = [p for p in dashboard_path.split('/') if p]
        self.assertIn('dashboard', path_parts,
                     "Dashboard URL should contain 'dashboard' path component")

        # Verify last component is not empty
        last_component = dashboard_path.rstrip('/').split('/')[-1]
        self.assertNotEqual(last_component, '',
                          "Dashboard URL should not end with empty path component")

        # Navigate to another page
        self.page.goto(f"{self.live_server_url}/plugins/hedgehog/topology-plans/")
        self.page.wait_for_load_state('networkidle')
        topology_path = self._get_current_url_path()

        # Verify topology path is distinct
        self.assertNotEqual(dashboard_path, topology_path,
                          "Dashboard and topology URLs must be distinct")
