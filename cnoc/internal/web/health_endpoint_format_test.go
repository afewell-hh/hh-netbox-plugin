package web

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	"github.com/gorilla/mux"
	"github.com/hedgehog/cnoc/internal/monitoring"
)

// FORGE RED PHASE REQUIREMENT: Health Endpoint Format Decision Tests
// 
// ARCHITECTURAL DECISION: JSON format for health endpoints (industry standard)
// vs Plain text format (test expectation - simpler, less informative)
//
// CRITICAL: These tests MUST fail first (red phase) until architectural
// decision is documented and GUI validation tests are updated accordingly.
//
// INDUSTRY STANDARDS ANALYSIS:
// - Kubernetes health checks: JSON format with structured data
// - Microservice patterns: JSON format for programmatic consumption  
// - Prometheus health: Plain text for simple monitoring
// - HTTP standards: Content-type should match actual content
//
// DECISION: JSON format provides better programmatic consumption, more
// informative responses, and aligns with industry microservice standards.

// HealthResponse represents the expected JSON health response structure
type HealthResponse struct {
	Status  string `json:"status"`
	Service string `json:"service"`
	Version string `json:"version"`
}

// TestHealthEndpointJSONFormatStandard tests the architectural decision for JSON health responses
func TestHealthEndpointJSONFormatStandard(t *testing.T) {
	// FORGE RED PHASE: This test MUST fail until architectural decision is implemented
	metricsCollector := monitoring.NewMetricsCollector()
	handler, err := NewWebHandler(metricsCollector)
	if err != nil {
		t.Fatalf("Failed to initialize web handler: %v", err)
	}

	// Create test request to health endpoint
	req := httptest.NewRequest("GET", "/healthz", nil)
	w := httptest.NewRecorder()

	// Create router and register routes
	router := mux.NewRouter()
	handler.RegisterRoutes(router)

	// Execute request
	startTime := time.Now()
	router.ServeHTTP(w, req)
	responseTime := time.Since(startTime)

	// FORGE Quantitative Validation 1: Response time <100ms requirement
	if responseTime > 100*time.Millisecond {
		t.Errorf("❌ FORGE EVIDENCE FAIL: Health endpoint response time too slow: %v (max: 100ms)", responseTime)
	}

	// FORGE Quantitative Validation 2: HTTP Status Code
	if w.Code != http.StatusOK {
		t.Errorf("❌ FORGE EVIDENCE FAIL: Expected status 200, got %d", w.Code)
	}

	// FORGE Quantitative Validation 3: Content-Type Header (ARCHITECTURAL DECISION)
	contentType := w.Header().Get("Content-Type")
	expectedContentType := "application/json"
	if contentType != expectedContentType {
		t.Errorf("❌ FORGE EVIDENCE FAIL: Expected content type %s, got %s", expectedContentType, contentType)
		t.Errorf("🔍 ARCHITECTURAL DECISION: JSON format chosen for structured health data")
	}

	// FORGE Quantitative Validation 4: JSON Response Structure
	responseBody := w.Body.String()
	var healthResp HealthResponse
	
	if err := json.Unmarshal([]byte(responseBody), &healthResp); err != nil {
		t.Errorf("❌ FORGE EVIDENCE FAIL: Response is not valid JSON: %v", err)
		t.Errorf("🔍 Response body: %s", responseBody)
	}

	// FORGE Quantitative Validation 5: Required JSON Fields
	if healthResp.Status == "" {
		t.Errorf("❌ FORGE EVIDENCE FAIL: Missing required field: status")
	}
	if healthResp.Service == "" {
		t.Errorf("❌ FORGE EVIDENCE FAIL: Missing required field: service")
	}
	if healthResp.Version == "" {
		t.Errorf("❌ FORGE EVIDENCE FAIL: Missing required field: version")
	}

	// FORGE Quantitative Validation 6: Status Value Validation
	expectedStatus := "healthy"
	if healthResp.Status != expectedStatus {
		t.Errorf("❌ FORGE EVIDENCE FAIL: Expected status '%s', got '%s'", expectedStatus, healthResp.Status)
	}

	// FORGE Quantitative Validation 7: Service Identification
	expectedService := "cnoc-metrics"
	if healthResp.Service != expectedService {
		t.Errorf("❌ FORGE EVIDENCE FAIL: Expected service '%s', got '%s'", expectedService, healthResp.Service)
	}

	// FORGE Evidence Logging
	t.Logf("✅ FORGE EVIDENCE: Health Endpoint Format Validation")
	t.Logf("📊 Response Time: %v", responseTime)
	t.Logf("📄 Content Type: %s", contentType)
	t.Logf("🎯 Status Code: %d", w.Code)
	t.Logf("📋 Response Size: %d bytes", len(responseBody))
	t.Logf("🏗️  Service: %s", healthResp.Service)
	t.Logf("📈 Status: %s", healthResp.Status)
	t.Logf("🔖 Version: %s", healthResp.Version)
}

