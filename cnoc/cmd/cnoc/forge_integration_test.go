package main

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net/http"
	"strings"
	"testing"
	"time"

	"github.com/hedgehog/cnoc/internal/api/rest/dto"
	"github.com/hedgehog/cnoc/internal/web"
)

// FORGE Enhanced Integration Test Suite
// Builds upon existing integration_test.go with comprehensive FORGE validation
// Addresses Issue #72 with quantitative response validation

// ForgeIntegrationTestSuite provides comprehensive end-to-end validation
type ForgeIntegrationTestSuite struct {
	BaseURL           string
	Client            *http.Client
	TestStartTime     time.Time
	ResponseMetrics   []ForgeResponseMetric
	ValidationResults []ForgeValidationResult
}

// ForgeResponseMetric tracks quantitative response metrics
type ForgeResponseMetric struct {
	Endpoint      string        `json:"endpoint"`
	Method        string        `json:"method"`
	StatusCode    int           `json:"status_code"`
	ResponseSize  int           `json:"response_size_bytes"`
	ResponseTime  time.Duration `json:"response_time_ns"`
	ContentType   string        `json:"content_type"`
	IssuE72Check  bool          `json:"issue_72_check"`
	Issue72Passed bool          `json:"issue_72_passed"`
	Timestamp     time.Time     `json:"timestamp"`
}

// ForgeValidationResult tracks validation outcomes
type ForgeValidationResult struct {
	TestName      string  `json:"test_name"`
	ValidationID  string  `json:"validation_id"`
	Passed        bool    `json:"passed"`
	Expected      string  `json:"expected"`
	Actual        string  `json:"actual"`
	ErrorMessage  string  `json:"error_message"`
	Severity      string  `json:"severity"` // "critical", "high", "medium", "low"
	Timestamp     time.Time `json:"timestamp"`
}

// NewForgeIntegrationTestSuite creates new integration test suite
func NewForgeIntegrationTestSuite(baseURL string) *ForgeIntegrationTestSuite {
	return &ForgeIntegrationTestSuite{
		BaseURL:         baseURL,
		Client:          &http.Client{Timeout: 30 * time.Second},
		TestStartTime:   time.Now(),
		ResponseMetrics: []ForgeResponseMetric{},
		ValidationResults: []ForgeValidationResult{},
	}
}

// TestForgeIntegrationSuite runs the comprehensive FORGE integration test suite
func TestForgeIntegrationSuite(t *testing.T) {
	// FORGE Requirement: Comprehensive end-to-end testing with quantitative validation
	
	suite := NewForgeIntegrationTestSuite("http://localhost:8080")
	
	// Wait for server readiness with timeout
	if err := suite.waitForServerWithMetrics(t); err != nil {
		t.Fatalf("❌ FORGE FAIL: Server not ready: %v", err)
	}
	
	// Run comprehensive test sequence
	t.Run("FORGE API Integration Tests", func(t *testing.T) {
		suite.runAPITestSuite(t)
	})
	
	t.Run("FORGE Web GUI Integration Tests", func(t *testing.T) {
		suite.runWebGUITestSuite(t)
	})
	
	t.Run("FORGE Performance Validation", func(t *testing.T) {
		suite.runPerformanceValidation(t)
	})
	
	// Generate comprehensive test report
	suite.generateForgeReport(t)
}

// waitForServerWithMetrics waits for server with detailed metrics collection
func (s *ForgeIntegrationTestSuite) waitForServerWithMetrics(t *testing.T) error {
	t.Log("🔄 FORGE: Waiting for server with metrics collection...")
	
	maxAttempts := 30
	for i := 0; i < maxAttempts; i++ {
		startTime := time.Now()
		
		resp, err := s.Client.Get(s.BaseURL + "/ready")
		responseTime := time.Since(startTime)
		
		metric := ForgeResponseMetric{
			Endpoint:     "/ready",
			Method:       "GET",
			ResponseTime: responseTime,
			Timestamp:    time.Now(),
		}
		
		if err == nil && resp.StatusCode == http.StatusOK {
			resp.Body.Close()
			metric.StatusCode = resp.StatusCode
			s.ResponseMetrics = append(s.ResponseMetrics, metric)
			
			t.Logf("✅ FORGE: Server ready after %d attempts, response time: %v", i+1, responseTime)
			return nil
		}
		
		if resp != nil {
			metric.StatusCode = resp.StatusCode
			resp.Body.Close()
		}
		
		s.ResponseMetrics = append(s.ResponseMetrics, metric)
		time.Sleep(1 * time.Second)
	}
	
	return fmt.Errorf("server not ready after %d attempts", maxAttempts)
}

