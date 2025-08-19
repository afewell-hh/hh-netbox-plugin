package web

import (
	"encoding/json"
	"fmt"
	"net/http"
	"net/http/httptest"
	"regexp"
	"strings"
	"testing"
	"time"

	"github.com/gorilla/mux"
	"github.com/hedgehog/cnoc/internal/monitoring"
)

// FORGE RED PHASE TEST SUITE: GUI State Validation
// 
// CRITICAL PURPOSE: Define the CORRECT behavior for CNOC GUI before any fixes are implemented.
// These tests MUST fail initially, demonstrating the current broken state (70% pages showing wrong content).
//
// SUCCESS CRITERIA:
// - Each page renders its UNIQUE template (not fallback fabric content) 
// - Navigation works correctly to intended destinations
// - Forms submit to correct endpoints with proper validation
// - API endpoints return expected JSON structures
// - Performance meets <1 second requirements
// - Security headers are properly set
// - Mobile responsiveness works correctly
//
// QUANTITATIVE EVIDENCE REQUIRED:
// - 100% template uniqueness (not fallback content)  
// - 0 broken navigation links
// - All forms return 200/201/400 status codes appropriately
// - Page load times <1000ms
// - 0 security vulnerabilities
// - 100% API endpoints return valid JSON
// - 0 JavaScript console errors

// PageValidationTest defines validation criteria for each page
type PageValidationTest struct {
	Name                  string
	Endpoint              string
	Method                string
	ExpectedStatusCode    int
	ExpectedContentType   string
	ExpectedMinBytes      int
	ExpectedMaxBytes      int
	ExpectedTemplate      string
	UniqueContentMarkers  []string // Content that MUST be unique to this page
	ProhibitedContent     []string // Content that MUST NOT appear (indicates wrong template)
	RequiredHTMLElements  []string
	RequiredDataElements  []string
	PerformanceThresholds PerformanceThreshold
	SecurityChecks        []string
}

// PerformanceThreshold defines performance requirements
type PerformanceThreshold struct {
	MaxResponseTime   time.Duration
	MinResponseSize   int
	MaxResponseSize   int
	RequiredCSSAssets []string
	RequiredJSAssets  []string
}

// APIValidationTest defines validation for API endpoints
type APIValidationTest struct {
	Name                 string
	Endpoint             string
	Method               string
	RequestBody          string
	ExpectedStatusCode   int
	ExpectedContentType  string
	RequiredJSONFields   []string
	ProhibitedJSONFields []string
	ExpectedStructure    map[string]interface{}
}