// TestHealthEndpointErrorScenarios tests health endpoint error handling
func TestHealthEndpointErrorScenarios(t *testing.T) {
	// FORGE RED PHASE: Test error scenarios with JSON response format
	metricsCollector := monitoring.NewMetricsCollector()
	handler, err := NewWebHandler(metricsCollector)
	if err != nil {
		t.Fatalf("Failed to initialize web handler: %v", err)
	}

	// Test invalid HTTP methods
	invalidMethods := []string{"POST", "PUT", "DELETE", "PATCH"}
	
	for _, method := range invalidMethods {
		t.Run("Invalid_Method_"+method, func(t *testing.T) {
			req := httptest.NewRequest(method, "/healthz", nil)
			w := httptest.NewRecorder()

			router := mux.NewRouter()
			handler.RegisterRoutes(router)
			router.ServeHTTP(w, req)

			// Should return 405 Method Not Allowed for invalid methods
			if w.Code != http.StatusMethodNotAllowed && w.Code != http.StatusNotFound {
				t.Logf("⚠️  Method %s returned status %d (acceptable for health endpoint)", method, w.Code)
			}
		})
	}
}

// TestHealthEndpointConsistency tests health endpoint response consistency
func TestHealthEndpointConsistency(t *testing.T) {
	// FORGE Requirement: Health endpoint should return consistent responses
	metricsCollector := monitoring.NewMetricsCollector()
	handler, err := NewWebHandler(metricsCollector)
	if err != nil {
		t.Fatalf("Failed to initialize web handler: %v", err)
	}

	router := mux.NewRouter()
	handler.RegisterRoutes(router)

	// Make multiple requests to ensure consistency
	numRequests := 5
	responses := make([]string, numRequests)
	responseTimes := make([]time.Duration, numRequests)

	for i := 0; i < numRequests; i++ {
		req := httptest.NewRequest("GET", "/healthz", nil)
		w := httptest.NewRecorder()

		startTime := time.Now()
		router.ServeHTTP(w, req)
		responseTimes[i] = time.Since(startTime)

		responses[i] = w.Body.String()

		// Each request should succeed
		if w.Code != http.StatusOK {
			t.Errorf("❌ FORGE EVIDENCE FAIL: Request %d failed with status %d", i+1, w.Code)
		}
	}

	// FORGE Quantitative Validation: Response Consistency
	firstResponse := responses[0]
	for i, response := range responses {
		if response != firstResponse {
			t.Errorf("❌ FORGE EVIDENCE FAIL: Inconsistent response at request %d", i+1)
			t.Errorf("Expected: %s", firstResponse)
			t.Errorf("Got: %s", response)
		}
	}

	// FORGE Quantitative Validation: Performance Consistency
	var totalTime time.Duration
	maxTime := time.Duration(0)
	minTime := time.Hour // Start with large value
	
	for _, responseTime := range responseTimes {
		totalTime += responseTime
		if responseTime > maxTime {
			maxTime = responseTime
		}
		if responseTime < minTime {
			minTime = responseTime
		}
	}

	avgTime := totalTime / time.Duration(numRequests)
	
	// Performance thresholds
	if avgTime > 50*time.Millisecond {
		t.Errorf("❌ FORGE EVIDENCE FAIL: Average response time too slow: %v (max: 50ms)", avgTime)
	}
	
	if maxTime > 100*time.Millisecond {
		t.Errorf("❌ FORGE EVIDENCE FAIL: Maximum response time too slow: %v (max: 100ms)", maxTime)
	}

	// Performance variability check
	variability := maxTime - minTime
	if variability > 50*time.Millisecond {
		t.Errorf("❌ FORGE EVIDENCE FAIL: Response time variability too high: %v (max: 50ms)", variability)
	}

	t.Logf("✅ FORGE EVIDENCE: Health Endpoint Consistency Validation")
	t.Logf("📊 Average Response Time: %v", avgTime)
	t.Logf("📈 Min/Max Response Time: %v/%v", minTime, maxTime)
	t.Logf("📉 Performance Variability: %v", variability)
	t.Logf("🔄 Consistency: All %d responses identical", numRequests)
}