// runAPITestSuite executes comprehensive API integration tests
func (s *ForgeIntegrationTestSuite) runAPITestSuite(t *testing.T) {
	// Enhanced API tests with FORGE quantitative validation
	
	t.Run("API Health Check", func(t *testing.T) {
		s.testAPIHealthCheckWithValidation(t)
	})
	
	t.Run("API Configuration Lifecycle", func(t *testing.T) {
		s.testConfigurationLifecycleWithMetrics(t)
	})
	
	t.Run("API Error Handling", func(t *testing.T) {
		s.testAPIErrorHandlingWithValidation(t)
	})
	
	t.Run("API Performance Validation", func(t *testing.T) {
		s.testAPIPerformanceValidation(t)
	})
}

// runWebGUITestSuite executes comprehensive Web GUI tests addressing Issue #72
func (s *ForgeIntegrationTestSuite) runWebGUITestSuite(t *testing.T) {
	// FORGE Requirement: Address Issue #72 with comprehensive web GUI validation
	
	webTestCases := []struct {
		name                string
		endpoint            string
		method              string
		expectedMinBytes    int // Issue #72: Critical byte count validation
		expectedStatusCode  int
		expectedContentType string
		htmlValidations     []string
		performanceMaxTime  time.Duration
	}{
		{
			name:                "Dashboard GUI Validation (Issue #72)",
			endpoint:            "/dashboard",
			method:              "GET", 
			expectedMinBytes:    6099, // Issue #72: Must exceed this threshold
			expectedStatusCode:  200,
			expectedContentType: "text/html; charset=utf-8",
			htmlValidations: []string{
				"<!DOCTYPE html>",
				"CNOC Dashboard",
				"navbar",
				"Statistics Row",
				"bootstrap",
			},
			performanceMaxTime: 500 * time.Millisecond,
		},
		{
			name:                "Root Route GUI Validation",
			endpoint:            "/",
			method:              "GET",
			expectedMinBytes:    6099, // Should redirect/render same as dashboard
			expectedStatusCode:  200,
			expectedContentType: "text/html; charset=utf-8",
			htmlValidations: []string{
				"<!DOCTYPE html>",
				"CNOC",
			},
			performanceMaxTime: 500 * time.Millisecond,
		},
		{
			name:                "Fabric List GUI Validation",
			endpoint:            "/fabrics",
			method:              "GET",
			expectedMinBytes:    4000, // Reasonable minimum for fabric list
			expectedStatusCode:  200,
			expectedContentType: "text/html; charset=utf-8",
			htmlValidations: []string{
				"<!DOCTYPE html>",
				"fabric",
				"bootstrap",
			},
			performanceMaxTime: 500 * time.Millisecond,
		},
		{
			name:                "Fabric Detail GUI Validation",
			endpoint:            "/fabrics/fabric-1",
			method:              "GET",
			expectedMinBytes:    5000, // Reasonable minimum for fabric detail
			expectedStatusCode:  200,
			expectedContentType: "text/html; charset=utf-8",
			htmlValidations: []string{
				"<!DOCTYPE html>",
				"fabric",
				"drift",
				"bootstrap",
			},
			performanceMaxTime: 500 * time.Millisecond,
		},
	}
	
	for _, tc := range webTestCases {
		t.Run(tc.name, func(t *testing.T) {
			s.validateWebGUIEndpoint(t, tc)
		})
	}
}

