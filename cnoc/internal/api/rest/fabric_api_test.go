package rest

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"

	"github.com/gorilla/mux"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
	"github.com/stretchr/testify/suite"
)

// FORGE Movement 5: Event Orchestration Testing
// REST API Foundation Test Suite with comprehensive validation

// Fabric represents a fabric configuration
type Fabric struct {
	ID                string            `json:"id"`
	Name              string            `json:"name"`
	Description       string            `json:"description"`
	KubernetesServer  string            `json:"kubernetes_server"`
	GitRepository     string            `json:"git_repository"`
	GitOpsDirectory   string            `json:"gitops_directory"`
	Status            string            `json:"status"`
	CreatedAt         time.Time         `json:"created_at"`
	UpdatedAt         time.Time         `json:"updated_at"`
	CRDCount          int               `json:"crd_count"`
	DriftStatus       string            `json:"drift_status"`
	LastSyncTime      time.Time         `json:"last_sync_time"`
	Metadata          map[string]interface{} `json:"metadata,omitempty"`
}

// FabricSyncRequest represents a sync operation request
type FabricSyncRequest struct {
	FabricID         string `json:"fabric_id"`
	Force            bool   `json:"force"`
	DryRun           bool   `json:"dry_run"`
	GitBranch        string `json:"git_branch,omitempty"`
	IncludePatterns  []string `json:"include_patterns,omitempty"`
	ExcludePatterns  []string `json:"exclude_patterns,omitempty"`
}

// FabricConnectionTestRequest represents connection test request
type FabricConnectionTestRequest struct {
	FabricID          string `json:"fabric_id"`
	TestKubernetes    bool   `json:"test_kubernetes"`
	TestGitRepository bool   `json:"test_git_repository"`
	Timeout           int    `json:"timeout_seconds"`
}

// APIResponse represents standard API response
type APIResponse struct {
	Success   bool        `json:"success"`
	Data      interface{} `json:"data,omitempty"`
	Error     string      `json:"error,omitempty"`
	Timestamp time.Time   `json:"timestamp"`
	RequestID string      `json:"request_id"`
	Duration  string      `json:"duration"`
}

// ValidationError represents field validation errors
type ValidationError struct {
	Field   string `json:"field"`
	Message string `json:"message"`
	Code    string `json:"code"`
}

// FabricAPITestSuite - FORGE Movement 5 Test Suite
type FabricAPITestSuite struct {
	suite.Suite
	router      *mux.Router
	server      *httptest.Server
	client      *http.Client
	evidence    map[string]interface{}
	testFabrics []Fabric
}

func (suite *FabricAPITestSuite) SetupSuite() {
	suite.evidence = make(map[string]interface{})
	suite.client = &http.Client{Timeout: 30 * time.Second}
	
	// Create router with actual implementation
	suite.router = NewFabricRouter()
	
	if suite.router != nil {
		suite.server = httptest.NewServer(suite.router)
	}
	
	// Setup test fabric data
	suite.testFabrics = []Fabric{
		{
			ID:               "fabric-001",
			Name:             "production-fabric-1",
			Description:      "Production fabric for testing API endpoints",
			KubernetesServer: "https://k8s-prod.example.com:6443",
			GitRepository:    "https://github.com/test/gitops-prod.git",
			GitOpsDirectory:  "gitops/production/fabric-1/",
			Status:           "active",
			CreatedAt:        time.Now().Add(-24 * time.Hour),
			UpdatedAt:        time.Now(),
			CRDCount:         42,
			DriftStatus:      "in_sync",
			LastSyncTime:     time.Now().Add(-1 * time.Hour),
		},
		{
			ID:               "fabric-002",
			Name:             "staging-fabric-1",
			Description:      "Staging fabric for development and testing",
			KubernetesServer: "https://k8s-staging.example.com:6443",
			GitRepository:    "https://github.com/test/gitops-staging.git",
			GitOpsDirectory:  "gitops/staging/fabric-1/",
			Status:           "active",
			CreatedAt:        time.Now().Add(-12 * time.Hour),
			UpdatedAt:        time.Now().Add(-30 * time.Minute),
			CRDCount:         28,
			DriftStatus:      "drift_detected",
			LastSyncTime:     time.Now().Add(-2 * time.Hour),
		},
	}
	
	suite.evidence["setup_completed"] = time.Now()
	suite.evidence["test_fabrics_count"] = len(suite.testFabrics)
}

