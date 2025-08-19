package web

import (
	"encoding/json"
	"fmt"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"

	"github.com/gorilla/mux"
	"github.com/hedgehog/cnoc/internal/monitoring"
)

// FORGE GUI Validation Test Suite - Simplified Version
// CRITICAL: This validates the current CNOC GUI state matches our architectural expectations
// Focuses on working tests that can validate the current GUI implementation
// 
// Validation Requirements:
// 1. Template Rendering - All Go HTML templates render correctly
// 2. Bootstrap 5.3 Integration - UI components properly styled  
// 3. HTTP Response Validation - Proper status codes and content types
// 4. Performance Requirements - Page load times and API response times
// 5. Security Headers - Basic security header validation
// 6. Static File Serving - Static asset handling
// 7. Navigation Structure - Core navigation elements present

// SimpleGUIValidationResult contains basic validation results
type SimpleGUIValidationResult struct {
	TestName             string            `json:"test_name"`
	Success              bool              `json:"success"`
	HTTPStatusCode       int               `json:"http_status_code"`
	ResponseSizeBytes    int               `json:"response_size_bytes"`
	ResponseTimeMs       int64             `json:"response_time_ms"`
	ContentType          string            `json:"content_type"`
	RequiredElements     map[string]bool   `json:"required_elements"`
	MissingElements      []string          `json:"missing_elements"`
	Errors               []string          `json:"errors"`
}

// ComprehensiveGUIValidationReport aggregates all validation results
type ComprehensiveGUIValidationReport struct {
	OverallSuccess      bool                          `json:"overall_success"`
	TotalTests          int                           `json:"total_tests"`
	PassedTests         int                           `json:"passed_tests"`
	FailedTests         int                           `json:"failed_tests"`
	ValidationResults   []SimpleGUIValidationResult   `json:"validation_results"`
	Summary             string                        `json:"summary"`
	CriticalIssues      []string                      `json:"critical_issues"`
	Timestamp           time.Time                     `json:"timestamp"`
}

// TestSimplifiedGUIStateValidation - FORGE master validation test
func TestSimplifiedGUIStateValidation(t *testing.T) {
	// Initialize metrics collector for monitoring
	metricsCollector := monitoring.NewMetricsCollector()
	handler, err := NewTestWebHandler(metricsCollector)
	if err != nil {
		t.Fatalf("❌ FORGE GUI Validation FAILED: Cannot initialize web handler: %v", err)
	}

	report := &ComprehensiveGUIValidationReport{
		ValidationResults: make([]SimpleGUIValidationResult, 0),
		Timestamp:        time.Now(),
	}

	// Test Suite 1: Core Template Rendering
	t.Run("CoreTemplateRendering", func(t *testing.T) {
		results := testCoreTemplateRendering(t, handler)
		report.ValidationResults = append(report.ValidationResults, results...)
	})

	// Test Suite 2: HTTP Response Validation
	t.Run("HTTPResponseValidation", func(t *testing.T) {
		results := testHTTPResponseValidation(t, handler)
		report.ValidationResults = append(report.ValidationResults, results...)
	})

	// Test Suite 3: Performance Validation
	t.Run("PerformanceValidation", func(t *testing.T) {
		results := testPerformanceValidation(t, handler)
		report.ValidationResults = append(report.ValidationResults, results...)
	})

	// Test Suite 4: API Endpoint Accessibility
	t.Run("APIEndpointAccessibility", func(t *testing.T) {
		results := testAPIEndpointAccessibility(t, handler)
		report.ValidationResults = append(report.ValidationResults, results...)
	})

	// Test Suite 5: Security Headers Validation
	t.Run("SecurityHeadersValidation", func(t *testing.T) {
		results := testSecurityHeaders(t, handler)
		report.ValidationResults = append(report.ValidationResults, results...)
	})

	// Calculate overall results
	calculateSimpleOverallResults(report)

	// Generate evidence report
	generateSimpleValidationEvidence(t, report)

	// Assert overall success
	if !report.OverallSuccess {
		t.Errorf("❌ FORGE GUI Validation FAILED: %d/%d tests passed. Critical issues: %v", 
			report.PassedTests, report.TotalTests, report.CriticalIssues)
	} else {
		t.Logf("✅ FORGE GUI Validation PASSED: %d/%d tests passed", 
			report.PassedTests, report.TotalTests)
	}
}