// validateWebGUIEndpoint performs comprehensive web GUI validation
func (s *ForgeIntegrationTestSuite) validateWebGUIEndpoint(t *testing.T, tc struct {
	name                string
	endpoint            string
	method              string
	expectedMinBytes    int
	expectedStatusCode  int
	expectedContentType string
	htmlValidations     []string
	performanceMaxTime  time.Duration
}) {
	startTime := time.Now()
	
	resp, err := s.Client.Get(s.BaseURL + tc.endpoint)
	responseTime := time.Since(startTime)
	
	if err != nil {
		t.Errorf("❌ FORGE FAIL: Request failed for %s: %v", tc.endpoint, err)
		return
	}
	defer resp.Body.Close()
	
	// Read response body
	bodyBytes, err := io.ReadAll(resp.Body)
	if err != nil {
		t.Errorf("❌ FORGE FAIL: Failed to read response body: %v", err)
		return
	}
	
	responseBody := string(bodyBytes)
	responseSize := len(responseBody)
	
	// Create response metric
	metric := ForgeResponseMetric{
		Endpoint:      tc.endpoint,
		Method:        tc.method,
		StatusCode:    resp.StatusCode,
		ResponseSize:  responseSize,
		ResponseTime:  responseTime,
		ContentType:   resp.Header.Get("Content-Type"),
		IssuE72Check:  tc.expectedMinBytes > 6000, // Mark if this is Issue #72 related
		Issue72Passed: responseSize >= tc.expectedMinBytes,
		Timestamp:     time.Now(),
	}
	s.ResponseMetrics = append(s.ResponseMetrics, metric)
	
	// FORGE Validation 1: Status Code
	if resp.StatusCode != tc.expectedStatusCode {
		validation := ForgeValidationResult{
			TestName:     tc.name,
			ValidationID: "status_code",
			Passed:       false,
			Expected:     fmt.Sprintf("%d", tc.expectedStatusCode),
			Actual:       fmt.Sprintf("%d", resp.StatusCode),
			ErrorMessage: "Status code mismatch",
			Severity:     "critical",
			Timestamp:    time.Now(),
		}
		s.ValidationResults = append(s.ValidationResults, validation)
		t.Errorf("❌ FORGE FAIL: Status code mismatch for %s: expected %d, got %d",
			tc.endpoint, tc.expectedStatusCode, resp.StatusCode)
	}
	
	// FORGE Validation 2: Content Type
	actualContentType := resp.Header.Get("Content-Type")
	if actualContentType != tc.expectedContentType {
		validation := ForgeValidationResult{
			TestName:     tc.name,
			ValidationID: "content_type",
			Passed:       false,
			Expected:     tc.expectedContentType,
			Actual:       actualContentType,
			ErrorMessage: "Content type mismatch",
			Severity:     "high",
			Timestamp:    time.Now(),
		}
		s.ValidationResults = append(s.ValidationResults, validation)
		t.Errorf("❌ FORGE FAIL: Content type mismatch for %s: expected %s, got %s",
			tc.endpoint, tc.expectedContentType, actualContentType)
	}
	
	// FORGE Validation 3: Issue #72 Critical - Response Size
	if responseSize < tc.expectedMinBytes {
		validation := ForgeValidationResult{
			TestName:     tc.name,
			ValidationID: "issue_72_response_size",
			Passed:       false,
			Expected:     fmt.Sprintf(">=%d bytes", tc.expectedMinBytes),
			Actual:       fmt.Sprintf("%d bytes", responseSize),
			ErrorMessage: "Issue #72: Response size below minimum threshold",
			Severity:     "critical",
			Timestamp:    time.Now(),
		}
		s.ValidationResults = append(s.ValidationResults, validation)
		t.Errorf("❌ FORGE FAIL (Issue #72): Response too small for %s: %d bytes (minimum: %d)",
			tc.endpoint, responseSize, tc.expectedMinBytes)
		
		// Log response preview for debugging
		preview := responseBody
		if len(preview) > 500 {
			preview = preview[:500] + "..."
		}
		t.Logf("🔍 Response preview: %s", preview)
	}
	
	// FORGE Validation 4: HTML Content Validation
	htmlValidationsPassed := 0
	for _, expectedHTML := range tc.htmlValidations {
		if strings.Contains(responseBody, expectedHTML) {
			htmlValidationsPassed++
		} else {
			validation := ForgeValidationResult{
				TestName:     tc.name,
				ValidationID: fmt.Sprintf("html_content_%s", expectedHTML),
				Passed:       false,
				Expected:     fmt.Sprintf("Contains '%s'", expectedHTML),
				Actual:       "Not found in response",
				ErrorMessage: "Required HTML content missing",
				Severity:     "medium",
				Timestamp:    time.Now(),
			}
			s.ValidationResults = append(s.ValidationResults, validation)
			t.Errorf("❌ FORGE FAIL: Missing HTML content in %s: '%s'", tc.endpoint, expectedHTML)
		}
	}
	
	// FORGE Validation 5: Performance Validation
	if responseTime > tc.performanceMaxTime {
		validation := ForgeValidationResult{
			TestName:     tc.name,
			ValidationID: "performance_response_time",
			Passed:       false,
			Expected:     fmt.Sprintf("<=%v", tc.performanceMaxTime),
			Actual:       fmt.Sprintf("%v", responseTime),
			ErrorMessage: "Response time exceeds maximum threshold",
			Severity:     "medium",
			Timestamp:    time.Now(),
		}
		s.ValidationResults = append(s.ValidationResults, validation)
		t.Errorf("❌ FORGE FAIL: Response too slow for %s: %v (max: %v)",
			tc.endpoint, responseTime, tc.performanceMaxTime)
	}
	
	// FORGE Evidence Logging
	t.Logf("✅ FORGE EVIDENCE: %s", tc.name)
	t.Logf("📊 Response Size: %d bytes", responseSize)
	t.Logf("⏱️  Response Time: %v", responseTime)
	t.Logf("🎯 Status Code: %d", resp.StatusCode)
	t.Logf("📄 Content Type: %s", actualContentType)
	t.Logf("🔍 HTML Validations Passed: %d/%d", htmlValidationsPassed, len(tc.htmlValidations))
	
	if tc.expectedMinBytes > 6000 {
		if responseSize >= tc.expectedMinBytes {
			t.Logf("✅ Issue #72 PASSED: Response size %d >= %d bytes", responseSize, tc.expectedMinBytes)
		} else {
			t.Logf("❌ Issue #72 FAILED: Response size %d < %d bytes", responseSize, tc.expectedMinBytes)
		}
	}
}

