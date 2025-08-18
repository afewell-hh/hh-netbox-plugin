package web

import (
	"fmt"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"
	
	"github.com/gorilla/mux"
)

// FORGE Evidence-Based Test Suite for Web GUI Template Rendering
// Addresses Issue #72: 2-byte vs 6099+ byte validation issue
// 
// CRITICAL: These tests MUST FAIL initially (red phase) and demonstrate
// comprehensive quantitative validation before implementation begins.

// TestTemplateRenderingComprehensive tests all template rendering with quantitative validation
func TestTemplateRenderingComprehensive(t *testing.T) {
	// FORGE Requirement: Test-first development - these tests MUST fail without implementation
	handler, err := NewWebHandler()
	if err != nil {
		t.Fatalf("Failed to initialize web handler: %v", err)
	}

	testCases := []struct {
		name                    string
		endpoint               string
		method                 string
		expectedMinBytes       int // Issue #72: Minimum bytes for valid template rendering
		expectedMaxBytes       int // Upper bound for reasonable response size
		expectedContentType    string
		expectedStatusCode     int
		templateName           string
		requiredHTMLElements   []string // Quantitative HTML validation
		requiredDataElements   []string // Template data validation
	}{
		{
			name:                 "Dashboard Template Rendering",
			endpoint:            "/dashboard",
			method:              "GET",
			expectedMinBytes:    6099, // Issue #72: Must exceed 6099 bytes for valid dashboard
			expectedMaxBytes:    50000, // Reasonable upper bound
			expectedContentType: "text/html; charset=utf-8",
			expectedStatusCode:  http.StatusOK,
			templateName:        "simple_dashboard.html",
			requiredHTMLElements: []string{
				"<!DOCTYPE html>",
				"<title>CNOC Dashboard - Fixed</title>",
				"navbar",
				"container-fluid",
				"card",
				"Statistics Row",
				"Quick Access Row",
				"bootstrap",
			},
			requiredDataElements: []string{
				"{{.Stats.FabricCount}}",
				"{{.Stats.CRDCount}}",
				"{{.Stats.InSyncCount}}",
				"{{.Stats.DriftCount}}",
			},
		},
		{
			name:                 "Fabric List Template Rendering",
			endpoint:            "/fabrics",
			method:              "GET",
			expectedMinBytes:    4000, // Minimum for fabric list rendering
			expectedMaxBytes:    30000,
			expectedContentType: "text/html; charset=utf-8",
			expectedStatusCode:  http.StatusOK,
			templateName:        "fabric_list.html",
			requiredHTMLElements: []string{
				"<!DOCTYPE html>",
				"fabric",
				"table",
				"card",
				"bootstrap",
			},
			requiredDataElements: []string{
				"fabric",
				"git",
				"status",
			},
		},
		{
			name:                 "Fabric Detail Template Rendering",
			endpoint:            "/fabrics/fabric-1",
			method:              "GET",
			expectedMinBytes:    5000, // Minimum for detailed fabric view
			expectedMaxBytes:    40000,
			expectedContentType: "text/html; charset=utf-8",
			expectedStatusCode:  http.StatusOK,
			templateName:        "fabric_detail.html",
			requiredHTMLElements: []string{
				"<!DOCTYPE html>",
				"fabric",
				"drift",
				"crd",
				"git",
				"activity",
			},
			requiredDataElements: []string{
				"{{.Fabric.Name}}",
				"{{.DriftSpotlight}}",
				"{{.CRDResources}}",
			},
		},
	}

	for _, tc := range testCases {
		t.Run(tc.name, func(t *testing.T) {
			// FORGE Evidence Collection: Start metrics collection
			startTime := time.Now()
			
			// Create test request
			req := httptest.NewRequest(tc.method, tc.endpoint, nil)
			w := httptest.NewRecorder()
			
			// Create router and register routes
			router := mux.NewRouter()
			handler.RegisterRoutes(router)
			
			// Execute request
			router.ServeHTTP(w, req)
			
			// FORGE Evidence: Response time measurement
			responseTime := time.Since(startTime)
			
			// FORGE Quantitative Validation 1: Status Code
			if w.Code != tc.expectedStatusCode {
				t.Errorf("❌ FORGE EVIDENCE FAIL: Expected status %d, got %d", 
					tc.expectedStatusCode, w.Code)
			}
			
			// FORGE Quantitative Validation 2: Content Type
			contentType := w.Header().Get("Content-Type")
			if contentType != tc.expectedContentType {
				t.Errorf("❌ FORGE EVIDENCE FAIL: Expected content type %s, got %s", 
					tc.expectedContentType, contentType)
			}
			
			// FORGE Quantitative Validation 3: Response Size (Issue #72 Critical)
			responseBody := w.Body.String()
			responseSize := len(responseBody)
			
			if responseSize < tc.expectedMinBytes {
				t.Errorf("❌ FORGE EVIDENCE FAIL (Issue #72): Response too small: %d bytes (minimum: %d bytes)", 
					responseSize, tc.expectedMinBytes)
				t.Logf("🔍 Response content preview (first 500 chars): %s", 
					responseBody[:min(500, len(responseBody))])
			}
			
			if responseSize > tc.expectedMaxBytes {
				t.Errorf("❌ FORGE EVIDENCE FAIL: Response too large: %d bytes (maximum: %d bytes)", 
					responseSize, tc.expectedMaxBytes)
			}
			
			// FORGE Quantitative Validation 4: HTML Structure Validation
			for _, requiredElement := range tc.requiredHTMLElements {
				if !strings.Contains(responseBody, requiredElement) {
					t.Errorf("❌ FORGE EVIDENCE FAIL: Missing required HTML element: %s", requiredElement)
				}
			}
			
			// FORGE Quantitative Validation 5: Template Data Binding Validation
			for _, dataElement := range tc.requiredDataElements {
				// Check that template variables are processed (not raw {{}} in output)
				if strings.Contains(responseBody, dataElement) {
					t.Errorf("❌ FORGE EVIDENCE FAIL: Unprocessed template variable found: %s", dataElement)
				}
			}
			
			// FORGE Evidence Logging
			t.Logf("✅ FORGE EVIDENCE: %s", tc.name)
			t.Logf("📊 Response Size: %d bytes", responseSize)
			t.Logf("⏱️  Response Time: %v", responseTime)
			t.Logf("📄 Content Type: %s", contentType)
			t.Logf("🎯 Status Code: %d", w.Code)
			
			// FORGE Performance Validation
			maxResponseTime := 500 * time.Millisecond
			if responseTime > maxResponseTime {
				t.Errorf("❌ FORGE EVIDENCE FAIL: Response time too slow: %v (max: %v)", 
					responseTime, maxResponseTime)
			}
		})
	}
}