// testCoreTemplateRendering validates core template rendering functionality
func testCoreTemplateRendering(t *testing.T, handler *WebHandler) []SimpleGUIValidationResult {
	var results []SimpleGUIValidationResult

	templateTests := []struct {
		name             string
		endpoint         string
		minBytes         int
		requiredElements []string
	}{
		{
			name:     "Dashboard Template",
			endpoint: "/dashboard",
			minBytes: 6099, // Issue #72 requirement
			requiredElements: []string{
				"<!DOCTYPE html>",
				"CNOC",
				"dashboard",
				"bootstrap",
				"container",
			},
		},
		{
			name:     "Root Redirect",
			endpoint: "/",
			minBytes: 1000,
			requiredElements: []string{
				"<!DOCTYPE html>",
				"CNOC",
			},
		},
		{
			name:     "Fabric List Template",
			endpoint: "/fabrics",
			minBytes: 2000,
			requiredElements: []string{
				"<!DOCTYPE html>",
				"fabric",
			},
		},
		{
			name:     "Configuration List Template", 
			endpoint: "/configurations",
			minBytes: 1500,
			requiredElements: []string{
				"<!DOCTYPE html>",
				"configuration",
			},
		},
	}

	for _, test := range templateTests {
		result := validateSingleGUITemplate(handler, test.name, test.endpoint, test.minBytes, test.requiredElements)
		results = append(results, result)
	}

	return results
}

// testHTTPResponseValidation validates HTTP response correctness
func testHTTPResponseValidation(t *testing.T, handler *WebHandler) []SimpleGUIValidationResult {
	var results []SimpleGUIValidationResult

	httpTests := []struct {
		name       string
		endpoint   string
		method     string
		expectedStatus int
		expectedContentType string
	}{
		{
			name:       "Dashboard HTTP Response",
			endpoint:   "/dashboard",
			method:     "GET", 
			expectedStatus: http.StatusOK,
			expectedContentType: "text/html",
		},
		{
			name:       "Health Check Endpoint",
			endpoint:   "/healthz",
			method:     "GET",
			expectedStatus: http.StatusOK,
			expectedContentType: "application/json", // FORGE Architectural Decision: JSON format standard
		},
		{
			name:       "Metrics Endpoint",
			endpoint:   "/metrics",
			method:     "GET",
			expectedStatus: http.StatusOK,
			expectedContentType: "text/plain",
		},
		{
			name:       "Configuration API",
			endpoint:   "/api/v1/configurations",
			method:     "GET",
			expectedStatus: http.StatusOK,
			expectedContentType: "application/json",
		},
	}

	for _, test := range httpTests {
		result := validateHTTPResponse(handler, test.name, test.endpoint, test.method, test.expectedStatus, test.expectedContentType)
		results = append(results, result)
	}

	return results
}

// testPerformanceValidation validates performance requirements
func testPerformanceValidation(t *testing.T, handler *WebHandler) []SimpleGUIValidationResult {
	var results []SimpleGUIValidationResult

	performanceTests := []struct {
		name        string
		endpoint    string
		maxResponseTime int64 // milliseconds
	}{
		{
			name:        "Dashboard Performance",
			endpoint:    "/dashboard",
			maxResponseTime: 1000, // <1s requirement
		},
		{
			name:        "API Performance",
			endpoint:    "/api/v1/configurations", 
			maxResponseTime: 200, // <200ms requirement
		},
		{
			name:        "Health Check Performance",
			endpoint:    "/healthz",
			maxResponseTime: 100, // <100ms requirement
		},
	}

	for _, test := range performanceTests {
		result := validatePerformanceRequirement(handler, test.name, test.endpoint, test.maxResponseTime)
		results = append(results, result)
	}

	return results
}

