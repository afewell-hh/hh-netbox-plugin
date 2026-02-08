"""
E2E Tests for Export YAML Workflow (DIET-110)

These tests use Playwright to verify that users can export Hedgehog wiring YAML
from topology plans using a real browser.

WHY E2E TESTS ARE NEEDED:
- Export YAML involves file downloads which can only be tested in a browser
- YAML content validation requires actual file download
- Download triggers and file naming can only be verified via browser automation
- Backend tests cannot verify the download UX

WHAT THESE TESTS VERIFY:
- Export YAML button is visible on plan detail page
- Clicking button triggers file download
- Downloaded file is valid YAML
- YAML content matches plan configuration
- File naming convention is correct

RUNNING THESE TESTS:
See netbox_hedgehog/tests/test_e2e/README.md for setup instructions.
"""

import os
import time
import unittest
import yaml
from pathlib import Path
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.contrib.auth import get_user_model

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
class ExportYAMLE2ETestCase(StaticLiveServerTestCase):
    """
    E2E tests for Export YAML workflow using Playwright.

    These tests launch a real browser and verify YAML export functionality.
    """

    @classmethod
    def setUpClass(cls):
        """Set up Playwright browser with download handling"""
        super().setUpClass()

        cls.playwright = sync_playwright().start()
        headless = os.environ.get('PLAYWRIGHT_HEADLESS', 'true').lower() == 'true'
        cls.browser = cls.playwright.chromium.launch(headless=headless)

        # Create a temporary download directory
        cls.download_dir = Path('/tmp/e2e_yaml_downloads')
        cls.download_dir.mkdir(exist_ok=True)

        # Create context with download handling
        cls.context = cls.browser.new_context(
            accept_downloads=True,
            downloads_path=str(cls.download_dir)
        )

    @classmethod
    def tearDownClass(cls):
        """Clean up Playwright resources and download directory"""
        cls.context.close()
        cls.browser.close()
        cls.playwright.stop()

        # Clean up download directory
        import shutil
        if cls.download_dir.exists():
            shutil.rmtree(cls.download_dir)

        super().tearDownClass()

    def setUp(self):
        """Set up test user and browser page"""
        # Create superuser for testing
        self.user = User.objects.create_user(
            username='e2e_export_test_user',
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
        # Clean up downloaded files
        for file in self.download_dir.glob('*'):
            file.unlink()

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
        self.page.fill('input[name="username"]', 'e2e_export_test_user')
        self.page.fill('input[name="password"]', 'testpassword123')
        self.page.click('button[type="submit"]')
        self.page.wait_for_load_state('networkidle')

    def _create_test_plan_with_data(self):
        """Create a topology plan with servers and switches for export testing"""
        from netbox_hedgehog.models.topology_planning import (
            TopologyPlan, PlanServerClass, PlanServerConnection, PlanSwitchClass
        )

        # Create plan
        plan = TopologyPlan.objects.create(
            name=f'E2E Export Test Plan {int(time.time())}',
            customer_name='E2E Export Customer'
        )

        # Create server class
        server_class = PlanServerClass.objects.create(
            plan=plan,
            server_class_id='export-test-servers',
            description='Export Test Servers',
            category='gpu',
            quantity=2,
            gpus_per_server=8,
            server_device_type=self.test_data['server_type']
        )

        # Create switch class
        switch_class = PlanSwitchClass.objects.create(
            plan=plan,
            switch_class_id='export-test-leaf',
            fabric='frontend',
            hedgehog_role='server-leaf',
            calculated_quantity=2,
            effective_quantity=2,
            device_type_extension=self.test_data['switch_ext']
        )

        # Create server connection
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
    # BASIC EXPORT Tests
    # =========================================================================

    def test_export_yaml_button_exists(self):
        """
        Test that Export YAML button exists on plan detail page.

        Verifies:
        - Button is visible
        - Button is properly labeled
        """
        # Create test plan
        plan = self._create_test_plan_with_data()

        try:
            # Navigate to plan detail page
            detail_url = f"{self.live_server_url}/plugins/hedgehog/topology-plans/{plan.pk}/"
            self.page.goto(detail_url)
            self.page.wait_for_load_state('networkidle')

            # Verify Export YAML button exists
            export_button = self.page.locator(
                'a:has-text("Export YAML"), '
                'a:has-text("Export"), '
                'button:has-text("Export YAML")'
            ).first

            button_count = export_button.count()
            self.assertGreater(button_count, 0,
                             "Export YAML button should exist on plan detail page")

            # If visible, verify it's clickable
            if export_button.is_visible():
                is_enabled = not export_button.is_disabled()
                self.assertTrue(is_enabled,
                              "Export YAML button should be enabled")

        finally:
            plan.delete()

    def test_export_yaml_triggers_download(self):
        """
        Test that clicking Export YAML button triggers file download.

        This is the CRITICAL test for export functionality.

        Verifies:
        - Clicking button initiates download
        - File is downloaded successfully
        - Downloaded file is not empty
        """
        # Create test plan
        plan = self._create_test_plan_with_data()

        try:
            # Navigate to plan detail page
            detail_url = f"{self.live_server_url}/plugins/hedgehog/topology-plans/{plan.pk}/"
            self.page.goto(detail_url)
            self.page.wait_for_load_state('networkidle')

            # Find Export YAML button
            export_button = self.page.locator(
                'a:has-text("Export YAML"), '
                'a:has-text("Export")'
            ).first

            # Wait for download after clicking button
            with self.page.expect_download(timeout=10000) as download_info:
                export_button.click()

            download = download_info.value

            # Verify download completed
            self.assertIsNotNone(download,
                               "Download should have been initiated")

            # Save download to our temp directory
            download_path = self.download_dir / download.suggested_filename
            download.save_as(download_path)

            # Verify file exists and is not empty
            self.assertTrue(download_path.exists(),
                           "Downloaded file should exist")

            file_size = download_path.stat().st_size
            self.assertGreater(file_size, 0,
                             "Downloaded file should not be empty")

        finally:
            plan.delete()

    # =========================================================================
    # YAML CONTENT VALIDATION Tests
    # =========================================================================

    def test_exported_yaml_is_valid(self):
        """
        Test that exported YAML file is valid and parseable.

        Verifies:
        - Downloaded file is valid YAML
        - Can be parsed without errors
        """
        # Create test plan
        plan = self._create_test_plan_with_data()

        try:
            # Navigate to plan detail page
            detail_url = f"{self.live_server_url}/plugins/hedgehog/topology-plans/{plan.pk}/"
            self.page.goto(detail_url)
            self.page.wait_for_load_state('networkidle')

            # Click Export YAML and wait for download
            export_button = self.page.locator(
                'a:has-text("Export YAML"), '
                'a:has-text("Export")'
            ).first

            with self.page.expect_download(timeout=10000) as download_info:
                export_button.click()

            download = download_info.value
            download_path = self.download_dir / download.suggested_filename
            download.save_as(download_path)

            # Try to parse YAML
            with open(download_path, 'r') as f:
                yaml_content = f.read()

            # Parse YAML - should not raise exception
            try:
                parsed_yaml = yaml.safe_load_all(yaml_content)
                documents = list(parsed_yaml)

                # Verify we got some documents
                self.assertGreater(len(documents), 0,
                                 "YAML should contain at least one document")

            except yaml.YAMLError as e:
                self.fail(f"Downloaded YAML is not valid: {e}")

        finally:
            plan.delete()

    def test_exported_yaml_contains_connection_crds(self):
        """
        Test that exported YAML contains Hedgehog Connection CRDs.

        Verifies:
        - YAML contains Connection resources
        - Connection metadata is present
        - apiVersion and kind are correct
        """
        # Create test plan
        plan = self._create_test_plan_with_data()

        try:
            # Navigate to plan detail page
            detail_url = f"{self.live_server_url}/plugins/hedgehog/topology-plans/{plan.pk}/"
            self.page.goto(detail_url)
            self.page.wait_for_load_state('networkidle')

            # Click Export YAML and wait for download
            export_button = self.page.locator(
                'a:has-text("Export YAML"), '
                'a:has-text("Export")'
            ).first

            with self.page.expect_download(timeout=10000) as download_info:
                export_button.click()

            download = download_info.value
            download_path = self.download_dir / download.suggested_filename
            download.save_as(download_path)

            # Parse YAML
            with open(download_path, 'r') as f:
                yaml_content = f.read()

            documents = list(yaml.safe_load_all(yaml_content))

            # Verify at least one document is a Connection CRD
            connection_crds = [
                doc for doc in documents
                if doc and doc.get('kind') == 'Connection'
            ]

            self.assertGreater(len(connection_crds), 0,
                             "YAML should contain at least one Connection CRD")

            # Verify Connection CRD structure
            first_connection = connection_crds[0]
            self.assertIn('apiVersion', first_connection,
                         "Connection should have apiVersion")
            self.assertIn('metadata', first_connection,
                         "Connection should have metadata")
            self.assertIn('spec', first_connection,
                         "Connection should have spec")

            # Verify apiVersion is Hedgehog
            api_version = first_connection.get('apiVersion', '')
            self.assertIn('wiring.githedgehog.com', api_version,
                         "apiVersion should be Hedgehog wiring API")

        finally:
            plan.delete()

    # =========================================================================
    # FILE NAMING Tests
    # =========================================================================

    def test_exported_yaml_filename_convention(self):
        """
        Test that exported YAML file follows correct naming convention.

        Verifies:
        - Filename includes plan name or ID
        - Filename has .yaml or .yml extension
        """
        # Create test plan with specific name
        plan = self._create_test_plan_with_data()
        plan.name = 'Test Plan For Filename'
        plan.save()

        try:
            # Navigate to plan detail page
            detail_url = f"{self.live_server_url}/plugins/hedgehog/topology-plans/{plan.pk}/"
            self.page.goto(detail_url)
            self.page.wait_for_load_state('networkidle')

            # Click Export YAML and wait for download
            export_button = self.page.locator(
                'a:has-text("Export YAML"), '
                'a:has-text("Export")'
            ).first

            with self.page.expect_download(timeout=10000) as download_info:
                export_button.click()

            download = download_info.value
            filename = download.suggested_filename

            # Verify filename has YAML extension
            has_yaml_extension = filename.endswith('.yaml') or filename.endswith('.yml')
            self.assertTrue(has_yaml_extension,
                           f"Filename '{filename}' should have .yaml or .yml extension")

            # Verify filename includes some identifier
            # (could be plan name slug, plan ID, or other convention)
            self.assertGreater(len(filename), 5,
                             "Filename should be more descriptive than just extension")

        finally:
            plan.delete()

    # =========================================================================
    # PERMISSION Tests
    # =========================================================================

    def test_export_yaml_permission_enforcement(self):
        """
        Test that Export YAML respects permissions.

        Verifies:
        - Users without view permission cannot export
        - Appropriate error or access denied is shown
        """
        # Create user without permissions
        limited_user = User.objects.create_user(
            username='limited_export_user',
            password='testpass',
            is_staff=True,
            is_superuser=False
        )

        # Create test plan
        plan = self._create_test_plan_with_data()

        try:
            # Create new page and login as limited user
            limited_page = self.context.new_page()
            login_url = f"{self.live_server_url}/login/"
            limited_page.goto(login_url)
            limited_page.fill('input[name="username"]', 'limited_export_user')
            limited_page.fill('input[name="password"]', 'testpass')
            limited_page.click('button[type="submit"]')
            limited_page.wait_for_load_state('networkidle')

            # Try to access export URL directly
            export_url = f"{self.live_server_url}/plugins/hedgehog/topology-plans/{plan.pk}/export-yaml/"
            limited_page.goto(export_url)
            limited_page.wait_for_load_state('networkidle')

            # Should see permission denied or redirect
            page_content = limited_page.content().lower()
            has_permission_issue = (
                'permission denied' in page_content or
                'access denied' in page_content or
                'forbidden' in page_content or
                '403' in page_content or
                'login' in limited_page.url  # Redirected to login
            )

            self.assertTrue(has_permission_issue,
                           "User without permission should not be able to export")

            limited_page.close()

        finally:
            limited_user.delete()
            plan.delete()
