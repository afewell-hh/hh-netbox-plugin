# FORGE Template Path Resolution RED PHASE EVIDENCE

**Date**: August 19, 2025  
**Test Suite**: Template Path Resolution Validation  
**Phase**: RED (Test-First Failure Demonstration)  
**Evidence Type**: Quantitative Template Path Resolution Issue Analysis  
**Test File**: `/home/ubuntu/cc/hedgehog-netbox-plugin/cnoc/internal/web/template_path_resolution_test.go`

## Executive Summary

The comprehensive test suite successfully demonstrates the template path resolution issue in the CNOC web handler system. The issue occurs when the WebHandler is instantiated from working directories other than the cnoc/ directory, causing template loading failures due to hardcoded relative path dependencies.

## Quantitative Evidence

### Template Loading Success/Failure Matrix

| Working Directory | Template Pattern | Expected Result | Actual Result | Status |
|------------------|-----------------|----------------|---------------|---------|
| `/home/ubuntu/cc/hedgehog-netbox-plugin/cnoc` | `web/templates/*.html` | ✅ Success (22 templates) | ✅ Success (22 templates) | PASS |
| `/home/ubuntu/cc/hedgehog-netbox-plugin` | `web/templates/*.html` | ❌ FAIL | ❌ FAIL (pattern matches no files) | RED PHASE ✅ |
| `/home/ubuntu/cc/hedgehog-netbox-plugin/..` | `web/templates/*.html` | ❌ FAIL | ❌ FAIL (pattern matches no files) | RED PHASE ✅ |
| `/tmp` | `web/templates/*.html` | ❌ FAIL | ❌ FAIL (pattern matches no files) | RED PHASE ✅ |

### Quantitative Metrics

- **Total Template Files Expected**: 22 templates
- **Working Directory Test Cases**: 4
- **RED Phase Demonstrations**: 3 out of 4 (75% failure rate)
- **Template Pattern Failures**: `html/template: pattern matches no files`
- **Successful Working Directory**: Only `cnoc/` directory works

### WebHandler Constructor Evidence

```
=== WebHandler Creation Results ===
✅ from_cnoc_directory: SUCCESS (22 templates loaded)
❌ from_project_root: FAILURE - "failed to parse templates from web/templates/*.html: html/template: pattern matches no files"
❌ from_parent_directory: FAILURE - "failed to parse templates from web/templates/*.html: html/template: pattern matches no files"  
❌ from_tmp_directory: FAILURE - "failed to parse templates from web/templates/*.html: html/template: pattern matches no files"
```

## Root Cause Analysis

### Issue Identification
The CNOC web handler uses a hardcoded relative template path in `NewWebHandler()`:
```go
func NewWebHandler(metricsCollector *monitoring.MetricsCollector) (*WebHandler, error) {
    return NewWebHandlerWithTemplatePath(metricsCollector, "web/templates/*.html")
}
```

### Path Resolution Problem
- **Hardcoded Pattern**: `"web/templates/*.html"`
- **Assumption**: Working directory is always `cnoc/`
- **Reality**: Users may run the executable from different directories
- **Failure Mode**: Template pattern matching fails when `web/` directory doesn't exist relative to current working directory

## Test Execution Evidence

