#!/usr/bin/env python3
"""
Playwright-based GUI validation test for Issue #40
Ensures sync status displays correctly from user perspective
"""

import asyncio
from playwright.async_api import async_playwright
import sys


async def test_sync_status_gui():
    """Test sync status display in the GUI using Playwright"""
    
    print("=" * 80)
    print("GUI SYNC STATUS VALIDATION - Issue #40")
    print("=" * 80)
    
    async with async_playwright() as p:
        # Launch browser in headless mode
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()
        
        print("\n1. Navigating to NetBox...")
        await page.goto("http://localhost:8000")
        
        # Check if we need to login
        if "login" in page.url.lower():
            print("2. Logging in...")
            await page.fill('input[name="username"]', 'admin')
            await page.fill('input[name="password"]', 'admin')
            await page.click('button[type="submit"]')
            await page.wait_for_load_state('networkidle')
        
        print("3. Navigating to Hedgehog plugin...")
        await page.goto("http://localhost:8000/plugins/hedgehog/")
        await page.wait_for_load_state('networkidle')
        
        print("4. Going to Fabrics page...")
        await page.goto("http://localhost:8000/plugins/hedgehog/fabrics/")
        await page.wait_for_load_state('networkidle')
        
        # Get all fabric links
        fabric_links = await page.locator('a[href*="/fabrics/"]').all()
        print(f"   Found {len(fabric_links)} fabric(s)")
        
        if not fabric_links:
            print("   ⚠️  No fabrics found. Creating test fabric...")
            # Create a test fabric via GUI
            await page.goto("http://localhost:8000/plugins/hedgehog/fabrics/add/")
            await page.fill('input[name="name"]', 'Test Status Fabric')
            await page.fill('textarea[name="description"]', 'Test fabric for sync status validation')
            await page.click('button[type="submit"][name="_create"]')
            await page.wait_for_load_state('networkidle')
        
        # Go to first fabric detail page
        await page.goto("http://localhost:8000/plugins/hedgehog/fabrics/")
        first_fabric = await page.locator('a[href*="/fabrics/"]').first
        fabric_url = await first_fabric.get_attribute('href')
        
        print(f"5. Checking fabric detail page: {fabric_url}")
        await page.goto(f"http://localhost:8000{fabric_url}")
        await page.wait_for_load_state('networkidle')
        
        # Check for sync status display
        print("\n6. Validating sync status display...")
        print("-" * 40)
        
        # Look for sync status in various possible locations
        status_selectors = [
            # Direct badge display
            '.badge:has-text("Not Configured")',
            '.badge:has-text("Never Synced")',
            '.badge:has-text("In Sync")',
            '.badge:has-text("Out of Sync")',
            '.badge:has-text("Sync Disabled")',
            '.badge:has-text("Sync Error")',
            # Status indicator component
            '.status-indicator',
            '.status-indicator-wrapper',
            # Table cells with status
            'td:has-text("Not Configured")',
            'td:has-text("Never Synced")',
            # Specific sync status row
            'th:has-text("Sync Status") + td',
            'th:has-text("Fabric Sync Status") + td',
        ]
        
        found_status = None
        status_element = None
        
        for selector in status_selectors:
            try:
                element = page.locator(selector).first
                if await element.is_visible():
                    found_status = await element.text_content()
                    status_element = element
                    print(f"   ✅ Found status element: {selector}")
                    print(f"      Status text: '{found_status}'")
                    break
            except:
                continue
        
        if not found_status:
            print("   ❌ Could not find sync status display!")
            # Take screenshot for debugging
            await page.screenshot(path="sync_status_debug.png")
            print("   📸 Screenshot saved to sync_status_debug.png")
        
        # Check Kubernetes configuration
        print("\n7. Checking Kubernetes configuration...")
        k8s_config = await page.locator('th:has-text("Kubernetes Server") + td').text_content() \
                      or await page.locator('th:has-text("Fabric Kubernetes Server") + td').text_content() \
                      or "Not found"
        
        print(f"   Kubernetes Server: {k8s_config.strip()}")
        
        # Validate status logic
        print("\n8. Validating status logic...")
        print("-" * 40)
        
        has_k8s = "Not configured" not in k8s_config and k8s_config.strip() != "Not found"
        
        if not has_k8s:
            if found_status and "Not Configured" in found_status:
                print("   ✅ PASS: No K8s server → Status shows 'Not Configured'")
            else:
                print(f"   ❌ FAIL: No K8s server but status shows '{found_status}'")
        else:
            if found_status and "Not Configured" not in found_status:
                print(f"   ✅ PASS: K8s configured → Status shows '{found_status}'")
            else:
                print(f"   ❌ FAIL: K8s configured but status shows '{found_status}'")
        
        # Check for contradictions
        print("\n9. Checking for contradictions...")
        
        # Get all visible text that might indicate sync status
        page_text = await page.content()
        
        contradictions = []
        
        if "Not configured" in k8s_config:
            if "In Sync" in page_text or "Out of Sync" in page_text:
                contradictions.append("Shows sync status without K8s configuration")
        
        if contradictions:
            print(f"   ❌ Found contradictions:")
            for c in contradictions:
                print(f"      - {c}")
        else:
            print("   ✅ No contradictions found")
        
        # Final summary
        print("\n" + "=" * 80)
        print("GUI VALIDATION SUMMARY")
        print("=" * 80)
        
        if found_status:
            print(f"✅ Sync status is displayed: '{found_status}'")
            if not has_k8s and "Not Configured" in found_status:
                print("✅ Status correctly shows 'Not Configured' when no K8s server")
            elif has_k8s and "Not Configured" not in found_status:
                print("✅ Status correctly shows appropriate state with K8s configured")
            else:
                print("⚠️  Status may not be displaying correctly")
        else:
            print("❌ Sync status display not found in GUI")
        
        await browser.close()


