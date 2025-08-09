# NetBox Hedgehog Plugin - GUI Testing Framework

## Overview

The GUI Testing Framework provides comprehensive browser automation testing for the NetBox Hedgehog plugin using Playwright. This framework ensures that the user interface works correctly and can detect critical bugs that backend tests might miss.

## 🚨 Critical Requirements Addressed

### 1. HTML Comment Bug Detection
- **Problem**: Git repository detail pages have HTML content commented out, breaking the UI
- **Solution**: Automated detection of suspicious HTML comments in page source
- **Target URL**: `http://localhost:8000/plugins/hedgehog/git-repositories/1/`

### 2. Button Functionality Validation
- **Problem**: Edit/delete buttons showing alert popups instead of working properly
- **Solution**: Automated button testing that detects unwanted alert dialogs
- **Coverage**: All CRUD operations across fabric and git repository pages

### 3. End-to-End Workflow Testing
- **Problem**: Backend tests don't validate actual user workflows
- **Solution**: Complete user journey automation from login to task completion
- **Scope**: Login → Navigation → CRUD operations → Sync operations

## 📁 Framework Structure

```
tests/gui/
├── pages/                          # Page Object Models
│   ├── fabric-page.ts             # Fabric management pages
│   └── git-repository-page.ts     # Git repository pages
├── test-specs/                    # Test specifications
│   ├── main-plugin-access.spec.ts      # Basic plugin access
│   ├── fabric-workflows.spec.ts        # Fabric management tests
│   ├── git-repository-workflows.spec.ts # Git repo tests + HTML bug detection
│   └── comprehensive-workflows.spec.ts # End-to-end integration
├── utils/                         # Test utilities
│   └── test-helpers.ts           # Common helper functions
├── fixtures/                      # Test data (future)
└── README.md                     # Framework documentation

scripts/
├── setup-gui-tests.sh           # One-time setup script
├── run-gui-tests.sh             # Test execution script
└── validate-gui.py              # Integration with validate_all.py

Configuration Files:
├── package.json                 # Node.js dependencies
├── playwright.config.ts         # Playwright configuration
├── tsconfig.json               # TypeScript configuration
└── validate_all.py             # Updated with GUI integration
```

## 🚀 Quick Start

### Setup (One-time)
```bash
# Run the setup script
./scripts/setup-gui-tests.sh

# This installs:
# - Node.js dependencies
# - Playwright browsers
# - Creates test directories
# - Sets up scripts
```

### Running Tests
```bash
# Run all GUI tests (headless)
npm run test:gui

# Run with visible browser
./scripts/run-gui-tests.sh --headed

# Run specific test suite
./scripts/run-gui-tests.sh --test "fabric"

# Debug mode (step through tests)
npm run test:gui:debug

# Integration with master validation
python validate_all.py  # Now includes GUI tests
```

## 🧪 Test Scenarios

### 1. Main Plugin Access (`main-plugin-access.spec.ts`)
- ✅ Login to NetBox with default credentials
- ✅ Navigate to plugin home page
- ✅ Verify plugin loads without errors
- ✅ Check for navigation elements
- ✅ Performance validation (load time < 10s)

### 2. Fabric Workflows (`fabric-workflows.spec.ts`)
- ✅ Navigate to fabric list page
- ✅ Test "Add Fabric" functionality
- ✅ Fill and submit fabric creation form
- ✅ Verify fabric appears in list
- ✅ Test fabric detail view
- ✅ Test edit functionality
- ✅ **Test delete button without alert popup**
- ✅ Test sync operations through GUI

### 3. Git Repository Workflows (`git-repository-workflows.spec.ts`)
- ✅ Navigate to git repositories list
- ✅ **Test git-repositories/1/ for HTML comment bugs**
- ✅ Test multiple repository detail pages
- ✅ Test repository sync functionality
- ✅ Test edit/delete button functionality
- ✅ Verify status indicators
- ✅ Test CRD management features

### 4. Comprehensive Workflows (`comprehensive-workflows.spec.ts`)
- ✅ Complete fabric creation and management workflow
- ✅ Git repository inspection workflow
- ✅ Overall plugin health validation
- ✅ **Critical UI bug detection and reporting**

## 🎯 Key Features

### HTML Comment Bug Detection
```typescript
async checkForHtmlCommentBug(): Promise<{
  found: boolean;
  comments: string[];
  details: string;
}> {
  // Detects HTML content commented out in templates
  const suspiciousComments = await this.helpers.checkForHtmlCommentBugs();
  const bugPatterns = [
    /<!--[\s\S]*?<div[\s\S]*?>/,  // HTML content commented out
    /<!--[\s\S]*?<form[\s\S]*?>/,  // Form elements in comments
    /<!--[\s\S]*?class=[\s\S]*?>/   // Elements with classes in comments
  ];
  // Returns detailed analysis of found issues
}
```

### Button Functionality Testing
```typescript
async testButtonFunctionality(selector: string): Promise<boolean> {
  // Set up dialog handler to catch alerts
  let dialogAppeared = false;
  this.page.on('dialog', async dialog => {
    dialogAppeared = true;
    await dialog.dismiss();
  });

  await button.click();
  return !dialogAppeared; // Returns false if alert popup appeared
}
```

### Performance Monitoring
```typescript
// Page load time validation
const startTime = Date.now();
await helpers.navigateToPluginHome();
const loadTime = Date.now() - startTime;
expect(loadTime).toBeLessThan(10000); // Must load within 10 seconds
```

