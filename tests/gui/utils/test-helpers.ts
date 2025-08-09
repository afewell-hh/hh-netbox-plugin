import { Page, expect, Locator } from '@playwright/test';

/**
 * Test utilities for NetBox Hedgehog plugin GUI testing
 */

export class TestHelpers {
  constructor(private page: Page) {}

  /**
   * Login to NetBox with default credentials
   */
  async loginToNetBox(username: string = 'admin', password: string = 'admin') {
    console.log('🔐 Logging in to NetBox...');
    await this.page.goto('/login/');
    
    // Wait for login form to be visible
    await this.page.waitForSelector('form', { timeout: 30000 });
    
    // Fill login form
    await this.page.fill('input[name="username"]', username);
    await this.page.fill('input[name="password"]', password);
    
    // Submit form and wait for navigation
    await Promise.all([
      this.page.waitForNavigation({ waitUntil: 'networkidle' }),
      this.page.click('button[type="submit"], input[type="submit"]')
    ]);
    
    // Verify successful login
    await expect(this.page).toHaveURL(/.*\/(home|dashboard).*/, { timeout: 30000 });
    console.log('✅ Successfully logged in to NetBox');
  }

  /**
   * Navigate to plugin main page
   */
  async navigateToPluginHome() {
    console.log('🧭 Navigating to Hedgehog plugin home...');
    await this.page.goto('/plugins/hedgehog/');
    await this.page.waitForLoadState('networkidle');
    
    // Verify we're on the plugin page
    await expect(this.page).toHaveURL(/.*\/plugins\/hedgehog\/.*/, { timeout: 10000 });
    console.log('✅ Successfully navigated to plugin home');
  }

  /**
   * Navigate to fabric list page
   */
  async navigateToFabricList() {
    console.log('🧭 Navigating to fabric list...');
    await this.page.goto('/plugins/hedgehog/fabrics/');
    await this.page.waitForLoadState('networkidle');
    
    // Verify we're on the fabrics page
    await expect(this.page).toHaveURL(/.*\/plugins\/hedgehog\/fabrics\/.*/, { timeout: 10000 });
    console.log('✅ Successfully navigated to fabric list');
  }

  /**
   * Navigate to git repositories page
   */
  async navigateToGitRepositories() {
    console.log('🧭 Navigating to git repositories...');
    await this.page.goto('/plugins/hedgehog/git-repositories/');
    await this.page.waitForLoadState('networkidle');
    console.log('✅ Successfully navigated to git repositories');
  }

  /**
   * Check for HTML comment bugs in page source
   */
  async checkForHtmlCommentBugs(): Promise<string[]> {
    const content = await this.page.content();
    const commentRegex = /<!--[\s\S]*?-->/g;
    const comments = content.match(commentRegex) || [];
    
    // Filter out legitimate comments (like Django template comments)
    const suspiciousComments = comments.filter(comment => {
      // Look for comments that contain actual content that should be rendered
      return comment.includes('<') && comment.includes('>') && 
             !comment.includes('{% comment %}') && 
             !comment.includes('/* ') &&
             comment.length > 20;
    });

    return suspiciousComments;
  }

  /**
   * Wait for element to be visible and ready for interaction
   */
  async waitForElement(selector: string, timeout: number = 10000): Promise<Locator> {
    const element = this.page.locator(selector);
    await element.waitFor({ state: 'visible', timeout });
    return element;
  }

  /**
   * Take screenshot with timestamp
   */
  async takeScreenshot(name: string) {
    const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
    const filename = `${name}-${timestamp}.png`;
    await this.page.screenshot({ 
      path: `test-results/screenshots/${filename}`,
      fullPage: true 
    });
    console.log(`📸 Screenshot saved: ${filename}`);
    return filename;
  }

  /**
   * Check for JavaScript errors in console
   */
  async checkConsoleErrors(): Promise<string[]> {
    const errors: string[] = [];
    
    this.page.on('console', (msg) => {
      if (msg.type() === 'error') {
        errors.push(msg.text());
      }
    });

    return errors;
  }

  /**
   * Verify page has no obvious errors
   */
  async verifyPageHealthy() {
    // Check for Django error pages
    const pageContent = await this.page.content();
    
    if (pageContent.includes('DoesNotExist') || 
        pageContent.includes('OperationalError') ||
        pageContent.includes('Traceback') ||
        pageContent.includes('Server Error')) {
      throw new Error('Page contains Django errors');
    }

    // Check for HTTP error codes in title
    const title = await this.page.title();
    if (title.includes('404') || title.includes('500') || title.includes('Error')) {
      throw new Error(`Page has error in title: ${title}`);
    }

    console.log('✅ Page appears healthy');
  }

  /**
   * Fill form and handle CSRF tokens automatically
   */
  async fillFormField(selector: string, value: string) {
    const field = await this.waitForElement(selector);
    await field.clear();
    await field.fill(value);
  }

  /**
   * Submit form and wait for response
   */
  async submitForm(formSelector: string = 'form') {
    await Promise.all([
      this.page.waitForNavigation({ waitUntil: 'networkidle' }),
      this.page.click(`${formSelector} button[type="submit"], ${formSelector} input[type="submit"]`)
    ]);
  }

  /**
   * Check if element exists without throwing error
   */
  async elementExists(selector: string): Promise<boolean> {
    try {
      const element = this.page.locator(selector);
      await element.waitFor({ state: 'attached', timeout: 5000 });
      return true;
    } catch {
      return false;
    }
  }

  /**
   * Wait for loading indicators to disappear
   */
  async waitForLoading() {
    try {
      // Wait for common loading indicators to disappear
      await this.page.waitForSelector('.loading, .spinner, .fa-spinner', { 
        state: 'hidden', 
        timeout: 30000 
      });
    } catch {
      // Continue if no loading indicators found
    }
  }

  /**
   * Verify button functionality (no alert popups)
   */
  async testButtonFunctionality(selector: string): Promise<boolean> {
    try {
      const button = await this.waitForElement(selector);
      
      // Set up dialog handler to catch alerts
      let dialogAppeared = false;
      this.page.on('dialog', async dialog => {
        dialogAppeared = true;
        await dialog.dismiss();
      });

      await button.click();
      
      // Wait a bit to see if dialog appears
      await this.page.waitForTimeout(1000);
      
      return !dialogAppeared;
    } catch (error) {
      console.error(`Button test failed for ${selector}:`, error);
      return false;
    }
  }
}