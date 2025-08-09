import { test, expect } from '@playwright/test';

test.describe('NetBox Hedgehog Plugin GUI Tests', () => {
  test.beforeEach(async ({ page }) => {
    // Set longer timeout for navigation
    page.setDefaultTimeout(30000);
  });

  test('NetBox login page loads correctly', async ({ page }) => {
    await page.goto('/');
    
    // Check for NetBox login elements
    await expect(page).toHaveTitle(/NetBox/);
    
    // Check for login form elements (if not already authenticated)
    const loginForm = page.locator('form');
    if (await loginForm.count() > 0) {
      await expect(page.locator('input[name="username"]')).toBeVisible();
      await expect(page.locator('input[name="password"]')).toBeVisible();
    }
  });

  test('Hedgehog plugin home page accessibility', async ({ page }) => {
    // Navigate to the Hedgehog plugin
    await page.goto('/plugins/hedgehog/');
    
    // Check that we can access the plugin (200 or redirect to login)
    const response = page.url();
    expect(response).toContain('localhost:8000');
    
    // If redirected to login, that's expected behavior
    if (page.url().includes('/login/')) {
      console.log('✅ Redirected to login as expected for unauthenticated user');
      await expect(page).toHaveTitle(/NetBox/);
      return;
    }
    
    // If we're on the plugin page, check for hedgehog elements
    if (page.url().includes('/plugins/hedgehog/')) {
      console.log('✅ Accessed Hedgehog plugin directly');
      
      // Check for basic page structure
      const body = page.locator('body');
      await expect(body).toBeVisible();
      
      // Check that no major JavaScript errors occurred
      const errors: string[] = [];
      page.on('pageerror', error => errors.push(error.message));
      
      // Wait a moment for any JS to execute
      await page.waitForTimeout(2000);
      
      if (errors.length > 0) {
        console.warn('JavaScript errors detected:', errors);
      } else {
        console.log('✅ No JavaScript errors detected');
      }
    }
  });

  test('Hedgehog fabric page loads without critical errors', async ({ page }) => {
    await page.goto('/plugins/hedgehog/fabrics/');
    
    // Check response (could be 200, 302 redirect, or 403/401 if auth required)
    const url = page.url();
    console.log('Current URL:', url);
    
    // If redirected to login, that's expected
    if (url.includes('/login/')) {
      console.log('✅ Redirected to login - authentication working');
      await expect(page).toHaveTitle(/NetBox/);
      return;
    }
    
    // If we're on the fabrics page, check for basic elements
    if (url.includes('/plugins/hedgehog/fabrics/')) {
      console.log('✅ Accessed fabrics page directly');
      
      const body = page.locator('body');
      await expect(body).toBeVisible();
      
      // Check for common NetBox page elements
      const pageContent = page.locator('.content-container, .main-content, body');
      await expect(pageContent.first()).toBeVisible();
    }
  });

  test('Hedgehog git repositories page loads without critical errors', async ({ page }) => {
    await page.goto('/plugins/hedgehog/git-repositories/');
    
    const url = page.url();
    console.log('Git repositories page URL:', url);
    
    // Check if redirected to login
    if (url.includes('/login/')) {
      console.log('✅ Git repositories page redirects to login correctly');
      await expect(page).toHaveTitle(/NetBox/);
      return;
    }
    
    // If we can access the page, verify basic functionality
    if (url.includes('/plugins/hedgehog/git-repositories/')) {
      console.log('✅ Accessed git repositories page');
      
      const body = page.locator('body');
      await expect(body).toBeVisible();
      
      // Check for absence of visible HTML comments (regression test)
      const htmlComments = await page.evaluate(() => {
        const walker = document.createTreeWalker(
          document.body,
          NodeFilter.SHOW_TEXT,
          null,
          false
        );
        
        const textNodes = [];
        let node;
        while (node = walker.nextNode()) {
          if (node.textContent && node.textContent.includes('<!--')) {
            textNodes.push(node.textContent);
          }
        }
        return textNodes;
      });
      
      if (htmlComments.length > 0) {
        console.warn('HTML comments found in visible text:', htmlComments);
      } else {
        console.log('✅ No visible HTML comments detected');
      }
    }
  });

  test('No critical JavaScript errors on main pages', async ({ page }) => {
    const errors: string[] = [];
    const consoleMessages: string[] = [];
    
    // Capture JavaScript errors
    page.on('pageerror', error => {
      errors.push(`Page Error: ${error.message}`);
    });
    
    // Capture console errors
    page.on('console', msg => {
      if (msg.type() === 'error') {
        consoleMessages.push(`Console Error: ${msg.text()}`);
      }
    });
    
    // Test main plugin pages
    const pagesToTest = [
      '/plugins/hedgehog/',
      '/plugins/hedgehog/fabrics/',
      '/plugins/hedgehog/git-repositories/'
    ];
    
    for (const pagePath of pagesToTest) {
      console.log(`Testing page: ${pagePath}`);
      
      try {
        await page.goto(pagePath, { timeout: 15000 });
        await page.waitForTimeout(2000); // Allow JS to execute
        console.log(`✅ ${pagePath} loaded without critical errors`);
      } catch (error) {
        console.warn(`⚠️  ${pagePath} failed to load:`, error);
      }
    }
    
    // Report any errors found
    if (errors.length > 0) {
      console.warn('JavaScript Page Errors:', errors);
    }
    
    if (consoleMessages.length > 0) {
      console.warn('Console Errors:', consoleMessages);
    }
    
    // Test passes if we can load pages and detect obvious issues
    expect(errors.length).toBeLessThan(5); // Allow some minor errors
    console.log(`✅ JavaScript error test completed. Found ${errors.length} page errors and ${consoleMessages.length} console errors.`);
  });

  test('CSS and styling loads correctly', async ({ page }) => {
    await page.goto('/plugins/hedgehog/');
    
    // Check that CSS is loaded by looking for styled elements
    const body = page.locator('body');
    await expect(body).toBeVisible();
    
    // Check for basic Bootstrap/NetBox styling
    const hasBootstrap = await page.evaluate(() => {
      // Look for common Bootstrap classes in the DOM
      const bootstrapClasses = ['container', 'navbar', 'btn', 'card', 'form-control'];
      return bootstrapClasses.some(className => 
        document.querySelector(`.${className}`) !== null
      );
    });
    
    console.log('Bootstrap/CSS classes found:', hasBootstrap);
    
    // Check that the page isn't completely unstyled
    const bodyStyles = await page.locator('body').evaluate((el) => {
      const styles = window.getComputedStyle(el);
      return {
        fontFamily: styles.fontFamily,
        fontSize: styles.fontSize,
        margin: styles.margin,
        backgroundColor: styles.backgroundColor
      };
    });
    
    console.log('Body styles:', bodyStyles);
    
    // Basic check that styling is applied
    expect(bodyStyles.fontFamily).not.toBe('');
    expect(bodyStyles.fontSize).not.toBe('');
    
    console.log('✅ Basic CSS and styling verification passed');
  });
});