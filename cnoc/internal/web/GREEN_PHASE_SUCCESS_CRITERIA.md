# FORGE GREEN Phase Success Criteria: GitOps Integration

**Success Criteria Document**: GitOps Service Integration with Web GUI  
**FORGE Movement**: 3 - Test-First Development (GREEN Phase)  
**Created**: 2025-08-19  
**Implementation Target**: Implementation-Specialist

## Overview

This document defines the exact requirements for GREEN phase success. All criteria must be met with quantitative evidence before completion claims are accepted.

## Mandatory Service Implementations Required

### 1. GitOpsRepositoryApplicationService Integration

**Interface Location**: `/home/ubuntu/cc/hedgehog-netbox-plugin/cnoc/internal/application/services/interfaces.go` (lines 54-81)

**Required Methods**:
```go
CreateRepository(ctx context.Context, request dto.CreateGitOpsRepositoryDTO) (*dto.GitOpsRepositoryDTO, error)
GetRepository(ctx context.Context, id string) (*dto.GitOpsRepositoryDTO, error)  
ListRepositories(ctx context.Context, page, pageSize int) (*dto.GitOpsRepositoryListDTO, error)
UpdateRepository(ctx context.Context, id string, request dto.UpdateGitOpsRepositoryDTO) (*dto.GitOpsRepositoryDTO, error)
DeleteRepository(ctx context.Context, id string) error
TestConnection(ctx context.Context, id string) (*dto.ConnectionTestResultDTO, error)
SyncRepository(ctx context.Context, id string, options map[string]string) (*dto.SyncResult, error)
ValidateRepository(ctx context.Context, request dto.ValidationRequestDTO) (*dto.GitOpsValidationResultDTO, error)
GetRepositoryStatus(ctx context.Context, id string) (*dto.GitRepositoryStatusDTO, error)
```

**Performance Requirements**:
- Repository creation: <2 seconds
- Repository listing: <2 seconds  
- Connection testing: <5 seconds
- Repository sync: <30 seconds

**Integration Points**:
- Web handlers: `HandleAPIRepositoryList`, `HandleAPIRepositoryDetail`
- Authentication service integration for encrypted credentials
- Real git repository operations (clone, pull, push)

### 2. Enhanced FabricApplicationService Integration

**Interface Location**: `/home/ubuntu/cc/hedgehog-netbox-plugin/cnoc/internal/application/services/interfaces.go` (lines 38-51)

**Required Methods**:
```go
SynchronizeFabric(ctx context.Context, command FabricSyncCommand) (*FabricSyncResult, error)
GetFabricStatus(ctx context.Context, fabricID string) (*FabricStatusDTO, error)
ValidateFabricConfiguration(ctx context.Context, fabricID string) (*FabricValidationResult, error)  
ListFabrics(ctx context.Context, page, pageSize int) (*FabricListDTO, error)
```

**Performance Requirements**:
- Fabric sync initiation: <1 second
- Fabric sync completion: <10 seconds with progress updates
- Fabric status retrieval: <500ms
- Fabric listing: <2 seconds

**Integration Points**:  
- Web handlers: `HandleFabricSync`, `HandleAPIFabricList`, `HandleAPIFabricGet`
- WebSocket integration for real-time sync progress
- GitOps workflow orchestrator integration

### 3. ConfigurationValidationService Integration

**Required Methods**:
```go
ValidateConfiguration(ctx context.Context, configID string) (*dto.ValidationResultDTO, error)
ValidateYAML(ctx context.Context, yamlContent []byte) (*dto.ValidationResultDTO, error)
ValidateBusinessRules(ctx context.Context, config *configuration.Configuration) error
```

**Performance Requirements**:
- Configuration validation: <1 second for typical YAML files
- YAML parsing: <500ms for files <1MB
- Business rule validation: <2 seconds

**Integration Points**:
- Web handlers: `HandleAPIConfigurationValidate`
- Real YAML parsing with error detection
- Component-specific validation logic

### 4. DriftDetectionService Integration

**Required Methods**:
```go
DetectDrift(ctx context.Context, fabricID string) (*FabricDriftSummary, error)
GetDriftHistory(ctx context.Context, fabricID string, timeRange TimeRange) (*DriftHistory, error)
AnalyzeDriftSeverity(ctx context.Context, driftData []ResourceDrift) (*SeverityAnalysis, error)
```

