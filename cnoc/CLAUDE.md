# CNOC (Cloud NetOps Command) - Production Go Backend with FORGE TDD Framework

**Mission**: Enterprise-grade cloud networking operations system using Go 1.24 + Bootstrap 5 architecture with comprehensive test-driven development validation to ensure production reliability.

**Architecture**: Domain-driven Go backend with Bootstrap 5 frontend, PostgreSQL persistence, and K3s deployment. Uses proven technology stack for rapid HNP feature parity achievement.

**Role Architecture**: Strict separation between test creation and implementation agents to prevent invalid test creation that leads to false confidence.

## CNOC Production Technology Stack

### Current Implementation (Production-Ready)
```yaml
Backend:
  Language: Go 1.24
  Web_Framework: Gorilla Mux router
  Templates: Go HTML templates with Bootstrap 5.3
  Architecture: Domain-driven design with monolithic deployment

Frontend:
  Framework: Bootstrap 5.3 (server-rendered)
  JavaScript: Vanilla ES6+ (no framework dependencies)
  Icons: Material Design Icons
  Responsive: Mobile-first responsive design

Infrastructure:
  Container: K3s Kubernetes cluster
  Database: PostgreSQL 15
  Cache: Redis 7
  Deployment: HOSS bootable ISO or direct K3s

Performance_Targets:
  API_Response: <200ms
  Domain_Operations: <100µs
  Dashboard_Load: <1s
```

### Future Considerations (Deferred)
Advanced technologies like WasmCloud and React are preserved as future options but deferred based on current production success with Go+Bootstrap stack.

## AGENT ROLE DEFINITIONS

### SDET Agents (Software Development Engineer in Test)
**Primary Responsibility**: Create valid, comprehensive tests BEFORE any implementation begins
**Forbidden Actions**: NEVER implement functionality you are testing
**Validation Requirements**: 
- Every test MUST fail first (red-green-refactor validation)
- Use mutation testing to verify test quality  
- Include quantitative success metrics (byte counts, response codes, performance thresholds)
- Tests must validate COMPLETE desired state, not partial functionality

**CRITICAL PROCESS**: After creating tests, SDET agents must validate test quality using:
1. **Red-Green-Refactor**: Verify test fails without implementation
2. **Mutation Testing**: Modify code to ensure test detects changes
3. **Evidence-Based Validation**: Provide quantitative proof test works
4. **Independence Verification**: Test runs consistently in any order

### Implementation Agents (Feature Developers)
**Primary Responsibility**: Make existing tests pass without modifying test logic
**Constraints**: 
- CANNOT start work until valid tests exist and are validated
- CANNOT modify test assertions or success criteria
- MUST achieve 100% test pass rate before marking task complete
- MUST provide evidence of test passage with quantitative metrics

### Project Planning Agents (Task Orchestrators) 
**Primary Responsibility**: Enforce test-first workflow in ALL code changes
**Mandatory Process**:
1. Decompose ANY code change request into test creation tasks FIRST
2. Assign test creation to SDET agents BEFORE implementation work
3. Block implementation until tests are validated
4. Ensure definition of done includes test evidence

## CNOC ARTIFACT TESTING REQUIREMENTS

### Go Backend Components (34 Files)
**Test Requirements**:
- Unit tests with 100% branch coverage on business logic
- Integration tests for database transactions and concurrency
- API contract tests with exact request/response validation
- Performance tests with <200ms response time requirements
- Error handling tests with graceful recovery validation

**Validation Criteria**:
```go
// INVALID TEST EXAMPLE (partial validation):
func TestAPIEndpoint(t *testing.T) {
    resp, err := http.Get("/api/fabrics")
    assert.NoError(t, err)
    assert.Equal(t, 200, resp.StatusCode) // INSUFFICIENT!
}

// VALID TEST EXAMPLE (complete validation):
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
    
    // Validate structure
    for _, fabric := range fabrics {
        assert.NotEmpty(t, fabric.ID)
        assert.NotEmpty(t, fabric.Name)
        assert.Contains(t, []string{"in_sync", "out_of_sync", "unknown"}, fabric.Status)
    }
}
```