## 📊 Integration with validate_all.py

The GUI tests are now integrated into the master validation script:

```python
# New validation checks added to validate_all.py

# 9. Check GUI test framework availability
self.run_check(
    "GUI Test Framework Available",
    "command -v node && command -v npx && test -f package.json",
    lambda out: "node" in out.lower()
)

# 10. Run GUI tests if framework is available
if self.run_check(
    "GUI Automation Tests",
    "python scripts/validate-gui.py",
    lambda out: "GUI validation completed successfully" in out
):
    print("   ✅ GUI tests passed - user interface validated")
else:
    print("   ⚠️ GUI tests failed or not available - check browser automation")
```

## 🔧 Configuration

### Playwright Configuration (`playwright.config.ts`)
```typescript
export default defineConfig({
  testDir: './tests/gui',
  fullyParallel: false,           // Sequential for stability
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  
  use: {
    baseURL: 'http://localhost:8000',
    headless: true,              // Run in background
    screenshot: 'only-on-failure', // Evidence on errors
    video: 'retain-on-failure',   // Video recording on failure
    actionTimeout: 30000,         // 30s action timeout
  },
  
  webServer: {
    command: 'python manage.py runserver 8000',
    port: 8000,
    reuseExistingServer: !process.env.CI,
  }
});
```

## 📈 Reporting and Evidence

### Test Results
- **HTML Report**: `playwright-report/index.html`
- **JSON Results**: `test-results/gui-test-results.json`
- **Screenshots**: `test-results/screenshots/` (on failures)
- **Videos**: `test-results/videos/` (on failures)

### Accessing Reports
```bash
# Open HTML report in browser
npx playwright show-report

# View JSON results
cat test-results/gui-test-results.json | jq .

# Integration report
cat test-results/gui-test-report-*.json
```

## 🐛 Expected Bug Detection

The framework is specifically designed to catch these issues:

### 1. HTML Comment Bug ❌
- **Location**: Git repository detail pages
- **Symptom**: HTML content wrapped in `<!-- -->` comments
- **Detection**: Pattern matching for suspicious comments
- **Evidence**: Screenshots + comment content extraction

### 2. Alert Popup Bug ❌
- **Location**: Delete buttons across the interface
- **Symptom**: JavaScript alert() instead of proper form handling
- **Detection**: Dialog event listeners during button clicks
- **Evidence**: Test failure + screenshot

### 3. Performance Issues ⚠️
- **Location**: All pages
- **Symptom**: Slow page load times, JavaScript errors
- **Detection**: Timing validation + console error monitoring
- **Evidence**: Performance metrics + error logs

## 🔄 CI/CD Integration

### Environment Variables
```bash
export CI=true                    # Enable CI mode
export SKIP_SERVER_START=true    # Don't start server (external)
```

### Docker Integration
```yaml
# In docker-compose or CI pipeline
services:
  gui-tests:
    build: .
    depends_on:
      - netbox
    command: ./scripts/run-gui-tests.sh --reporter=json
    volumes:
      - ./test-results:/app/test-results
```

## 🛠️ Maintenance and Extension

### Adding New Tests
1. **Create Page Object**: Add new file in `tests/gui/pages/`
2. **Write Test Spec**: Add new spec in `tests/gui/test-specs/`
3. **Use Helpers**: Leverage common functions from `utils/test-helpers.ts`
4. **Follow Patterns**: Use existing tests as templates

### Updating for NetBox Changes
1. **Update Selectors**: Modify selectors in page objects
2. **Adjust Expectations**: Update test assertions for UI changes
3. **Add New Features**: Extend page objects for new functionality

### Debugging Failed Tests
1. **Run with --headed**: See browser actions visually
2. **Use --debug**: Step through tests interactively
3. **Check Screenshots**: Review failure screenshots
4. **Console Logs**: Look for JavaScript errors

## 📞 Support and Troubleshooting

### Common Issues

#### Node.js/Playwright Not Found
```bash
# Solution: Run setup script
./scripts/setup-gui-tests.sh
```

#### NetBox Server Not Running
```bash
# Solution: Start NetBox
python manage.py runserver 8000
```

#### Tests Timeout
```bash
# Solution: Check page performance
curl -w "@curl-format.txt" -o /dev/null -s "http://localhost:8000/plugins/hedgehog/"
```

#### Permissions Issues
```bash
# Solution: Ensure proper file permissions
chmod +x scripts/*.sh scripts/*.py
```

### Getting Help
1. **Check Logs**: Review test output and screenshots
2. **Run Setup**: Re-run `./scripts/setup-gui-tests.sh`
3. **Test Manually**: Verify NetBox works in browser first
4. **Check Network**: Ensure localhost:8000 is accessible

---

## 🎉 Success Criteria

The GUI testing framework is successful when:

✅ **Setup completes without errors**
✅ **Tests run in both headed and headless modes**
✅ **HTML comment bug is detected and reported**
✅ **Button functionality is properly validated**
✅ **Integration with validate_all.py works**
✅ **Screenshots and evidence are generated on failures**
✅ **Performance metrics are collected and validated**
✅ **Framework can be extended for new test scenarios**

This framework provides the critical missing piece: **actual user interface validation** that complements backend testing to ensure the NetBox Hedgehog plugin works correctly from a user's perspective.