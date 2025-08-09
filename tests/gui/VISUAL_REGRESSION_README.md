# Visual Regression Testing

This directory contains comprehensive visual regression testing for the NetBox Hedgehog Plugin GUI.

## Overview

Visual regression testing automatically detects visual changes in the user interface by comparing screenshots of the current application state against baseline screenshots. This helps catch unintended visual changes during development and refactoring.

## Key Features

- **Full Page Screenshot Comparison**: Tests all major pages for visual consistency
- **Responsive Design Testing**: Validates UI across desktop, tablet, and mobile viewports
- **Component-Level Testing**: Individual UI component visual validation
- **Baseline Management**: Automatic baseline creation and management
- **Diff Generation**: Visual difference detection with highlighted changes
- **Comprehensive Reporting**: Detailed reports on visual differences

## Test Structure

### Core Files

- `test_visual_regression.py` - Main visual regression test suite
- `run_visual_tests.py` - Test runner script for validation

### Page Coverage

The visual regression tests cover:

- Dashboard overview page
- Fabric list and detail views
- Git repository management pages
- Drift detection dashboard
- VPC, connection, switch, and server views
- Form pages (create/edit)
- Error pages

### Viewport Testing

Tests run across multiple viewports:
- Desktop: 1920x1080
- Laptop: 1366x768  
- Tablet: 1024x768
- Mobile: 375x667

## Usage

### Running Visual Tests

```bash
# From the gui test directory
python run_visual_tests.py

# Or using pytest directly
pytest tests/test_visual_regression.py -v
```

### Creating Baselines

```bash
# Run the baseline creation test
pytest tests/test_visual_regression.py::TestVisualRegression::test_create_visual_baselines -v
```

### Dependencies

Required packages (automatically installed via requirements.txt):
- `pixelmatch>=0.3.0` - Image comparison
- `Pillow>=9.0.0` - Image processing
- `playwright>=1.40.0` - Browser automation
- `pytest-playwright>=0.4.0` - Playwright pytest integration

## Screenshot Organization

```
screenshots/
├── baselines/          # Baseline screenshots for comparison
├── actual/             # Current test screenshots
└── diffs/              # Visual difference images
```

## Test Configuration

### Thresholds

- Page-level tests: 5% difference threshold
- Component tests: 2% difference threshold
- Critical regressions: >5% difference

### Viewport Configurations

Responsive testing covers standard viewport sizes:
- Desktop (1920x1080) - Primary development viewport
- Tablet (1024x768) - Medium screen testing
- Mobile (375x667) - Mobile-first responsive validation

## Integration with CI/CD

The visual regression tests are designed to integrate with continuous integration:

1. **Baseline Updates**: New baselines created on main branch
2. **PR Validation**: Visual diffs detected on pull requests
3. **Failure Handling**: Tests fail if visual changes exceed thresholds
4. **Report Generation**: Comprehensive visual regression reports

## Best Practices

1. **Stable Testing**: Tests disable animations for consistent screenshots
2. **Network Idle**: Waits for network idle before capturing screenshots
3. **Element Waiting**: Ensures all elements are loaded before testing
4. **Error Handling**: Graceful handling of missing elements or pages
5. **Cleanup**: Automatic cleanup of old screenshot data

## Troubleshooting

### Common Issues

1. **Missing Dependencies**: Run `pip install pixelmatch Pillow`
2. **Browser Installation**: Run `playwright install` for browser binaries
3. **Baseline Missing**: Tests automatically create baselines on first run
4. **Permission Errors**: Ensure screenshot directories are writable

### Debug Mode

Enable debug logging by setting environment variable:
```bash
export PYTEST_LOG_LEVEL=DEBUG
```

## Maintenance

- **Baseline Updates**: Review and update baselines when UI intentionally changes
- **Threshold Tuning**: Adjust comparison thresholds based on project needs
- **Cleanup**: Periodically clean old screenshot data using provided utilities