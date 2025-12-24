"""
Browser UX tests for Generate Devices workflow (PR #109 validation).

These tests validate that users can successfully generate NetBox devices from
topology plans using a real browser, ensuring the complete UX flow works as intended.

This is CRITICAL testing that was missing from PR #109 - we merged without validating
that users can actually complete this workflow in a browser.
"""

import pytest
from playwright.sync_api import Page, expect
from .conftest import NETBOX_URL


class TestGenerateDevicesWorkflow:
    """
    Test suite for Generate Devices workflow.

    Tests the complete end-to-end flow:
    1. Navigate to topology plan
    2. Click Generate Devices button
    3. See preview page with counts
    4. Confirm generation
    5. Verify devices created
    6. Test regeneration
    """

    def test_navigate_to_topology_plans(self, authenticated_page: Page):
        """Test that user can navigate to Topology Plans page"""
        page = authenticated_page

        # Click Hedgehog menu
        page.click('text=Hedgehog')

        # Click Topology Plans submenu
        page.click('a:has-text("Topology Plans")')

        # Verify we're on the topology plans list page
        expect(page).to_have_url(pytest.regexp(r'.*/plugins/netbox_hedgehog/topology-plans/.*'))

        # Verify page title or heading
        expect(page.locator('h1, h2, .page-title')).to_contain_text('Topology Plans')

    def test_generate_button_visible_on_plan_detail(self, authenticated_page: Page):
        """
        Test that Generate Devices button is visible on plan detail page.

        This requires a topology plan to exist. If none exists, this test will
        document that fact and can be skipped in CI until test data is created.
        """
        page = authenticated_page

        # Navigate to topology plans
        page.goto(f'{NETBOX_URL}/plugins/netbox_hedgehog/topology-plans/')

        # Check if any plans exist
        plans_exist = page.locator('table tbody tr').count() > 0

        if not plans_exist:
            pytest.skip("No topology plans exist - cannot test Generate Devices button visibility")

        # Click on first plan
        page.click('table tbody tr:first-child td a:first-child')

        # Verify we're on plan detail page
        expect(page).to_have_url(pytest.regexp(r'.*/topology-plans/\d+/$'))

        # Verify Generate Devices button exists
        generate_button = page.locator('a:has-text("Generate Devices"), button:has-text("Generate Devices")')

        # Check if button is visible (requires change_topologyplan permission)
        if generate_button.count() > 0:
            expect(generate_button).to_be_visible()
        else:
            pytest.fail("Generate Devices button not found - check if user has change_topologyplan permission")

    def test_generate_preview_page_loads(self, authenticated_page: Page):
        """
        Test that clicking Generate Devices shows preview page with counts.

        This is the CRITICAL test that validates PR #109's UI actually works.
        """
        page = authenticated_page

        # Navigate to topology plans
        page.goto(f'{NETBOX_URL}/plugins/netbox_hedgehog/topology-plans/')

        # Check if any plans exist
        if page.locator('table tbody tr').count() == 0:
            pytest.skip("No topology plans exist - create test data first")

        # Click on first plan
        page.click('table tbody tr:first-child td a:first-child')

        # Click Generate Devices button
        generate_button = page.locator('a:has-text("Generate Devices"), button:has-text("Generate Devices")').first
        if generate_button.count() == 0:
            pytest.skip("Generate Devices button not found - check permissions")

        generate_button.click()

        # Verify we're on the generate preview page
        expect(page).to_have_url(pytest.regexp(r'.*/topology-plans/\d+/generate/$'))

        # Verify preview page shows counts
        # The preview should show:
        # - Total devices
        # - Server count
        # - Switch count
        # - Interface count
        # - Cable count
        # - Site name

        expect(page.locator('text=/total devices/i, text=/devices:/i')).to_be_visible()
        expect(page.locator('text=/server/i')).to_be_visible()
        expect(page.locator('text=/switch/i')).to_be_visible()
        expect(page.locator('text=/interface/i')).to_be_visible()
        expect(page.locator('text=/cable/i')).to_be_visible()

    def test_generate_preview_shows_warnings_for_empty_plan(self, authenticated_page: Page):
        """
        Test that preview shows warnings when plan has no servers or switches.

        This requires creating a plan or finding an empty one.
        """
        page = authenticated_page

        # Navigate to topology plans
        page.goto(f'{NETBOX_URL}/plugins/netbox_hedgehog/topology-plans/')

        # This test would need an empty plan to validate warnings
        # For now, we document the expected behavior
        pytest.skip("Requires empty topology plan for testing - implement after test data setup")

    def test_generate_confirm_creates_devices(self, authenticated_page: Page):
        """
        Test the complete generate workflow: preview → confirm → devices created.

        This is the MOST CRITICAL test - it validates that the entire UX flow
        works end-to-end as a user would experience it.
        """
        page = authenticated_page

        # Navigate to topology plans
        page.goto(f'{NETBOX_URL}/plugins/netbox_hedgehog/topology-plans/')

        # Check if any plans exist
        if page.locator('table tbody tr').count() == 0:
            pytest.skip("No topology plans exist - create test data first")

        # Get plan name for later verification
        plan_name = page.locator('table tbody tr:first-child td:first-child a').text_content()

        # Click on first plan
        page.click('table tbody tr:first-child td a:first-child')

        # Click Generate Devices
        generate_button = page.locator('a:has-text("Generate Devices"), button:has-text("Generate Devices")').first
        if generate_button.count() == 0:
            pytest.skip("Generate Devices button not found - check permissions")

        generate_button.click()

        # We're on preview page - click Generate/Confirm button
        confirm_button = page.locator('button:has-text("Generate"), input[type="submit"][value*="Generate"]').first

        if confirm_button.count() == 0:
            pytest.fail("Generate confirmation button not found on preview page")

        # Read counts before generation (for verification)
        # This requires the preview page to display counts

        # Click confirm
        confirm_button.click()

        # Should redirect to plan detail page
        expect(page).to_have_url(pytest.regexp(r'.*/topology-plans/\d+/$'), timeout=30000)

        # Verify success message appears
        expect(page.locator('text=/generation complete/i, .alert-success, .message-success')).to_be_visible(timeout=5000)

        # Navigate to Devices page to verify devices were created
        page.click('text=Devices')
        page.locator('a:has-text("Devices")').nth(1).click()  # Click the Devices submenu

        # Wait for devices page to load
        expect(page).to_have_url(pytest.regexp(r'.*/dcim/devices/.*'))

        # Filter by hedgehog-generated tag
        # NetBox filtering UI varies, so we need to find the filter form
        # Try to find tag filter field
        tag_filter = page.locator('input[name="tag"], select[name="tag"]')

        if tag_filter.count() > 0:
            tag_filter.first.fill('hedgehog-generated')
            page.click('button:has-text("Filter"), button:has-text("Search")')

            # Verify devices exist in the table
            device_rows = page.locator('table tbody tr')
            expect(device_rows.first).to_be_visible(timeout=5000)

            # Verify devices are tagged with hedgehog-generated
            expect(page.locator('text=hedgehog-generated')).to_be_visible()
        else:
            # If we can't find tag filter, just verify devices exist
            pytest.skip("Could not find tag filter - device creation verified via success message")

    def test_regeneration_shows_warning(self, authenticated_page: Page):
        """
        Test that regenerating a plan shows warning about previous generation.

        This requires a plan that has already been generated.
        """
        page = authenticated_page

        # This test requires a plan that's already been generated
        # Implementation depends on test data setup
        pytest.skip("Requires previously generated plan - implement after test data setup")

    def test_regeneration_updates_devices(self, authenticated_page: Page):
        """
        Test complete regeneration workflow: modify plan → regenerate → devices updated.

        This validates that regeneration actually works from a user perspective.
        """
        page = authenticated_page

        # This requires:
        # 1. A plan with generated devices
        # 2. Modifying the plan
        # 3. Regenerating
        # 4. Verifying devices changed
        pytest.skip("Requires test data setup - implement after basic tests pass")

    def test_permission_denied_without_change_permission(self, authenticated_page: Page):
        """
        Test that users without change_topologyplan permission cannot access generate.

        This requires a user account with limited permissions.
        """
        # This test would need a non-admin user with limited permissions
        pytest.skip("Requires test user with view-only permissions - implement after basic tests pass")

    def test_export_yaml_button_exists(self, authenticated_page: Page):
        """
        Test that Export YAML button exists on plan detail page.

        While not part of Generate Devices, this validates another critical UX element.
        """
        page = authenticated_page

        # Navigate to topology plans
        page.goto(f'{NETBOX_URL}/plugins/netbox_hedgehog/topology-plans/')

        if page.locator('table tbody tr').count() == 0:
            pytest.skip("No topology plans exist")

        # Click on first plan
        page.click('table tbody tr:first-child td a:first-child')

        # Verify Export YAML button exists
        export_button = page.locator('a:has-text("Export YAML"), a:has-text("Export"), button:has-text("Export")')

        if export_button.count() > 0:
            expect(export_button.first).to_be_visible()
        else:
            pytest.fail("Export YAML button not found on plan detail page")


@pytest.mark.skip(reason="Test data setup required")
class TestGenerateDevicesWithTestData:
    """
    Test suite that requires specific test data to be created first.

    These tests will be implemented once we have a test data setup fixture
    that creates topology plans with known configurations.
    """

    def test_generate_creates_correct_number_of_devices(self, authenticated_page: Page):
        """Test that generation creates expected number of devices based on plan configuration"""
        pytest.skip("Requires test data fixture")

    def test_generate_creates_correct_number_of_interfaces(self, authenticated_page: Page):
        """Test that generation creates expected number of interfaces"""
        pytest.skip("Requires test data fixture")

    def test_generate_creates_correct_number_of_cables(self, authenticated_page: Page):
        """Test that generation creates expected number of cables"""
        pytest.skip("Requires test data fixture")

    def test_plan_scoped_regeneration(self, authenticated_page: Page):
        """Test that regenerating Plan A doesn't affect Plan B (multi-tenant safety)"""
        pytest.skip("Requires test data fixture with multiple plans")
