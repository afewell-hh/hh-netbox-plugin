# GREEN PHASE SUCCESS CRITERIA - Template Path Resolution Fix

**Date**: August 19, 2025  
**RED Phase Evidence**: Comprehensive template path resolution issue documented  
**Phase**: GREEN (Implementation Requirements)  
**Success Validation**: Must pass all RED phase tests that currently fail

## Critical Success Requirements

### 1. Template Loading Success Rate: 100%

**Current State**: 25% success rate (1 out of 4 working directories)  
**Required**: 100% success rate (4 out of 4 working directories)

**Specific Requirements**:
- ✅ From `/home/ubuntu/cc/hedgehog-netbox-plugin/cnoc`: Already working (22 templates loaded)
- ❌→✅ From `/home/ubuntu/cc/hedgehog-netbox-plugin`: Must load 22 templates
- ❌→✅ From `/home/ubuntu/cc/hedgehog-netbox-plugin/..`: Must load 22 templates  
- ❌→✅ From `/tmp`: Must load 22 templates

### 2. Error Elimination Requirements

**Current Errors**: `html/template: pattern matches no files: 'web/templates/*.html'`  
**Required**: Zero template loading errors across all working directories

### 3. Template Count Consistency

**Required**: Exactly 22 templates loaded regardless of working directory  
**Templates Must Include**: 
- simple_dashboard.html
- base.html
- fabric_list.html
- configuration_list.html
- All other existing templates

### 4. Template Execution Validation

**Required**: All templates must execute successfully and produce valid HTML
- simple_dashboard.html: Must render 6,000+ bytes
- base.html: Must render 13,000+ bytes
- All templates: Must contain valid HTML structure

## Implementation Requirements

### Path Resolution Strategy

The implementation must use a priority-based fallback system:

```go
func resolveTemplatePath() (string, error) {
    templatePaths := []string{
        "web/templates/*.html",                                            // Current working directory
        "cnoc/web/templates/*.html",                                       // From project root
        filepath.Join(getExecutableDir(), "web/templates/*.html"),         // Relative to executable
        "/home/ubuntu/cc/hedgehog-netbox-plugin/cnoc/web/templates/*.html", // Absolute fallback
    }
    
    for _, pattern := range templatePaths {
        if templates, err := template.ParseGlob(pattern); err == nil && len(templates.Templates()) > 0 {
            return pattern, nil
        }
    }
    
    return "", fmt.Errorf("no template files found in any search path")
}
```

### Required Functions to Implement

1. **getExecutableDir()**: Detect current executable location
2. **resolveTemplatePath()**: Priority-based path resolution
3. **validateTemplateCount()**: Ensure 22 templates are loaded
4. **logTemplateLoadingDetails()**: Debug information for troubleshooting

### WebHandler Constructor Update

```go
func NewWebHandler(metricsCollector *monitoring.MetricsCollector) (*WebHandler, error) {
    templatePath, err := resolveTemplatePath()
    if err != nil {
        return nil, fmt.Errorf("template path resolution failed: %v", err)
    }
    return NewWebHandlerWithTemplatePath(metricsCollector, templatePath)
}
```

## Test Validation Requirements

### All RED Phase Tests Must Pass

1. **TestTemplateLoadingFromWebHandlerConstructor**: All 4 working directories must succeed
2. **TestTemplatePathResolutionWithDifferentExecutablePaths**: All path resolution scenarios must work
3. **TestTemplatePathResolutionQuantitativeMetrics**: 100% success rate required
4. **TestTemplatePathResolutionFromDifferentWorkingDirectories**: All directory tests must pass
5. **TestTemplateGlobPatternMatching**: All glob patterns must work correctly

### Quantitative Success Metrics

- **Template Loading Success Rate**: 100.0% (currently 25.0%)
- **Working Directories Successful**: 4 out of 4 (currently 1 out of 4)
- **Template Count**: Consistently 22 templates across all scenarios
- **Error Count**: 0 (currently 3 error scenarios)