// testAPIHealthCheckWithValidation performs enhanced health check validation
func (s *ForgeIntegrationTestSuite) testAPIHealthCheckWithValidation(t *testing.T) {
	startTime := time.Now()
	
	resp, err := s.Client.Get(s.BaseURL + "/health")
	responseTime := time.Since(startTime)
	
	if err != nil {
		t.Errorf("❌ FORGE FAIL: Health check request failed: %v", err)
		return
	}
	defer resp.Body.Close()
	
	// Record metrics
	bodyBytes, _ := io.ReadAll(resp.Body)
	responseSize := len(bodyBytes)
	
	metric := ForgeResponseMetric{
		Endpoint:     "/health",
		Method:       "GET",
		StatusCode:   resp.StatusCode,
		ResponseSize: responseSize,
		ResponseTime: responseTime,
		ContentType:  resp.Header.Get("Content-Type"),
		Timestamp:    time.Now(),
	}
	s.ResponseMetrics = append(s.ResponseMetrics, metric)
	
	// Validate health check response
	if resp.StatusCode != http.StatusOK {
		t.Errorf("❌ FORGE FAIL: Health check status: expected 200, got %d", resp.StatusCode)
	}
	
	var health map[string]interface{}
	if err := json.Unmarshal(bodyBytes, &health); err != nil {
		t.Errorf("❌ FORGE FAIL: Health check JSON parse error: %v", err)
		return
	}
	
	if health["status"] != "healthy" {
		t.Errorf("❌ FORGE FAIL: Service not healthy: %v", health)
	}
	
	t.Logf("✅ FORGE EVIDENCE: Health check - %v, %d bytes", responseTime, responseSize)
}