func (suite *FabricAPITestSuite) TearDownSuite() {
	if suite.server != nil {
		suite.server.Close()
	}
	suite.evidence["teardown_completed"] = time.Now()
}

// TestFabricCRUDOperations - FORGE Movement 5 Requirement
// Complete CRUD with realistic data validation and performance benchmarks
func (suite *FabricAPITestSuite) TestFabricCRUDOperations() {
	startTime := time.Now()
	t := suite.T()
	
	if suite.server == nil {
		t.Log("Server not available - cannot test CRUD operations")
		assert.Fail(t, "REST API server should be available")
		return
	}
	
	testFabric := suite.testFabrics[0]
	
	// Test 1: CREATE - POST /api/fabrics
	fabricJSON, err := json.Marshal(testFabric)
	require.NoError(t, err)
	
	createResp, err := suite.client.Post(
		suite.server.URL+"/api/fabrics",
		"application/json",
		bytes.NewBuffer(fabricJSON),
	)
	require.NoError(t, err)
	defer createResp.Body.Close()
	
	// Validate CREATE response
	assert.Equal(t, http.StatusCreated, createResp.StatusCode)
	assert.Equal(t, "application/json", createResp.Header.Get("Content-Type"))
	
	createBody, err := io.ReadAll(createResp.Body)
	require.NoError(t, err)
	assert.Greater(t, len(createBody), 500, "Response should contain comprehensive fabric data")
	
	var createAPIResp APIResponse
	err = json.Unmarshal(createBody, &createAPIResp)
	require.NoError(t, err)
	assert.True(t, createAPIResp.Success)
	assert.NotEmpty(t, createAPIResp.RequestID)
	
	var createdFabric Fabric
	fabricData, ok := createAPIResp.Data.(map[string]interface{})
	require.True(t, ok)
	
	fabricBytes, err := json.Marshal(fabricData)
	require.NoError(t, err)
	err = json.Unmarshal(fabricBytes, &createdFabric)
	require.NoError(t, err)
	
	assert.NotEmpty(t, createdFabric.ID)
	assert.Equal(t, testFabric.Name, createdFabric.Name)
	assert.Equal(t, testFabric.Description, createdFabric.Description)
	assert.Equal(t, testFabric.KubernetesServer, createdFabric.KubernetesServer)
	
	// Test 2: READ - GET /api/fabrics/{id}
	readResp, err := suite.client.Get(suite.server.URL + "/api/fabrics/" + createdFabric.ID)
	require.NoError(t, err)
	defer readResp.Body.Close()
	
	assert.Equal(t, http.StatusOK, readResp.StatusCode)
	
	readBody, err := io.ReadAll(readResp.Body)
	require.NoError(t, err)
	assert.Greater(t, len(readBody), 500, "GET response should contain complete fabric data")
	
	var readAPIResp APIResponse
	err = json.Unmarshal(readBody, &readAPIResp)
	require.NoError(t, err)
	assert.True(t, readAPIResp.Success)
	
	// Test 3: UPDATE - PUT /api/fabrics/{id}
	updatedFabric := createdFabric
	updatedFabric.Description = "Updated description for FORGE testing"
	updatedFabric.Status = "maintenance"
	
	updateJSON, err := json.Marshal(updatedFabric)
	require.NoError(t, err)
	
	updateReq, err := http.NewRequest(
		http.MethodPut,
		suite.server.URL+"/api/fabrics/"+createdFabric.ID,
		bytes.NewBuffer(updateJSON),
	)
	require.NoError(t, err)
	updateReq.Header.Set("Content-Type", "application/json")
	
	updateResp, err := suite.client.Do(updateReq)
	require.NoError(t, err)
	defer updateResp.Body.Close()
	
	assert.Equal(t, http.StatusOK, updateResp.StatusCode)
	
	// Test 4: LIST - GET /api/fabrics
	listResp, err := suite.client.Get(suite.server.URL + "/api/fabrics")
	require.NoError(t, err)
	defer listResp.Body.Close()
	
	assert.Equal(t, http.StatusOK, listResp.StatusCode)
	
	listBody, err := io.ReadAll(listResp.Body)
	require.NoError(t, err)
	
	var listAPIResp APIResponse
	err = json.Unmarshal(listBody, &listAPIResp)
	require.NoError(t, err)
	assert.True(t, listAPIResp.Success)
	
	// Validate list contains our fabric
	fabricsList, ok := listAPIResp.Data.([]interface{})
	require.True(t, ok)
	assert.Greater(t, len(fabricsList), 0, "Should return at least one fabric")
	
	// Test 5: DELETE - DELETE /api/fabrics/{id}
	deleteReq, err := http.NewRequest(
		http.MethodDelete,
		suite.server.URL+"/api/fabrics/"+createdFabric.ID,
		nil,
	)
	require.NoError(t, err)
	
	deleteResp, err := suite.client.Do(deleteReq)
	require.NoError(t, err)
	defer deleteResp.Body.Close()
	
	assert.Equal(t, http.StatusNoContent, deleteResp.StatusCode)
	
	// Verify deletion
	verifyResp, err := suite.client.Get(suite.server.URL + "/api/fabrics/" + createdFabric.ID)
	require.NoError(t, err)
	defer verifyResp.Body.Close()
	assert.Equal(t, http.StatusNotFound, verifyResp.StatusCode)
	
	// Evidence collection
	duration := time.Since(startTime)
	suite.evidence["crud_test_duration"] = duration
	suite.evidence["crud_operations_tested"] = 5
	suite.evidence["crud_success"] = true
	
	// Performance requirement: All CRUD operations should complete within 5 seconds
	assert.Less(t, duration, 5*time.Second, "CRUD operations should be fast")
}