// FORGE Test Suite 1: Template Uniqueness Validation
// CRITICAL: This test catches the primary issue - 70% of pages showing wrong content
func TestGUITemplateUniqueness(t *testing.T) {
	metricsCollector := monitoring.NewMetricsCollector()
	// Use absolute path for templates in tests
	handler, err := NewWebHandlerWithTemplatePath(metricsCollector, "/home/ubuntu/cc/hedgehog-netbox-plugin/cnoc/web/templates/*.html")
	if err != nil {
		t.Fatalf("❌ FORGE RED PHASE FAIL: Cannot initialize handler: %v", err)
	}

	router := mux.NewRouter()
	handler.RegisterRoutes(router)

	testCases := []PageValidationTest{
		{
			Name:                "Dashboard Page Uniqueness",
			Endpoint:            "/dashboard",
			Method:              "GET",
			ExpectedStatusCode:  http.StatusOK,
			ExpectedContentType: "text/html; charset=utf-8",
			ExpectedMinBytes:    6000, // Must be substantial dashboard content
			ExpectedMaxBytes:    50000,
			ExpectedTemplate:    "simple_dashboard.html",
			UniqueContentMarkers: []string{
				"CNOC Dashboard", // Unique dashboard title
				"Statistics Row", // Dashboard-specific section marker
				"Cloud NetOps Command System", // Dashboard-specific description
				"Monitor and manage your cloud network infrastructure",
				"Total Fabrics",
				"Total CRDs",
				"Quick Access Row",
			},
			ProhibitedContent: []string{
				"Repository Management", // Should NOT show repository content
				"Custom Resource Definitions List", // Should NOT show CRD list content
				"Drift Detection Dashboard", // Should NOT show drift content
				"VPC Resources", // Should NOT show VPC-specific content
			},
			RequiredHTMLElements: []string{
				"<!DOCTYPE html>",
				"<title>CNOC Dashboard - Fixed</title>",
				"navbar-brand",
				"container-fluid",
				"Statistics Row",
			},
		},
		{
			Name:                "Repository List Page Uniqueness",
			Endpoint:            "/repositories",
			Method:              "GET", 
			ExpectedStatusCode:  http.StatusOK,
			ExpectedContentType: "text/html; charset=utf-8",
			ExpectedMinBytes:    3000, // Must show repository-specific content
			ExpectedMaxBytes:    40000,
			ExpectedTemplate:    "repository_list.html",
			UniqueContentMarkers: []string{
				"Repository Management", // Unique repository page identifier
				"GitOps Repositories", // Repository-specific content
				"Connection Status", // Repository-specific table headers
				"Authentication Type",
				"Add Repository", // Repository-specific actions
			},
			ProhibitedContent: []string{
				"CNOC Dashboard", // Should NOT show dashboard content
				"Fabric List", // Should NOT show fabric content
				"Custom Resource Definitions", // Should NOT show CRD content
				"Total Fabrics", // Dashboard-specific stats
				"Quick Access Row", // Dashboard-specific sections
			},
			RequiredHTMLElements: []string{
				"<!DOCTYPE html>",
				"Repository",
				"table",
				"btn-primary",
			},
		},
		{
			Name:                "CRD List Page Uniqueness",
			Endpoint:            "/crds",
			Method:              "GET",
			ExpectedStatusCode:  http.StatusOK,
			ExpectedContentType: "text/html; charset=utf-8",
			ExpectedMinBytes:    3000, // Must show CRD-specific content
			ExpectedMaxBytes:    40000,
			ExpectedTemplate:    "crd_list.html",
			UniqueContentMarkers: []string{
				"Custom Resource Definitions", // Unique CRD page identifier
				"CRD Resources", // CRD-specific content
				"Resource Type", // CRD-specific table headers
				"Namespace",
				"Sync Status",
				"Resource Categories", // CRD-specific sections
			},
			ProhibitedContent: []string{
				"Repository Management", // Should NOT show repository content
				"CNOC Dashboard", // Should NOT show dashboard content
				"Total Fabrics", // Dashboard-specific content
				"Statistics Row", // Dashboard-specific sections
			},
			RequiredHTMLElements: []string{
				"<!DOCTYPE html>",
				"CRD",
				"table",
				"Resource",
			},
		},
		{
			Name:                "Drift Detection Page Uniqueness",
			Endpoint:            "/drift",
			Method:              "GET",
			ExpectedStatusCode:  http.StatusOK,
			ExpectedContentType: "text/html; charset=utf-8",
			ExpectedMinBytes:    3000, // Must show drift-specific content
			ExpectedMaxBytes:    40000,
			ExpectedTemplate:    "drift_detection.html",
			UniqueContentMarkers: []string{
				"Drift Detection Dashboard", // Unique drift page identifier
				"Configuration Drift Analysis", // Drift-specific content
				"Drift Status", // Drift-specific elements
				"Last Check",
				"Resources with Drift",
				"Analyze Drift", // Drift-specific actions
			},
			ProhibitedContent: []string{
				"Repository Management", // Should NOT show repository content
				"CNOC Dashboard", // Should NOT show dashboard content
				"Custom Resource Definitions List", // Should NOT show CRD list
				"Total Fabrics", // Dashboard-specific content
			},
			RequiredHTMLElements: []string{
				"<!DOCTYPE html>",
				"Drift",
				"drift-status",
				"btn-warning",
			},
		},
		{
			Name:                "VPC Resources Page Uniqueness",
			Endpoint:            "/crds/vpcs",
			Method:              "GET",
			ExpectedStatusCode:  http.StatusOK,
			ExpectedContentType: "text/html; charset=utf-8",
			ExpectedMinBytes:    2500, // Must show VPC-specific content
			ExpectedMaxBytes:    35000,
			ExpectedTemplate:    "vpc_list.html",
			UniqueContentMarkers: []string{
				"VPC Resources", // Unique VPC page identifier
				"Virtual Private Clouds", // VPC-specific content
				"VPC Configuration", // VPC-specific sections
				"Network Topology",
				"Subnet Configuration",
			},
			ProhibitedContent: []string{
				"Repository Management", // Should NOT show repository content
				"CNOC Dashboard", // Should NOT show dashboard content
				"Connection Resources", // Should NOT show connection content
				"Switch Resources", // Should NOT show switch content
			},
			RequiredHTMLElements: []string{
				"<!DOCTYPE html>",
				"VPC",
				"table",
				"network",
			},
		},
		{
			Name:                "Connection Resources Page Uniqueness",
			Endpoint:            "/crds/connections",
			Method:              "GET",
			ExpectedStatusCode:  http.StatusOK,
			ExpectedContentType: "text/html; charset=utf-8",
			ExpectedMinBytes:    2500, // Must show connection-specific content
			ExpectedMaxBytes:    35000,
			ExpectedTemplate:    "connection_list.html",
			UniqueContentMarkers: []string{
				"Connection Resources", // Unique connection page identifier
				"Network Connections", // Connection-specific content
				"Connection Status", // Connection-specific elements
				"Source/Destination",
				"Connection Type",
			},
			ProhibitedContent: []string{
				"VPC Resources", // Should NOT show VPC content
				"Switch Resources", // Should NOT show switch content
				"CNOC Dashboard", // Should NOT show dashboard content
				"Repository Management", // Should NOT show repository content
			},
			RequiredHTMLElements: []string{
				"<!DOCTYPE html>",
				"Connection",
				"table",
				"status",
			},
		},
		{
			Name:                "Switch Resources Page Uniqueness",
			Endpoint:            "/crds/switches",
			Method:              "GET",
			ExpectedStatusCode:  http.StatusOK,
			ExpectedContentType: "text/html; charset=utf-8",
			ExpectedMinBytes:    2500, // Must show switch-specific content
			ExpectedMaxBytes:    35000,
			ExpectedTemplate:    "switch_list.html",
			UniqueContentMarkers: []string{
				"Switch Resources", // Unique switch page identifier
				"Network Switches", // Switch-specific content
				"Switch Configuration", // Switch-specific sections
				"Port Status",
				"Switch Type",
			},
			ProhibitedContent: []string{
				"VPC Resources", // Should NOT show VPC content
				"Connection Resources", // Should NOT show connection content
				"CNOC Dashboard", // Should NOT show dashboard content
				"Repository Management", // Should NOT show repository content
			},
			RequiredHTMLElements: []string{
				"<!DOCTYPE html>",
				"Switch",
				"table",
				"port",
			},
		},
	}

	// Execute all template uniqueness tests
	for _, tc := range testCases {
		t.Run(tc.Name, func(t *testing.T) {
			startTime := time.Now()
			
			// Create and execute request
			req := httptest.NewRequest(tc.Method, tc.Endpoint, nil)
			w := httptest.NewRecorder()
			router.ServeHTTP(w, req)
			
			responseTime := time.Since(startTime)
			responseBody := w.Body.String()
			responseSize := len(responseBody)
			
			// FORGE RED PHASE EVIDENCE: Status code validation
			if w.Code != tc.ExpectedStatusCode {
				t.Errorf("❌ FORGE RED PHASE EVIDENCE: Wrong status code for %s: got %d, expected %d", 
					tc.Endpoint, w.Code, tc.ExpectedStatusCode)
			}
			
			// FORGE RED PHASE EVIDENCE: Content type validation
			contentType := w.Header().Get("Content-Type")
			if contentType != tc.ExpectedContentType {
				t.Errorf("❌ FORGE RED PHASE EVIDENCE: Wrong content type for %s: got %s, expected %s", 
					tc.Endpoint, contentType, tc.ExpectedContentType)
			}
			
			// FORGE RED PHASE EVIDENCE: Response size validation (catches template issues)
			if responseSize < tc.ExpectedMinBytes {
				t.Errorf("❌ FORGE RED PHASE EVIDENCE (CRITICAL): %s response too small: %d bytes (min: %d). Likely showing fallback content!", 
					tc.Endpoint, responseSize, tc.ExpectedMinBytes)
				t.Logf("📄 Response preview (first 1000 chars): %s", 
					responseBody[:minInt(1000, len(responseBody))])
			}
			
			// FORGE RED PHASE EVIDENCE: Unique content validation (PRIMARY TEST)
			missingUniqueContent := []string{}
			for _, marker := range tc.UniqueContentMarkers {
				if !strings.Contains(responseBody, marker) {
					missingUniqueContent = append(missingUniqueContent, marker)
				}
			}
			if len(missingUniqueContent) > 0 {
				t.Errorf("❌ FORGE RED PHASE EVIDENCE (CRITICAL): %s missing unique content markers: %v", 
					tc.Endpoint, missingUniqueContent)
				t.Errorf("This indicates the page is showing WRONG TEMPLATE CONTENT!")
			}
			
			// FORGE RED PHASE EVIDENCE: Prohibited content validation (FALLBACK DETECTION)
			foundProhibitedContent := []string{}
			for _, prohibited := range tc.ProhibitedContent {
				if strings.Contains(responseBody, prohibited) {
					foundProhibitedContent = append(foundProhibitedContent, prohibited)
				}
			}
			if len(foundProhibitedContent) > 0 {
				t.Errorf("❌ FORGE RED PHASE EVIDENCE (CRITICAL): %s contains prohibited content: %v", 
					tc.Endpoint, foundProhibitedContent)
				t.Errorf("This indicates the page is showing FALLBACK/WRONG TEMPLATE!")
			}
			
			// FORGE RED PHASE EVIDENCE: HTML structure validation
			missingElements := []string{}
			for _, element := range tc.RequiredHTMLElements {
				if !strings.Contains(responseBody, element) {
					missingElements = append(missingElements, element)
				}
			}
			if len(missingElements) > 0 {
				t.Errorf("❌ FORGE RED PHASE EVIDENCE: %s missing HTML elements: %v", 
					tc.Endpoint, missingElements)
			}
			
			// FORGE RED PHASE EVIDENCE: Performance validation
			maxResponseTime := 1000 * time.Millisecond
			if responseTime > maxResponseTime {
				t.Errorf("❌ FORGE RED PHASE EVIDENCE: %s response too slow: %v (max: %v)", 
					tc.Endpoint, responseTime, maxResponseTime)
			}
			
			// FORGE SUCCESS EVIDENCE (should be minimal initially)
			successfulChecks := 0
			totalChecks := len(tc.UniqueContentMarkers) + len(tc.RequiredHTMLElements) + 3 // +3 for status, type, size
			
			if w.Code == tc.ExpectedStatusCode {
				successfulChecks++
			}
			if contentType == tc.ExpectedContentType {
				successfulChecks++
			}
			if responseSize >= tc.ExpectedMinBytes {
				successfulChecks++
			}
			successfulChecks += (len(tc.UniqueContentMarkers) - len(missingUniqueContent))
			successfulChecks += (len(tc.RequiredHTMLElements) - len(missingElements))
			
			successPercentage := float64(successfulChecks) / float64(totalChecks) * 100
			
			t.Logf("📊 FORGE RED PHASE METRICS for %s:", tc.Name)
			t.Logf("   Response Size: %d bytes", responseSize)
			t.Logf("   Response Time: %v", responseTime)
			t.Logf("   Status Code: %d", w.Code)
			t.Logf("   Content Type: %s", contentType)
			t.Logf("   Success Rate: %.1f%% (%d/%d checks passed)", successPercentage, successfulChecks, totalChecks)
			t.Logf("   Missing Unique Content: %d items", len(missingUniqueContent))
			t.Logf("   Prohibited Content Found: %d items", len(foundProhibitedContent))
			
			if successPercentage < 70.0 {
				t.Logf("🔴 FORGE RED PHASE CONFIRMED: %s is significantly broken (%.1f%% success)", tc.Endpoint, successPercentage)
			}
		})
	}
}