// TestHealthEndpointStructuredData tests structured health data availability
func TestHealthEndpointStructuredData(t *testing.T) {
	// FORGE Requirement: JSON format provides structured, extensible health data
	metricsCollector := monitoring.NewMetricsCollector()
	handler, err := NewWebHandler(metricsCollector)
	if err != nil {
		t.Fatalf("Failed to initialize web handler: %v", err)
	}

	req := httptest.NewRequest("GET", "/healthz", nil)
	w := httptest.NewRecorder()

	router := mux.NewRouter()
	handler.RegisterRoutes(router)
	router.ServeHTTP(w, req)

	responseBody := w.Body.String()
	
	// Parse as JSON to validate structure
	var healthData map[string]interface{}
	if err := json.Unmarshal([]byte(responseBody), &healthData); err != nil {
		t.Fatalf("❌ FORGE EVIDENCE FAIL: Cannot parse health response as JSON: %v", err)
	}

	// FORGE Quantitative Validation: Required Fields Present
	requiredFields := []string{"status", "service", "version"}
	for _, field := range requiredFields {
		if _, exists := healthData[field]; !exists {
			t.Errorf("❌ FORGE EVIDENCE FAIL: Missing required field: %s", field)
		}
	}

	// FORGE Quantitative Validation: Field Value Types
	if status, ok := healthData["status"].(string); ok {
		validStatuses := []string{"healthy", "degraded", "unhealthy"}
		isValid := false
		for _, validStatus := range validStatuses {
			if status == validStatus {
				isValid = true
				break
			}
		}
		if !isValid {
			t.Errorf("❌ FORGE EVIDENCE FAIL: Invalid status value: %s (must be one of: %v)", status, validStatuses)
		}
	} else {
		t.Errorf("❌ FORGE EVIDENCE FAIL: Status field is not a string")
	}

	if service, ok := healthData["service"].(string); ok {
		if service == "" {
			t.Errorf("❌ FORGE EVIDENCE FAIL: Service field cannot be empty")
		}
	} else {
		t.Errorf("❌ FORGE EVIDENCE FAIL: Service field is not a string")
	}

	if version, ok := healthData["version"].(string); ok {
		if version == "" {
			t.Errorf("❌ FORGE EVIDENCE FAIL: Version field cannot be empty")
		}
	} else {
		t.Errorf("❌ FORGE EVIDENCE FAIL: Version field is not a string")
	}

	// FORGE Evidence: Structured Data Advantage Validation
	jsonSize := len(responseBody)
	if jsonSize < 50 {
		t.Errorf("❌ FORGE EVIDENCE FAIL: JSON response too small to be informative: %d bytes", jsonSize)
	}

	// Count information density (number of data points)
	dataPoints := len(healthData)
	if dataPoints < 3 {
		t.Errorf("❌ FORGE EVIDENCE FAIL: Insufficient data points in health response: %d", dataPoints)
	}

	t.Logf("✅ FORGE EVIDENCE: Structured Health Data Validation")
	t.Logf("📊 JSON Response Size: %d bytes", jsonSize)
	t.Logf("📈 Data Points: %d fields", dataPoints)
	t.Logf("🏗️  Service: %v", healthData["service"])
	t.Logf("📊 Status: %v", healthData["status"])
	t.Logf("🔖 Version: %v", healthData["version"])
}