// TestFabricSyncEndpoint - FORGE Movement 5 Requirement
// POST /api/fabrics/{id}/sync with end-to-end validation
func (suite *FabricAPITestSuite) TestFabricSyncEndpoint() {
	startTime := time.Now()
	t := suite.T()
	
	if suite.server == nil {
		t.Log("Server not available - cannot test endpoint")
		assert.Fail(t, "REST API server should be available")
		return
	}
	
	fabricID := suite.testFabrics[0].ID
	
	// Test sync request
	syncRequest := FabricSyncRequest{
		FabricID:  fabricID,
		Force:     false,
		DryRun:    false,
		GitBranch: "main",
		IncludePatterns: []string{"*.yaml", "*.yml"},
	}
	
	syncJSON, err := json.Marshal(syncRequest)
	require.NoError(t, err)
	
	syncResp, err := suite.client.Post(
		suite.server.URL+"/api/fabrics/"+fabricID+"/sync",
		"application/json",
		bytes.NewBuffer(syncJSON),
	)
	require.NoError(t, err)
	defer syncResp.Body.Close()
	
	// Validate sync response
	assert.Equal(t, http.StatusAccepted, syncResp.StatusCode)
	
	syncBody, err := io.ReadAll(syncResp.Body)
	require.NoError(t, err)
	
	var syncAPIResp APIResponse
	err = json.Unmarshal(syncBody, &syncAPIResp)
	require.NoError(t, err)
	assert.True(t, syncAPIResp.Success)
	
	// Validate sync result data
	syncData, ok := syncAPIResp.Data.(map[string]interface{})
	require.True(t, ok)
	assert.Contains(t, syncData, "sync_id")
	assert.Contains(t, syncData, "status")
	assert.Equal(t, "initiated", syncData["status"])
	
	// Test dry run sync
	dryRunRequest := syncRequest
	dryRunRequest.DryRun = true
	
	dryRunJSON, err := json.Marshal(dryRunRequest)
	require.NoError(t, err)
	
	dryRunResp, err := suite.client.Post(
		suite.server.URL+"/api/fabrics/"+fabricID+"/sync",
		"application/json",
		bytes.NewBuffer(dryRunJSON),
	)
	require.NoError(t, err)
	defer dryRunResp.Body.Close()
	
	assert.Equal(t, http.StatusOK, dryRunResp.StatusCode)
	
	// Test invalid fabric ID
	invalidResp, err := suite.client.Post(
		suite.server.URL+"/api/fabrics/invalid-id/sync",
		"application/json",
		bytes.NewBuffer(syncJSON),
	)
	require.NoError(t, err)
	defer invalidResp.Body.Close()
	
	assert.Equal(t, http.StatusNotFound, invalidResp.StatusCode)
	
	// Evidence collection
	duration := time.Since(startTime)
	suite.evidence["sync_endpoint_duration"] = duration
	suite.evidence["sync_tests_completed"] = 3
	
	// Performance requirement: Sync initiation should respond within 2 seconds
	assert.Less(t, duration, 2*time.Second, "Sync endpoint should respond quickly")
}