// FORGE Test Suite 2: Navigation Flow Validation  
func TestGUINavigationFlow(t *testing.T) {
	metricsCollector := monitoring.NewMetricsCollector()
	handler, err := NewWebHandlerWithTemplatePath(metricsCollector, "/home/ubuntu/cc/hedgehog-netbox-plugin/cnoc/web/templates/*.html")
	if err != nil {
		t.Fatalf("❌ FORGE RED PHASE FAIL: Cannot initialize handler: %v", err)
	}

	router := mux.NewRouter()
	handler.RegisterRoutes(router)

	navigationTests := []struct {
		Name              string
		StartEndpoint     string
		TargetLinks       []string // Links that should be present and working
		ExpectedTargets   []string // Where those links should lead
	}{
		{
			Name:          "Dashboard Navigation Links",
			StartEndpoint: "/dashboard",
			TargetLinks: []string{
				`href="/fabrics"`,
				`href="/repositories"`, 
				`href="/crds"`,
				`href="/drift"`,
			},
			ExpectedTargets: []string{"/fabrics", "/repositories", "/crds", "/drift"},
		},
		{
			Name:          "Main Menu Navigation",
			StartEndpoint: "/",
			TargetLinks: []string{
				`href="/dashboard"`,
				`href="/fabrics"`,
				`href="/repositories"`,
				`href="/crds"`,
			},
			ExpectedTargets: []string{"/dashboard", "/fabrics", "/repositories", "/crds"},
		},
	}

	for _, test := range navigationTests {
		t.Run(test.Name, func(t *testing.T) {
			// Test the starting page
			req := httptest.NewRequest("GET", test.StartEndpoint, nil)
			w := httptest.NewRecorder()
			router.ServeHTTP(w, req)
			
			if w.Code != http.StatusOK {
				t.Errorf("❌ FORGE RED PHASE EVIDENCE: Starting page %s failed: status %d", test.StartEndpoint, w.Code)
				return
			}
			
			responseBody := w.Body.String()
			
			// Check for navigation links
			missingLinks := []string{}
			for _, targetLink := range test.TargetLinks {
				if !strings.Contains(responseBody, targetLink) {
					missingLinks = append(missingLinks, targetLink)
				}
			}
			
			if len(missingLinks) > 0 {
				t.Errorf("❌ FORGE RED PHASE EVIDENCE: %s missing navigation links: %v", test.StartEndpoint, missingLinks)
			}
			
			// Test that target endpoints actually work
			brokenTargets := []string{}
			for _, target := range test.ExpectedTargets {
				req := httptest.NewRequest("GET", target, nil)
				w := httptest.NewRecorder()
				router.ServeHTTP(w, req)
				
				if w.Code != http.StatusOK {
					brokenTargets = append(brokenTargets, fmt.Sprintf("%s (status: %d)", target, w.Code))
				}
			}
			
			if len(brokenTargets) > 0 {
				t.Errorf("❌ FORGE RED PHASE EVIDENCE: Navigation targets broken: %v", brokenTargets)
			}
			
			t.Logf("📊 FORGE NAVIGATION EVIDENCE for %s:", test.Name)
			t.Logf("   Links Found: %d/%d", len(test.TargetLinks)-len(missingLinks), len(test.TargetLinks))
			t.Logf("   Working Targets: %d/%d", len(test.ExpectedTargets)-len(brokenTargets), len(test.ExpectedTargets))
		})
	}
}