### HTML Template Components (5 Templates)
**Test Requirements**:
- Template compilation and rendering validation with realistic data
- Complete page content verification (NOT just HTTP status)
- Cross-browser compatibility testing
- Visual regression testing for layout consistency
- Accessibility compliance verification

**Validation Criteria**:
```go
// INVALID TEST (URL routing only - your exact issue):
func TestFabricPage(t *testing.T) {
    resp, err := http.Get("/fabrics")
    assert.Equal(t, 200, resp.StatusCode) // INSUFFICIENT!
}

// VALID TEST (complete rendering validation):
func TestFabricPageRendersCompletely(t *testing.T) {
    resp, err := http.Get("/fabrics")
    assert.Equal(t, 200, resp.StatusCode)
    
    body := string(respBody)
    assert.True(t, len(body) > 6000) // Minimum expected HTML
    assert.Contains(t, body, "<!DOCTYPE html")
    assert.Contains(t, body, "CNOC Dashboard")
    assert.Contains(t, body, "Total Fabrics")
    assert.Contains(t, body, "In Sync")
    assert.Contains(t, body, "<table") // Table structure exists
    assert.Contains(t, body, "mdi-server-network") // Icons loaded
    
    // Parse and validate DOM structure
    doc, err := html.Parse(strings.NewReader(body))
    assert.NoError(t, err)
    
    // Verify essential elements exist
    fabricCards := findElementsByClass(doc, "card")
    assert.GreaterOrEqual(t, len(fabricCards), 3)
}
```

### Kubernetes Integration Components
**Test Requirements**:
- Cluster connectivity and authentication validation
- YAML configuration parsing and schema verification
- Service discovery and health check testing
- Resource allocation within cluster capacity limits
- GitOps repository synchronization testing

### GitOps Repository Components  
**Test Requirements**:
- Repository authentication with encrypted credentials
- Git operations (clone, pull, push) success verification
- Directory structure and file parsing validation
- Sync status accuracy and error reporting
- Configuration change tracking and rollback capability

## PROCESS ENFORCEMENT INSTRUCTIONS

### For Queen Agents (Task Assignment Orchestrators)
**MANDATORY PROTOCOL**: Every code change request MUST trigger this workflow:

1. **Task Reception**: Immediately decompose into test creation + implementation phases
2. **SDET Assignment**: Assign test creation to SDET agents FIRST
3. **Implementation Blocking**: NO implementation work until valid tests exist
4. **Validation Gates**: Tests must pass quality validation before implementation
5. **Evidence Collection**: Require quantitative proof of completion at each step

**FAILURE ESCALATION**: If any agent attempts implementation without valid tests, immediately halt task and escalate to human oversight.

### For All Agents Working on CNOC
**PRIMARY DIRECTIVE**: Test creation drives development, not vice versa
**CRITICAL REMINDER**: Your experience shows 100% GUI failure rate without valid tests
**SUCCESS METRIC**: Target >95% implementation success with valid tests vs 0% without

## EVIDENCE-BASED VALIDATION FRAMEWORK

### Required Evidence for Test Completion
- Test failure demonstration (red phase)
- Mutation testing results showing test detects changes  
- Quantitative metrics (response bytes, element counts, performance data)
- Independence verification (tests run in any order)

### Required Evidence for Implementation Completion
- 100% test pass rate with quantitative proof
- No test modifications during implementation
- Performance benchmarks met
- Integration testing successful

## CRITICAL SUCCESS FACTORS

1. **Absolute Separation**: Different agents for test creation vs implementation
2. **Quality Gates**: Comprehensive validation at each phase  
3. **Evidence Requirements**: Quantitative metrics for all claims
4. **Process Enforcement**: No exceptions to test-first workflow
5. **Continuous Improvement**: Monitor false completion rates and agent compliance

**Historical Context**: This framework addresses the critical issue of "hundreds/thousands of false completion reports" by implementing research-backed validation techniques and strict role separation to ensure test validity and TDD process adherence.

---

**Framework Version**: 1.0  
**Implementation**: Phase 1 - Agent Role Separation  
**Target Metrics**: <1% false completion rate, >95% GUI implementation success  
**Validation**: Evidence-based quantitative verification required for all claims