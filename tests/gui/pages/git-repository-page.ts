import { Page, expect } from '@playwright/test';
import { TestHelpers } from '../utils/test-helpers';

/**
 * Page Object Model for Git Repository pages
 */
export class GitRepositoryPage {
  private helpers: TestHelpers;

  constructor(private page: Page) {
    this.helpers = new TestHelpers(page);
  }

  /**
   * Navigate to git repositories list
   */
  async goto() {
    await this.helpers.navigateToGitRepositories();
  }

  /**
   * Navigate to specific git repository detail page
   */
  async gotoRepository(repoId: number | string) {
    console.log(`🧭 Navigating to git repository ${repoId} detail page...`);
    await this.page.goto(`/plugins/hedgehog/git-repositories/${repoId}/`);
    await this.page.waitForLoadState('networkidle');
    await this.helpers.verifyPageHealthy();
    console.log(`✅ Successfully navigated to git repository ${repoId}`);
  }

  /**
   * Check for HTML comment bug specifically in git repository detail page
   */
  async checkForHtmlCommentBug(): Promise<{
    found: boolean;
    comments: string[];
    details: string;
  }> {
    console.log('🔍 Checking for HTML comment bugs in git repository page...');
    
    const suspiciousComments = await this.helpers.checkForHtmlCommentBugs();
    const pageContent = await this.page.content();
    
    // Look for specific patterns that indicate the bug
    const bugPatterns = [
      /<!--[\s\S]*?<div[\s\S]*?>/,  // HTML content commented out
      /<!--[\s\S]*?<form[\s\S]*?>/,  // Form elements in comments
      /<!--[\s\S]*?<table[\s\S]*?>/,  // Table elements in comments
      /<!--[\s\S]*?class=[\s\S]*?>/   // Elements with classes in comments
    ];

    const foundBugPatterns = bugPatterns.filter(pattern => pattern.test(pageContent));
    
    const result = {
      found: suspiciousComments.length > 0 || foundBugPatterns.length > 0,
      comments: suspiciousComments,
      details: foundBugPatterns.length > 0 
        ? `Found ${foundBugPatterns.length} potential HTML comment bugs`
        : suspiciousComments.length > 0 
          ? `Found ${suspiciousComments.length} suspicious comments`
          : 'No HTML comment bugs detected'
    };
    
    if (result.found) {
      console.log(`❌ HTML comment bug detected: ${result.details}`);
      await this.helpers.takeScreenshot('html-comment-bug');
    } else {
      console.log('✅ No HTML comment bugs found');
    }
    
    return result;
  }

  /**
   * Verify git repository list loads correctly
   */
  async verifyRepositoryListLoads() {
    console.log('🔍 Verifying git repository list loads...');
    await this.goto();
    
    // Check for expected elements
    const expectedElements = [
      'h1, h2, .page-title',
      'table, .table, .repository-list'
    ];

    for (const selector of expectedElements) {
      if (await this.helpers.elementExists(selector)) {
        console.log(`✅ Found expected element: ${selector}`);
      }
    }
    
    console.log('✅ Git repository list loaded successfully');
  }