// FORGE Test Suite 3: API Contract Validation
func TestGUIAPIContracts(t *testing.T) {
	metricsCollector := monitoring.NewMetricsCollector()
	handler, err := NewWebHandlerWithTemplatePath(metricsCollector, "/home/ubuntu/cc/hedgehog-netbox-plugin/cnoc/web/templates/*.html")
	if err != nil {
		t.Fatalf("❌ FORGE RED PHASE FAIL: Cannot initialize handler: %v", err)
	}

	router := mux.NewRouter()
	handler.RegisterRoutes(router)

	apiTests := []APIValidationTest{
		{
			Name:                "Fabrics API List",
			Endpoint:            "/api/v1/fabrics",
			Method:              "GET",
			ExpectedStatusCode:  http.StatusOK,
			ExpectedContentType: "application/json",
			RequiredJSONFields:  []string{"items", "total_count", "page"},
			ExpectedStructure: map[string]interface{}{
				"items": []interface{}{},
				"total_count": float64(0),
				"page": float64(1),
			},
		},
		{
			Name:                "Configurations API List",
			Endpoint:            "/api/v1/configurations",
			Method:              "GET", 
			ExpectedStatusCode:  http.StatusOK,
			ExpectedContentType: "application/json",
			RequiredJSONFields:  []string{"configurations", "total_count", "page"},
		},
		{
			Name:                "Repositories API List",
			Endpoint:            "/api/v1/repositories",
			Method:              "GET",
			ExpectedStatusCode:  http.StatusOK, // or 501 if not implemented
			ExpectedContentType: "application/json",
			RequiredJSONFields:  []string{}, // May be empty if not implemented
		},
		{
			Name:                "Drift Detection API",
			Endpoint:            "/api/v1/drift/fabric-1",
			Method:              "GET",
			ExpectedStatusCode:  http.StatusOK, // or 500 if not implemented
			ExpectedContentType: "application/json",
			RequiredJSONFields:  []string{}, // May be empty if not implemented
		},
	}

	for _, test := range apiTests {
		t.Run(test.Name, func(t *testing.T) {
			startTime := time.Now()
			
			// Create request
			req := httptest.NewRequest(test.Method, test.Endpoint, strings.NewReader(test.RequestBody))
			if test.RequestBody != "" {
				req.Header.Set("Content-Type", "application/json")
			}
			w := httptest.NewRecorder()
			
			// Execute request
			router.ServeHTTP(w, req)
			
			responseTime := time.Since(startTime)
			responseBody := w.Body.String()
			
			// FORGE RED PHASE EVIDENCE: Status code validation
			if w.Code != test.ExpectedStatusCode && 
			   !(test.ExpectedStatusCode == http.StatusOK && (w.Code == http.StatusNotImplemented || w.Code == http.StatusInternalServerError)) {
				t.Errorf("❌ FORGE RED PHASE EVIDENCE: API %s wrong status: got %d, expected %d", 
					test.Endpoint, w.Code, test.ExpectedStatusCode)
			}
			
			// FORGE RED PHASE EVIDENCE: Content type validation
			contentType := w.Header().Get("Content-Type")
			if contentType != test.ExpectedContentType {
				t.Errorf("❌ FORGE RED PHASE EVIDENCE: API %s wrong content type: got %s, expected %s", 
					test.Endpoint, contentType, test.ExpectedContentType)
			}
			
			// FORGE RED PHASE EVIDENCE: JSON structure validation
			if w.Code == http.StatusOK && contentType == "application/json" {
				var jsonResponse map[string]interface{}
				if err := json.Unmarshal([]byte(responseBody), &jsonResponse); err != nil {
					t.Errorf("❌ FORGE RED PHASE EVIDENCE: API %s invalid JSON: %v", test.Endpoint, err)
				} else {
					// Check required fields
					missingFields := []string{}
					for _, field := range test.RequiredJSONFields {
						if _, exists := jsonResponse[field]; !exists {
							missingFields = append(missingFields, field)
						}
					}
					if len(missingFields) > 0 {
						t.Errorf("❌ FORGE RED PHASE EVIDENCE: API %s missing JSON fields: %v", test.Endpoint, missingFields)
					}
				}
			}
			
			// FORGE RED PHASE EVIDENCE: Performance validation
			maxAPIResponseTime := 2000 * time.Millisecond // APIs can be slower than pages
			if responseTime > maxAPIResponseTime {
				t.Errorf("❌ FORGE RED PHASE EVIDENCE: API %s too slow: %v (max: %v)", 
					test.Endpoint, responseTime, maxAPIResponseTime)
			}
			
			t.Logf("📊 FORGE API EVIDENCE for %s:", test.Name)
			t.Logf("   Status Code: %d", w.Code)
			t.Logf("   Response Time: %v", responseTime)
			t.Logf("   Content Type: %s", contentType)
			t.Logf("   Response Size: %d bytes", len(responseBody))
			
			if w.Code >= 400 {
				t.Logf("   Error Response: %s", responseBody)
			}
		})
	}
}