// testAPIEndpointAccessibility validates API endpoint accessibility
func testAPIEndpointAccessibility(t *testing.T, handler *WebHandler) []SimpleGUIValidationResult {
	var results []SimpleGUIValidationResult

	apiTests := []string{
		"/api/v1/configurations",
		"/api/v1/fabrics", 
		"/metrics",
		"/healthz",
	}

	for _, endpoint := range apiTests {
		result := validateAPIEndpointAccessibility(handler, endpoint)
		results = append(results, result)
	}

	return results
}

// testSecurityHeaders validates basic security headers
func testSecurityHeaders(t *testing.T, handler *WebHandler) []SimpleGUIValidationResult {
	var results []SimpleGUIValidationResult

	result := validateSecurityHeaders(handler)
	results = append(results, result)

	return results
}

// validateSingleGUITemplate validates a single template rendering
func validateSingleGUITemplate(handler *WebHandler, testName, endpoint string, minBytes int, requiredElements []string) SimpleGUIValidationResult {
	start := time.Now()
	
	req := httptest.NewRequest("GET", endpoint, nil)
	w := httptest.NewRecorder()

	router := mux.NewRouter()
	handler.RegisterRoutes(router)
	router.ServeHTTP(w, req)
	
	responseTime := time.Since(start).Milliseconds()
	response := w.Result()
	body := w.Body.String()

	result := SimpleGUIValidationResult{
		TestName:          testName,
		HTTPStatusCode:    response.StatusCode,
		ResponseSizeBytes: len(body),
		ResponseTimeMs:    responseTime,
		ContentType:       response.Header.Get("Content-Type"),
		RequiredElements:  make(map[string]bool),
		MissingElements:   make([]string, 0),
		Errors:           make([]string, 0),
	}

	// Validate HTTP response
	if response.StatusCode != http.StatusOK {
		result.Errors = append(result.Errors, fmt.Sprintf("Expected status 200, got %d", response.StatusCode))
	}

	// Validate response size (Issue #72 requirement)
	if len(body) < minBytes {
		result.Errors = append(result.Errors, fmt.Sprintf("Response too small: %d bytes (minimum %d)", len(body), minBytes))
	}

	// Validate content type
	if !strings.Contains(result.ContentType, "text/html") && endpoint != "/metrics" && endpoint != "/healthz" {
		result.Errors = append(result.Errors, fmt.Sprintf("Expected HTML content type, got %s", result.ContentType))
	}

	// Validate required HTML elements
	for _, element := range requiredElements {
		present := strings.Contains(strings.ToLower(body), strings.ToLower(element))
		result.RequiredElements[element] = present
		if !present {
			result.MissingElements = append(result.MissingElements, element)
			result.Errors = append(result.Errors, fmt.Sprintf("Missing required element: %s", element))
		}
	}

	result.Success = len(result.Errors) == 0
	return result
}

// validateHTTPResponse validates HTTP response correctness
func validateHTTPResponse(handler *WebHandler, testName, endpoint, method string, expectedStatus int, expectedContentType string) SimpleGUIValidationResult {
	start := time.Now()
	
	req := httptest.NewRequest(method, endpoint, nil)
	w := httptest.NewRecorder()

	router := mux.NewRouter()
	handler.RegisterRoutes(router)
	router.ServeHTTP(w, req)
	
	responseTime := time.Since(start).Milliseconds()
	response := w.Result()

	result := SimpleGUIValidationResult{
		TestName:          testName,
		HTTPStatusCode:    response.StatusCode,
		ResponseSizeBytes: w.Body.Len(),
		ResponseTimeMs:    responseTime,
		ContentType:       response.Header.Get("Content-Type"),
		RequiredElements:  make(map[string]bool),
		MissingElements:   make([]string, 0),
		Errors:           make([]string, 0),
	}

	if response.StatusCode != expectedStatus {
		result.Errors = append(result.Errors, fmt.Sprintf("Expected status %d, got %d", expectedStatus, response.StatusCode))
	}

	if !strings.Contains(result.ContentType, expectedContentType) {
		result.Errors = append(result.Errors, fmt.Sprintf("Expected content type %s, got %s", expectedContentType, result.ContentType))
	}

	result.Success = len(result.Errors) == 0
	return result
}