### 1. Template Pattern Validation from Different Directories
```
TestTemplatePathResolutionWithDifferentExecutablePaths/simulate_executable_from_project_root:
✅ EXPECTED RED PHASE FAILURE: Template pattern web/templates/*.html fails from /home/ubuntu/cc/hedgehog-netbox-plugin
✅ Error: html/template: pattern matches no files: `web/templates/*.html`
✅ This proves the template path resolution issue exists
```

### 2. Correct Path Demonstration
```
Correct pattern from project root: cnoc/web/templates/*.html
✅ CORRECT PATH SUCCESS: loaded 22 templates from /home/ubuntu/cc/hedgehog-netbox-plugin
```

### 3. Solution Validation with Absolute Paths
```
Absolute path: /home/ubuntu/cc/hedgehog-netbox-plugin/cnoc/web/templates/*.html
✅ ABSOLUTE PATH SUCCESS: loaded 22 templates from /tmp
```

## Template Execution Evidence

### Successful Template Types
- **simple_dashboard.html**: 6,247 bytes rendered successfully
- **base.html**: 13,020 bytes rendered successfully  
- **fabric_list.html**: 4 bytes rendered (partial template - missing `<html>` tag indicates template fragment)

### Template Count Validation
- **Expected Templates**: 10+ templates minimum
- **Actual Templates Found**: 22 templates consistently
- **Template Loading Success Rate**: 100% when path is correct

## Error Message Analysis

### Primary Error Pattern
```
html/template: pattern matches no files: `web/templates/*.html`
```

### Error Classification
- **Type**: File path resolution error
- **Cause**: Relative path dependency on specific working directory
- **Impact**: WebHandler constructor fails completely
- **Severity**: Critical - prevents web server startup

## Test-Driven Development Validation

### RED Phase Confirmation Criteria ✅
1. **Test Failure Demonstration**: ✅ Tests fail predictably from non-cnoc directories
2. **Quantitative Evidence**: ✅ 3 out of 4 working directories fail (75% failure rate)
3. **Error Message Documentation**: ✅ Specific error patterns captured
4. **Root Cause Identification**: ✅ Hardcoded relative path dependency identified
5. **Solution Path Validation**: ✅ Absolute paths and correct relative paths proven to work

## Success Criteria for GREEN Phase Implementation

### Required Fixes
1. **Dynamic Path Resolution**: Detect executable location and resolve template path accordingly
2. **Fallback Path Strategy**: Try multiple path patterns until templates are found
3. **Absolute Path Option**: Allow configuration of absolute template paths
4. **Working Directory Independence**: Ensure templates load regardless of current working directory

### Validation Requirements for GREEN Phase
1. **All 4 working directories**: Must successfully load 22 templates
2. **Error handling**: Graceful fallback when primary path fails
3. **Performance**: Template loading should not be significantly slower
4. **Backward compatibility**: Existing usage from cnoc/ directory must continue working

## Implementation Guidance

### Recommended Solution Pattern
```go
// Priority-based path resolution
templatePaths := []string{
    "web/templates/*.html",                                            // Current behavior (cnoc/ directory)
    "cnoc/web/templates/*.html",                                       // From project root
    filepath.Join(executable_dir, "web/templates/*.html"),             // Relative to executable
    "/home/ubuntu/cc/hedgehog-netbox-plugin/cnoc/web/templates/*.html", // Absolute fallback
}

for _, pattern := range templatePaths {
    if templates, err := template.ParseGlob(pattern); err == nil && len(templates.Templates()) > 0 {
        return templates, nil
    }
}
```

## Test Functions Created

### Primary Test Functions
1. **TestTemplatePathResolutionFromDifferentWorkingDirectories**: Core path resolution validation
2. **TestTemplateGlobPatternMatching**: Glob pattern specific testing
3. **TestTemplatePathResolutionQuantitativeMetrics**: Comprehensive metrics collection
4. **TestTemplateLoadingFromWebHandlerConstructor**: Real WebHandler behavior validation
5. **TestTemplatePathResolutionWithDifferentExecutablePaths**: Executable path simulation

### Test Coverage Metrics
- **Template Path Patterns**: 5+ different patterns tested
- **Working Directories**: 4 different directories tested
- **Error Scenarios**: Pattern matching failures documented
- **Success Scenarios**: Absolute and correct relative paths validated
- **Template Execution**: HTML rendering validation included

## Evidence Files Generated

1. **Test Suite**: `/home/ubuntu/cc/hedgehog-netbox-plugin/cnoc/internal/web/template_path_resolution_test.go`
2. **Evidence Report**: This document
3. **Test Execution Logs**: Quantitative failure/success evidence captured

## Next Phase Requirements

The GREEN phase implementation must:
1. Resolve all RED phase failures (3 out of 4 working directories currently fail)
2. Maintain 100% template loading success across all working directories
3. Provide quantitative evidence of fix effectiveness (all test functions must pass)
4. Pass all existing functionality tests
5. Maintain 22-template loading capability across all scenarios

---
**FORGE Methodology Compliance**: ✅ RED Phase Complete  
**Evidence Quality**: Comprehensive quantitative validation with 75% failure rate demonstration  
**Implementation Readiness**: Ready for GREEN phase development  
**Test Failure Rate**: 75% (3 out of 4 working directories fail as expected)