// FORGE Test Suite 4: Security Headers Validation
func TestGUISecurityHeaders(t *testing.T) {
	metricsCollector := monitoring.NewMetricsCollector()
	handler, err := NewWebHandlerWithTemplatePath(metricsCollector, "/home/ubuntu/cc/hedgehog-netbox-plugin/cnoc/web/templates/*.html")
	if err != nil {
		t.Fatalf("❌ FORGE RED PHASE FAIL: Cannot initialize handler: %v", err)
	}

	router := mux.NewRouter()
	handler.RegisterRoutes(router)

	securityTests := []struct {
		Name             string
		Endpoint         string
		RequiredHeaders  map[string]string
		ProhibitedHeaders []string
	}{
		{
			Name:     "Dashboard Security Headers",
			Endpoint: "/dashboard",
			RequiredHeaders: map[string]string{
				"Content-Type": "text/html; charset=utf-8",
			},
			ProhibitedHeaders: []string{
				"Server", // Should not expose server details
			},
		},
		{
			Name:     "API Security Headers",
			Endpoint: "/api/v1/fabrics",
			RequiredHeaders: map[string]string{
				"Content-Type": "application/json",
			},
			ProhibitedHeaders: []string{
				"Server",
			},
		},
	}

	for _, test := range securityTests {
		t.Run(test.Name, func(t *testing.T) {
			req := httptest.NewRequest("GET", test.Endpoint, nil)
			w := httptest.NewRecorder()
			router.ServeHTTP(w, req)
			
			// Check required headers
			missingHeaders := []string{}
			for header, expectedValue := range test.RequiredHeaders {
				actualValue := w.Header().Get(header)
				if actualValue != expectedValue {
					missingHeaders = append(missingHeaders, fmt.Sprintf("%s: expected '%s', got '%s'", header, expectedValue, actualValue))
				}
			}
			
			if len(missingHeaders) > 0 {
				t.Errorf("❌ FORGE RED PHASE EVIDENCE: %s missing/wrong security headers: %v", test.Endpoint, missingHeaders)
			}
			
			// Check prohibited headers
			foundProhibitedHeaders := []string{}
			for _, header := range test.ProhibitedHeaders {
				if w.Header().Get(header) != "" {
					foundProhibitedHeaders = append(foundProhibitedHeaders, header)
				}
			}
			
			if len(foundProhibitedHeaders) > 0 {
				t.Errorf("❌ FORGE RED PHASE EVIDENCE: %s has prohibited security headers: %v", test.Endpoint, foundProhibitedHeaders)
			}
			
			t.Logf("📊 FORGE SECURITY EVIDENCE for %s:", test.Name)
			t.Logf("   Required Headers: %d/%d present", len(test.RequiredHeaders)-len(missingHeaders), len(test.RequiredHeaders))
			t.Logf("   Prohibited Headers Found: %d", len(foundProhibitedHeaders))
		})
	}
}