## Performance Requirements

### Template Loading Performance
- **Maximum Loading Time**: 50ms per WebHandler creation
- **Memory Usage**: No significant increase from current implementation
- **Fallback Performance**: Each path attempt should fail fast (<5ms)

### Backward Compatibility
- **Existing Behavior**: Must continue working from cnoc/ directory
- **No Breaking Changes**: Current API and behavior must remain unchanged
- **Template Content**: All existing templates must render identically

## Error Handling Requirements

### Graceful Degradation
```go
// If all template paths fail, provide helpful error message
func getTemplatePathError(attempts []string, errors []error) error {
    var errorDetails strings.Builder
    errorDetails.WriteString("Failed to load templates from any path:\n")
    for i, path := range attempts {
        errorDetails.WriteString(fmt.Sprintf("  %s: %v\n", path, errors[i]))
    }
    errorDetails.WriteString("Ensure templates exist in one of the search paths")
    return fmt.Errorf(errorDetails.String())
}
```

### Debug Logging
- **Template Path Attempts**: Log each path tried
- **Success/Failure Details**: Clear indication of what worked
- **Template Count Information**: Log number of templates loaded
- **Performance Metrics**: Log template loading time

## Validation Testing Protocol

### GREEN Phase Test Execution

1. **Run from cnoc directory**: `go test -v ./internal/web -run TestTemplatePathResolution`
2. **Run from project root**: Must pass all tests when working directory is root
3. **Run from parent directory**: Must pass all tests from parent
4. **Run from arbitrary directory**: Must pass all tests from /tmp

### Success Criteria Validation

```bash
# All these commands must pass with 100% success
cd /home/ubuntu/cc/hedgehog-netbox-plugin/cnoc && go test -v ./internal/web -run TestTemplatePathResolution
cd /home/ubuntu/cc/hedgehog-netbox-plugin && go test -v ./cnoc/internal/web -run TestTemplatePathResolution  
cd /home/ubuntu/cc && go test -v ./hedgehog-netbox-plugin/cnoc/internal/web -run TestTemplatePathResolution
cd /tmp && go test -v /home/ubuntu/cc/hedgehog-netbox-plugin/cnoc/internal/web -run TestTemplatePathResolution
```

## Implementation Priority

### Phase 1: Core Path Resolution (Critical)
1. Implement `resolveTemplatePath()` function with fallback logic
2. Update `NewWebHandler()` to use dynamic path resolution
3. Add executable directory detection

### Phase 2: Error Handling and Logging (Important)
1. Add comprehensive error messages with path details
2. Implement debug logging for troubleshooting
3. Add template count validation

### Phase 3: Performance and Polish (Nice to Have)
1. Optimize path resolution performance
2. Add configuration options for custom template paths
3. Implement template loading metrics

## Success Validation Checklist

- [ ] All 4 working directories load 22 templates successfully
- [ ] Zero template loading errors across all scenarios  
- [ ] TestTemplateLoadingFromWebHandlerConstructor passes 100%
- [ ] TestTemplatePathResolutionWithDifferentExecutablePaths passes 100%
- [ ] All existing functionality continues to work
- [ ] Template execution produces expected HTML output
- [ ] Performance impact is minimal (<50ms loading time)
- [ ] Error messages are helpful and actionable

## Definition of Done

**The GREEN phase is complete when:**
1. All RED phase tests pass without modification
2. Template loading success rate reaches 100%
3. WebHandler creation succeeds from any working directory
4. No regressions in existing functionality
5. Comprehensive error handling provides actionable feedback

---
**GREEN Phase Implementation Target**: Fix template path resolution issue with 100% working directory compatibility  
**Validation Method**: All existing RED phase tests must pass  
**Success Metric**: 4 out of 4 working directories successfully load 22 templates