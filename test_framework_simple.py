#!/usr/bin/env python3
"""
Simple standalone test to verify Playwright framework works.

This tests that:
1. Playwright is installed correctly
2. Chromium browser works
3. NetBox is accessible at localhost:8000
4. Login functionality works

Run with: python3 test_framework_simple.py
"""

from playwright.sync_api import sync_playwright
import sys

NETBOX_URL = 'http://localhost:8000'
NETBOX_USERNAME = 'admin'
NETBOX_PASSWORD = 'admin'


def test_netbox_login():
    """Test that we can log in to NetBox"""
    print("🧪 Testing Playwright + NetBox Login")
    print("=" * 50)

    with sync_playwright() as p:
        print("✅ Playwright initialized")

        # Launch browser
        browser = p.chromium.launch(headless=True)
        print("✅ Chromium browser launched (headless)")

        # Create context and page
        context = browser.new_context(viewport={'width': 1920, 'height': 1080})
        page = context.new_page()
        print("✅ Browser page created")

        # Navigate to NetBox
        try:
            print(f"\n📡 Connecting to {NETBOX_URL}...")
            page.goto(f'{NETBOX_URL}/login/', timeout=10000)
            print("✅ NetBox login page loaded")
        except Exception as e:
            print(f"❌ ERROR: Could not connect to NetBox at {NETBOX_URL}")
            print(f"   Make sure NetBox Docker container is running!")
            print(f"   Error: {e}")
            browser.close()
            return False

        # Verify login form exists
        try:
            username_field = page.locator('input[name="username"]')
            password_field = page.locator('input[name="password"]')
            submit_button = page.locator('button[type="submit"]')

            if not username_field.is_visible():
                raise Exception("Username field not visible")
            if not password_field.is_visible():
                raise Exception("Password field not visible")
            if not submit_button.is_visible():
                raise Exception("Submit button not visible")

            print("✅ Login form elements found")
        except Exception as e:
            print(f"❌ ERROR: Login form not found: {e}")
            browser.close()
            return False

        # Fill in login form
        try:
            page.fill('input[name="username"]', NETBOX_USERNAME)
            page.fill('input[name="password"]', NETBOX_PASSWORD)
            print(f"✅ Credentials entered ({NETBOX_USERNAME})")
        except Exception as e:
            print(f"❌ ERROR: Could not fill login form: {e}")
            browser.close()
            return False

        # Submit form
        try:
            page.click('button[type="submit"]')
            page.wait_for_url(f'{NETBOX_URL}/', timeout=5000)
            print("✅ Login submitted, redirected to home page")
        except Exception as e:
            print(f"❌ ERROR: Login failed or redirect didn't happen: {e}")
            browser.close()
            return False

        # Verify we're logged in
        try:
            # Look for username in the page (indicates logged in)
            if NETBOX_USERNAME in page.content():
                print(f"✅ Successfully logged in as {NETBOX_USERNAME}")
            else:
                print(f"⚠️  WARNING: Logged in but username not found in page")
        except Exception as e:
            print(f"❌ ERROR: Could not verify login: {e}")
            browser.close()
            return False

        browser.close()
        print("\n" + "=" * 50)
        print("🎉 SUCCESS! Playwright framework is working!")
        print("=" * 50)
        return True


if __name__ == '__main__':
    success = test_netbox_login()
    sys.exit(0 if success else 1)
