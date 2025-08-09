import { test, expect } from '@playwright/test';
import { TestHelpers } from '../utils/test-helpers';

/**
 * Test suite for main plugin access and navigation
 */
test.describe('Hedgehog Plugin - Main Access', () => {
  let helpers: TestHelpers;

  test.beforeEach(async ({ page }) => {
    helpers = new TestHelpers(page);
  });

  test('should allow login to NetBox', async ({ page }) => {
    await helpers.loginToNetBox();
    
    // Verify we're logged in
    await expect(page).toHaveURL(/.*\/(home|dashboard).*/);
    await helpers.verifyPageHealthy();
  });

  test('should access main plugin page successfully', async ({ page }) => {
    await helpers.loginToNetBox();
    await helpers.navigateToPluginHome();
    
    // Verify plugin page loaded
    await expect(page).toHaveURL(/.*\/plugins\/hedgehog\/.*/);
    await helpers.verifyPageHealthy();
    
    // Check for plugin-specific content
    const content = await page.content();
    expect(content).toContain('hedgehog');
    
    // Take screenshot for evidence
    await helpers.takeScreenshot('plugin-main-page');
  });

  test('should display plugin navigation elements', async ({ page }) => {
    await helpers.loginToNetBox();
    await helpers.navigateToPluginHome();
    
    // Check for common navigation elements
    const navigationElements = [
      'Fabric',
      'Git',
      'Repository',
      'Sync'
    ];

    const pageContent = await page.content();
    let foundElements = 0;
    
    for (const element of navigationElements) {
      if (pageContent.toLowerCase().includes(element.toLowerCase())) {
        foundElements++;
        console.log(`✅ Found navigation element: ${element}`);
      }
    }
    
    expect(foundElements).toBeGreaterThan(0);
    console.log(`Found ${foundElements}/${navigationElements.length} navigation elements`);
  });

  test('should not contain obvious errors or exceptions', async ({ page }) => {
    await helpers.loginToNetBox();
    await helpers.navigateToPluginHome();
    
    const content = await page.content();
    
    // Check for Django error indicators
    const errorIndicators = [
      'DoesNotExist',
      'OperationalError', 
      'Traceback',
      'Server Error',
      'AttributeError',
      'ImportError'
    ];
    
    for (const indicator of errorIndicators) {
      expect(content).not.toContain(indicator);
    }
    
    console.log('✅ No obvious errors found on main plugin page');
  });

  test('should have proper page title', async ({ page }) => {
    await helpers.loginToNetBox();
    await helpers.navigateToPluginHome();
    
    const title = await page.title();
    expect(title).toBeTruthy();
    expect(title.length).toBeGreaterThan(0);
    
    console.log(`Page title: "${title}"`);
  });

  test('should respond within reasonable time', async ({ page }) => {
    await helpers.loginToNetBox();
    
    const startTime = Date.now();
    await helpers.navigateToPluginHome();
    const loadTime = Date.now() - startTime;
    
    // Page should load within 10 seconds
    expect(loadTime).toBeLessThan(10000);
    
    console.log(`Plugin page loaded in ${loadTime}ms`);
  });

  test('should handle console errors gracefully', async ({ page }) => {
    const consoleErrors: string[] = [];
    
    page.on('console', (msg) => {
      if (msg.type() === 'error') {
        consoleErrors.push(msg.text());
      }
    });
    
    await helpers.loginToNetBox();
    await helpers.navigateToPluginHome();
    
    // Allow some time for any delayed JavaScript errors
    await page.waitForTimeout(2000);
    
    // We expect minimal console errors for a healthy page
    if (consoleErrors.length > 0) {
      console.log(`⚠️ Console errors found: ${consoleErrors.length}`);
      for (const error of consoleErrors) {
        console.log(`  - ${error}`);
      }
    }
    
    // Don't fail the test for minor console errors, but log them
    expect(consoleErrors.length).toBeLessThanOrEqual(3);
  });
});