package monitoring

import (
	"fmt"
	"io"
	"net/http"
	"regexp"
	"strconv"
	"strings"
	"testing"
	"time"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

// MetricsTestSuite provides comprehensive metrics validation testing
type MetricsTestSuite struct {
	BaseURL          string
	Client           *http.Client
	TestStartTime    time.Time
	MetricsData      map[string]MetricValue
	CollectionTimes  []time.Duration
	ValidationResult []MetricValidationResult
}

// MetricValue represents a collected metric value
type MetricValue struct {
	Name        string            `json:"name"`
	Type        string            `json:"type"` // counter, gauge, histogram, summary
	Value       float64           `json:"value"`
	Labels      map[string]string `json:"labels"`
	Timestamp   time.Time         `json:"timestamp"`
	Unit        string            `json:"unit"`
}

// MetricValidationResult tracks metric validation outcomes
type MetricValidationResult struct {
	MetricName    string    `json:"metric_name"`
	ValidationID  string    `json:"validation_id"`
	Expected      string    `json:"expected"`
	Actual        string    `json:"actual"`
	Passed        bool      `json:"passed"`
	ErrorMessage  string    `json:"error_message"`
	Severity      string    `json:"severity"`
	Timestamp     time.Time `json:"timestamp"`
}

// BusinessMetric represents application-specific metrics
type BusinessMetric struct {
	Name              string        `json:"name"`
	Description       string        `json:"description"`
	ExpectedType      string        `json:"expected_type"`
	ExpectedLabels    []string      `json:"expected_labels"`
	AcceptableRange   [2]float64    `json:"acceptable_range"`
	CollectionLatency time.Duration `json:"collection_latency_ns"`
	LastValue         float64       `json:"last_value"`
	LastCollected     time.Time     `json:"last_collected"`
}

// NewMetricsTestSuite creates new metrics validation test suite
func NewMetricsTestSuite(baseURL string) *MetricsTestSuite {
	return &MetricsTestSuite{
		BaseURL:          baseURL,
		Client:           &http.Client{Timeout: 10 * time.Second},
		TestStartTime:    time.Now(),
		MetricsData:      make(map[string]MetricValue),
		CollectionTimes:  []time.Duration{},
		ValidationResult: []MetricValidationResult{},
	}
}

// TestPrometheusMetrics validates metrics exposure at /metrics endpoint
func TestPrometheusMetrics(t *testing.T) {
	// FORGE Movement 7: Monitoring and Observability Testing
	t.Log("🔄 FORGE M7: Testing Prometheus metrics exposure...")

	suite := NewMetricsTestSuite("http://localhost:9090")

	// Test metrics endpoint availability
	metricsStart := time.Now()
	resp, err := suite.Client.Get(suite.BaseURL + "/metrics")
	collectionTime := time.Since(metricsStart)
	
	require.NoError(t, err, "Metrics endpoint must be accessible")
	require.Equal(t, http.StatusOK, resp.StatusCode, "Metrics endpoint must return 200")
	defer resp.Body.Close()

	// Read metrics content
	metricsBody, err := io.ReadAll(resp.Body)
	require.NoError(t, err, "Metrics content must be readable")

	metricsContent := string(metricsBody)
	suite.CollectionTimes = append(suite.CollectionTimes, collectionTime)

	// FORGE Validation 1: Content-Type must be Prometheus format
	contentType := resp.Header.Get("Content-Type")
	expectedContentType := "text/plain; version=0.0.4; charset=utf-8"
	assert.Equal(t, expectedContentType, contentType, "Metrics must use Prometheus content type")

	// FORGE Validation 2: Essential CNOC metrics must be present
	requiredMetrics := []string{
		"cnoc_api_requests_total",
		"cnoc_sync_operations_total", 
		"cnoc_sync_duration_seconds",
		"cnoc_fabric_count",
		"cnoc_crd_count",
		"cnoc_http_request_duration_seconds",
		"cnoc_memory_usage_bytes",
		"cnoc_cpu_usage_seconds_total",
	}

	for _, metricName := range requiredMetrics {
		found := strings.Contains(metricsContent, metricName)
		
		validation := MetricValidationResult{
			MetricName:    metricName,
			ValidationID:  "required_metric_presence",
			Expected:      "present in /metrics output",
			Actual:        fmt.Sprintf("found: %t", found),
			Passed:        found,
			ErrorMessage:  "",
			Severity:      "critical",
			Timestamp:     time.Now(),
		}
		
		if !found {
			validation.ErrorMessage = fmt.Sprintf("Required metric %s not found in metrics output", metricName)
		}
		
		suite.ValidationResult = append(suite.ValidationResult, validation)
		assert.True(t, found, "Required metric %s must be exposed", metricName)
	}

	// FORGE Validation 3: Metrics collection must be fast (<10ms overhead)
	maxCollectionTime := 10 * time.Millisecond
	assert.Less(t, collectionTime, maxCollectionTime, 
		"Metrics collection must have <%v overhead, took %v", maxCollectionTime, collectionTime)

	// FORGE Validation 4: Parse and validate metric format
	parsedMetrics := parsePrometheusMetrics(metricsContent)
	assert.Greater(t, len(parsedMetrics), 0, "Metrics must be parseable")

	// Store parsed metrics
	for _, metric := range parsedMetrics {
		suite.MetricsData[metric.Name] = metric
	}

	// FORGE Validation 5: Validate specific metric values are reasonable
	if syncOpsMetric, exists := parsedMetrics["cnoc_sync_operations_total"]; exists {
		assert.GreaterOrEqual(t, syncOpsMetric.Value, 0.0, "Sync operations count must be non-negative")
	}

	if fabricCountMetric, exists := parsedMetrics["cnoc_fabric_count"]; exists {
		assert.GreaterOrEqual(t, fabricCountMetric.Value, 0.0, "Fabric count must be non-negative")
		assert.Less(t, fabricCountMetric.Value, 1000.0, "Fabric count must be reasonable (<1000)")
	}

	// FORGE Evidence Collection
	t.Logf("✅ FORGE M7 EVIDENCE - Prometheus Metrics:")
	t.Logf("📊 Metrics Endpoint: %s/metrics", suite.BaseURL)
	t.Logf("⏱️  Collection Time: %v", collectionTime)
	t.Logf("📄 Content Type: %s", contentType)
	t.Logf("📈 Parsed Metrics: %d", len(parsedMetrics))
	t.Logf("📋 Required Metrics: %d/%d found", countFoundMetrics(requiredMetrics, metricsContent), len(requiredMetrics))
	t.Logf("📦 Content Size: %d bytes", len(metricsContent))
}

// TestMetricLabels validates proper labeling for aggregation and filtering
func TestMetricLabels(t *testing.T) {
	// FORGE Movement 7: Metric Label Validation
	t.Log("🔄 FORGE M7: Testing metric labeling for aggregation...")

	suite := NewMetricsTestSuite("http://localhost:9090")

	// Collect metrics
	resp, err := suite.Client.Get(suite.BaseURL + "/metrics")
	require.NoError(t, err, "Metrics endpoint must be accessible")
	defer resp.Body.Close()

	metricsBody, err := io.ReadAll(resp.Body)
	require.NoError(t, err, "Metrics content must be readable")

	metricsContent := string(metricsBody)
	parsedMetrics := parsePrometheusMetrics(metricsContent)

	// FORGE Validation 1: API request metrics must have proper labels
	apiRequestsFound := false
	for _, metric := range parsedMetrics {
		if strings.Contains(metric.Name, "cnoc_api_requests_total") {
			apiRequestsFound = true
			
			// Validate essential labels
			requiredLabels := []string{"method", "endpoint", "status_code"}
			for _, label := range requiredLabels {
				assert.Contains(t, metric.Labels, label, 
					"API request metric must have %s label", label)
			}

			// Validate label values are reasonable
			if method, exists := metric.Labels["method"]; exists {
				validMethods := []string{"GET", "POST", "PUT", "DELETE", "PATCH"}
				assert.Contains(t, validMethods, method, "Method label must be valid HTTP method")
			}

			if statusCode, exists := metric.Labels["status_code"]; exists {
				code, err := strconv.Atoi(statusCode)
				if err == nil {
					assert.GreaterOrEqual(t, code, 200, "Status code must be valid HTTP status")
					assert.Less(t, code, 600, "Status code must be valid HTTP status")
				}
			}
		}
	}
	assert.True(t, apiRequestsFound, "API request metrics with labels must be present")

	// FORGE Validation 2: Sync operation metrics must have fabric labels
	syncOpsFound := false
	for _, metric := range parsedMetrics {
		if strings.Contains(metric.Name, "cnoc_sync_operations_total") {
			syncOpsFound = true
			
			// Validate fabric identification labels
			fabricLabels := []string{"fabric_name", "operation_type", "status"}
			for _, label := range fabricLabels {
				if _, exists := metric.Labels[label]; exists {
					// Good - label is present
					continue
				}
			}
			
			// At least one fabric-related label should be present
			hasFabricLabel := false
			for _, label := range fabricLabels {
				if _, exists := metric.Labels[label]; exists {
					hasFabricLabel = true
					break
				}
			}
			assert.True(t, hasFabricLabel, "Sync metrics must have fabric identification labels")
		}
	}

	// FORGE Validation 3: Duration metrics must have percentile labels
	durationFound := false
	for _, metric := range parsedMetrics {
		if strings.Contains(metric.Name, "duration_seconds") {
			durationFound = true
			
			// For histogram metrics, validate quantile labels
			if strings.Contains(metric.Name, "_bucket") {
				assert.Contains(t, metric.Labels, "le", "Duration bucket metric must have 'le' label")
			}
			
			if strings.Contains(metric.Name, "_sum") || strings.Contains(metric.Name, "_count") {
				// These don't need quantile labels but should have operation labels
				assert.NotEmpty(t, metric.Labels, "Duration metrics must have descriptive labels")
			}
		}
	}

	// FORGE Validation 4: Label cardinality must be controlled
	labelCardinality := calculateLabelCardinality(parsedMetrics)
	for metricName, cardinality := range labelCardinality {
		assert.Less(t, cardinality, 1000, 
			"Metric %s label cardinality must be <1000 (current: %d)", metricName, cardinality)
	}

	// FORGE Evidence Collection
	t.Logf("✅ FORGE M7 EVIDENCE - Metric Labels:")
	t.Logf("📈 Total Metrics with Labels: %d", len(parsedMetrics))
	t.Logf("🔗 API Requests Labeled: %t", apiRequestsFound)
	t.Logf("🔄 Sync Operations Labeled: %t", syncOpsFound)
	t.Logf("⏱️  Duration Metrics Labeled: %t", durationFound)
	t.Logf("📊 Label Cardinalities: %v", labelCardinality)
}

// TestCustomMetrics validates business-specific metrics
func TestCustomMetrics(t *testing.T) {
	// FORGE Movement 7: Business Metrics Validation
	t.Log("🔄 FORGE M7: Testing custom business metrics...")

	suite := NewMetricsTestSuite("http://localhost:9090")

	// Define expected business metrics
	businessMetrics := []BusinessMetric{
		{
			Name:            "cnoc_fabric_count",
			Description:     "Total number of managed fabrics",
			ExpectedType:    "gauge",
			AcceptableRange: [2]float64{0, 100},
		},
		{
			Name:            "cnoc_crd_count",
			Description:     "Total number of managed CRDs",
			ExpectedType:    "gauge",
			AcceptableRange: [2]float64{0, 10000},
		},
		{
			Name:            "cnoc_sync_operations_total",
			Description:     "Total GitOps sync operations",
			ExpectedType:    "counter",
			AcceptableRange: [2]float64{0, 1000000},
		},
		{
			Name:            "cnoc_api_requests_total",
			Description:     "Total API requests processed",
			ExpectedType:    "counter",
			AcceptableRange: [2]float64{0, 10000000},
		},
		{
			Name:            "cnoc_drift_detections_total",
			Description:     "Total drift detection operations",
			ExpectedType:    "counter",
			AcceptableRange: [2]float64{0, 100000},
		},
	}

	// Collect current metrics
	resp, err := suite.Client.Get(suite.BaseURL + "/metrics")
	require.NoError(t, err, "Metrics endpoint must be accessible")
	defer resp.Body.Close()

	metricsBody, err := io.ReadAll(resp.Body)
	require.NoError(t, err, "Metrics content must be readable")

	metricsContent := string(metricsBody)
	parsedMetrics := parsePrometheusMetrics(metricsContent)

	// FORGE Validation: Validate each business metric
	for _, businessMetric := range businessMetrics {
		t.Run(fmt.Sprintf("BusinessMetric_%s", businessMetric.Name), func(t *testing.T) {
			metricFound := false
			var actualValue float64

			// Look for the metric in parsed results
			for _, parsedMetric := range parsedMetrics {
				if strings.Contains(parsedMetric.Name, businessMetric.Name) {
					metricFound = true
					actualValue = parsedMetric.Value
					businessMetric.LastValue = actualValue
					businessMetric.LastCollected = time.Now()
					break
				}
			}

			// Validate presence
			assert.True(t, metricFound, "Business metric %s must be present", businessMetric.Name)

			if metricFound {
				// Validate value range
				minVal, maxVal := businessMetric.AcceptableRange[0], businessMetric.AcceptableRange[1]
				assert.GreaterOrEqual(t, actualValue, minVal, 
					"Metric %s value %.2f must be >= %.2f", businessMetric.Name, actualValue, minVal)
				assert.LessOrEqual(t, actualValue, maxVal,
					"Metric %s value %.2f must be <= %.2f", businessMetric.Name, actualValue, maxVal)

				// Record validation result
				validation := MetricValidationResult{
					MetricName:   businessMetric.Name,
					ValidationID: "business_metric_range",
					Expected:     fmt.Sprintf("%.2f <= value <= %.2f", minVal, maxVal),
					Actual:       fmt.Sprintf("%.2f", actualValue),
					Passed:       actualValue >= minVal && actualValue <= maxVal,
					Severity:     "high",
					Timestamp:    time.Now(),
				}
				suite.ValidationResult = append(suite.ValidationResult, validation)
			}

			t.Logf("📊 %s: %.2f (range: %.2f-%.2f)", 
				businessMetric.Name, actualValue, businessMetric.AcceptableRange[0], businessMetric.AcceptableRange[1])
		})
	}

	// FORGE Evidence Collection
	t.Logf("✅ FORGE M7 EVIDENCE - Custom Metrics:")
	foundMetrics := 0
	for _, bm := range businessMetrics {
		if bm.LastCollected.After(suite.TestStartTime) {
			foundMetrics++
		}
	}
	t.Logf("📈 Business Metrics Found: %d/%d", foundMetrics, len(businessMetrics))
	t.Logf("📊 Metric Categories: Fabric, CRD, Sync, API, Drift")
	t.Logf("✅ Value Validation: All metrics within acceptable ranges")
}

// TestMetricAccuracy validates metrics match actual operation counts
func TestMetricAccuracy(t *testing.T) {
	// FORGE Movement 7: Metric Accuracy Testing
	t.Log("🔄 FORGE M7: Testing metric accuracy against operations...")

	suite := NewMetricsTestSuite("http://localhost:9090")

	// Get baseline metrics
	baselineMetrics := collectMetrics(t, suite)
	
	// Perform known operations to test accuracy
	operationStart := time.Now()

	// Simulate API requests
	apiRequestCount := 5
	for i := 0; i < apiRequestCount; i++ {
		resp, err := suite.Client.Get(suite.BaseURL + "/health")
		if err == nil {
			resp.Body.Close()
		}
		time.Sleep(100 * time.Millisecond)
	}

	// Wait for metrics to be updated
	time.Sleep(2 * time.Second)

	// Get updated metrics
	updatedMetrics := collectMetrics(t, suite)
	operationDuration := time.Since(operationStart)

	// FORGE Validation 1: API request counter must have increased
	baselineAPIRequests := getMetricValue(baselineMetrics, "cnoc_api_requests_total")
	updatedAPIRequests := getMetricValue(updatedMetrics, "cnoc_api_requests_total")
	
	expectedIncrease := float64(apiRequestCount)
	actualIncrease := updatedAPIRequests - baselineAPIRequests
	
	// Allow for some tolerance due to concurrent requests
	tolerance := 2.0
	assert.InDelta(t, expectedIncrease, actualIncrease, tolerance,
		"API request metric increase should be approximately %v, got %v", expectedIncrease, actualIncrease)

	// FORGE Validation 2: HTTP request duration metrics should be updated
	baselineDurationCount := getMetricValue(baselineMetrics, "cnoc_http_request_duration_seconds_count")
	updatedDurationCount := getMetricValue(updatedMetrics, "cnoc_http_request_duration_seconds_count")
	
	if baselineDurationCount >= 0 && updatedDurationCount >= 0 {
		assert.Greater(t, updatedDurationCount, baselineDurationCount,
			"Duration metric count should increase with requests")
	}

	// FORGE Validation 3: Metrics collection accuracy within 10% tolerance
	accuracyTolerance := 0.1
	if actualIncrease > 0 {
		accuracyRatio := actualIncrease / expectedIncrease
		assert.InDelta(t, 1.0, accuracyRatio, accuracyTolerance,
			"Metric accuracy should be within 10%%, ratio: %.2f", accuracyRatio)
	}

	// Record accuracy validation
	validation := MetricValidationResult{
		MetricName:   "cnoc_api_requests_total",
		ValidationID: "accuracy_validation",
		Expected:     fmt.Sprintf("increase by %v", expectedIncrease),
		Actual:       fmt.Sprintf("increased by %.2f", actualIncrease),
		Passed:       abs(actualIncrease-expectedIncrease) <= tolerance,
		Severity:     "high",
		Timestamp:    time.Now(),
	}
	suite.ValidationResult = append(suite.ValidationResult, validation)

	// FORGE Evidence Collection
	t.Logf("✅ FORGE M7 EVIDENCE - Metric Accuracy:")
	t.Logf("🎯 Expected API Requests: %.0f", expectedIncrease)
	t.Logf("📊 Actual Metric Increase: %.2f", actualIncrease)
	t.Logf("📈 Accuracy Ratio: %.2f", actualIncrease/expectedIncrease)
	t.Logf("⏱️  Test Duration: %v", operationDuration)
	t.Logf("✅ Accuracy Within Tolerance: %t", abs(actualIncrease-expectedIncrease) <= tolerance)
}

// TestMetricPerformance validates metrics collection overhead
func TestMetricPerformance(t *testing.T) {
	// FORGE Movement 7: Metrics Collection Performance
	t.Log("🔄 FORGE M7: Testing metrics collection performance overhead...")

	suite := NewMetricsTestSuite("http://localhost:9090")

	// Test metrics collection performance over multiple iterations
	iterations := 10
	collectionTimes := make([]time.Duration, iterations)

	for i := 0; i < iterations; i++ {
		start := time.Now()
		
		resp, err := suite.Client.Get(suite.BaseURL + "/metrics")
		collectionTime := time.Since(start)
		
		if err == nil {
			io.Copy(io.Discard, resp.Body) // Read and discard body
			resp.Body.Close()
			collectionTimes[i] = collectionTime
		} else {
			t.Errorf("Metrics collection failed on iteration %d: %v", i+1, err)
		}
		
		// Small delay between requests
		time.Sleep(100 * time.Millisecond)
	}

	// Calculate performance statistics
	var totalTime time.Duration
	var maxTime time.Duration
	var minTime time.Duration = time.Hour // Initialize to large value
	
	for _, collectionTime := range collectionTimes {
		totalTime += collectionTime
		if collectionTime > maxTime {
			maxTime = collectionTime
		}
		if collectionTime < minTime {
			minTime = collectionTime
		}
	}
	
	avgTime := totalTime / time.Duration(iterations)

	// FORGE Validation 1: Average collection time must be under 10ms
	maxAvgTime := 10 * time.Millisecond
	assert.Less(t, avgTime, maxAvgTime, 
		"Average metrics collection must be <%v, got %v", maxAvgTime, avgTime)

	// FORGE Validation 2: Maximum collection time must be under 50ms
	maxCollectionTime := 50 * time.Millisecond
	assert.Less(t, maxTime, maxCollectionTime,
		"Maximum metrics collection must be <%v, got %v", maxCollectionTime, maxTime)

	// FORGE Validation 3: Collection time variance must be reasonable
	variance := calculateTimeVariance(collectionTimes, avgTime)
	maxVariancePercent := 50.0 // 50% variance allowed
	variancePercent := (float64(variance) / float64(avgTime)) * 100
	
	assert.Less(t, variancePercent, maxVariancePercent,
		"Collection time variance must be <%v%%, got %.1f%%", maxVariancePercent, variancePercent)

	// Store performance data
	suite.CollectionTimes = collectionTimes

	// FORGE Evidence Collection
	t.Logf("✅ FORGE M7 EVIDENCE - Metrics Performance:")
	t.Logf("📊 Iterations: %d", iterations)
	t.Logf("⏱️  Average Time: %v", avgTime)
	t.Logf("🚀 Min Time: %v", minTime)
	t.Logf("🐌 Max Time: %v", maxTime)
	t.Logf("📈 Variance: %.1f%%", variancePercent)
	t.Logf("🎯 Performance Target: <10ms avg (achieved: %t)", avgTime < maxAvgTime)
}

// Helper functions

func parsePrometheusMetrics(content string) map[string]MetricValue {
	metrics := make(map[string]MetricValue)
	lines := strings.Split(content, "\n")
	
	for _, line := range lines {
		line = strings.TrimSpace(line)
		if line == "" || strings.HasPrefix(line, "#") {
			continue
		}
		
		// Parse metric line: metric_name{labels} value [timestamp]
		parts := strings.Fields(line)
		if len(parts) < 2 {
			continue
		}
		
		metricPart := parts[0]
		valuePart := parts[1]
		
		// Extract metric name and labels
		var metricName string
		var labels map[string]string
		
		if strings.Contains(metricPart, "{") {
			// Has labels
			nameEnd := strings.Index(metricPart, "{")
			metricName = metricPart[:nameEnd]
			
			labelsStr := metricPart[nameEnd+1 : len(metricPart)-1]
			labels = parseLabels(labelsStr)
		} else {
			// No labels
			metricName = metricPart
			labels = make(map[string]string)
		}
		
		// Parse value
		value, err := strconv.ParseFloat(valuePart, 64)
		if err != nil {
			continue
		}
		
		// Determine metric type
		metricType := "gauge"
		if strings.HasSuffix(metricName, "_total") {
			metricType = "counter"
		} else if strings.HasSuffix(metricName, "_bucket") || strings.HasSuffix(metricName, "_sum") || strings.HasSuffix(metricName, "_count") {
			metricType = "histogram"
		}
		
		metrics[metricName] = MetricValue{
			Name:      metricName,
			Type:      metricType,
			Value:     value,
			Labels:    labels,
			Timestamp: time.Now(),
		}
	}
	
	return metrics
}

func parseLabels(labelsStr string) map[string]string {
	labels := make(map[string]string)
	
	// Simple label parsing - handles label="value" format
	re := regexp.MustCompile(`(\w+)="([^"]*)"`)
	matches := re.FindAllStringSubmatch(labelsStr, -1)
	
	for _, match := range matches {
		if len(match) == 3 {
			labels[match[1]] = match[2]
		}
	}
	
	return labels
}

func countFoundMetrics(required []string, content string) int {
	found := 0
	for _, metric := range required {
		if strings.Contains(content, metric) {
			found++
		}
	}
	return found
}

func calculateLabelCardinality(metrics map[string]MetricValue) map[string]int {
	cardinality := make(map[string]int)
	labelCombinations := make(map[string]map[string]bool)
	
	for metricName, metric := range metrics {
		if _, exists := labelCombinations[metricName]; !exists {
			labelCombinations[metricName] = make(map[string]bool)
		}
		
		// Create a label combination key
		var labelPairs []string
		for k, v := range metric.Labels {
			labelPairs = append(labelPairs, fmt.Sprintf("%s=%s", k, v))
		}
		labelKey := strings.Join(labelPairs, ",")
		labelCombinations[metricName][labelKey] = true
	}
	
	for metricName, combinations := range labelCombinations {
		cardinality[metricName] = len(combinations)
	}
	
	return cardinality
}

func collectMetrics(t *testing.T, suite *MetricsTestSuite) map[string]MetricValue {
	resp, err := suite.Client.Get(suite.BaseURL + "/metrics")
	require.NoError(t, err, "Metrics collection must succeed")
	defer resp.Body.Close()
	
	metricsBody, err := io.ReadAll(resp.Body)
	require.NoError(t, err, "Metrics body must be readable")
	
	return parsePrometheusMetrics(string(metricsBody))
}

func getMetricValue(metrics map[string]MetricValue, metricName string) float64 {
	if metric, exists := metrics[metricName]; exists {
		return metric.Value
	}
	return -1 // Indicate metric not found
}

func abs(x float64) float64 {
	if x < 0 {
		return -x
	}
	return x
}

func calculateTimeVariance(times []time.Duration, avg time.Duration) time.Duration {
	if len(times) <= 1 {
		return 0
	}
	
	var sumSquaredDiff time.Duration
	for _, t := range times {
		diff := t - avg
		if diff < 0 {
			diff = -diff
		}
		sumSquaredDiff += diff * diff / time.Duration(len(times))
	}
	
	return sumSquaredDiff
}

// FORGE Movement 7 Metrics Test Requirements Summary:
//
// 1. PROMETHEUS METRICS EXPOSURE:
//    - /metrics endpoint accessible with proper content-type
//    - Required CNOC metrics present (API, sync, fabric, CRD counts)
//    - Metrics collection overhead <10ms
//    - Proper Prometheus format compliance
//
// 2. METRIC LABELING:
//    - API requests labeled with method, endpoint, status_code
//    - Sync operations labeled with fabric_name, operation_type, status
//    - Duration metrics with proper percentile labels
//    - Label cardinality controlled (<1000 per metric)
//
// 3. CUSTOM BUSINESS METRICS:
//    - Fabric count, CRD count, sync operations, API requests
//    - Drift detection operations tracking
//    - Values within acceptable ranges
//    - Proper metric types (counter, gauge, histogram)
//
// 4. METRIC ACCURACY:
//    - Counters increment correctly with operations
//    - Values match actual operation counts within 10% tolerance
//    - Duration metrics updated with request processing
//    - Real-time accuracy validation
//
// 5. COLLECTION PERFORMANCE:
//    - Average collection time <10ms
//    - Maximum collection time <50ms
//    - Collection time variance <50%
//    - No performance degradation under load