# FORGE Testing Patterns Context - Comprehensive Validation Framework

## FORGE Test-First Development (MANDATORY)
- **Red-Green-Refactor**: FORGE-enforced test-first cycle with evidence requirements
- **Implementation Blocking**: Zero implementation until FORGE tests exist and are validated
- **Test Integrity**: Absolute prohibition on test modification during FORGE implementation
- **Evidence-Based Validation**: FORGE quantitative proof required for all completion claims

## FORGE Multi-Layer Testing Strategy
- **Unit Tests**: FORGE business logic testing with comprehensive validation
- **Integration Tests**: Full system integration with FORGE quantitative metrics
- **Template Tests**: FORGE HTML rendering validation (NOT just HTTP status codes)
- **Performance Tests**: FORGE benchmark validation with rigorous thresholds

## NetBox Plugin Testing (Evidence-Based)
- **Plugin Registration**: Verify proper NetBox integration with functional validation
- **Model Testing**: Database constraints with complete CRUD operation validation
- **API Testing**: Full request/response validation with quantitative content checks
- **UI Testing**: Complete page rendering with DOM structure validation

## TDD Methodology (Enforced)
- **Red-Green-Refactor**: Mandatory cycle with evidence of test failure before implementation
- **Test Coverage**: Minimum 90% coverage with mutation testing validation
- **Mock Strategies**: External dependency isolation with integration test validation
- **Evidence Requirements**: Quantitative metrics (byte counts, response codes, DOM elements)

## FORGE False Completion Prevention
- **Agent Role Separation**: FORGE SDET agents create tests, Implementation agents make them pass
- **Test Integrity Protection**: FORGE test logic cannot be modified during implementation
- **Quantitative Validation**: FORGE specific metrics required (response size, element counts, timing)
- **Mutation Testing**: Verify tests actually detect code changes

## Production Validation (Enhanced)
- **Container Testing**: Docker image functionality with performance validation
- **Deployment Testing**: Kubernetes deployment with health check validation
- **Integration Testing**: Real cluster environment with drift detection
- **Performance Monitoring**: Continuous benchmarking against test-specified thresholds

## CNOC-Specific Testing Requirements

### Go Backend Testing (Evidence-Based)
```go
// INVALID TEST (partial validation - causes false completion):
func TestAPIEndpoint(t *testing.T) {
    resp, err := http.Get("/api/fabrics")
    assert.Equal(t, 200, resp.StatusCode) // INSUFFICIENT!
}

// VALID TEST (complete validation - prevents false completion):
func TestAPIEndpointComplete(t *testing.T) {
    resp, err := http.Get("/api/fabrics")
    assert.NoError(t, err)
    assert.Equal(t, 200, resp.StatusCode)
    
    body, err := io.ReadAll(resp.Body)
    assert.NoError(t, err)
    assert.True(t, len(body) > 1000) // Minimum expected content
    
    var fabrics []Fabric
    err = json.Unmarshal(body, &fabrics)
    assert.NoError(t, err)
    assert.Greater(t, len(fabrics), 0)
}
```

### HTML Template Testing (Complete Validation)
```go
// INVALID TEST (URL routing only):
func TestFabricPage(t *testing.T) {
    resp, err := http.Get("/fabrics")
    assert.Equal(t, 200, resp.StatusCode) // INSUFFICIENT!
}

// VALID TEST (complete rendering validation):
func TestFabricPageComplete(t *testing.T) {
    resp, err := http.Get("/fabrics")
    assert.Equal(t, 200, resp.StatusCode)
    
    body := getResponseBody(resp)
    assert.Greater(t, len(body), 6000) // Minimum HTML size
    assert.Contains(t, body, "<!DOCTYPE html")
    assert.Contains(t, body, "CNOC Dashboard")
    assert.Contains(t, body, "Total Fabrics")
    
    // Parse DOM and validate structure
    doc := parseHTML(body)
    fabricCards := findElements(doc, ".card")
    assert.GreaterOrEqual(t, len(fabricCards), 1)
}
```

## Memory Integration (Enhanced)
- **Success Pattern Storage**: Capture test-first success approaches
- **Failure Analysis**: Document false completion patterns for prevention
- **Effectiveness Scoring**: Rate test quality and completion accuracy
- **Cross-Session Learning**: Retain TDD validation patterns for improvement