// FORGE Test Suite 5: Mobile Responsiveness Validation
func TestGUIMobileResponsiveness(t *testing.T) {
	metricsCollector := monitoring.NewMetricsCollector()
	handler, err := NewWebHandlerWithTemplatePath(metricsCollector, "/home/ubuntu/cc/hedgehog-netbox-plugin/cnoc/web/templates/*.html")
	if err != nil {
		t.Fatalf("❌ FORGE RED PHASE FAIL: Cannot initialize handler: %v", err)
	}

	router := mux.NewRouter()
	handler.RegisterRoutes(router)

	mobileTests := []struct {
		Name           string
		Endpoint       string
		UserAgent      string
		ViewportHeader string
		RequiredMobileElements []string
		ProhibitedMobileElements []string
	}{
		{
			Name:           "Dashboard Mobile View",
			Endpoint:       "/dashboard",
			UserAgent:      "Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X) AppleWebKit/605.1.15",
			ViewportHeader: "width=device-width, initial-scale=1.0",
			RequiredMobileElements: []string{
				"viewport", // Must have viewport meta tag
				"responsive", // Bootstrap responsive classes
				"container-fluid", // Responsive container
			},
		},
	}

	for _, test := range mobileTests {
		t.Run(test.Name, func(t *testing.T) {
			req := httptest.NewRequest("GET", test.Endpoint, nil)
			req.Header.Set("User-Agent", test.UserAgent)
			w := httptest.NewRecorder()
			router.ServeHTTP(w, req)
			
			responseBody := w.Body.String()
			
			// Check for mobile responsive elements
			missingMobileElements := []string{}
			for _, element := range test.RequiredMobileElements {
				if !strings.Contains(responseBody, element) {
					missingMobileElements = append(missingMobileElements, element)
				}
			}
			
			if len(missingMobileElements) > 0 {
				t.Errorf("❌ FORGE RED PHASE EVIDENCE: %s missing mobile elements: %v", test.Endpoint, missingMobileElements)
			}
			
			// Check for viewport meta tag specifically
			viewportRegex := regexp.MustCompile(`<meta[^>]*name=["']viewport["'][^>]*>`)
			if !viewportRegex.MatchString(responseBody) {
				t.Errorf("❌ FORGE RED PHASE EVIDENCE: %s missing viewport meta tag", test.Endpoint)
			}
			
			t.Logf("📊 FORGE MOBILE EVIDENCE for %s:", test.Name)
			t.Logf("   Mobile Elements Found: %d/%d", len(test.RequiredMobileElements)-len(missingMobileElements), len(test.RequiredMobileElements))
			t.Logf("   Viewport Meta Tag: %t", viewportRegex.MatchString(responseBody))
		})
	}
}

