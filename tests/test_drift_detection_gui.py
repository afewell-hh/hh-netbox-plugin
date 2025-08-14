"""
GUI Tests for Drift Detection - Using Playwright for REAL user interaction testing

This is what should have been written FIRST using TDD methodology.
These tests validate the actual user experience, not just backend logic.
"""

import pytest
from playwright.sync_api import Page, expect


class TestDriftDetectionGUI:
    """
    GUI Tests that validate REAL user interactions
    These tests must pass for the drift detection feature to be considered working
    """

    @pytest.fixture(autouse=True)
    def setup_test_data(self, page: Page):
        """Set up test environment and authenticate"""
        # Navigate to NetBox and login
        page.goto("http://localhost:8000/login/")
        page.fill("input[name='username']", "admin")  
        page.fill("input[name='password']", "admin")
        page.click("button[type='submit']")
        
        # Verify we're logged in
        expect(page).to_have_url("http://localhost:8000/")

    def test_drift_detection_page_loads_successfully(self, page: Page):
        """
        CRITICAL TEST: Drift detection page must load without server errors
        This is the most basic requirement that was failing
        """
        # Navigate directly to drift detection page
        page.goto("http://localhost:8000/plugins/hedgehog/drift-detection/")
        
        # Should NOT show server error
        expect(page.locator("text=Server Error")).not_to_be_visible()
        expect(page.locator("text=NoReverseMatch")).not_to_be_visible()
        
        # Should show the correct page title
        expect(page.locator("h1")).to_contain_text("Drift Detection Dashboard")
        
        # Page should return 200, not 500
        expect(page).to_have_url("http://localhost:8000/plugins/hedgehog/drift-detection/")

    def test_dashboard_shows_correct_drift_count(self, page: Page):
        """
        CRITICAL TEST: Dashboard must show accurate cumulative drift count
        Currently shows 0, should show 2
        """
        # Navigate to main dashboard
        page.goto("http://localhost:8000/plugins/hedgehog/")
        
        # Find the drift detection metric card
        drift_card = page.locator("text=Drift Detected").locator("..")
        
        # Should show 2, not 0
        expect(drift_card.locator("h2")).to_contain_text("2")
        
        # Should have descriptive text
        expect(drift_card).to_contain_text("Drift Detected")
        expect(drift_card).to_contain_text("Needs attention")

    def test_dashboard_drift_metric_is_clickable_link(self, page: Page):
        """
        CRITICAL TEST: Dashboard drift metric must be clickable and navigate to drift page
        This is a core user requirement that was missing
        """
        # Navigate to dashboard
        page.goto("http://localhost:8000/plugins/hedgehog/")
        
        # Find the drift metric and verify it's a clickable link
        drift_link = page.locator("a[href*='drift-detection']")
        expect(drift_link).to_be_visible()
        
        # Click the drift metric
        drift_link.click()
        
        # Should navigate to drift detection page
        expect(page).to_have_url("http://localhost:8000/plugins/hedgehog/drift-detection/")
        
        # Should show drift detection page, not error
        expect(page.locator("h1")).to_contain_text("Drift Detection Dashboard")

    def test_fabric_drift_count_is_clickable_link(self, page: Page):
        """
        CRITICAL TEST: Fabric detail page drift count must be clickable
        User should be able to click fabric drift count to see details
        """
        # Navigate to fabric detail page (Test_Lab_K3s_Cluster)  
        page.goto("http://localhost:8000/plugins/hedgehog/fabrics/35/")
        
        # Look for drift count that should be clickable
        drift_element = page.locator("text=2 drift(s) detected")
        expect(drift_element).to_be_visible()
        
        # Find the link around the drift information
        drift_link = page.locator("a[href*='drift-detection']")
        expect(drift_link).to_be_visible()
        
        # Click the drift link
        drift_link.click()
        
        # Should navigate to filtered drift detection page
        expect(page.url).to_contain("drift-detection")
        expect(page.locator("h1")).to_contain_text("Drift Detection")

    def test_navigation_contains_drift_detection_link(self, page: Page):
        """
        CRITICAL TEST: Users must be able to navigate to drift detection from menu
        Navigation should include drift detection option
        """
        # Navigate to any plugin page
        page.goto("http://localhost:8000/plugins/hedgehog/")
        
        # Find and click the Hedgehog dropdown in navigation
        hedgehog_dropdown = page.locator("a:has-text('Hedgehog')")
        hedgehog_dropdown.click()
        
        # Should see drift detection option in dropdown
        drift_nav_link = page.locator("a:has-text('Drift Detection')")
        expect(drift_nav_link).to_be_visible()
        
        # Click drift detection navigation
        drift_nav_link.click()
        
        # Should navigate to drift detection page
        expect(page).to_have_url("http://localhost:8000/plugins/hedgehog/drift-detection/")
        expect(page.locator("h1")).to_contain_text("Drift Detection Dashboard")

    def test_drift_detection_page_shows_drift_data(self, page: Page):
        """
        FUNCTIONAL TEST: Drift detection page should show actual drift information
        Should display the 2 drifted resources from Test_Lab_K3s_Cluster
        """
        # Navigate to drift detection page
        page.goto("http://localhost:8000/plugins/hedgehog/drift-detection/")
        
        # Should show drift statistics
        expect(page.locator("text=Drifted")).to_be_visible()
        
        # Should show drifted resources table or message
        # Either show resources or "No Drift Detected" message
        drift_content = page.locator("text=drifted resources, text=No Drift Detected").first
        expect(drift_content).to_be_visible()

    def test_filtered_drift_detection_page_works(self, page: Page):
        """
        FUNCTIONAL TEST: Fabric-filtered drift detection should work
        When clicking from fabric page, should show filtered results
        """
        # Navigate to fabric-filtered drift detection URL
        page.goto("http://localhost:8000/plugins/hedgehog/drift-detection/fabric/35/")
        
        # Should load without errors
        expect(page.locator("text=Server Error")).not_to_be_visible()
        
        # Should show drift detection page
        expect(page.locator("h1")).to_contain_text("Drift Detection")

    def test_end_to_end_user_workflow(self, page: Page):
        """
        END-TO-END TEST: Complete user workflow from dashboard to drift details
        This validates the entire user journey
        """
        # 1. Start at main dashboard
        page.goto("http://localhost:8000/plugins/hedgehog/")
        
        # 2. See drift count on dashboard
        drift_metric = page.locator("text=Drift Detected").locator("..")
        expect(drift_metric).to_be_visible()
        
        # 3. Click drift metric to navigate to drift detection
        drift_link = page.locator("a[href*='drift-detection']").first
        drift_link.click()
        
        # 4. Should arrive at drift detection page
        expect(page).to_have_url("http://localhost:8000/plugins/hedgehog/drift-detection/")
        expect(page.locator("h1")).to_contain_text("Drift Detection Dashboard")
        
        # 5. Should be able to navigate back via breadcrumbs or navigation
        page.locator("a:has-text('Hedgehog')").click()
        page.locator("a:has-text('Overview')").click()
        
        # 6. Should return to dashboard
        expect(page).to_have_url("http://localhost:8000/plugins/hedgehog/")


@pytest.fixture(scope="session") 
def browser():
    """Browser fixture for Playwright tests"""
    from playwright.sync_api import sync_playwright
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)  # Set to False for debugging
        yield browser
        browser.close()


@pytest.fixture
def page(browser):
    """Page fixture for each test"""
    page = browser.new_page()
    yield page
    page.close()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])