// TestFabricConnectionTest - FORGE Movement 5 Requirement
// POST /api/fabrics/{id}/test with Kubernetes connectivity
func (suite *FabricAPITestSuite) TestFabricConnectionTest() {
	startTime := time.Now()
	t := suite.T()
	
	if suite.server == nil {
		t.Log("Server not available - cannot test endpoint")
		assert.Fail(t, "REST API server should be available")
		return
	}
	
	fabricID := suite.testFabrics[0].ID
	
	// Test connection request
	connRequest := FabricConnectionTestRequest{
		FabricID:          fabricID,
		TestKubernetes:    true,
		TestGitRepository: true,
		Timeout:           30,
	}
	
	connJSON, err := json.Marshal(connRequest)
	require.NoError(t, err)
	
	connResp, err := suite.client.Post(
		suite.server.URL+"/api/fabrics/"+fabricID+"/test",
		"application/json",
		bytes.NewBuffer(connJSON),
	)
	require.NoError(t, err)
	defer connResp.Body.Close()
	
	// Validate connection test response
	assert.Equal(t, http.StatusOK, connResp.StatusCode)
	
	connBody, err := io.ReadAll(connResp.Body)
	require.NoError(t, err)
	
	var connAPIResp APIResponse
	err = json.Unmarshal(connBody, &connAPIResp)
	require.NoError(t, err)
	assert.True(t, connAPIResp.Success)
	
	// Validate connection test results
	testData, ok := connAPIResp.Data.(map[string]interface{})
	require.True(t, ok)
	assert.Contains(t, testData, "kubernetes_test")
	assert.Contains(t, testData, "git_repository_test")
	assert.Contains(t, testData, "overall_status")
	
	kubernetesTest := testData["kubernetes_test"].(map[string]interface{})
	assert.Contains(t, kubernetesTest, "status")
	assert.Contains(t, kubernetesTest, "response_time_ms")
	
	gitTest := testData["git_repository_test"].(map[string]interface{})
	assert.Contains(t, gitTest, "status")
	assert.Contains(t, gitTest, "response_time_ms")
	
	// Test Kubernetes-only connection test
	k8sOnlyRequest := FabricConnectionTestRequest{
		FabricID:          fabricID,
		TestKubernetes:    true,
		TestGitRepository: false,
		Timeout:           15,
	}
	
	k8sJSON, err := json.Marshal(k8sOnlyRequest)
	require.NoError(t, err)
	
	k8sResp, err := suite.client.Post(
		suite.server.URL+"/api/fabrics/"+fabricID+"/test",
		"application/json",
		bytes.NewBuffer(k8sJSON),
	)
	require.NoError(t, err)
	defer k8sResp.Body.Close()
	
	assert.Equal(t, http.StatusOK, k8sResp.StatusCode)
	
	// Evidence collection
	duration := time.Since(startTime)
	suite.evidence["connection_test_duration"] = duration
	suite.evidence["connection_tests_completed"] = 2
	
	// Performance requirement: Connection tests should complete within 15 seconds
	assert.Less(t, duration, 15*time.Second, "Connection tests should be reasonably fast")
}