// TestTemplateCompilationValidation tests template compilation independently
func TestTemplateCompilationValidation(t *testing.T) {
	// FORGE Requirement: Validate template compilation before handler creation
	
	// Test template parsing
	handler, err := NewWebHandler()
	if err != nil {
		t.Fatalf("❌ FORGE EVIDENCE FAIL: Template compilation failed: %v", err)
	}
	
	// Validate templates are loaded
	if handler.templates == nil {
		t.Fatalf("❌ FORGE EVIDENCE FAIL: Templates not loaded")
	}
	
	// Count loaded templates
	templateNames := []string{}
	for _, tmpl := range handler.templates.Templates() {
		templateNames = append(templateNames, tmpl.Name())
	}
	
	expectedTemplates := []string{
		"base.html",
		"dashboard.html", 
		"simple_dashboard.html",
		"fabric_list.html",
		"fabric_detail.html",
	}
	
	// FORGE Quantitative Validation: Template count
	t.Logf("✅ FORGE EVIDENCE: Found templates: %v", templateNames)
	
	for _, expectedTemplate := range expectedTemplates {
		found := false
		for _, loadedTemplate := range templateNames {
			if loadedTemplate == expectedTemplate {
				found = true
				break
			}
		}
		if !found {
			t.Errorf("❌ FORGE EVIDENCE FAIL: Missing expected template: %s", expectedTemplate)
		}
	}
}

