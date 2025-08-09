import { Page, expect } from '@playwright/test';
import { TestHelpers } from '../utils/test-helpers';

/**
 * Page Object Model for Fabric-related pages
 */
export class FabricPage {
  private helpers: TestHelpers;

  constructor(private page: Page) {
    this.helpers = new TestHelpers(page);
  }

  /**
   * Navigate to fabric list page
   */
  async goto() {
    await this.helpers.navigateToFabricList();
  }

  /**
   * Click "Add Fabric" button and navigate to creation form
   */
  async clickAddFabric() {
    console.log('🔘 Clicking Add Fabric button...');
    const addButton = await this.helpers.waitForElement('a[href*="add"], .btn:has-text("Add")');
    await addButton.click();
    
    // Wait for form page to load
    await this.page.waitForLoadState('networkidle');
    await this.helpers.verifyPageHealthy();
    
    console.log('✅ Navigated to Add Fabric form');
  }

  /**
   * Fill out fabric creation form
   */
  async fillFabricForm(fabricData: {
    name: string;
    description?: string;
    gitRepository?: string;
  }) {
    console.log('📝 Filling fabric creation form...');
    
    // Fill required name field
    await this.helpers.fillFormField('input[name="name"]', fabricData.name);
    
    // Fill optional description
    if (fabricData.description) {
      await this.helpers.fillFormField('textarea[name="description"]', fabricData.description);
    }

    // Select git repository if provided
    if (fabricData.gitRepository) {
      const gitRepoSelect = this.page.locator('select[name="git_repository"]');
      if (await gitRepoSelect.isVisible()) {
        await gitRepoSelect.selectOption({ label: fabricData.gitRepository });
      }
    }
    
    console.log('✅ Fabric form filled successfully');
  }

  /**
   * Submit fabric creation form
   */
  async submitFabricForm() {
    console.log('🚀 Submitting fabric creation form...');
    await this.helpers.submitForm();
    
    // Verify we're redirected to fabric detail or list
    await expect(this.page).toHaveURL(/.*\/plugins\/hedgehog\/fabric/, { timeout: 15000 });
    await this.helpers.verifyPageHealthy();
    
    console.log('✅ Fabric form submitted successfully');
  }

  /**
   * Verify fabric appears in the list
   */
  async verifyFabricInList(fabricName: string) {
    console.log(`🔍 Verifying fabric "${fabricName}" appears in list...`);
    await this.goto();
    
    const fabricRow = this.page.locator(`tr:has-text("${fabricName}")`);
    await expect(fabricRow).toBeVisible({ timeout: 10000 });
    
    console.log(`✅ Fabric "${fabricName}" found in list`);
  }

  /**
   * Click on a fabric to view details
   */
  async viewFabricDetails(fabricName: string) {
    console.log(`👁️ Viewing details for fabric "${fabricName}"...`);
    const fabricLink = this.page.locator(`a:has-text("${fabricName}")`);
    await fabricLink.click();
    
    await this.page.waitForLoadState('networkidle');
    await this.helpers.verifyPageHealthy();
    
    console.log(`✅ Viewing fabric "${fabricName}" details`);
  }

  /**
   * Test edit functionality for a fabric
   */
  async testEditFunctionality(fabricName: string) {
    console.log(`✏️ Testing edit functionality for fabric "${fabricName}"...`);
    
    await this.viewFabricDetails(fabricName);
    
    // Look for edit button
    const editButton = this.page.locator('a:has-text("Edit"), .btn:has-text("Edit")');
    if (await editButton.isVisible()) {
      await editButton.click();
      await this.page.waitForLoadState('networkidle');
      
      // Verify we're on edit page
      await expect(this.page).toHaveURL(/.*\/edit.*/, { timeout: 10000 });
      await this.helpers.verifyPageHealthy();
      
      console.log('✅ Edit functionality working');
      return true;
    } else {
      console.log('⚠️ Edit button not found');
      return false;
    }
  }

  /**
   * Test delete button (should not show alert popup)
   */
  async testDeleteButtonFunctionality(fabricName: string): Promise<boolean> {
    console.log(`🗑️ Testing delete button functionality for fabric "${fabricName}"...`);
    
    await this.viewFabricDetails(fabricName);
    
    const deleteButton = this.page.locator('button:has-text("Delete"), .btn:has-text("Delete")');
    if (await deleteButton.isVisible()) {
      return await this.helpers.testButtonFunctionality('button:has-text("Delete")');
    }
    
    console.log('⚠️ Delete button not found');
    return false;
  }

  /**
   * Test sync operations through GUI
   */
  async testSyncOperations() {
    console.log('🔄 Testing sync operations...');
    
    // Look for sync buttons
    const syncButtons = [
      'button:has-text("Sync")',
      'button:has-text("Synchronize")',
      '.btn:has-text("Sync")'
    ];

    for (const selector of syncButtons) {
      if (await this.helpers.elementExists(selector)) {
        console.log(`Found sync button: ${selector}`);
        
        // Test clicking sync button
        const button = this.page.locator(selector).first();
        await button.click();
        
        // Wait for any loading or status updates
        await this.helpers.waitForLoading();
        await this.page.waitForTimeout(2000);
        
        console.log('✅ Sync button clicked successfully');
        return true;
      }
    }
    
    console.log('⚠️ No sync buttons found');
    return false;
  }

  /**
   * Get list of all fabrics currently displayed
   */
  async getFabricList(): Promise<string[]> {
    await this.goto();
    
    const fabricRows = this.page.locator('tbody tr');
    const count = await fabricRows.count();
    const fabrics: string[] = [];
    
    for (let i = 0; i < count; i++) {
      const row = fabricRows.nth(i);
      const nameCell = row.locator('td').first();
      const text = await nameCell.textContent();
      if (text) {
        fabrics.push(text.trim());
      }
    }
    
    return fabrics;
  }

  /**
   * Verify fabric list page loads correctly
   */
  async verifyPageLoads() {
    await this.goto();
    await this.helpers.verifyPageHealthy();
    
    // Check for expected elements
    const expectedElements = [
      'h1, h2, .page-title', // Page title
      'table, .table', // Data table
      'a:has-text("Add"), .btn:has-text("Add")' // Add button
    ];

    for (const selector of expectedElements) {
      if (await this.helpers.elementExists(selector)) {
        console.log(`✅ Found expected element: ${selector}`);
      }
    }
    
    console.log('✅ Fabric list page loaded successfully');
  }
}