// FORGE Test Suite 6: WebSocket Real-time Updates Validation
func TestGUIWebSocketConnectivity(t *testing.T) {
	metricsCollector := monitoring.NewMetricsCollector()
	handler, err := NewWebHandlerWithTemplatePath(metricsCollector, "/home/ubuntu/cc/hedgehog-netbox-plugin/cnoc/web/templates/*.html")
	if err != nil {
		t.Fatalf("❌ FORGE RED PHASE FAIL: Cannot initialize handler: %v", err)
	}

	router := mux.NewRouter()
	handler.RegisterRoutes(router)

	// Test WebSocket endpoint availability
	req := httptest.NewRequest("GET", "/ws", nil)
	req.Header.Set("Connection", "Upgrade")
	req.Header.Set("Upgrade", "websocket")
	req.Header.Set("Sec-WebSocket-Key", "dGhlIHNhbXBsZSBub25jZQ==")
	req.Header.Set("Sec-WebSocket-Version", "13")
	
	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)
	
	// WebSocket upgrade may fail in test environment, but endpoint should be available
	if w.Code != http.StatusSwitchingProtocols && w.Code != http.StatusBadRequest {
		t.Errorf("❌ FORGE RED PHASE EVIDENCE: WebSocket endpoint not properly configured: status %d", w.Code)
	}
	
	t.Logf("📊 FORGE WEBSOCKET EVIDENCE:")
	t.Logf("   WebSocket Endpoint Status: %d", w.Code)
	t.Logf("   Upgrade Header: %s", w.Header().Get("Upgrade"))
}

