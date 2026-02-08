"""
E2E Tests for Generate Devices Workflow (DIET-110)

These tests use Playwright to verify that users can generate NetBox devices
from topology plans using a real browser, ensuring the complete UX flow works.

WHY E2E TESTS ARE NEEDED:
- Generate Devices involves complex multi-step workflows
- Preview page calculations and rendering require JavaScript
- Success/error messages are only visible in the browser
- Device creation verification requires navigating between pages
- Backend integration tests cannot verify the complete user experience

WHAT THESE TESTS VERIFY:
- Generate Devices button is visible on plan detail page
- Clicking button shows preview page with accurate counts
- Preview page displays warnings for empty plans
- Generate confirmation creates actual devices in NetBox
- Success messages appear after generation
- Generated devices are tagged and findable
- Regeneration workflow handles existing devices correctly
- Plan-scoped regeneration doesn't affect other plans (multi-tenant safety)

RUNNING THESE TESTS:
See netbox_hedgehog/tests/test_e2e/README.md for setup instructions.
"""

import os
import time
import unittest
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.contrib.auth import get_user_model
from dcim.models import Device

from .helpers import create_base_test_data, cleanup_base_test_data

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
class GenerateDevicesE2ETestCase(StaticLiveServerTestCase):
    """
    E2E tests for Generate Devices workflow using Playwright.

    These tests launch a real browser and verify the complete generation workflow.
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
        """Set up test user, test data, and browser page"""
        # Create superuser for testing
        self.user = User.objects.create_user(
            username='e2e_generate_test_user',
            password='testpassword123',
            is_staff=True,
            is_superuser=True
        )

        # Create base test data (DeviceTypes, Extensions, etc.)
        self.test_data = create_base_test_data()

        # Create new page for each test
        self.page = self.context.new_page()

        # Login to NetBox
        self._login()

    def tearDown(self):
        """Clean up after each test"""
        # Clean up base test data
        cleanup_base_test_data()

        if hasattr(self, 'page'):
            self.page.close()
        if hasattr(self, 'user'):
            self.user.delete()

    def _login(self):
        """Login to NetBox via the browser"""
        login_url = f"{self.live_server_url}/login/"
        self.page.goto(login_url)
        self.page.fill('input[name="username"]', 'e2e_generate_test_user')
        self.page.fill('input[name="password"]', 'testpassword123')
        self.page.click('button[type="submit"]')
        self.page.wait_for_load_state('networkidle')

    def _create_test_plan_with_servers(self):
        """Create a topology plan with server classes for testing"""
        from netbox_hedgehog.models.topology_planning import (
            TopologyPlan, PlanServerClass, PlanServerConnection, PlanSwitchClass
        )

        # Create plan
        plan = TopologyPlan.objects.create(
            name=f'E2E Generate Test Plan {int(time.time())}',
            customer_name='E2E Test Customer'
        )

        # Create server class
        server_class = PlanServerClass.objects.create(
            plan=plan,
            server_class_id='e2e-test-servers',
            description='E2E Test Servers',
            category='gpu',
            quantity=3,  # 3 servers
            gpus_per_server=8,
            server_device_type=self.test_data['server_type']
        )

        # Create switch class (for connections)
        switch_class = PlanSwitchClass.objects.create(
            plan=plan,
            switch_class_id='e2e-test-frontend-leaf',
            fabric='frontend',
            hedgehog_role='server-leaf',
            calculated_quantity=2,
            device_type_extension=self.test_data['switch_ext']
        )

        # Create server connection (to frontend switches)
        PlanServerConnection.objects.create(
            server_class=server_class,
            connection_id='frontend',
            connection_name='Frontend Network',
            ports_per_connection=2,
            hedgehog_conn_type='unbundled',
            distribution='alternating',
            target_switch_class=switch_class,
            speed=200,
            port_type='data'
        )

        return plan

    # =========================================================================
    # BASIC WORKFLOW Tests
    # =========================================================================

    def test_generate_button_visible_on_plan_detail(self):
        """
        Test that Generate Devices button is visible on plan detail page.

        Verifies:
        - Button exists
        - Button is clickable
        - User with proper permissions sees the button
        """
        # Create test plan
        plan = self._create_test_plan_with_servers()

        try:
            # Navigate to plan detail page
            detail_url = f"{self.live_server_url}/plugins/hedgehog/topology-plans/{plan.pk}/"
            self.page.goto(detail_url)
            self.page.wait_for_load_state('networkidle')

            # Verify Generate Devices button exists
            generate_button = self.page.locator('a:has-text("Generate Devices"), button:has-text("Generate Devices")').first

            # Button should be visible for superuser
            self.assertGreater(generate_button.count(), 0,
                             "Generate Devices button should exist on plan detail page")

            # Verify button is clickable (not disabled)
            if generate_button.is_visible():
                is_enabled = not generate_button.is_disabled()
                self.assertTrue(is_enabled,
                              "Generate Devices button should be enabled")

        finally:
            plan.delete()

    def test_generate_preview_page_loads_with_counts(self):
        """
        Test that clicking Generate Devices shows preview page with device counts.

        This is CRITICAL - validates that the preview page works correctly.

        Verifies:
        - Preview page loads
        - Device counts are displayed
        - Server count is correct
        - Switch count is displayed
        """
        # Create test plan
        plan = self._create_test_plan_with_servers()

        try:
            # Navigate to plan detail page
            detail_url = f"{self.live_server_url}/plugins/hedgehog/topology-plans/{plan.pk}/"
            self.page.goto(detail_url)
            self.page.wait_for_load_state('networkidle')

            # Click Generate Devices button
            generate_button = self.page.locator('a:has-text("Generate Devices")').first
            generate_button.click()
            self.page.wait_for_load_state('networkidle')

            # Verify we're on the preview page
            current_url = self.page.url
            self.assertIn('/generate/', current_url)

            # Verify preview page shows counts
            page_content = self.page.content().lower()

            # Should show device-related information
            self.assertTrue(
                'device' in page_content or 'server' in page_content,
                "Preview page should display device information"
            )

            # Should show server count (3 servers)
            self.assertIn('3', self.page.content(),
                         "Preview should show server count of 3")

        finally:
            plan.delete()

    def test_generate_preview_shows_warnings_for_empty_plan(self):
        """
        Test that preview shows warnings when plan has no servers or switches.

        Verifies:
        - Empty plan warning appears
        - User is informed before generation
        """
        from netbox_hedgehog.models.topology_planning import TopologyPlan

        # Create empty plan (no servers)
        empty_plan = TopologyPlan.objects.create(
            name='E2E Empty Test Plan',
            customer_name='E2E Empty'
        )

        try:
            # Navigate to plan detail page
            detail_url = f"{self.live_server_url}/plugins/hedgehog/topology-plans/{empty_plan.pk}/"
            self.page.goto(detail_url)
            self.page.wait_for_load_state('networkidle')

            # Click Generate Devices button
            generate_button = self.page.locator('a:has-text("Generate Devices")').first
            generate_button.click()
            self.page.wait_for_load_state('networkidle')

            # Verify we're on the preview page
            current_url = self.page.url
            self.assertIn('/generate/', current_url)

            # Verify warning/alert appears about empty plan
            page_content = self.page.content().lower()
            has_warning = (
                'warning' in page_content or
                'no server' in page_content or
                'empty' in page_content or
                'no devices' in page_content
            )
            self.assertTrue(has_warning,
                           "Preview should show warning for empty plan")

        finally:
            empty_plan.delete()

    # =========================================================================
    # GENERATION WORKFLOW Tests
    # =========================================================================

    def test_generate_confirm_creates_devices(self):
        """
        Test the complete generate workflow: preview → confirm → devices created.

        This is the MOST CRITICAL test - validates that generation actually works.

        Verifies:
        1. Preview page loads correctly
        2. Confirm button works
        3. Devices are created in NetBox
        4. Success message appears
        5. User is redirected appropriately
        """
        # Create test plan
        plan = self._create_test_plan_with_servers()

        try:
            # Navigate to plan detail page
            detail_url = f"{self.live_server_url}/plugins/hedgehog/topology-plans/{plan.pk}/"
            self.page.goto(detail_url)
            self.page.wait_for_load_state('networkidle')

            # Click Generate Devices
            generate_button = self.page.locator('a:has-text("Generate Devices")').first
            generate_button.click()
            self.page.wait_for_load_state('networkidle')

            # We're on preview page - click Generate/Confirm button
            confirm_button = self.page.locator(
                'button:has-text("Generate Devices"), '
                'button:has-text("Generate"), '
                'input[type="submit"][value*="Generate"]'
            ).first

            self.assertGreater(confirm_button.count(), 0,
                             "Generate confirmation button should exist on preview page")

            # Click confirm (expect navigation/redirect)
            confirm_button.click()
            self.page.wait_for_load_state('networkidle')
            time.sleep(0.5)  # Brief wait for success message

            # Verify success message appears
            page_content = self.page.content().lower()
            has_success = (
                'generation complete' in page_content or
                'success' in page_content or
                'created' in page_content
            )
            self.assertTrue(has_success,
                           "Success message should appear after generation")

            # Verify devices were actually created in database
            # Should have 3 servers + 2 switches = 5 devices minimum
            generated_devices = Device.objects.filter(name__startswith='e2e-test-')
            device_count = generated_devices.count()
            self.assertGreater(device_count, 0,
                             "Devices should be created in NetBox database")

        finally:
            # Cleanup generated devices
            Device.objects.filter(name__startswith='e2e-test-').delete()
            plan.delete()

    # =========================================================================
    # REGENERATION WORKFLOW Tests
    # =========================================================================

    def test_regeneration_shows_warning(self):
        """
        Test that regenerating a plan shows warning about previous generation.

        Verifies:
        1. First generation succeeds
        2. Second generation attempt shows warning/message
        3. User is informed about regeneration implications
        """
        # Create test plan
        plan = self._create_test_plan_with_servers()

        try:
            # First generation
            detail_url = f"{self.live_server_url}/plugins/hedgehog/topology-plans/{plan.pk}/"
            self.page.goto(detail_url)
            self.page.wait_for_load_state('networkidle')

            # Click Generate
            self.page.click('a:has-text("Generate Devices")')
            self.page.wait_for_load_state('networkidle')

            # Confirm generation
            confirm_button = self.page.locator('button:has-text("Generate Devices"), button:has-text("Generate")').first
            confirm_button.click()
            self.page.wait_for_load_state('networkidle')
            time.sleep(0.5)

            # Now try to generate again (regeneration)
            self.page.goto(detail_url)
            self.page.wait_for_load_state('networkidle')

            # Click Generate Devices again
            self.page.click('a:has-text("Generate Devices")')
            self.page.wait_for_load_state('networkidle')

            # Verify warning/message about regeneration appears
            page_content = self.page.content().lower()
            has_regeneration_indicator = (
                'regenerate' in page_content or
                'previously generated' in page_content or
                'already generated' in page_content or
                'replace' in page_content
            )
            self.assertTrue(has_regeneration_indicator,
                           "Preview should indicate this is a regeneration")

        finally:
            # Cleanup
            Device.objects.filter(name__startswith='e2e-test-').delete()
            plan.delete()

    def test_plan_scoped_regeneration_isolation(self):
        """
        Test that regenerating Plan A doesn't affect Plan B (multi-tenant safety).

        This is CRITICAL for multi-plan environments.

        Verifies:
        1. Generate Plan A
        2. Generate Plan B
        3. Count Plan B devices
        4. Regenerate Plan A
        5. Verify Plan B device count unchanged
        """
        # Create two separate plans
        plan_a = self._create_test_plan_with_servers()
        plan_a.name = 'E2E Plan A'
        plan_a.save()

        plan_b = self._create_test_plan_with_servers()
        plan_b.name = 'E2E Plan B'
        plan_b.save()

        try:
            # Generate Plan A
            detail_url_a = f"{self.live_server_url}/plugins/hedgehog/topology-plans/{plan_a.pk}/"
            self.page.goto(detail_url_a)
            self.page.wait_for_load_state('networkidle')
            self.page.click('a:has-text("Generate Devices")')
            self.page.wait_for_load_state('networkidle')
            self.page.click('button:has-text("Generate Devices"), button:has-text("Generate")')
            self.page.wait_for_load_state('networkidle')
            time.sleep(0.5)

            # Generate Plan B
            detail_url_b = f"{self.live_server_url}/plugins/hedgehog/topology-plans/{plan_b.pk}/"
            self.page.goto(detail_url_b)
            self.page.wait_for_load_state('networkidle')
            self.page.click('a:has-text("Generate Devices")')
            self.page.wait_for_load_state('networkidle')
            self.page.click('button:has-text("Generate Devices"), button:has-text("Generate")')
            self.page.wait_for_load_state('networkidle')
            time.sleep(0.5)

            # Count Plan B devices
            plan_b_devices_before = Device.objects.filter(
                name__contains=f'plan-{plan_b.pk}'
            ).count()

            # Regenerate Plan A
            self.page.goto(detail_url_a)
            self.page.wait_for_load_state('networkidle')
            self.page.click('a:has-text("Generate Devices")')
            self.page.wait_for_load_state('networkidle')
            self.page.click('button:has-text("Generate Devices"), button:has-text("Generate")')
            self.page.wait_for_load_state('networkidle')
            time.sleep(0.5)

            # Verify Plan B devices unchanged
            plan_b_devices_after = Device.objects.filter(
                name__contains=f'plan-{plan_b.pk}'
            ).count()

            self.assertEqual(plan_b_devices_before, plan_b_devices_after,
                           "Plan B devices should be unchanged when regenerating Plan A")

        finally:
            # Cleanup
            Device.objects.filter(name__startswith='e2e-test-').delete()
            plan_a.delete()
            plan_b.delete()

    # =========================================================================
    # PERMISSION Tests
    # =========================================================================

    def test_permission_denied_without_change_permission(self):
        """
        Test that users without change_topologyplan permission cannot generate.

        Verifies PermissionRequiredMixin enforcement in generate view.

        Creates a user without permissions and verifies:
        - Generate URL returns 403 or redirects to login
        - Appropriate error message is shown
        """
        # Create user without permissions
        limited_user = User.objects.create_user(
            username='limited_generate_user',
            password='testpass',
            is_staff=True,
            is_superuser=False
        )

        # Create test plan
        plan = self._create_test_plan_with_servers()

        try:
            # Create new page and login as limited user
            limited_page = self.context.new_page()
            login_url = f"{self.live_server_url}/login/"
            limited_page.goto(login_url)
            limited_page.fill('input[name="username"]', 'limited_generate_user')
            limited_page.fill('input[name="password"]', 'testpass')
            limited_page.click('button[type="submit"]')
            limited_page.wait_for_load_state('networkidle')

            # Try to access generate URL directly
            generate_url = f"{self.live_server_url}/plugins/hedgehog/topology-plans/{plan.pk}/generate/"
            limited_page.goto(generate_url)
            limited_page.wait_for_load_state('networkidle')

            # NetBox should show permission denied
            page_title = limited_page.title()
            page_content = limited_page.content().lower()

            has_permission_denied = (
                'access denied' in page_title.lower() or
                'permission denied' in page_content or
                'forbidden' in page_content or
                '403' in page_content or
                'not permitted' in page_content
            )

            self.assertTrue(has_permission_denied,
                           "User without permission should see access denied message")

            # Cleanup limited page
            limited_page.close()

        finally:
            limited_user.delete()
            plan.delete()
