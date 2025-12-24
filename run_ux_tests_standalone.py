#!/usr/bin/env python3
"""
Standalone browser UX test runner (bypasses pytest to avoid Django import conflicts).

This runs the same tests as the pytest suite but without pytest's module loading,
which avoids the "ModuleNotFoundError: No module named 'netbox'" issue.

Run with: python3 run_ux_tests_standalone.py
"""

from playwright.sync_api import sync_playwright, expect
import sys
import traceback

NETBOX_URL = 'http://localhost:8000'
NETBOX_USERNAME = 'admin'
NETBOX_PASSWORD = 'admin'

# Test plans created by setup_ux_test_data
TEST_PLAN_1_ID = 4  # UX Test Plan 1 - Generate Devices (3 servers)
TEST_PLAN_2_ID = 5  # UX Test Plan 2 - Multi-Plan Isolation (2 servers)
TEST_PLAN_3_ID = 6  # UX Test Plan 3 - Empty (Warnings)


class TestResults:
    """Track test results"""
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.skipped = 0
        self.errors = []

    def add_pass(self, test_name):
        self.passed += 1
        print(f"  ✅ PASS: {test_name}")

    def add_fail(self, test_name, error):
        self.failed += 1
        self.errors.append((test_name, error))
        print(f"  ❌ FAIL: {test_name}")
        print(f"      Error: {error}")

    def add_skip(self, test_name, reason):
        self.skipped += 1
        print(f"  ⏭️  SKIP: {test_name} - {reason}")

    def print_summary(self):
        total = self.passed + self.failed + self.skipped
        print(f"\n{'='*60}")
        print(f"Test Results: {self.passed}/{total} passed")
        print(f"  ✅ Passed: {self.passed}")
        print(f"  ❌ Failed: {self.failed}")
        print(f"  ⏭️  Skipped: {self.skipped}")
        print(f"{'='*60}")

        if self.errors:
            print("\nFailed Tests:")
            for test_name, error in self.errors:
                print(f"  - {test_name}: {error}")

        return self.failed == 0


def login(page):
    """Helper function to log in to NetBox"""
    page.goto(f'{NETBOX_URL}/login/')
    page.fill('input[name="username"]', NETBOX_USERNAME)
    page.fill('input[name="password"]', NETBOX_PASSWORD)
    page.click('button[type="submit"]')
    page.wait_for_url(f'{NETBOX_URL}/', timeout=5000)


def test_login_page_loads(page, results):
    """Test that login page loads"""
    try:
        page.goto(f'{NETBOX_URL}/login/')
        expect(page.locator('input[name="username"]')).to_be_visible()
        expect(page.locator('input[name="password"]')).to_be_visible()
        expect(page.locator('button[type="submit"]')).to_be_visible()
        results.add_pass("test_login_page_loads")
    except Exception as e:
        results.add_fail("test_login_page_loads", str(e))


def test_successful_login(page, results):
    """Test successful login"""
    try:
        page.goto(f'{NETBOX_URL}/login/')
        page.fill('input[name="username"]', NETBOX_USERNAME)
        page.fill('input[name="password"]', NETBOX_PASSWORD)
        page.click('button[type="submit"]')
        page.wait_for_url(f'{NETBOX_URL}/', timeout=5000)
        # Check for logged in state by looking for the toast message or user menu
        expect(page.locator('text=/Logged in as/i, .toast-body')).to_be_visible(timeout=5000)
        results.add_pass("test_successful_login")
    except Exception as e:
        results.add_fail("test_successful_login", str(e))


def test_navigate_to_topology_plans(page, results):
    """Test navigating to topology plans"""
    try:
        login(page)
        page.click('text=Hedgehog')
        page.click('a:has-text("Topology Plans")')
        expect(page).to_have_url(f'{NETBOX_URL}/plugins/netbox_hedgehog/topology-plans/')
        expect(page.locator('h1, h2, .page-title')).to_contain_text('Topology Plans')
        results.add_pass("test_navigate_to_topology_plans")
    except Exception as e:
        results.add_fail("test_navigate_to_topology_plans", str(e))


def test_generate_button_visible(page, results):
    """Test Generate Devices button is visible"""
    try:
        login(page)
        page.goto(f'{NETBOX_URL}/plugins/netbox_hedgehog/topology-plans/{TEST_PLAN_1_ID}/')

        generate_button = page.locator('a:has-text("Generate Devices"), button:has-text("Generate Devices")')
        expect(generate_button.first).to_be_visible()
        results.add_pass("test_generate_button_visible")
    except Exception as e:
        results.add_fail("test_generate_button_visible", str(e))


def test_generate_preview_page_loads(page, results):
    """Test that clicking Generate shows preview page"""
    try:
        login(page)
        page.goto(f'{NETBOX_URL}/plugins/netbox_hedgehog/topology-plans/{TEST_PLAN_1_ID}/')

        page.click('a:has-text("Generate Devices"), button:has-text("Generate Devices")')
        expect(page).to_have_url(f'{NETBOX_URL}/plugins/netbox_hedgehog/topology-plans/{TEST_PLAN_1_ID}/generate/')

        # Verify preview shows counts
        expect(page.locator('text=/devices/i')).to_be_visible()
        expect(page.locator('text=/server/i')).to_be_visible()
        expect(page.locator('text=/switch/i')).to_be_visible()
        results.add_pass("test_generate_preview_page_loads")
    except Exception as e:
        results.add_fail("test_generate_preview_page_loads", str(e))