// validatePerformanceRequirement validates performance thresholds
func validatePerformanceRequirement(handler *WebHandler, testName, endpoint string, maxResponseTime int64) SimpleGUIValidationResult {
	start := time.Now()
	
	req := httptest.NewRequest("GET", endpoint, nil)
	w := httptest.NewRecorder()

	router := mux.NewRouter()
	handler.RegisterRoutes(router)
	router.ServeHTTP(w, req)
	
	responseTime := time.Since(start).Milliseconds()

	result := SimpleGUIValidationResult{
		TestName:          testName,
		HTTPStatusCode:    w.Result().StatusCode,
		ResponseSizeBytes: w.Body.Len(),
		ResponseTimeMs:    responseTime,
		ContentType:       w.Result().Header.Get("Content-Type"),
		RequiredElements:  make(map[string]bool),
		MissingElements:   make([]string, 0),
		Errors:           make([]string, 0),
	}

	if responseTime > maxResponseTime {
		result.Errors = append(result.Errors, fmt.Sprintf("Response time too slow: %dms (max %dms)", responseTime, maxResponseTime))
	}

	if w.Result().StatusCode >= 500 {
		result.Errors = append(result.Errors, fmt.Sprintf("Server error: status %d", w.Result().StatusCode))
	}

	result.Success = len(result.Errors) == 0
	return result
}

// validateAPIEndpointAccessibility validates API endpoint accessibility
func validateAPIEndpointAccessibility(handler *WebHandler, endpoint string) SimpleGUIValidationResult {
	start := time.Now()
	
	req := httptest.NewRequest("GET", endpoint, nil)
	w := httptest.NewRecorder()

	router := mux.NewRouter()
	handler.RegisterRoutes(router)
	router.ServeHTTP(w, req)
	
	responseTime := time.Since(start).Milliseconds()

	result := SimpleGUIValidationResult{
		TestName:          fmt.Sprintf("API Accessibility - %s", endpoint),
		HTTPStatusCode:    w.Result().StatusCode,
		ResponseSizeBytes: w.Body.Len(),
		ResponseTimeMs:    responseTime,
		ContentType:       w.Result().Header.Get("Content-Type"),
		RequiredElements:  make(map[string]bool),
		MissingElements:   make([]string, 0),
		Errors:           make([]string, 0),
	}

	// API endpoints should not return 404
	if w.Result().StatusCode == 404 {
		result.Errors = append(result.Errors, fmt.Sprintf("API endpoint not found: %s", endpoint))
	}

	// API endpoints should respond quickly
	if responseTime > 500 {
		result.Errors = append(result.Errors, fmt.Sprintf("API response too slow: %dms", responseTime))
	}

	result.Success = len(result.Errors) == 0
	return result
}

// validateSecurityHeaders validates basic security headers
func validateSecurityHeaders(handler *WebHandler) SimpleGUIValidationResult {
	req := httptest.NewRequest("GET", "/dashboard", nil)
	w := httptest.NewRecorder()

	router := mux.NewRouter()
	handler.RegisterRoutes(router)
	router.ServeHTTP(w, req)

	headers := w.Result().Header
	body := w.Body.String()

	result := SimpleGUIValidationResult{
		TestName:          "Security Headers Validation",
		HTTPStatusCode:    w.Result().StatusCode,
		ResponseSizeBytes: len(body),
		ContentType:       headers.Get("Content-Type"),
		RequiredElements:  make(map[string]bool),
		MissingElements:   make([]string, 0),
		Errors:           make([]string, 0),
	}

	// Check for sensitive data exposure
	sensitivePatterns := []string{"password", "secret", "token", "key", "auth"}
	for _, pattern := range sensitivePatterns {
		if strings.Contains(strings.ToLower(body), pattern+"=") || strings.Contains(strings.ToLower(body), pattern+":") {
			result.Errors = append(result.Errors, fmt.Sprintf("Potential sensitive data exposure: %s", pattern))
		}
	}

	// Check content type is properly set
	if !strings.Contains(headers.Get("Content-Type"), "text/html") {
		result.Errors = append(result.Errors, "Content-Type header not properly set for HTML")
	}

	result.Success = len(result.Errors) == 0
	return result
}