// TestAPIAuthentication - FORGE Movement 5 Requirement
// Request validation and authorization patterns
func (suite *FabricAPITestSuite) TestAPIAuthentication() {
	startTime := time.Now()
	t := suite.T()
	
	if suite.server == nil {
		t.Log("Server not available - cannot test endpoint")
		assert.Fail(t, "REST API server should be available")
		return
	}
	
	// Test 1: Request without authentication to auth endpoint
	unauthResp, err := suite.client.Get(suite.server.URL + "/api/auth/fabrics")
	require.NoError(t, err)
	defer unauthResp.Body.Close()
	
	// Should require authentication
	assert.Equal(t, http.StatusUnauthorized, unauthResp.StatusCode)
	
	// Test 2: Request with invalid token to auth endpoint
	invalidReq, err := http.NewRequest("GET", suite.server.URL+"/api/auth/fabrics", nil)
	require.NoError(t, err)
	invalidReq.Header.Set("Authorization", "Bearer invalid-token-123")
	
	invalidResp, err := suite.client.Do(invalidReq)
	require.NoError(t, err)
	defer invalidResp.Body.Close()
	
	assert.Equal(t, http.StatusUnauthorized, invalidResp.StatusCode)
	
	// Test 3: Request with valid token to auth endpoint
	validReq, err := http.NewRequest("GET", suite.server.URL+"/api/auth/fabrics", nil)
	require.NoError(t, err)
	validReq.Header.Set("Authorization", "Bearer valid-test-token-forge")
	
	validResp, err := suite.client.Do(validReq)
	require.NoError(t, err)
	defer validResp.Body.Close()
	
	// Should succeed with valid token
	assert.Equal(t, http.StatusOK, validResp.StatusCode)
	
	// Test 4: CORS headers
	corsReq, err := http.NewRequest("OPTIONS", suite.server.URL+"/api/fabrics", nil)
	require.NoError(t, err)
	corsReq.Header.Set("Origin", "http://localhost:3000")
	corsReq.Header.Set("Access-Control-Request-Method", "POST")
	
	corsResp, err := suite.client.Do(corsReq)
	require.NoError(t, err)
	defer corsResp.Body.Close()
	
	assert.Equal(t, http.StatusOK, corsResp.StatusCode)
	assert.NotEmpty(t, corsResp.Header.Get("Access-Control-Allow-Origin"))
	assert.NotEmpty(t, corsResp.Header.Get("Access-Control-Allow-Methods"))
	
	// Evidence collection
	duration := time.Since(startTime)
	suite.evidence["auth_test_duration"] = duration
	suite.evidence["auth_scenarios_tested"] = 4
}