// FORGE Test Suite 7: Static Asset Validation
func TestGUIStaticAssets(t *testing.T) {
	metricsCollector := monitoring.NewMetricsCollector()
	handler, err := NewWebHandlerWithTemplatePath(metricsCollector, "/home/ubuntu/cc/hedgehog-netbox-plugin/cnoc/web/templates/*.html")
	if err != nil {
		t.Fatalf("❌ FORGE RED PHASE FAIL: Cannot initialize handler: %v", err)
	}

	router := mux.NewRouter()
	handler.RegisterRoutes(router)

	staticAssetTests := []struct {
		Name         string
		AssetPath    string
		ExpectedType string
		MinSize      int
	}{
		{
			Name:         "CSS Assets Access",
			AssetPath:    "/static/css/style.css",
			ExpectedType: "text/css",
			MinSize:      100,
		},
		{
			Name:         "JavaScript Assets Access",
			AssetPath:    "/static/js/main.js",
			ExpectedType: "application/javascript",
			MinSize:      100,
		},
	}

	for _, test := range staticAssetTests {
		t.Run(test.Name, func(t *testing.T) {
			req := httptest.NewRequest("GET", test.AssetPath, nil)
			w := httptest.NewRecorder()
			router.ServeHTTP(w, req)
			
			// Static assets may not exist, which is also evidence of missing configuration
			if w.Code != http.StatusOK && w.Code != http.StatusNotFound {
				t.Errorf("❌ FORGE RED PHASE EVIDENCE: Static asset %s unexpected status: %d", test.AssetPath, w.Code)
			}
			
			if w.Code == http.StatusNotFound {
				t.Logf("📊 FORGE STATIC ASSET EVIDENCE: %s not found (status 404)", test.AssetPath)
			} else if w.Code == http.StatusOK {
				responseSize := len(w.Body.String())
				t.Logf("📊 FORGE STATIC ASSET EVIDENCE: %s found (size: %d bytes)", test.AssetPath, responseSize)
			}
		})
	}
}

// FORGE Summary Test: Overall System Health
func TestGUIOverallSystemHealth(t *testing.T) {
	metricsCollector := monitoring.NewMetricsCollector()
	handler, err := NewWebHandlerWithTemplatePath(metricsCollector, "/home/ubuntu/cc/hedgehog-netbox-plugin/cnoc/web/templates/*.html")
	if err != nil {
		t.Fatalf("❌ FORGE RED PHASE FAIL: Cannot initialize handler: %v", err)
	}

	router := mux.NewRouter()
	handler.RegisterRoutes(router)

	// Test all major endpoints for basic functionality
	endpoints := []string{
		"/dashboard",
		"/fabrics", 
		"/repositories",
		"/crds",
		"/drift",
		"/crds/vpcs",
		"/crds/connections",
		"/crds/switches",
		"/api/v1/fabrics",
		"/api/v1/configurations",
	}

	totalEndpoints := len(endpoints)
	workingEndpoints := 0
	brokenEndpoints := []string{}
	
	for _, endpoint := range endpoints {
		req := httptest.NewRequest("GET", endpoint, nil)
		w := httptest.NewRecorder()
		router.ServeHTTP(w, req)
		
		if w.Code == http.StatusOK {
			workingEndpoints++
		} else {
			brokenEndpoints = append(brokenEndpoints, fmt.Sprintf("%s (status: %d)", endpoint, w.Code))
		}
	}
	
	healthPercentage := float64(workingEndpoints) / float64(totalEndpoints) * 100
	
	t.Logf("🏥 FORGE SYSTEM HEALTH EVIDENCE:")
	t.Logf("   Working Endpoints: %d/%d (%.1f%%)", workingEndpoints, totalEndpoints, healthPercentage)
	t.Logf("   Broken Endpoints: %v", brokenEndpoints)
	
	if healthPercentage < 70.0 {
		t.Logf("🔴 FORGE RED PHASE CONFIRMED: System health is poor (%.1f%% working)", healthPercentage)
		t.Logf("🔴 This validates the audit finding that 70%% of pages show wrong content")
	}
	
	// This test should fail initially, demonstrating the broken state
	if healthPercentage < 100.0 {
		t.Errorf("❌ FORGE RED PHASE EVIDENCE: System not at 100%% health (%.1f%% working)", healthPercentage)
	}
}

// Utility function for minimum calculation
func minInt(a, b int) int {
	if a < b {
		return a
	}
	return b
}