// testConfigurationLifecycleWithMetrics tests full configuration lifecycle with metrics
func (s *ForgeIntegrationTestSuite) testConfigurationLifecycleWithMetrics(t *testing.T) {
	// Create configuration with metrics
	createRequest := dto.CreateConfigurationRequestDTO{
		Name:        "forge-integration-test",
		Description: "FORGE methodology integration test configuration",
		Mode:        "development",
		Version:     "1.0.0",
		Labels: map[string]string{
			"test":        "forge-integration",
			"environment": "test",
			"created_by":  "forge_test_suite",
		},
		Components: []dto.ComponentDTO{
			{
				Name:    "forge-test-component",
				Version: "1.0.0",
				Enabled: true,
				Resources: dto.ResourceRequirementsDTO{
					CPU:      "200m",
					Memory:   "256Mi",
					Replicas: 2,
				},
				Configuration: map[string]interface{}{
					"port":        8080,
					"environment": "test",
					"forge_mode":  true,
				},
			},
		},
	}
	
	// Test CREATE with metrics
	startTime := time.Now()
	jsonData, _ := json.Marshal(createRequest)
	
	resp, err := s.Client.Post(s.BaseURL+"/api/v1/configurations", "application/json", bytes.NewBuffer(jsonData))
	responseTime := time.Since(startTime)
	
	if err != nil {
		t.Errorf("❌ FORGE FAIL: Create request failed: %v", err)
		return
	}
	defer resp.Body.Close()
	
	bodyBytes, _ := io.ReadAll(resp.Body)
	responseSize := len(bodyBytes)
	
	// Record CREATE metrics
	s.ResponseMetrics = append(s.ResponseMetrics, ForgeResponseMetric{
		Endpoint:     "/api/v1/configurations",
		Method:       "POST",
		StatusCode:   resp.StatusCode,
		ResponseSize: responseSize,
		ResponseTime: responseTime,
		ContentType:  resp.Header.Get("Content-Type"),
		Timestamp:    time.Now(),
	})
	
	if resp.StatusCode != http.StatusCreated {
		t.Errorf("❌ FORGE FAIL: Create status: expected 201, got %d", resp.StatusCode)
		t.Logf("Response body: %s", string(bodyBytes))
		return
	}
	
	var configDTO dto.ConfigurationDTO
	if err := json.Unmarshal(bodyBytes, &configDTO); err != nil {
		t.Errorf("❌ FORGE FAIL: Create response JSON parse error: %v", err)
		return
	}
	
	configID := configDTO.ID
	if configID == "" {
		t.Errorf("❌ FORGE FAIL: Configuration ID empty in create response")
		return
	}
	
	t.Logf("✅ FORGE EVIDENCE: CREATE - ID: %s, Time: %v, Size: %d bytes", configID, responseTime, responseSize)
	
	// Test GET with metrics
	startTime = time.Now()
	getResp, err := s.Client.Get(s.BaseURL + "/api/v1/configurations/" + configID)
	responseTime = time.Since(startTime)
	
	if err != nil {
		t.Errorf("❌ FORGE FAIL: Get request failed: %v", err)
		return
	}
	defer getResp.Body.Close()
	
	getBodyBytes, _ := io.ReadAll(getResp.Body)
	getResponseSize := len(getBodyBytes)
	
	// Record GET metrics
	s.ResponseMetrics = append(s.ResponseMetrics, ForgeResponseMetric{
		Endpoint:     fmt.Sprintf("/api/v1/configurations/%s", configID),
		Method:       "GET",
		StatusCode:   getResp.StatusCode,
		ResponseSize: getResponseSize,
		ResponseTime: responseTime,
		ContentType:  getResp.Header.Get("Content-Type"),
		Timestamp:    time.Now(),
	})
	
	if getResp.StatusCode != http.StatusOK {
		t.Errorf("❌ FORGE FAIL: Get status: expected 200, got %d", getResp.StatusCode)
	}
	
	t.Logf("✅ FORGE EVIDENCE: GET - Time: %v, Size: %d bytes", responseTime, getResponseSize)
}

// testAPIErrorHandlingWithValidation tests API error handling scenarios
func (s *ForgeIntegrationTestSuite) testAPIErrorHandlingWithValidation(t *testing.T) {
	errorTestCases := []struct {
		name           string
		endpoint       string
		method         string
		expectedStatus int
		body           string
	}{
		{
			name:           "Invalid Configuration ID",
			endpoint:       "/api/v1/configurations/invalid-id-12345",
			method:         "GET",
			expectedStatus: http.StatusNotFound,
		},
		{
			name:           "Invalid JSON in Create",
			endpoint:       "/api/v1/configurations",
			method:         "POST",
			expectedStatus: http.StatusBadRequest,
			body:           `{"invalid": json}`,
		},
		{
			name:           "Non-existent Endpoint",
			endpoint:       "/api/v1/nonexistent",
			method:         "GET",
			expectedStatus: http.StatusNotFound,
		},
	}
	
	for _, tc := range errorTestCases {
		t.Run(tc.name, func(t *testing.T) {
			startTime := time.Now()
			
			var resp *http.Response
			var err error
			
			switch tc.method {
			case "GET":
				resp, err = s.Client.Get(s.BaseURL + tc.endpoint)
			case "POST":
				body := strings.NewReader(tc.body)
				resp, err = s.Client.Post(s.BaseURL+tc.endpoint, "application/json", body)
			}
			
			responseTime := time.Since(startTime)
			
			if err != nil {
				t.Errorf("❌ FORGE FAIL: Request error for %s: %v", tc.name, err)
				return
			}
			defer resp.Body.Close()
			
			bodyBytes, _ := io.ReadAll(resp.Body)
			responseSize := len(bodyBytes)
			
			// Record error handling metrics
			s.ResponseMetrics = append(s.ResponseMetrics, ForgeResponseMetric{
				Endpoint:     tc.endpoint,
				Method:       tc.method,
				StatusCode:   resp.StatusCode,
				ResponseSize: responseSize,
				ResponseTime: responseTime,
				ContentType:  resp.Header.Get("Content-Type"),
				Timestamp:    time.Now(),
			})
			
			if resp.StatusCode != tc.expectedStatus {
				t.Errorf("❌ FORGE FAIL: Error status for %s: expected %d, got %d",
					tc.name, tc.expectedStatus, resp.StatusCode)
			}
			
			t.Logf("✅ FORGE EVIDENCE: Error handling %s - Status: %d, Time: %v", 
				tc.name, resp.StatusCode, responseTime)
		})
	}
}