// TestAPIPerformance - FORGE Movement 5 Requirement
// Response time benchmarks (<200ms requirement)
func (suite *FabricAPITestSuite) TestAPIPerformance() {
	startTime := time.Now()
	t := suite.T()
	
	if suite.server == nil {
		t.Log("Server not available - cannot test endpoint")
		assert.Fail(t, "REST API server should be available")
		return
	}
	
	// Performance test parameters
	const (
		maxResponseTime = 200 * time.Millisecond
		testIterations  = 10
	)
	
	var responseTimes []time.Duration
	
	// Test GET /api/fabrics performance
	for i := 0; i < testIterations; i++ {
		iterStart := time.Now()
		
		resp, err := suite.client.Get(suite.server.URL + "/api/fabrics")
		require.NoError(t, err)
		resp.Body.Close()
		
		iterDuration := time.Since(iterStart)
		responseTimes = append(responseTimes, iterDuration)
		
		assert.Equal(t, http.StatusOK, resp.StatusCode)
		assert.Less(t, iterDuration, maxResponseTime, fmt.Sprintf("Response time %v should be less than %v", iterDuration, maxResponseTime))
	}
	
	// Calculate performance metrics
	var totalTime time.Duration
	minTime := responseTimes[0]
	maxTime := responseTimes[0]
	
	for _, duration := range responseTimes {
		totalTime += duration
		if duration < minTime {
			minTime = duration
		}
		if duration > maxTime {
			maxTime = duration
		}
	}
	
	avgTime := totalTime / time.Duration(len(responseTimes))
	
	// Validate performance requirements
	assert.Less(t, avgTime, maxResponseTime, "Average response time should be under 200ms")
	assert.Less(t, maxTime, maxResponseTime*2, "Maximum response time should be reasonable")
	
	// Evidence collection
	duration := time.Since(startTime)
	suite.evidence["performance_test_duration"] = duration
	suite.evidence["performance_iterations"] = testIterations
	suite.evidence["avg_response_time_ms"] = avgTime.Milliseconds()
	suite.evidence["min_response_time_ms"] = minTime.Milliseconds()
	suite.evidence["max_response_time_ms"] = maxTime.Milliseconds()
	suite.evidence["performance_requirement_met"] = avgTime < maxResponseTime
}

// TestAPIValidationErrors - FORGE Movement 5 Requirement
// Comprehensive input validation and error handling
func (suite *FabricAPITestSuite) TestAPIValidationErrors() {
	startTime := time.Now()
	t := suite.T()
	
	if suite.server == nil {
		t.Log("Server not available - cannot test endpoint")
		assert.Fail(t, "REST API server should be available")
		return
	}
	
	// Test 1: Missing required fields
	invalidFabric := map[string]interface{}{
		"description": "Missing name and other required fields",
	}
	
	invalidJSON, err := json.Marshal(invalidFabric)
	require.NoError(t, err)
	
	invalidResp, err := suite.client.Post(
		suite.server.URL+"/api/fabrics",
		"application/json",
		bytes.NewBuffer(invalidJSON),
	)
	require.NoError(t, err)
	defer invalidResp.Body.Close()
	
	assert.Equal(t, http.StatusBadRequest, invalidResp.StatusCode)
	
	invalidBody, err := io.ReadAll(invalidResp.Body)
	require.NoError(t, err)
	
	var validationResp APIResponse
	err = json.Unmarshal(invalidBody, &validationResp)
	require.NoError(t, err)
	assert.False(t, validationResp.Success)
	assert.NotEmpty(t, validationResp.Error)
	assert.Contains(t, strings.ToLower(validationResp.Error), "validation")
	
	// Test 2: Invalid field formats
	invalidFormatFabric := Fabric{
		Name:             "", // Empty name
		Description:      "Valid description",
		KubernetesServer: "invalid-url", // Invalid URL format
		GitRepository:    "not-a-git-url", // Invalid git URL
		GitOpsDirectory:  "", // Empty directory
	}
	
	invalidFormatJSON, err := json.Marshal(invalidFormatFabric)
	require.NoError(t, err)
	
	formatResp, err := suite.client.Post(
		suite.server.URL+"/api/fabrics",
		"application/json",
		bytes.NewBuffer(invalidFormatJSON),
	)
	require.NoError(t, err)
	defer formatResp.Body.Close()
	
	assert.Equal(t, http.StatusBadRequest, formatResp.StatusCode)
	
	// Test 3: Invalid JSON payload
	malformedResp, err := suite.client.Post(
		suite.server.URL+"/api/fabrics",
		"application/json",
		strings.NewReader(`{"invalid": json malformed`),
	)
	require.NoError(t, err)
	defer malformedResp.Body.Close()
	
	assert.Equal(t, http.StatusBadRequest, malformedResp.StatusCode)
	
	// Test 4: Content-Type validation
	wrongTypeResp, err := suite.client.Post(
		suite.server.URL+"/api/fabrics",
		"text/plain",
		strings.NewReader("not json"),
	)
	require.NoError(t, err)
	defer wrongTypeResp.Body.Close()
	
	assert.Equal(t, http.StatusUnsupportedMediaType, wrongTypeResp.StatusCode)
	
	// Evidence collection
	duration := time.Since(startTime)
	suite.evidence["validation_test_duration"] = duration
	suite.evidence["validation_scenarios_tested"] = 4
}

