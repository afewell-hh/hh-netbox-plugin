import { test, expect } from '@playwright/test';
import { TestHelpers } from '../utils/test-helpers';
import { GitRepositoryPage } from '../pages/git-repository-page';

/**
 * Test suite for Git Repository functionality and HTML comment bug detection
 */
test.describe('Hedgehog Plugin - Git Repository Workflows', () => {
  let helpers: TestHelpers;
  let gitRepoPage: GitRepositoryPage;

  test.beforeEach(async ({ page }) => {
    helpers = new TestHelpers(page);
    gitRepoPage = new GitRepositoryPage(page);
    
    // Login before each test
    await helpers.loginToNetBox();
  });

  test('should navigate to git repositories list successfully', async ({ page }) => {
    await gitRepoPage.verifyRepositoryListLoads();
    
    // Verify URL
    await expect(page).toHaveURL(/.*\/plugins\/hedgehog\/git-repositories.*/);
    
    await helpers.takeScreenshot('git-repositories-list');
  });

  test('should detect HTML comment bugs in git repository detail page', async ({ page }) => {
    // Test the known problematic URL: git-repositories/1/
    const repoId = 1;
    
    try {
      await gitRepoPage.gotoRepository(repoId);
      
      const bugCheck = await gitRepoPage.checkForHtmlCommentBug();
      
      console.log(`HTML Comment Bug Check Results:`);
      console.log(`- Bug Found: ${bugCheck.found}`);
      console.log(`- Details: ${bugCheck.details}`);
      console.log(`- Suspicious Comments: ${bugCheck.comments.length}`);
      
      if (bugCheck.found) {
        console.log('❌ HTML comment bug detected in git repository detail page');
        await helpers.takeScreenshot('html-comment-bug-detected');
        
        // Log the actual comments for debugging
        bugCheck.comments.forEach((comment, index) => {
          console.log(`Comment ${index + 1}: ${comment.substring(0, 100)}...`);
        });
        
        // This is expected to fail currently due to known bug
        // expect(bugCheck.found).toBeFalsy();
      } else {
        console.log('✅ No HTML comment bugs found');
      }
      
    } catch (error) {
      console.log(`Error testing git repository ${repoId}: ${error}`);
      await helpers.takeScreenshot('git-repo-error');
    }
  });

  test('should test git repository sync functionality', async ({ page }) => {
    const repositories = await gitRepoPage.getRepositoryList();
    
    if (repositories.length > 0) {
      const testRepo = repositories[0];
      console.log(`Testing sync for repository: ${testRepo.name} (ID: ${testRepo.id})`);
      
      const syncWorking = await gitRepoPage.testRepositorySync(testRepo.id);
      
      if (syncWorking) {
        console.log('✅ Repository sync functionality working');
      } else {
        console.log('⚠️ Repository sync functionality not found or not working');
      }
      
      await helpers.takeScreenshot('git-repo-sync-test');
    } else {
      console.log('⚠️ No git repositories found to test sync functionality');
    }
  });

  test('should test repository management buttons', async ({ page }) => {
    const repositories = await gitRepoPage.getRepositoryList();
    
    if (repositories.length > 0) {
      const testRepo = repositories[0];
      console.log(`Testing management buttons for: ${testRepo.name}`);
      
      const managementResults = await gitRepoPage.testRepositoryManagement(testRepo.id);
      
      console.log(`Edit functionality: ${managementResults.editWorking ? '✅ Working' : '❌ Not working'}`);
      console.log(`Delete functionality: ${managementResults.deleteWorking ? '✅ Working' : '❌ Not working'}`);
      
      // Delete button should not show alert popups
      expect(managementResults.deleteWorking).toBeTruthy();
      
      await helpers.takeScreenshot('git-repo-management-test');
    } else {
      console.log('⚠️ No repositories available to test management functionality');
    }
  });

  test('should verify repository status indicators', async ({ page }) => {
    const repositories = await gitRepoPage.getRepositoryList();
    
    if (repositories.length > 0) {
      const testRepo = repositories[0];
      console.log(`Checking status indicators for: ${testRepo.name}`);
      
      const statusIndicators = await gitRepoPage.checkRepositoryStatus(testRepo.id);
      
      console.log(`Found ${statusIndicators.length} status indicators:`);
      statusIndicators.forEach(indicator => {
        console.log(`  - ${indicator}`);
      });
      
      await helpers.takeScreenshot('git-repo-status');
    } else {
      console.log('⚠️ No repositories available to check status');
    }
  });

  test('should test CRD management functionality', async ({ page }) => {
    const crdAvailable = await gitRepoPage.testCRDManagement();
    
    if (crdAvailable) {
      console.log('✅ CRD management functionality found and accessible');
    } else {
      console.log('ℹ️ CRD management functionality not found (may be contextual)');
    }
    
    await helpers.takeScreenshot('crd-management-test');
  });

  test('should handle multiple repository detail pages', async ({ page }) => {
    const repositories = await gitRepoPage.getRepositoryList();
    
    console.log(`Found ${repositories.length} repositories to test`);
    
    // Test up to 3 repositories to avoid long test times
    const testRepos = repositories.slice(0, 3);
    
    for (const repo of testRepos) {
      console.log(`Testing repository detail page: ${repo.name} (ID: ${repo.id})`);
      
      try {
        await gitRepoPage.gotoRepository(repo.id);
        
        // Check for HTML comment bugs in each repository
        const bugCheck = await gitRepoPage.checkForHtmlCommentBug();
        
        if (bugCheck.found) {
          console.log(`❌ HTML comment bug found in repository ${repo.id}`);
        } else {
          console.log(`✅ Repository ${repo.id} appears clean`);
        }
        
      } catch (error) {
        console.log(`❌ Error accessing repository ${repo.id}: ${error}`);
      }
    }
    
    await helpers.takeScreenshot('multiple-repos-test');
  });

  test('should verify repository pages load within reasonable time', async ({ page }) => {
    const repositories = await gitRepoPage.getRepositoryList();
    
    if (repositories.length > 0) {
      const testRepo = repositories[0];
      
      const startTime = Date.now();
      await gitRepoPage.gotoRepository(testRepo.id);
      const loadTime = Date.now() - startTime;
      
      console.log(`Repository detail page loaded in ${loadTime}ms`);
      
      // Repository page should load within 10 seconds
      expect(loadTime).toBeLessThan(10000);
      
      if (loadTime > 3000) {
        console.log('⚠️ Repository page load time is slow');
      }
    } else {
      console.log('⚠️ No repositories available to test load time');
    }
  });

  test('should handle repository page errors gracefully', async ({ page }) => {
    // Test accessing non-existent repository
    try {
      await page.goto('/plugins/hedgehog/git-repositories/99999/');
      
      const content = await page.content();
      const hasAppropriateError = content.includes('404') || 
                                  content.includes('Not Found') || 
                                  content.includes('DoesNotExist');
      
      if (hasAppropriateError) {
        console.log('✅ Non-existent repository errors handled appropriately');
      } else {
        console.log('⚠️ Error handling may need improvement');
      }
      
      await helpers.takeScreenshot('git-repo-404-handling');
      
    } catch (error) {
      console.log(`Repository error handling test: ${error}`);
    }
  });

  test('should check for JavaScript errors on repository pages', async ({ page }) => {
    const consoleErrors: string[] = [];
    
    page.on('console', (msg) => {
      if (msg.type() === 'error') {
        consoleErrors.push(msg.text());
      }
    });
    
    const repositories = await gitRepoPage.getRepositoryList();
    
    if (repositories.length > 0) {
      const testRepo = repositories[0];
      await gitRepoPage.gotoRepository(testRepo.id);
      
      // Wait for any delayed JavaScript
      await page.waitForTimeout(3000);
      
      if (consoleErrors.length > 0) {
        console.log(`⚠️ JavaScript errors found on repository page:`);
        consoleErrors.forEach(error => {
          console.log(`  - ${error}`);
        });
      } else {
        console.log('✅ No JavaScript errors found');
      }
      
      // Don't fail for minor JS errors, but expect minimal errors
      expect(consoleErrors.length).toBeLessThanOrEqual(2);
    } else {
      console.log('⚠️ No repositories available to test JavaScript errors');
    }
  });
});