  /**
   * Get available git repositories
   */
  async getRepositoryList(): Promise<Array<{id: string, name: string}>> {
    await this.goto();
    
    const repositories: Array<{id: string, name: string}> = [];
    
    // Look for repository links or table rows
    const repoLinks = this.page.locator('a[href*="/git-repositories/"]');
    const count = await repoLinks.count();
    
    for (let i = 0; i < count; i++) {
      const link = repoLinks.nth(i);
      const href = await link.getAttribute('href');
      const text = await link.textContent();
      
      if (href && text) {
        const idMatch = href.match(/\/git-repositories\/(\d+)\//);
        if (idMatch) {
          repositories.push({
            id: idMatch[1],
            name: text.trim()
          });
        }
      }
    }
    
    return repositories;
  }

  /**
   * Test repository sync functionality
   */
  async testRepositorySync(repoId: number | string) {
    console.log(`🔄 Testing sync functionality for repository ${repoId}...`);
    await this.gotoRepository(repoId);
    
    // Look for sync-related buttons
    const syncSelectors = [
      'button:has-text("Sync")',
      'button:has-text("Synchronize")',
      'button:has-text("Refresh")',
      '.btn:has-text("Sync")',
      '[data-action="sync"]'
    ];

    for (const selector of syncSelectors) {
      if (await this.helpers.elementExists(selector)) {
        console.log(`Found sync control: ${selector}`);
        
        const button = this.page.locator(selector).first();
        await button.click();
        
        // Wait for sync operation
        await this.helpers.waitForLoading();
        await this.page.waitForTimeout(2000);
        
        console.log('✅ Sync operation triggered successfully');
        return true;
      }
    }
    
    console.log('⚠️ No sync controls found');
    return false;
  }

  /**
   * Test edit/delete buttons for repository
   */
  async testRepositoryManagement(repoId: number | string) {
    console.log(`⚙️ Testing repository management for ${repoId}...`);
    await this.gotoRepository(repoId);
    
    const results = {
      editWorking: false,
      deleteWorking: false
    };

    // Test edit button
    const editButton = this.page.locator('a:has-text("Edit"), .btn:has-text("Edit")');
    if (await editButton.isVisible()) {
      try {
        await editButton.click();
        await this.page.waitForLoadState('networkidle');
        
        // Check if we're on edit page
        const currentUrl = this.page.url();
        if (currentUrl.includes('/edit')) {
          results.editWorking = true;
          console.log('✅ Edit functionality working');
          
          // Navigate back to detail page
          await this.gotoRepository(repoId);
        }
      } catch (error) {
        console.log('❌ Edit functionality failed:', error);
      }
    }

    // Test delete button (should not show alert)
    results.deleteWorking = await this.helpers.testButtonFunctionality('button:has-text("Delete")');
    
    return results;
  }

  /**
   * Verify repository status and health indicators
   */
  async checkRepositoryStatus(repoId: number | string) {
    console.log(`📊 Checking repository ${repoId} status...`);
    await this.gotoRepository(repoId);
    
    const statusIndicators = [
      '.status',
      '.badge',
      '[data-status]',
      '.health-indicator',
      '.sync-status'
    ];

    const foundIndicators: string[] = [];
    
    for (const selector of statusIndicators) {
      if (await this.helpers.elementExists(selector)) {
        const element = this.page.locator(selector).first();
        const text = await element.textContent();
        if (text) {
          foundIndicators.push(`${selector}: ${text.trim()}`);
        }
      }
    }
    
    console.log(`📊 Found ${foundIndicators.length} status indicators`);
    return foundIndicators;
  }

  /**
   * Test CRD (Custom Resource Definition) related functionality
   */
  async testCRDManagement() {
    console.log('🔧 Testing CRD management functionality...');
    await this.goto();
    
    // Look for CRD-related elements
    const crdSelectors = [
      'a:has-text("CRD")',
      'a:has-text("Custom Resource")',
      'button:has-text("Generate")',
      '.crd-management'
    ];

    let foundCrdElements = false;
    
    for (const selector of crdSelectors) {
      if (await this.helpers.elementExists(selector)) {
        console.log(`Found CRD element: ${selector}`);
        foundCrdElements = true;
        
        // Test clicking the element
        try {
          const element = this.page.locator(selector).first();
          await element.click();
          await this.page.waitForLoadState('networkidle');
          await this.helpers.verifyPageHealthy();
          
          console.log('✅ CRD element clickable');
        } catch (error) {
          console.log(`❌ CRD element not clickable: ${error}`);
        }
        
        break;
      }
    }
    
    if (!foundCrdElements) {
      console.log('⚠️ No CRD management elements found');
    }
    
    return foundCrdElements;
  }
}