// testAPIPerformanceValidation validates API performance requirements
func (s *ForgeIntegrationTestSuite) testAPIPerformanceValidation(t *testing.T) {
	// Performance benchmarking
	performanceTests := []struct {
		name        string
		endpoint    string
		method      string
		maxTime     time.Duration
		iterations  int
	}{
		{"Health Check Performance", "/health", "GET", 100 * time.Millisecond, 10},
		{"Configuration List Performance", "/api/v1/configurations", "GET", 500 * time.Millisecond, 5},
	}
	
	for _, pt := range performanceTests {
		t.Run(pt.name, func(t *testing.T) {
			times := make([]time.Duration, pt.iterations)
			
			for i := 0; i < pt.iterations; i++ {
				startTime := time.Now()
				
				resp, err := s.Client.Get(s.BaseURL + pt.endpoint)
				responseTime := time.Since(startTime)
				times[i] = responseTime
				
				if err != nil {
					t.Errorf("❌ FORGE FAIL: Performance test request failed: %v", err)
					continue
				}
				
				bodyBytes, _ := io.ReadAll(resp.Body)
				resp.Body.Close()
				
				// Record performance metric
				s.ResponseMetrics = append(s.ResponseMetrics, ForgeResponseMetric{
					Endpoint:     pt.endpoint,
					Method:       pt.method,
					StatusCode:   resp.StatusCode,
					ResponseSize: len(bodyBytes),
					ResponseTime: responseTime,
					ContentType:  resp.Header.Get("Content-Type"),
					Timestamp:    time.Now(),
				})
				
				if responseTime > pt.maxTime {
					t.Errorf("❌ FORGE FAIL: Performance violation iteration %d: %v > %v",
						i+1, responseTime, pt.maxTime)
				}
			}
			
			// Calculate average performance
			var totalTime time.Duration
			for _, t := range times {
				totalTime += t
			}
			avgTime := totalTime / time.Duration(len(times))
			
			t.Logf("✅ FORGE EVIDENCE: %s - Avg: %v, Max allowed: %v", 
				pt.name, avgTime, pt.maxTime)
		})
	}
}

// runPerformanceValidation validates overall system performance
func (s *ForgeIntegrationTestSuite) runPerformanceValidation(t *testing.T) {
	// Analyze collected performance metrics
	totalRequests := len(s.ResponseMetrics)
	if totalRequests == 0 {
		t.Error("❌ FORGE FAIL: No response metrics collected")
		return
	}
	
	// Calculate performance statistics
	var totalResponseTime time.Duration
	var totalResponseSize int
	slowRequests := 0
	issue72Failures := 0
	
	for _, metric := range s.ResponseMetrics {
		totalResponseTime += metric.ResponseTime
		totalResponseSize += metric.ResponseSize
		
		if metric.ResponseTime > 1*time.Second {
			slowRequests++
		}
		
		if metric.IssuE72Check && !metric.Issue72Passed {
			issue72Failures++
		}
	}
	
	avgResponseTime := totalResponseTime / time.Duration(totalRequests)
	avgResponseSize := totalResponseSize / totalRequests
	slowRequestPercent := float64(slowRequests) / float64(totalRequests) * 100
	
	// FORGE Performance Validation
	if avgResponseTime > 500*time.Millisecond {
		t.Errorf("❌ FORGE FAIL: Average response time too slow: %v", avgResponseTime)
	}
	
	if slowRequestPercent > 10.0 {
		t.Errorf("❌ FORGE FAIL: Too many slow requests: %.1f%%", slowRequestPercent)
	}
	
	if issue72Failures > 0 {
		t.Errorf("❌ FORGE FAIL: Issue #72 failures: %d requests below minimum bytes", issue72Failures)
	}
	
	// FORGE Evidence Logging
	t.Logf("✅ FORGE PERFORMANCE EVIDENCE:")
	t.Logf("📊 Total Requests: %d", totalRequests)
	t.Logf("⏱️  Average Response Time: %v", avgResponseTime)
	t.Logf("📦 Average Response Size: %d bytes", avgResponseSize)
	t.Logf("🐌 Slow Requests: %d (%.1f%%)", slowRequests, slowRequestPercent)
	t.Logf("🎯 Issue #72 Failures: %d", issue72Failures)
}