**Performance Requirements**:
- Drift detection: <3 seconds for fabric-wide scan
- Drift analysis: <1 second for severity calculation  
- Real-time notifications: <500ms WebSocket latency

**Integration Points**:
- Web handlers: `HandleDriftDetection`, `HandleAPIFabricDrift`
- WebSocket real-time drift notifications
- Kubernetes cluster state comparison

## Quantitative Success Metrics

### Performance Benchmarks (MANDATORY)
All tests in `/home/ubuntu/cc/hedgehog-netbox-plugin/cnoc/internal/web/gitops_integration_test.go` must pass with these metrics:

```bash
# Run performance validation
go test ./internal/web -v -run "TestGitOpsIntegration" -timeout 60s

# Expected results:
- Repository data loading: <2000ms ✅
- Fabric sync operations: <10000ms ✅  
- Configuration validation: <1000ms ✅
- Drift detection refresh: <3000ms ✅
- Real-time updates: <500ms ✅
- End-to-end workflows: <20000ms ✅
```

### Integration Test Success (MANDATORY)
All integration test functions must pass:

1. `TestGitOpsIntegration_Configuration_Service_With_Web_GUI` ✅
2. `TestGitOpsIntegration_Fabric_Synchronization_With_Real_Services` ✅  
3. `TestGitOpsIntegration_Configuration_Validation_With_Real_Services` ✅
4. `TestGitOpsIntegration_WebSocket_Real_Time_Updates` ✅
5. `TestGitOpsIntegration_End_To_End_User_Workflows` ✅

### API Response Validation (MANDATORY)
All API endpoints must return properly formatted responses:

**Repository API**:
```bash
GET /api/v1/repositories → HTTP 200, valid GitOpsRepositoryListDTO
GET /api/v1/repositories/{id} → HTTP 200, valid GitOpsRepositoryDTO
POST /api/v1/repositories/{id}/test-connection → HTTP 200, valid ConnectionTestResultDTO
```

**Fabric API**:
```bash  
GET /api/v1/fabrics → HTTP 200, valid FabricListDTO
GET /api/v1/fabrics/{id} → HTTP 200, valid FabricStatusDTO
POST /api/v1/fabrics/{id}/sync → HTTP 202, sync initiation confirmed
POST /api/v1/fabrics/{id}/validate → HTTP 200, valid FabricValidationResult
```

**Configuration API**:
```bash
POST /api/v1/configurations/{id}/validate → HTTP 200, valid ValidationResultDTO  
```

### WebSocket Integration (MANDATORY)
Real-time updates must work with quantitative validation:

```go
// WebSocket connection test must pass
ws, _, err := websocket.DefaultDialer.Dial(wsURL, nil)  
assert.NoError(t, err) // Connection must succeed

// Real-time messages must be received
assert.GreaterOrEqual(t, len(receivedMessages), 1) // Must receive updates
assert.Less(t, messageLatency, 500*time.Millisecond) // <500ms latency
```

## Service Factory Integration (MANDATORY)

### Enhanced ServiceFactory Methods
File: `/home/ubuntu/cc/hedgehog-netbox-plugin/cnoc/internal/web/service_factory.go`

**Required additions**:
```go
func (sf *ServiceFactory) GetGitOpsRepositoryService() services.GitOpsRepositoryApplicationService
func (sf *ServiceFactory) GetDriftDetectionService() services.DriftDetectionService  
func (sf *ServiceFactory) GetConfigurationValidationService() services.ConfigurationValidationService
```

### Service Wiring Requirements
All services must be properly instantiated and wired:

```go
// Real service implementations (not mocks)
gitOpsRepoService := services.NewGitOpsRepositoryService(credentialStore, gitClient)
driftService := services.NewDriftDetectionService(k8sClient, configValidator)
validationService := services.NewConfigurationValidationService(yamlParser, businessRules)

// Proper dependency injection
serviceFactory := &ServiceFactory{
    configurationService: configService,
    fabricService:        fabricService,  
    gitOpsRepositoryService: gitOpsRepoService,
    driftDetectionService: driftService,
    configurationValidationService: validationService,
}
```

