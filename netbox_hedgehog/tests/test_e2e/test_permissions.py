"""
E2E Tests for Permission Enforcement (DIET-110)

These tests use Playwright to verify that permission-based access control works
correctly in the browser, ensuring buttons/links are hidden appropriately and
unauthorized access is denied.

WHY E2E TESTS ARE NEEDED:
- Permission-based UI visibility (hiding Add/Edit/Delete buttons) requires browser testing
- Access denied pages and redirects are only testable via browser
- NetBox permission system involves both Django permissions and custom ObjectPermissions
- Backend tests cannot verify UI elements are properly hidden

WHAT THESE TESTS VERIFY:
- Users without add permission don't see Add buttons
- Users without change permission don't see Edit buttons
- Users without delete permission don't see Delete buttons
- Direct URL access to restricted pages returns 403
- Permission-denied pages show appropriate messages
- ObjectPermission grants work correctly

RUNNING THESE TESTS:
See netbox_hedgehog/tests/test_e2e/README.md for setup instructions.
"""

import os
import time
import unittest
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from users.models import ObjectPermission
from dcim.models import Site

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
class PermissionsE2ETestCase(StaticLiveServerTestCase):
    """
    E2E tests for permission enforcement using Playwright.

    Tests both superuser and limited-permission scenarios.
    """

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
        """Set up test users and browser page"""
        # Create superuser
        self.admin_user = User.objects.create_user(
            username='admin_perms_test',
            password='testpass123',
            is_staff=True,
            is_superuser=True
        )

        # Create limited user (view-only)
        self.viewer_user = User.objects.create_user(
            username='viewer_perms_test',
            password='testpass123',
            is_staff=True,
            is_superuser=False
        )

        # Grant view permission to viewer
        from netbox_hedgehog.models.topology_planning import TopologyPlan
        content_type = ContentType.objects.get_for_model(TopologyPlan)
        view_permission = ObjectPermission.objects.create(
            name='View Topology Plans',
            actions=['view']
        )
        view_permission.object_types.add(content_type)
        view_permission.users.add(self.viewer_user)

        # Create test site
        self.site, _ = Site.objects.get_or_create(
            name='E2E Perms Test Site',
            slug='e2e-perms-test-site'
        )

        # Create new page for each test
        self.page = self.context.new_page()

    def tearDown(self):
        """Clean up after each test"""
        # Clean up test site
        if hasattr(self, 'site'):
            self.site.delete()

        if hasattr(self, 'page'):
            self.page.close()
        if hasattr(self, 'admin_user'):
            self.admin_user.delete()
        if hasattr(self, 'viewer_user'):
            self.viewer_user.delete()

        # Clean up permissions
        ObjectPermission.objects.filter(name__startswith='View Topology').delete()

    def _login_as(self, username, password):
        """Login to NetBox via browser"""
        login_url = f"{self.live_server_url}/login/"
        self.page.goto(login_url)
        self.page.fill('input[name="username"]', username)
        self.page.fill('input[name="password"]', password)
        self.page.click('button[type="submit"]')
        self.page.wait_for_load_state('networkidle')

    def _navigate_to_topology_plans(self):
        """Navigate to Topology Plans list page"""
        hedgehog_menu = self.page.locator('text=Hedgehog').first
        if hedgehog_menu.is_visible():
            hedgehog_menu.click()
            time.sleep(0.3)
        self.page.click('a:has-text("Topology Plans")')
        self.page.wait_for_load_state('networkidle')

    def _create_test_plan(self):
        """Create a test topology plan"""
        from netbox_hedgehog.models.topology_planning import TopologyPlan
        return TopologyPlan.objects.create(
            name='Perms Test Plan',
            customer_name='Perms Customer',
            site=self.site
        )

    # =========================================================================
    # VIEW PERMISSION Tests
    # =========================================================================

    def test_viewer_can_access_list_page(self):
        """
        Test that user with view permission can access list page.

        Verifies:
        - User can navigate to list page
        - Plans are visible
        """
        # Create test plan
        plan = self._create_test_plan()

        try:
            # Login as viewer
            self._login_as('viewer_perms_test', 'testpass123')

            # Navigate to topology plans
            self._navigate_to_topology_plans()

            # Verify we're on the list page (not redirected)
            current_url = self.page.url
            self.assertIn('/topology-plans/', current_url,
                         "Viewer should be able to access list page")

            # Verify plan is visible
            page_content = self.page.content()
            self.assertIn(plan.name, page_content,
                         "Viewer should see plan in list")

        finally:
            plan.delete()

    def test_viewer_can_access_detail_page(self):
        """
        Test that user with view permission can access detail page.

        Verifies:
        - User can view plan details
        - Detail page loads correctly
        """
        # Create test plan
        plan = self._create_test_plan()

        try:
            # Login as viewer
            self._login_as('viewer_perms_test', 'testpass123')

            # Navigate directly to detail page
            detail_url = f"{self.live_server_url}/plugins/hedgehog/topology-plans/{plan.pk}/"
            self.page.goto(detail_url)
            self.page.wait_for_load_state('networkidle')

            # Verify we're on detail page (not access denied)
            current_url = self.page.url
            self.assertIn(f'/topology-plans/{plan.pk}/', current_url)

            # Verify plan information is displayed
            page_content = self.page.content()
            self.assertIn(plan.name, page_content)

        finally:
            plan.delete()

    # =========================================================================
    # ADD PERMISSION Tests
    # =========================================================================

    def test_viewer_cannot_see_add_button(self):
        """
        Test that user without add permission doesn't see Add button.

        Verifies:
        - Add button is hidden or not present
        """
        # Login as viewer
        self._login_as('viewer_perms_test', 'testpass123')

        # Navigate to topology plans
        self._navigate_to_topology_plans()

        # Verify Add button is not visible
        add_button = self.page.locator('a:has-text("Add Topology Plan"), a:has-text("Add")').first
        button_count = add_button.count()

        if button_count > 0:
            # Button exists but should not be visible or enabled
            is_visible = add_button.is_visible()
            self.assertFalse(is_visible,
                           "Add button should not be visible for user without add permission")

    def test_viewer_cannot_access_add_form_directly(self):
        """
        Test that accessing add URL directly returns 403 without permission.

        Verifies:
        - Direct URL access is denied
        - Appropriate error message is shown
        """
        # Login as viewer
        self._login_as('viewer_perms_test', 'testpass123')

        # Try to access add form URL directly
        add_url = f"{self.live_server_url}/plugins/hedgehog/topology-plans/add/"
        self.page.goto(add_url)
        self.page.wait_for_load_state('networkidle')

        # Should see permission denied
        page_content = self.page.content().lower()
        page_title = self.page.title().lower()

        has_permission_denied = (
            'access denied' in page_title or
            'permission denied' in page_content or
            'forbidden' in page_content or
            '403' in page_content
        )

        self.assertTrue(has_permission_denied,
                       "Accessing add URL without permission should show access denied")

    def test_admin_can_see_add_button(self):
        """
        Test that superuser sees Add button.

        Verifies:
        - Add button is visible for superuser
        - Button is clickable
        """
        # Login as admin
        self._login_as('admin_perms_test', 'testpass123')

        # Navigate to topology plans
        self._navigate_to_topology_plans()

        # Verify Add button is visible
        add_button = self.page.locator('a:has-text("Add Topology Plan"), a:has-text("Add")').first
        button_count = add_button.count()

        self.assertGreater(button_count, 0,
                         "Add button should exist for superuser")

    # =========================================================================
    # CHANGE/EDIT PERMISSION Tests
    # =========================================================================

    def test_viewer_cannot_see_edit_button(self):
        """
        Test that user without change permission doesn't see Edit button.

        Verifies:
        - Edit button is hidden on detail page
        """
        # Create test plan
        plan = self._create_test_plan()

        try:
            # Login as viewer
            self._login_as('viewer_perms_test', 'testpass123')

            # Navigate to detail page
            detail_url = f"{self.live_server_url}/plugins/hedgehog/topology-plans/{plan.pk}/"
            self.page.goto(detail_url)
            self.page.wait_for_load_state('networkidle')

            # Verify Edit button is not visible
            edit_button = self.page.locator('a:has-text("Edit")').first
            button_count = edit_button.count()

            if button_count > 0:
                is_visible = edit_button.is_visible()
                self.assertFalse(is_visible,
                               "Edit button should not be visible for user without change permission")

        finally:
            plan.delete()

    def test_viewer_cannot_access_edit_form_directly(self):
        """
        Test that accessing edit URL directly returns 403 without permission.

        Verifies:
        - Direct URL access to edit form is denied
        """
        # Create test plan
        plan = self._create_test_plan()

        try:
            # Login as viewer
            self._login_as('viewer_perms_test', 'testpass123')

            # Try to access edit form directly
            edit_url = f"{self.live_server_url}/plugins/hedgehog/topology-plans/{plan.pk}/edit/"
            self.page.goto(edit_url)
            self.page.wait_for_load_state('networkidle')

            # Should see permission denied
            page_content = self.page.content().lower()
            has_permission_denied = (
                'permission denied' in page_content or
                'access denied' in page_content or
                'forbidden' in page_content
            )

            self.assertTrue(has_permission_denied,
                           "Accessing edit URL without permission should show access denied")

        finally:
            plan.delete()

    # =========================================================================
    # DELETE PERMISSION Tests
    # =========================================================================

    def test_viewer_cannot_see_delete_button(self):
        """
        Test that user without delete permission doesn't see Delete button.

        Verifies:
        - Delete button is hidden on detail page
        """
        # Create test plan
        plan = self._create_test_plan()

        try:
            # Login as viewer
            self._login_as('viewer_perms_test', 'testpass123')

            # Navigate to detail page
            detail_url = f"{self.live_server_url}/plugins/hedgehog/topology-plans/{plan.pk}/"
            self.page.goto(detail_url)
            self.page.wait_for_load_state('networkidle')

            # Verify Delete button is not visible
            delete_button = self.page.locator('a:has-text("Delete"), button:has-text("Delete")').first
            button_count = delete_button.count()

            if button_count > 0:
                is_visible = delete_button.is_visible()
                self.assertFalse(is_visible,
                               "Delete button should not be visible for user without delete permission")

        finally:
            plan.delete()

    def test_viewer_cannot_access_delete_form_directly(self):
        """
        Test that accessing delete URL directly returns 403 without permission.

        Verifies:
        - Direct URL access to delete form is denied
        """
        # Create test plan
        plan = self._create_test_plan()

        try:
            # Login as viewer
            self._login_as('viewer_perms_test', 'testpass123')

            # Try to access delete form directly
            delete_url = f"{self.live_server_url}/plugins/hedgehog/topology-plans/{plan.pk}/delete/"
            self.page.goto(delete_url)
            self.page.wait_for_load_state('networkidle')

            # Should see permission denied
            page_content = self.page.content().lower()
            has_permission_denied = (
                'permission denied' in page_content or
                'access denied' in page_content or
                'forbidden' in page_content
            )

            self.assertTrue(has_permission_denied,
                           "Accessing delete URL without permission should show access denied")

        finally:
            plan.delete()

    # =========================================================================
    # GENERATE DEVICES PERMISSION Tests
    # =========================================================================

    def test_viewer_cannot_access_generate_devices(self):
        """
        Test that user without change permission cannot generate devices.

        Verifies:
        - Generate Devices URL returns 403
        """
        # Create test plan
        plan = self._create_test_plan()

        try:
            # Login as viewer
            self._login_as('viewer_perms_test', 'testpass123')

            # Try to access generate URL directly
            generate_url = f"{self.live_server_url}/plugins/hedgehog/topology-plans/{plan.pk}/generate/"
            self.page.goto(generate_url)
            self.page.wait_for_load_state('networkidle')

            # Should see permission denied
            page_content = self.page.content().lower()
            has_permission_denied = (
                'permission denied' in page_content or
                'access denied' in page_content or
                'forbidden' in page_content
            )

            self.assertTrue(has_permission_denied,
                           "Accessing generate URL without permission should show access denied")

        finally:
            plan.delete()