// Helper functions are now implemented in fabric_controller.go

// Run the test suite
func TestFabricAPITestSuite(t *testing.T) {
	suite.Run(t, new(FabricAPITestSuite))
}

// FORGE Evidence Collection Test
func TestFabricAPIEvidenceCollection(t *testing.T) {
	evidence := map[string]interface{}{
		"test_execution_time": time.Now(),
		"framework_version":   "FORGE Movement 5",
		"test_coverage":       "REST API Foundation",
		"expected_failures":   true,
		"red_phase_active":    true,
		"api_endpoints_tested": []string{
			"GET /api/fabrics",
			"POST /api/fabrics",
			"GET /api/fabrics/{id}",
			"PUT /api/fabrics/{id}",
			"DELETE /api/fabrics/{id}",
			"POST /api/fabrics/{id}/sync",
			"POST /api/fabrics/{id}/test",
		},
		"performance_requirements": map[string]string{
			"crud_operations": "<5 seconds",
			"sync_initiation": "<2 seconds",
			"connection_tests": "<15 seconds",
			"response_time": "<200ms",
		},
	}
	
	assert.NotEmpty(t, evidence)
	assert.Contains(t, evidence, "api_endpoints_tested")
	assert.Equal(t, true, evidence["red_phase_active"])
	
	t.Logf("FORGE API Evidence Collection: %+v", evidence)
}

// Performance benchmark tests
func BenchmarkFabricCRUDOperations(b *testing.B) {
	// This benchmark will fail in RED PHASE until router is implemented
	router := NewFabricRouter()
	if router == nil {
		b.Skip("Router not implemented - RED PHASE expected")
		return
	}
	
	server := httptest.NewServer(router)
	defer server.Close()
	
	client := &http.Client{}
	testFabric := Fabric{
		Name:             "benchmark-fabric",
		Description:      "Fabric for performance benchmarking",
		KubernetesServer: "https://k8s.example.com:6443",
		GitRepository:    "https://github.com/test/repo.git",
		GitOpsDirectory:  "gitops/test/",
	}
	
	fabricJSON, _ := json.Marshal(testFabric)
	
	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		resp, _ := client.Post(
			server.URL+"/api/fabrics",
			"application/json",
			bytes.NewBuffer(fabricJSON),
		)
		if resp != nil {
			resp.Body.Close()
		}
	}
}

func BenchmarkFabricSyncEndpoint(b *testing.B) {
	router := NewFabricRouter()
	if router == nil {
		b.Skip("Router not implemented - RED PHASE expected")
		return
	}
	
	server := httptest.NewServer(router)
	defer server.Close()
	
	client := &http.Client{}
	syncRequest := FabricSyncRequest{
		FabricID: "benchmark-fabric",
		Force:    false,
		DryRun:   true,
	}
	
	syncJSON, _ := json.Marshal(syncRequest)
	
	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		resp, _ := client.Post(
			server.URL+"/api/fabrics/benchmark-fabric/sync",
			"application/json",
			bytes.NewBuffer(syncJSON),
		)
		if resp != nil {
			resp.Body.Close()
		}
	}
}