## Error Handling Requirements (MANDATORY)

### Service Unavailability Handling
All web handlers must gracefully handle service failures:

```go
if h.serviceFactory.GetGitOpsRepositoryService() == nil {
    http.Error(w, "GitOps repository service not available", http.StatusServiceUnavailable)
    return
}
```

### Network and Timeout Handling  
All service calls must include proper timeout and error handling:

```go
ctx, cancel := context.WithTimeout(ctx, 30*time.Second)
defer cancel()

result, err := service.SomeOperation(ctx, params)
if err != nil {
    // Proper error response with details
    w.WriteHeader(http.StatusInternalServerError)
    json.NewEncoder(w).Encode(ErrorResponse{
        Error: "Operation failed",
        Details: err.Error(),
        Timestamp: time.Now(),
    })
    return
}
```

## Real Data Integration (MANDATORY)

### Configuration Service Integration  
Must use real seeded data from service factory:

```go
// Must work with actual seeded configurations
configService := h.serviceFactory.GetConfigurationService()
configList, err := configService.ListConfigurations(ctx, 1, 50)
// Must return actual configurations, not mock data
```

### Fabric Service Integration
Must work with real fabric data:

```go
// Must manage actual fabric instances
fabricService := h.serviceFactory.GetFabricService()  
fabricStatus, err := fabricService.GetFabricStatus(ctx, fabricID)
// Must return real fabric synchronization status
```

## Build and Test Requirements (MANDATORY)

### Successful Build
```bash
go build ./internal/web
# Must build without errors
```

### All Tests Pass
```bash  
go test ./internal/web -v -timeout 60s
# All tests must pass with real service implementations
```

### No Test Modifications Allowed
- Original test file `/home/ubuntu/cc/hedgehog-netbox-plugin/cnoc/internal/web/gitops_integration_test.go` must remain unchanged
- Test integrity must be preserved (FORGE principle)
- Any test failures must be resolved through service implementation, not test modification

## Evidence Collection Requirements

### Performance Metrics Evidence
Must provide quantitative proof for all performance claims:

```bash
# Example evidence format:
Repository Creation: 1.234s ✅ (< 2s requirement)
Fabric Sync: 8.567s ✅ (< 10s requirement)  
Config Validation: 0.234s ✅ (< 1s requirement)
Drift Detection: 2.345s ✅ (< 3s requirement)
WebSocket Latency: 0.123s ✅ (< 0.5s requirement)
```

### Integration Success Evidence
Must demonstrate working integration at all service boundaries:

1. **Web Layer → Application Services**: All API endpoints return valid responses
2. **Application Services → Domain Services**: Business logic properly executed
3. **Domain Services → Infrastructure**: Real git, Kubernetes, and storage operations
4. **Real-time Updates**: WebSocket messages delivered with proper formatting

### Cross-Validation Evidence  
Independent verification required:

- Service implementations must work with existing configuration service
- All integrations must maintain compatibility with current web handlers
- Performance must be validated under realistic load conditions
- Error scenarios must be properly handled and recoverable

## Final Acceptance Criteria

### ✅ GREEN Phase Complete When:
1. All service interfaces properly implemented with real functionality
2. All integration tests pass with quantitative performance validation
3. All API endpoints return valid responses with proper error handling
4. WebSocket real-time updates function with <500ms latency
5. End-to-end workflows complete successfully within time limits
6. Service factory properly wires all dependencies
7. Build succeeds without errors or warnings
8. Evidence provided for all performance and functionality claims

### ❌ GREEN Phase FAILS if:
- Any integration test fails
- Performance thresholds not met
- Service implementations are mocks or stubs
- API responses are malformed or missing
- WebSocket functionality non-functional
- Build errors or dependency issues
- Missing quantitative evidence for claims
- Test file modified (integrity violation)

---

**SUCCESS MEASUREMENT**: All criteria must be met with quantitative evidence  
**NO EXCEPTIONS**: False completion prevention enforced  
**EVIDENCE REQUIRED**: Performance metrics, test results, integration proof  
**HANDOFF TARGET**: Only to QA Lead after all criteria satisfied

*Implementation-Specialist: Use this document as your exact requirements specification. All items marked MANDATORY must be completed with evidence before GREEN phase success can be claimed.*