// generateForgeReport generates comprehensive FORGE test evidence report
func (s *ForgeIntegrationTestSuite) generateForgeReport(t *testing.T) {
	totalDuration := time.Since(s.TestStartTime)
	totalValidations := len(s.ValidationResults)
	passedValidations := 0
	
	for _, validation := range s.ValidationResults {
		if validation.Passed {
			passedValidations++
		}
	}
	
	successRate := float64(passedValidations) / float64(totalValidations) * 100
	
	report := ForgeIntegrationReport{
		GeneratedAt:       time.Now(),
		TestDuration:      totalDuration,
		TotalRequests:     len(s.ResponseMetrics),
		TotalValidations:  totalValidations,
		PassedValidations: passedValidations,
		FailedValidations: totalValidations - passedValidations,
		SuccessRate:       successRate,
		ResponseMetrics:   s.ResponseMetrics,
		ValidationResults: s.ValidationResults,
	}
	
	// Log summary
	t.Logf("🎉 FORGE INTEGRATION TEST COMPLETE")
	t.Logf("⏱️  Total Duration: %v", totalDuration)
	t.Logf("📊 Total Requests: %d", report.TotalRequests)
	t.Logf("✅ Passed Validations: %d/%d (%.1f%%)", passedValidations, totalValidations, successRate)
	t.Logf("❌ Failed Validations: %d", report.FailedValidations)
	
	// Save detailed report (optional)
	if jsonData, err := json.MarshalIndent(report, "", "  "); err == nil {
		t.Logf("📄 Detailed report available in test logs")
		// Could save to file if needed: os.WriteFile("forge_integration_report.json", jsonData, 0644)
		_ = jsonData // Use the json data for logging if needed
	}
}

// ForgeIntegrationReport comprehensive integration test report
type ForgeIntegrationReport struct {
	GeneratedAt       time.Time                 `json:"generated_at"`
	TestDuration      time.Duration            `json:"test_duration_ns"`
	TotalRequests     int                      `json:"total_requests"`
	TotalValidations  int                      `json:"total_validations"`
	PassedValidations int                      `json:"passed_validations"`
	FailedValidations int                      `json:"failed_validations"`
	SuccessRate       float64                  `json:"success_rate_percent"`
	ResponseMetrics   []ForgeResponseMetric    `json:"response_metrics"`
	ValidationResults []ForgeValidationResult  `json:"validation_results"`
}

// FORGE Integration Test Requirements Summary:
//
// 1. ISSUE #72 CRITICAL VALIDATION:
//    - All web GUI responses must exceed minimum byte thresholds
//    - Dashboard must exceed 6099 bytes for proper template rendering
//    - Quantitative response size validation with detailed logging
//
// 2. COMPREHENSIVE END-TO-END TESTING:
//    - API endpoints with full lifecycle testing
//    - Web GUI endpoints with HTML content validation
//    - Error handling scenarios with proper status codes
//    - Performance validation with response time limits
//
// 3. QUANTITATIVE EVIDENCE COLLECTION:
//    - Response time measurements for all requests
//    - Response size tracking for Issue #72 compliance
//    - Content type and status code validation
//    - HTML content presence verification
//
// 4. PERFORMANCE REQUIREMENTS:
//    - Maximum response times defined per endpoint type
//    - Performance regression detection
//    - Slow request percentage monitoring
//    - Average response time calculations
//
// 5. FORGE METHODOLOGY COMPLIANCE:
//    - Comprehensive metrics collection
//    - Detailed validation result tracking
//    - Evidence-based pass/fail determination
//    - Quantitative success rate calculations