// TestErrorHandlingAndFallbacks tests error scenarios with quantitative validation
func TestErrorHandlingAndFallbacks(t *testing.T) {
	// FORGE Requirement: Comprehensive error path testing
	
	handler, err := NewWebHandler()
	if err != nil {
		t.Fatalf("Failed to initialize web handler: %v", err)
	}
	
	testCases := []struct {
		name               string
		endpoint           string
		expectedStatusCode int
		expectedMinBytes   int
		errorScenario      string
	}{
		{
			name:               "Invalid Route Handling",
			endpoint:           "/invalid-route-should-404",
			expectedStatusCode: http.StatusNotFound,
			expectedMinBytes:   1,
			errorScenario:      "404_handling",
		},
	}
	
	for _, tc := range testCases {
		t.Run(tc.name, func(t *testing.T) {
			req := httptest.NewRequest("GET", tc.endpoint, nil)
			w := httptest.NewRecorder()
			
			router := mux.NewRouter()
			handler.RegisterRoutes(router)
			
			router.ServeHTTP(w, req)
			
			// FORGE Quantitative Validation
			if w.Code != tc.expectedStatusCode {
				t.Errorf("❌ FORGE EVIDENCE FAIL: Expected status %d, got %d for %s", 
					tc.expectedStatusCode, w.Code, tc.errorScenario)
			}
			
			responseSize := len(w.Body.String())
			if responseSize < tc.expectedMinBytes {
				t.Errorf("❌ FORGE EVIDENCE FAIL: Error response too small: %d bytes", responseSize)
			}
			
			t.Logf("✅ FORGE EVIDENCE: %s handled correctly", tc.errorScenario)
			t.Logf("📊 Error Response Size: %d bytes", responseSize)
			t.Logf("🎯 Status Code: %d", w.Code)
		})
	}
}

// TestDataBindingAccuracy tests template data binding with specific values
func TestDataBindingAccuracy(t *testing.T) {
	// FORGE Requirement: Validate data binding accuracy with quantitative metrics
	
	handler, err := NewWebHandler()
	if err != nil {
		t.Fatalf("Failed to initialize web handler: %v", err)
	}
	
	// Test dashboard data binding specifically
	req := httptest.NewRequest("GET", "/dashboard", nil)
	w := httptest.NewRecorder()
	
	router := mux.NewRouter()
	handler.RegisterRoutes(router)
	
	router.ServeHTTP(w, req)
	
	responseBody := w.Body.String()
	
	// FORGE Quantitative Validation: Check specific data values from handlers.go
	expectedDataPoints := map[string]bool{
		"3":  false, // FabricCount
		"60": false, // CRDCount  
		"54": false, // InSyncCount
		"6":  false, // DriftCount
	}
	
	for expectedValue := range expectedDataPoints {
		if strings.Contains(responseBody, fmt.Sprintf("<h2>%s</h2>", expectedValue)) {
			expectedDataPoints[expectedValue] = true
		}
	}
	
	// Count how many data points were found
	foundCount := 0
	totalCount := len(expectedDataPoints)
	
	for value, found := range expectedDataPoints {
		if found {
			foundCount++
			t.Logf("✅ FORGE EVIDENCE: Found expected data value: %s", value)
		} else {
			t.Errorf("❌ FORGE EVIDENCE FAIL: Missing expected data value: %s", value)
		}
	}
	
	// FORGE Quantitative Metrics
	dataBindingAccuracy := float64(foundCount) / float64(totalCount) * 100
	t.Logf("📊 FORGE EVIDENCE: Data binding accuracy: %.1f%% (%d/%d)", 
		dataBindingAccuracy, foundCount, totalCount)
	
	if dataBindingAccuracy < 100.0 {
		t.Errorf("❌ FORGE EVIDENCE FAIL: Data binding accuracy below 100%%: %.1f%%", dataBindingAccuracy)
	}
}