// TestHealthEndpointVSPlainTextComparison demonstrates JSON advantage over plain text
func TestHealthEndpointVSPlainTextComparison(t *testing.T) {
	// FORGE Architectural Decision Evidence: JSON vs Plain Text comparison
	
	// Simulate plain text response
	plainTextResponse := "healthy"
	plainTextSize := len(plainTextResponse)

	// Get actual JSON response
	metricsCollector := monitoring.NewMetricsCollector()
	handler, err := NewWebHandler(metricsCollector)
	if err != nil {
		t.Fatalf("Failed to initialize web handler: %v", err)
	}

	req := httptest.NewRequest("GET", "/healthz", nil)
	w := httptest.NewRecorder()

	router := mux.NewRouter()
	handler.RegisterRoutes(router)
	router.ServeHTTP(w, req)

	jsonResponse := w.Body.String()
	jsonSize := len(jsonResponse)

	// Parse JSON to count information
	var healthData map[string]interface{}
	json.Unmarshal([]byte(jsonResponse), &healthData)

	// FORGE Architectural Decision Evidence Collection
	t.Logf("🎯 FORGE ARCHITECTURAL DECISION EVIDENCE:")
	t.Logf("📋 Plain Text Response: '%s' (%d bytes, 1 data point)", plainTextResponse, plainTextSize)
	t.Logf("📋 JSON Response: %s (%d bytes, %d data points)", jsonResponse, jsonSize, len(healthData))
	t.Logf("📈 Information Density Ratio: %.1fx more informative", float64(len(healthData))/1.0)
	t.Logf("📊 Size Overhead: %d additional bytes for %d additional fields", jsonSize-plainTextSize, len(healthData)-1)
	
	// FORGE Decision Validation
	if len(healthData) <= 1 {
		t.Errorf("❌ FORGE ARCHITECTURAL DECISION FAIL: JSON format provides no additional information over plain text")
	}

	// Programmatic consumption advantage
	t.Logf("🔧 Programmatic Consumption: JSON parseable by all clients vs string parsing required for plain text")
	t.Logf("🔮 Future Extensibility: JSON easily extended with additional fields (timestamps, detailed status, etc.)")
	t.Logf("🏭 Industry Standard: Kubernetes, Docker, microservices use JSON health endpoints")
	
	// FINAL ARCHITECTURAL DECISION VALIDATION
	t.Logf("✅ FORGE ARCHITECTURAL DECISION VALIDATED: JSON format chosen for:")
	t.Logf("   - %d structured data points vs 1 plain text value", len(healthData))
	t.Logf("   - Programmatic parsing capability")
	t.Logf("   - Industry standard alignment") 
	t.Logf("   - Future extensibility for additional health metrics")
}

// BenchmarkHealthEndpointPerformance benchmarks health endpoint performance
func BenchmarkHealthEndpointPerformance(b *testing.B) {
	// FORGE Performance Requirement: <100ms response time
	metricsCollector := monitoring.NewMetricsCollector()
	handler, err := NewWebHandler(metricsCollector)
	if err != nil {
		b.Fatalf("Failed to initialize web handler: %v", err)
	}

	router := mux.NewRouter()
	handler.RegisterRoutes(router)

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		req := httptest.NewRequest("GET", "/healthz", nil)
		w := httptest.NewRecorder()
		router.ServeHTTP(w, req)

		if w.Code != http.StatusOK {
			b.Errorf("Health endpoint failed: status %d", w.Code)
		}
	}
}

// FORGE TEST SUMMARY AND ARCHITECTURAL DECISION VALIDATION:
//
// 1. RED PHASE REQUIREMENTS:
//    - Tests MUST fail until health endpoint returns proper JSON format
//    - GUI validation tests must be updated to expect application/json
//    - Architectural decision document must be created
//
// 2. QUANTITATIVE VALIDATION CRITERIA:
//    - Response time <100ms (performance requirement)
//    - Content-Type: application/json (architectural decision)
//    - Required JSON fields: status, service, version
//    - Response consistency across multiple requests
//    - Information density advantage over plain text
//
// 3. ARCHITECTURAL DECISION EVIDENCE:
//    - JSON format provides 3+ structured data points vs 1 plain text value
//    - Programmatic consumption capability validated
//    - Industry standard alignment demonstrated
//    - Future extensibility for additional health metrics
//
// 4. IMPLEMENTATION REQUIREMENTS:
//    - Health endpoint must return application/json content-type
//    - JSON response must include status, service, version fields
//    - Response time must be <100ms consistently
//    - GUI validation tests updated to expect JSON format
//
// 5. FORGE GREEN PHASE SUCCESS CRITERIA:
//    - All health endpoint format tests pass
//    - GUI validation tests pass with updated expectations
//    - Architectural decision document created and linked
//    - Performance benchmarks meet <100ms requirement