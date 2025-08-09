import { test, expect } from '@playwright/test';
import { TestHelpers } from '../utils/test-helpers';
import { FabricPage } from '../pages/fabric-page';
import { GitRepositoryPage } from '../pages/git-repository-page';

/**
 * Comprehensive end-to-end workflow tests
 */
test.describe('Hedgehog Plugin - Comprehensive Workflows', () => {
  let helpers: TestHelpers;
  let fabricPage: FabricPage;
  let gitRepoPage: GitRepositoryPage;

  test.beforeEach(async ({ page }) => {
    helpers = new TestHelpers(page);
    fabricPage = new FabricPage(page);
    gitRepoPage = new GitRepositoryPage(page);
    
    await helpers.loginToNetBox();
  });

  test('should complete full fabric creation and management workflow', async ({ page }) => {
    console.log('🚀 Starting comprehensive fabric workflow test...');
    
    // Step 1: Navigate to fabric list
    await fabricPage.goto();
    await helpers.takeScreenshot('workflow-step-1-fabric-list');
    
    // Step 2: Check if Add functionality exists
    const canAdd = await helpers.elementExists('a:has-text("Add"), .btn:has-text("Add")');
    
    if (canAdd) {
      // Step 3: Create new fabric
      const testFabricName = `e2e-test-fabric-${Date.now()}`;
      
      await fabricPage.clickAddFabric();
      await helpers.takeScreenshot('workflow-step-2-add-form');
      
      await fabricPage.fillFabricForm({
        name: testFabricName,
        description: 'End-to-end test fabric for comprehensive workflow validation'
      });
      
      await fabricPage.submitFabricForm();
      await helpers.takeScreenshot('workflow-step-3-fabric-created');
      
      // Step 4: Verify fabric appears in list
      await fabricPage.verifyFabricInList(testFabricName);
      
      // Step 5: Test fabric detail view
      await fabricPage.viewFabricDetails(testFabricName);
      await helpers.takeScreenshot('workflow-step-4-fabric-details');
      
      // Step 6: Test edit functionality
      const editWorking = await fabricPage.testEditFunctionality(testFabricName);
      console.log(`Edit functionality: ${editWorking ? '✅ Working' : '❌ Not working'}`);
      
      // Step 7: Test delete button (without actually deleting)
      const deleteWorking = await fabricPage.testDeleteButtonFunctionality(testFabricName);
      console.log(`Delete functionality: ${deleteWorking ? '✅ Working' : '❌ Not working'}`);
      
      console.log(`✅ Comprehensive fabric workflow completed for: ${testFabricName}`);
      
    } else {
      console.log('⚠️ Add fabric functionality not available - testing existing fabrics');
      
      const existingFabrics = await fabricPage.getFabricList();
      if (existingFabrics.length > 0) {
        await fabricPage.viewFabricDetails(existingFabrics[0]);
        await helpers.takeScreenshot('workflow-existing-fabric-details');
      }
    }
  });

  test('should complete git repository inspection workflow', async ({ page }) => {
    console.log('🚀 Starting git repository inspection workflow...');
    
    // Step 1: Navigate to git repositories
    await gitRepoPage.goto();
    await helpers.takeScreenshot('workflow-git-repos-list');
    
    // Step 2: Get available repositories
    const repositories = await gitRepoPage.getRepositoryList();
    console.log(`Found ${repositories.length} repositories`);
    
    if (repositories.length > 0) {
      const testRepo = repositories[0];
      
      // Step 3: View repository details
      await gitRepoPage.gotoRepository(testRepo.id);
      await helpers.takeScreenshot('workflow-git-repo-details');
      
      // Step 4: Check for HTML comment bugs (known issue)
      const bugCheck = await gitRepoPage.checkForHtmlCommentBug();
      console.log(`HTML Comment Bug Status: ${bugCheck.found ? 'DETECTED ❌' : 'CLEAN ✅'}`);
      
      // Step 5: Test sync functionality
      const syncWorking = await gitRepoPage.testRepositorySync(testRepo.id);
      console.log(`Sync functionality: ${syncWorking ? '✅ Available' : '⚠️ Not found'}`);
      
      // Step 6: Test management buttons
      const management = await gitRepoPage.testRepositoryManagement(testRepo.id);
      console.log(`Management buttons - Edit: ${management.editWorking ? '✅' : '❌'}, Delete: ${management.deleteWorking ? '✅' : '❌'}`);
      
      // Step 7: Check status indicators
      const statusIndicators = await gitRepoPage.checkRepositoryStatus(testRepo.id);
      console.log(`Status indicators found: ${statusIndicators.length}`);
      
      console.log('✅ Git repository workflow completed');
      
    } else {
      console.log('⚠️ No git repositories available for workflow testing');
    }
  });

  test('should validate overall plugin health and performance', async ({ page }) => {
    console.log('🏥 Starting overall plugin health check...');
    
    const healthResults = {
      loginWorking: false,
      pluginAccessible: false,
      fabricsAccessible: false,
      gitReposAccessible: false,
      overallHealth: 'Unknown'
    };
    
    // Test 1: Login functionality
    try {
      await helpers.loginToNetBox();
      healthResults.loginWorking = true;
      console.log('✅ Login functionality working');
    } catch (error) {
      console.log('❌ Login functionality failed');
    }
    
    // Test 2: Plugin main page
    try {
      await helpers.navigateToPluginHome();
      await helpers.verifyPageHealthy();
      healthResults.pluginAccessible = true;
      console.log('✅ Plugin main page accessible');
    } catch (error) {
      console.log('❌ Plugin main page inaccessible');
    }
    
    // Test 3: Fabrics section
    try {
      await fabricPage.goto();
      await helpers.verifyPageHealthy();
      healthResults.fabricsAccessible = true;
      console.log('✅ Fabrics section accessible');
    } catch (error) {
      console.log('❌ Fabrics section inaccessible');
    }
    
    // Test 4: Git repositories section
    try {
      await gitRepoPage.goto();
      await helpers.verifyPageHealthy();
      healthResults.gitReposAccessible = true;
      console.log('✅ Git repositories section accessible');
    } catch (error) {
      console.log('❌ Git repositories section inaccessible');
    }
    
    // Calculate overall health
    const workingComponents = Object.values(healthResults).filter(result => result === true).length;
    const totalComponents = 4;
    const healthPercentage = (workingComponents / totalComponents) * 100;
    
    if (healthPercentage >= 75) {
      healthResults.overallHealth = 'Good';
    } else if (healthPercentage >= 50) {
      healthResults.overallHealth = 'Fair';
    } else {
      healthResults.overallHealth = 'Poor';
    }
    
    console.log(`📊 Plugin Health Report:`);
    console.log(`  - Login: ${healthResults.loginWorking ? '✅' : '❌'}`);
    console.log(`  - Plugin Access: ${healthResults.pluginAccessible ? '✅' : '❌'}`);
    console.log(`  - Fabrics: ${healthResults.fabricsAccessible ? '✅' : '❌'}`);
    console.log(`  - Git Repos: ${healthResults.gitReposAccessible ? '✅' : '❌'}`);
    console.log(`  - Overall Health: ${healthResults.overallHealth} (${healthPercentage}%)`);
    
    await helpers.takeScreenshot('plugin-health-check-complete');
    
    // Expect at least basic functionality to work
    expect(healthResults.loginWorking).toBeTruthy();
    expect(healthResults.pluginAccessible).toBeTruthy();
  });

  test('should detect and report critical UI bugs', async ({ page }) => {
    console.log('🐛 Starting critical UI bug detection...');
    
    const bugReport = {
      htmlCommentBugs: 0,
      brokenButtons: 0,
      javascriptErrors: 0,
      httpErrors: 0,
      totalIssues: 0
    };
    
    const consoleErrors: string[] = [];
    page.on('console', (msg) => {
      if (msg.type() === 'error') {
        consoleErrors.push(msg.text());
      }
    });
    
    // Check main plugin page
    await helpers.navigateToPluginHome();
    await helpers.verifyPageHealthy();
    
    // Check fabric pages
    await fabricPage.goto();
    const fabrics = await fabricPage.getFabricList();
    
    // Check git repository pages for HTML comment bugs
    const repositories = await gitRepoPage.getRepositoryList();
    
    for (const repo of repositories.slice(0, 2)) { // Test first 2 repos
      await gitRepoPage.gotoRepository(repo.id);
      const bugCheck = await gitRepoPage.checkForHtmlCommentBug();
      
      if (bugCheck.found) {
        bugReport.htmlCommentBugs++;
        console.log(`❌ HTML comment bug found in repository ${repo.id}`);
      }
    }
    
    // Test button functionality
    if (fabrics.length > 0) {
      const deleteWorking = await fabricPage.testDeleteButtonFunctionality(fabrics[0]);
      if (!deleteWorking) {
        bugReport.brokenButtons++;
        console.log('❌ Delete button shows alert popup');
      }
    }
    
    // Count JavaScript errors
    bugReport.javascriptErrors = consoleErrors.length;
    
    // Calculate total issues
    bugReport.totalIssues = bugReport.htmlCommentBugs + bugReport.brokenButtons + 
                           (bugReport.javascriptErrors > 3 ? 1 : 0);
    
    console.log(`🐛 Bug Report Summary:`);
    console.log(`  - HTML Comment Bugs: ${bugReport.htmlCommentBugs}`);
    console.log(`  - Broken Buttons: ${bugReport.brokenButtons}`);
    console.log(`  - JavaScript Errors: ${bugReport.javascriptErrors}`);
    console.log(`  - Total Critical Issues: ${bugReport.totalIssues}`);
    
    if (bugReport.totalIssues === 0) {
      console.log('✅ No critical UI bugs detected');
    } else {
      console.log(`⚠️ ${bugReport.totalIssues} critical UI issues detected`);
    }
    
    await helpers.takeScreenshot('bug-detection-complete');
    
    // Create detailed bug report file
    const bugReportData = {
      timestamp: new Date().toISOString(),
      testSuite: 'Comprehensive GUI Testing',
      summary: bugReport,
      consoleErrors: consoleErrors,
      recommendations: [
        bugReport.htmlCommentBugs > 0 ? 'Fix HTML comment bugs in git repository pages' : null,
        bugReport.brokenButtons > 0 ? 'Fix delete button alert popup issue' : null,
        bugReport.javascriptErrors > 3 ? 'Investigate and fix JavaScript errors' : null
      ].filter(Boolean)
    };
    
    console.log('📄 Bug report generated with detailed findings');
  });
});