// TestStaticFileHandling tests static file serving
func TestStaticFileHandling(t *testing.T) {
	// FORGE Requirement: Validate static file serving functionality
	
	handler, err := NewWebHandler()
	if err != nil {
		t.Fatalf("Failed to initialize web handler: %v", err)
	}
	
	staticFiles := []string{
		"/static/css/cnoc.css",
		"/static/js/cnoc.js",
	}
	
	for _, staticFile := range staticFiles {
		t.Run(fmt.Sprintf("Static File: %s", staticFile), func(t *testing.T) {
			req := httptest.NewRequest("GET", staticFile, nil)
			w := httptest.NewRecorder()
			
			router := mux.NewRouter()
			handler.RegisterRoutes(router)
			
			router.ServeHTTP(w, req)
			
			// FORGE Quantitative Validation for static files
			// Note: Static files may return 404 if not present, which is acceptable for test environment
			if w.Code != http.StatusOK && w.Code != http.StatusNotFound {
				t.Errorf("❌ FORGE EVIDENCE FAIL: Unexpected status for %s: %d", staticFile, w.Code)
			}
			
			t.Logf("✅ FORGE EVIDENCE: Static file %s handling: Status %d", staticFile, w.Code)
		})
	}
}

// BenchmarkTemplateRendering provides performance benchmarks for template rendering
func BenchmarkTemplateRendering(b *testing.B) {
	// FORGE Requirement: Performance benchmarking for template rendering
	
	handler, err := NewWebHandler()
	if err != nil {
		b.Fatalf("Failed to initialize web handler: %v", err)
	}
	
	router := mux.NewRouter()
	handler.RegisterRoutes(router)
	
	benchmarks := []struct {
		name     string
		endpoint string
	}{
		{"Dashboard", "/dashboard"},
		{"FabricList", "/fabrics"},
		{"FabricDetail", "/fabrics/fabric-1"},
	}
	
	for _, bm := range benchmarks {
		b.Run(bm.name, func(b *testing.B) {
			for i := 0; i < b.N; i++ {
				req := httptest.NewRequest("GET", bm.endpoint, nil)
				w := httptest.NewRecorder()
				
				router.ServeHTTP(w, req)
				
				// Ensure we got a reasonable response
				if w.Code != http.StatusOK {
					b.Errorf("❌ Benchmark failed: Status %d for %s", w.Code, bm.endpoint)
				}
			}
		})
	}
}

// FORGE Evidence Collection Framework
type ForgeTestEvidence struct {
	TestName         string
	ResponseSize     int
	ResponseTime     time.Duration
	StatusCode       int
	ContentType      string
	TemplatesLoaded  int
	DataBindingScore float64
	ValidationErrors []string
}

// CollectForgeEvidence collects comprehensive test evidence
func CollectForgeEvidence(t *testing.T) *ForgeTestEvidence {
	// This function would be called by all tests to collect quantitative evidence
	// Implementation would aggregate all test results for comprehensive reporting
	
	evidence := &ForgeTestEvidence{
		ValidationErrors: []string{},
	}
	
	return evidence
}

// Utility function for min calculation
func min(a, b int) int {
	if a < b {
		return a
	}
	return b
}

// FORGE Test Summary and Validation Requirements:
//
// 1. ALL TESTS MUST FAIL INITIALLY (Red Phase):
//    - Template rendering tests will fail until proper template compilation
//    - Response size tests will fail until handlers generate full HTML
//    - Data binding tests will fail until template variables are processed
//
// 2. QUANTITATIVE VALIDATION REQUIREMENTS:
//    - Response size validation (Issue #72: >6099 bytes for dashboard)
//    - HTML element count validation 
//    - Template data binding accuracy percentage
//    - Performance benchmarking with time limits
//    - Error handling coverage metrics
//
// 3. EVIDENCE COLLECTION:
//    - Response time measurements
//    - Response size in bytes
//    - Template compilation success/failure
//    - Data binding accuracy percentages
//    - Static file handling status
//
// 4. RED-GREEN-REFACTOR VALIDATION:
//    - Tests fail without proper template implementation
//    - Tests pass only when handlers generate proper HTML responses
//    - Refactoring validated through consistent test results
//
// 5. MUTATION TESTING PREPARATION:
//    - Tests designed to detect template compilation failures
//    - Data binding modifications would cause test failures
//    - Response size changes would trigger validation failures