async def test_sync_button_functionality():
    """Test that sync button behaves correctly based on configuration"""
    
    print("\n" + "=" * 80)
    print("SYNC BUTTON FUNCTIONALITY TEST")
    print("=" * 80)
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()
        
        # Login
        await page.goto("http://localhost:8000")
        if "login" in page.url.lower():
            await page.fill('input[name="username"]', 'admin')
            await page.fill('input[name="password"]', 'admin')
            await page.click('button[type="submit"]')
        
        # Go to fabrics
        await page.goto("http://localhost:8000/plugins/hedgehog/fabrics/")
        
        # Check first fabric
        first_fabric = await page.locator('a[href*="/fabrics/"]').first
        fabric_url = await first_fabric.get_attribute('href')
        await page.goto(f"http://localhost:8000{fabric_url}")
        
        print("\nChecking sync buttons...")
        
        # Look for sync-related buttons
        sync_button = page.locator('a:has-text("Sync Now")').first
        test_button = page.locator('a:has-text("Test Connection")').first
        
        if await sync_button.is_visible():
            is_disabled = await sync_button.get_attribute('disabled')
            classes = await sync_button.get_attribute('class')
            
            print(f"   Sync Now button: Visible")
            print(f"   Disabled: {is_disabled}")
            print(f"   Classes: {classes}")
            
            if is_disabled or 'disabled' in (classes or ''):
                print("   ⚠️  Sync button is disabled (likely no K8s configured)")
            else:
                print("   ✅ Sync button is enabled")
        else:
            print("   ❌ Sync Now button not found")
        
        if await test_button.is_visible():
            print("   ✅ Test Connection button found")
        else:
            print("   ❌ Test Connection button not found")
        
        await browser.close()


async def main():
    """Run all GUI validation tests"""
    try:
        await test_sync_status_gui()
        await test_sync_button_functionality()
        print("\n✅ GUI validation complete")
        return 0
    except Exception as e:
        print(f"\n❌ GUI validation failed: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)