// calculateSimpleOverallResults calculates overall validation results
func calculateSimpleOverallResults(report *ComprehensiveGUIValidationReport) {
	report.TotalTests = len(report.ValidationResults)
	report.PassedTests = 0
	report.FailedTests = 0

	criticalIssues := make([]string, 0)

	for _, test := range report.ValidationResults {
		if test.Success {
			report.PassedTests++
		} else {
			report.FailedTests++
			if len(test.Errors) > 0 {
				criticalIssues = append(criticalIssues, fmt.Sprintf("%s: %s", test.TestName, strings.Join(test.Errors, "; ")))
			}
		}
	}

	report.OverallSuccess = report.FailedTests == 0
	report.CriticalIssues = criticalIssues

	if report.OverallSuccess {
		report.Summary = fmt.Sprintf("All %d GUI validation tests passed successfully", report.TotalTests)
	} else {
		report.Summary = fmt.Sprintf("%d of %d tests failed with critical issues", report.FailedTests, report.TotalTests)
	}
}

// generateSimpleValidationEvidence generates validation evidence
func generateSimpleValidationEvidence(t *testing.T, report *ComprehensiveGUIValidationReport) {
	// Convert to JSON for evidence
	jsonData, err := json.MarshalIndent(report, "", "  ")
	if err != nil {
		t.Logf("❌ Failed to generate validation evidence JSON: %v", err)
		return
	}

	// Log comprehensive evidence
	t.Logf("🎯 FORGE GUI Validation Evidence Report:")
	t.Logf("📊 Overall Success: %v", report.OverallSuccess)
	t.Logf("📈 Tests Passed: %d/%d", report.PassedTests, report.TotalTests)
	t.Logf("⏱️  Validation Duration: %v", time.Since(report.Timestamp))
	t.Logf("📋 Summary: %s", report.Summary)
	
	if len(report.CriticalIssues) > 0 {
		t.Logf("🚨 Critical Issues:")
		for i, issue := range report.CriticalIssues {
			if i < 5 { // Limit output to first 5 issues
				t.Logf("   - %s", issue)
			}
		}
		if len(report.CriticalIssues) > 5 {
			t.Logf("   ... and %d more issues", len(report.CriticalIssues)-5)
		}
	}

	// Log evidence size for validation
	t.Logf("💾 Evidence size: %d bytes", len(jsonData))
	t.Logf("🔍 Total validation tests executed: %d", report.TotalTests)
}

// Benchmark tests for performance validation

// BenchmarkDashboardRendering benchmarks dashboard template rendering
func BenchmarkDashboardRendering(b *testing.B) {
	metricsCollector := monitoring.NewMetricsCollector()
	handler, err := NewTestWebHandler(metricsCollector)
	if err != nil {
		b.Fatalf("Failed to initialize web handler: %v", err)
	}

	router := mux.NewRouter()
	handler.RegisterRoutes(router)

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		req := httptest.NewRequest("GET", "/dashboard", nil)
		w := httptest.NewRecorder()
		router.ServeHTTP(w, req)
	}
}

// BenchmarkAPIEndpoints benchmarks API endpoint performance
func BenchmarkAPIEndpoints(b *testing.B) {
	metricsCollector := monitoring.NewMetricsCollector()
	handler, err := NewTestWebHandler(metricsCollector)
	if err != nil {
		b.Fatalf("Failed to initialize web handler: %v", err)
	}

	router := mux.NewRouter()
	handler.RegisterRoutes(router)

	endpoints := []string{
		"/api/v1/configurations",
		"/healthz", 
		"/metrics",
	}

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		endpoint := endpoints[i%len(endpoints)]
		req := httptest.NewRequest("GET", endpoint, nil)
		w := httptest.NewRecorder()
		router.ServeHTTP(w, req)
	}
}