def test_empty_plan_shows_warning(page, results):
    """Test that empty plan shows warning"""
    try:
        login(page)
        page.goto(f'{NETBOX_URL}/plugins/netbox_hedgehog/topology-plans/{TEST_PLAN_3_ID}/')

        page.click('a:has-text("Generate Devices"), button:has-text("Generate Devices")')
        expect(page).to_have_url(f'{NETBOX_URL}/plugins/netbox_hedgehog/topology-plans/{TEST_PLAN_3_ID}/generate/')

        # Verify warning appears
        expect(page.locator('text=/warning/i, text=/no.*server/i, text=/no.*switch/i, .alert-warning')).to_be_visible()
        results.add_pass("test_empty_plan_shows_warning")
    except Exception as e:
        results.add_fail("test_empty_plan_shows_warning", str(e))


def test_generate_workflow_complete(page, results):
    """Test complete generate workflow from preview to creation"""
    try:
        login(page)
        page.goto(f'{NETBOX_URL}/plugins/netbox_hedgehog/topology-plans/{TEST_PLAN_1_ID}/')

        # Click Generate
        page.click('a:has-text("Generate Devices"), button:has-text("Generate Devices")')

        # Click Confirm/Generate button
        confirm_button = page.locator('button:has-text("Generate"), input[type="submit"][value*="Generate"], button:has-text("Regenerate")')
        confirm_button.first.click()

        # Wait for redirect back to plan detail
        expect(page).to_have_url(f'{NETBOX_URL}/plugins/netbox_hedgehog/topology-plans/{TEST_PLAN_1_ID}/', timeout=30000)

        # Verify success message
        expect(page.locator('text=/generation complete/i, text=/success/i, .alert-success')).to_be_visible(timeout=5000)

        results.add_pass("test_generate_workflow_complete")
    except Exception as e:
        results.add_fail("test_generate_workflow_complete", str(e))


def test_multi_plan_isolation(page, results):
    """Test that regenerating Plan A doesn't affect Plan B"""
    try:
        login(page)

        # Generate Plan B first
        page.goto(f'{NETBOX_URL}/plugins/netbox_hedgehog/topology-plans/{TEST_PLAN_2_ID}/')
        page.click('a:has-text("Generate Devices"), button:has-text("Generate Devices")')

        # Get Plan B preview content
        plan_b_preview_before = page.content()

        # Click Generate for Plan B
        confirm_button = page.locator('button:has-text("Generate"), button:has-text("Regenerate")')
        confirm_button.first.click()
        expect(page).to_have_url(f'{NETBOX_URL}/plugins/netbox_hedgehog/topology-plans/{TEST_PLAN_2_ID}/', timeout=30000)

        # Regenerate Plan A
        page.goto(f'{NETBOX_URL}/plugins/netbox_hedgehog/topology-plans/{TEST_PLAN_1_ID}/')
        page.click('a:has-text("Generate Devices"), button:has-text("Generate Devices")')

        regenerate_button = page.locator('button:has-text("Generate"), button:has-text("Regenerate")')
        regenerate_button.first.click()
        expect(page).to_have_url(f'{NETBOX_URL}/plugins/netbox_hedgehog/topology-plans/{TEST_PLAN_1_ID}/', timeout=30000)

        # Check Plan B still has its data
        page.goto(f'{NETBOX_URL}/plugins/netbox_hedgehog/topology-plans/{TEST_PLAN_2_ID}/')
        page.click('a:has-text("Generate Devices"), button:has-text("Generate Devices")')

        plan_b_preview_after = page.content()

        # Verify Plan B server class is still there
        assert 'ux-test-servers-plan2' in plan_b_preview_after, "Plan B data missing after Plan A regeneration!"

        results.add_pass("test_multi_plan_isolation")
    except Exception as e:
        results.add_fail("test_multi_plan_isolation", str(e))


def main():
    print("🧪 Browser UX Test Suite - Standalone Runner")
    print("="*60)
    print(f"NetBox URL: {NETBOX_URL}")
    print(f"Username: {NETBOX_USERNAME}")
    print()

    results = TestResults()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={'width': 1920, 'height': 1080})
        page = context.new_page()

        print("Running Login Tests:")
        test_login_page_loads(page, results)
        test_successful_login(page, results)

        print("\nRunning Navigation Tests:")
        test_navigate_to_topology_plans(page, results)

        print("\nRunning Generate Devices Tests:")
        test_generate_button_visible(page, results)
        test_generate_preview_page_loads(page, results)
        test_empty_plan_shows_warning(page, results)
        test_generate_workflow_complete(page, results)

        print("\nRunning Multi-Plan Isolation Tests:")
        test_multi_plan_isolation(page, results)

        browser.close()

    success = results.print_summary()
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
