# NetBox Hedgehog Plugin - GUI Testing Framework

## Overview

This directory contains comprehensive GUI tests for the NetBox Hedgehog plugin using Playwright automation framework.

## Test Structure

```
tests/gui/
├── pages/                    # Page Object Models
│   ├── fabric-page.ts       # Fabric management pages
│   └── git-repository-page.ts # Git repository pages
├── test-specs/              # Test specifications
│   ├── main-plugin-access.spec.ts
│   ├── fabric-workflows.spec.ts
│   ├── git-repository-workflows.spec.ts
│   └── comprehensive-workflows.spec.ts
├── utils/                   # Test utilities
│   └── test-helpers.ts      # Common test functions
└── fixtures/               # Test data and fixtures

```

## Key Test Scenarios

### 1. Main Plugin Access
- Login to NetBox
- Navigate to plugin pages
- Verify basic functionality

### 2. Fabric Workflows
- List fabrics
- Create new fabrics
- Edit/delete functionality
- Sync operations

### 3. Git Repository Workflows
- List repositories
- View repository details
- **HTML comment bug detection** (critical)
- Management operations

### 4. Comprehensive Integration
- End-to-end workflows
- Performance validation
- Error detection and reporting

## Running Tests

### Prerequisites
```bash
# Setup (run once)
./scripts/setup-gui-tests.sh
```

### Basic Test Execution
```bash
# Run all tests (headless)
npm run test:gui

# Run with browser visible
npm run test:gui:headed

# Run specific test
npm run test:gui -- fabric-workflows

# Debug mode
npm run test:gui:debug
```

### Advanced Usage
```bash
# Custom test runner
./scripts/run-gui-tests.sh --headed --test "fabric"

# Integration with validation framework
python scripts/validate-gui.py
```

## Integration with validate_all.py

The GUI tests integrate with the main validation script:

```python
# In validate_all.py
def run_gui_validation():
    result = subprocess.run(['python', 'scripts/validate-gui.py'])
    return result.returncode == 0
```

## Key Features

### 1. HTML Comment Bug Detection
- Specifically tests for HTML content commented out in templates
- Critical for detecting the known git-repositories/1/ page bug

### 2. Button Functionality Testing
- Verifies edit/delete buttons work without alert popups
- Tests form submissions and navigation

### 3. Performance Monitoring
- Page load time validation
- JavaScript error detection
- Console log monitoring

### 4. Screenshots and Evidence
- Automatic screenshots on failures
- Evidence collection for debugging
- Performance metrics logging

## Configuration

Key configuration in `playwright.config.ts`:
- Headless mode by default
- Screenshots on failure
- Video recording on failure
- Custom timeout settings
- NetBox server integration

## Expected Issues

The tests are designed to detect these known issues:
1. **HTML comment bug** in git repository detail pages
2. **Alert popups** from delete buttons
3. **Form validation** issues
4. **Performance problems** in page loading

## Maintenance

### Adding New Tests
1. Create new spec file in `test-specs/`
2. Use Page Object Models from `pages/`
3. Utilize common helpers from `utils/`
4. Follow existing patterns for consistency

### Updating Page Objects
1. Modify files in `pages/` directory
2. Update selectors as NetBox UI changes
3. Add new functionality methods as needed

### Integration Updates
1. Update `validate_all.py` integration
2. Modify `scripts/validate-gui.py` as needed
3. Ensure CI/CD compatibility

## Troubleshooting

### Common Issues
1. **NetBox not running**: Ensure `python manage.py runserver 8000`
2. **Browser not found**: Run `npx playwright install`
3. **Permissions**: Ensure login credentials work
4. **Timeouts**: Check page load performance

### Debug Tips
1. Use `--headed` flag to see browser actions
2. Use `--debug` flag for step-through debugging
3. Check screenshots in `test-results/screenshots/`
4. Review console logs for JavaScript errors

## Reporting

Test results are available in multiple formats:
- HTML report: `playwright-report/index.html`
- JSON results: `test-results/gui-test-results.json`
- JUnit XML: `test-results/gui-results.xml`
- Screenshots: `test-results/screenshots/`

Access HTML report: `npx playwright show-report`