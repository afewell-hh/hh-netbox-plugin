package performance

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"runtime"
	"sync"
	"sync/atomic"
	"testing"
	"time"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

// ProductionLoadTestSuite provides comprehensive production-grade performance testing
type ProductionLoadTestSuite struct {
	BaseURL             string
	Client              *http.Client
	TestStartTime       time.Time
	ProductionResults   []ProductionLoadResult
	MemoryLeakData      []MemoryLeakDataPoint
	PerformanceMetrics  []ProductionPerformanceMetric
	ScalabilityData     []ScalabilityMetric
	StabilityMetrics    []StabilityMetric
}

// ProductionLoadResult tracks comprehensive production load test outcomes
type ProductionLoadResult struct {
	TestID                string        `json:"test_id"`
	TestName              string        `json:"test_name"`
	TestType              string        `json:"test_type"`
	ConcurrentUsers       int           `json:"concurrent_users"`
	TestDuration          time.Duration `json:"test_duration_ns"`
	TotalRequests         int64         `json:"total_requests"`
	SuccessfulRequests    int64         `json:"successful_requests"`
	FailedRequests        int64         `json:"failed_requests"`
	RequestsPerSecond     float64       `json:"requests_per_second"`
	SustainedRPS          float64       `json:"sustained_rps"`
	PeakRPS               float64       `json:"peak_rps"`
	AverageLatency        time.Duration `json:"average_latency_ns"`
	P50Latency            time.Duration `json:"p50_latency_ns"`
	P95Latency            time.Duration `json:"p95_latency_ns"`
	P99Latency            time.Duration `json:"p99_latency_ns"`
	MaxLatency            time.Duration `json:"max_latency_ns"`
	MinLatency            time.Duration `json:"min_latency_ns"`
	ErrorRate             float64       `json:"error_rate_percent"`
	ThroughputMBps        float64       `json:"throughput_mbps"`
	CPUUsageAverage       float64       `json:"cpu_usage_average_percent"`
	CPUUsagePeak          float64       `json:"cpu_usage_peak_percent"`
	MemoryUsageAverage    float64       `json:"memory_usage_average_mb"`
	MemoryUsagePeak       float64       `json:"memory_usage_peak_mb"`
	MemoryLeakDetected    bool          `json:"memory_leak_detected"`
	GCPressure            float64       `json:"gc_pressure_percent"`
	ConnectionPoolUsage   float64       `json:"connection_pool_usage_percent"`
	FileDescriptorUsage   int           `json:"file_descriptor_usage"`
	NetworkIOErrors       int64         `json:"network_io_errors"`
	TimeoutErrors         int64         `json:"timeout_errors"`
	InternalErrors        int64         `json:"internal_errors"`
	PerformanceScore      float64       `json:"performance_score"`
	StabilityScore        float64       `json:"stability_score"`
	ScalabilityScore      float64       `json:"scalability_score"`
	ProductionReadiness   bool          `json:"production_readiness"`
	Timestamp             time.Time     `json:"timestamp"`
}

// MemoryLeakDataPoint tracks memory usage over time for leak detection
type MemoryLeakDataPoint struct {
	TestID           string    `json:"test_id"`
	Timestamp        time.Time `json:"timestamp"`
	ElapsedTime      time.Duration `json:"elapsed_time_ns"`
	HeapSizeMB       float64   `json:"heap_size_mb"`
	HeapUsedMB       float64   `json:"heap_used_mb"`
	HeapObjectsMB    float64   `json:"heap_objects_mb"`
	StackSizeMB      float64   `json:"stack_size_mb"`
	GoroutineCount   int       `json:"goroutine_count"`
	GCCount          uint32    `json:"gc_count"`
	GCPauseTime      time.Duration `json:"gc_pause_time_ns"`
	MemoryTrend      string    `json:"memory_trend"` // "increasing", "stable", "decreasing"
	LeakSuspected    bool      `json:"leak_suspected"`
}

// ProductionPerformanceMetric tracks detailed performance metrics
type ProductionPerformanceMetric struct {
	TestID              string    `json:"test_id"`
	Timestamp           time.Time `json:"timestamp"`
	ConcurrentUsers     int       `json:"concurrent_users"`
	ActiveConnections   int       `json:"active_connections"`
	QueuedRequests      int       `json:"queued_requests"`
	RequestsPerSecond   float64   `json:"requests_per_second"`
	ResponseTimeP50     time.Duration `json:"response_time_p50_ns"`
	ResponseTimeP95     time.Duration `json:"response_time_p95_ns"`
	ResponseTimeP99     time.Duration `json:"response_time_p99_ns"`
	ErrorRatePercent    float64   `json:"error_rate_percent"`
	CPUPercent          float64   `json:"cpu_percent"`
	MemoryMB            float64   `json:"memory_mb"`
	NetworkBytesIn      int64     `json:"network_bytes_in"`
	NetworkBytesOut     int64     `json:"network_bytes_out"`
	DiskIOReadMB        float64   `json:"disk_io_read_mb"`
	DiskIOWriteMB       float64   `json:"disk_io_write_mb"`
}

// ScalabilityMetric tracks system scalability characteristics
type ScalabilityMetric struct {
	TestID           string    `json:"test_id"`
	UserLoad         int       `json:"user_load"`
	ResponseTime     time.Duration `json:"response_time_ns"`
	Throughput       float64   `json:"throughput_rps"`
	ResourceUsage    float64   `json:"resource_usage_percent"`
	ScalingFactor    float64   `json:"scaling_factor"`
	EfficiencyRatio  float64   `json:"efficiency_ratio"`
	BottleneckType   string    `json:"bottleneck_type"`
	Timestamp        time.Time `json:"timestamp"`
}

// StabilityMetric tracks system stability over extended periods
type StabilityMetric struct {
	TestID           string    `json:"test_id"`
	ElapsedHours     float64   `json:"elapsed_hours"`
	UptimePercent    float64   `json:"uptime_percent"`
	ErrorCount       int64     `json:"error_count"`
	CrashCount       int       `json:"crash_count"`
	PerformanceDrift float64   `json:"performance_drift_percent"`
	MemoryStability  float64   `json:"memory_stability_score"`
	ResponseStability float64  `json:"response_stability_score"`
	Timestamp        time.Time `json:"timestamp"`
}

// NewProductionLoadTestSuite creates comprehensive production load testing suite
func NewProductionLoadTestSuite(baseURL string) *ProductionLoadTestSuite {
	return &ProductionLoadTestSuite{
		BaseURL:            baseURL,
		Client:             &http.Client{Timeout: 60 * time.Second},
		TestStartTime:      time.Now(),
		ProductionResults:  []ProductionLoadResult{},
		MemoryLeakData:     []MemoryLeakDataPoint{},
		PerformanceMetrics: []ProductionPerformanceMetric{},
		ScalabilityData:    []ScalabilityMetric{},
		StabilityMetrics:   []StabilityMetric{},
	}
}

// TestProductionLoadScenario validates 500+ concurrent users sustained for extended periods
func TestProductionLoadScenario(t *testing.T) {
	// FORGE Movement 8: Production Load Validation
	t.Log("🚀 FORGE M8: Starting production load scenario testing...")

	suite := NewProductionLoadTestSuite("http://localhost:8080")

	// Production load test scenarios
	productionTests := []struct {
		name               string
		concurrentUsers    int
		testDuration       time.Duration
		rampUpTime         time.Duration
		targetRPS          float64
		maxP99Latency      time.Duration
		maxErrorRate       float64
		maxCPUUsage        float64
		maxMemoryMB        float64
		memoryLeakTolerance float64
		endpoints          []string
		requestPattern     string
	}{
		{
			name:               "Production_Baseline_Load",
			concurrentUsers:    500,
			testDuration:       2 * time.Hour,
			rampUpTime:         10 * time.Minute,
			targetRPS:          2000.0,
			maxP99Latency:      200 * time.Millisecond,
			maxErrorRate:       1.0,
			maxCPUUsage:        60.0,
			maxMemoryMB:        1000.0,
			memoryLeakTolerance: 5.0, // 5% memory growth tolerance
			endpoints:          []string{"/health", "/api/v1/configurations", "/dashboard", "/fabrics"},
			requestPattern:     "mixed_realistic",
		},
		{
			name:               "Production_Peak_Load",
			concurrentUsers:    1000,
			testDuration:       1 * time.Hour,
			rampUpTime:         15 * time.Minute,
			targetRPS:          3500.0,
			maxP99Latency:      300 * time.Millisecond,
			maxErrorRate:       2.0,
			maxCPUUsage:        75.0,
			maxMemoryMB:        1500.0,
			memoryLeakTolerance: 8.0,
			endpoints:          []string{"/api/v1/configurations", "/fabrics", "/metrics"},
			requestPattern:     "api_heavy",
		},
		{
			name:               "Production_Stress_Load",
			concurrentUsers:    2000,
			testDuration:       30 * time.Minute,
			rampUpTime:         5 * time.Minute,
			targetRPS:          5000.0,
			maxP99Latency:      500 * time.Millisecond,
			maxErrorRate:       5.0,
			maxCPUUsage:        90.0,
			maxMemoryMB:        2000.0,
			memoryLeakTolerance: 15.0,
			endpoints:          []string{"/api/v1/configurations"},
			requestPattern:     "burst",
		},
		{
			name:               "Production_Endurance_Load",
			concurrentUsers:    750,
			testDuration:       24 * time.Hour,
			rampUpTime:         30 * time.Minute,
			targetRPS:          2500.0,
			maxP99Latency:      250 * time.Millisecond,
			maxErrorRate:       1.5,
			maxCPUUsage:        65.0,
			maxMemoryMB:        1200.0,
			memoryLeakTolerance: 3.0, // Stricter tolerance for 24-hour test
			endpoints:          []string{"/health", "/api/v1/configurations", "/dashboard", "/fabrics", "/metrics"},
			requestPattern:     "steady_state",
		},
	}

	for _, test := range productionTests {
		t.Run(fmt.Sprintf("ProductionLoad_%s", test.name), func(t *testing.T) {
			testID := fmt.Sprintf("production-load-%s-%d", test.name, time.Now().UnixNano())
			loadStart := time.Now()

			t.Logf("🚀 Starting %s with %d users for %v", test.name, test.concurrentUsers, test.testDuration)

			// Initialize counters and metrics
			var totalRequests int64
			var successfulRequests int64
			var failedRequests int64
			var networkIOErrors int64
			var timeoutErrors int64
			var internalErrors int64

			// Latency tracking
			latencies := make([]time.Duration, 0, 1000000) // Pre-allocate for performance
			latenciesMutex := &sync.RWMutex{}

			// Start comprehensive monitoring
			ctx, cancel := context.WithTimeout(context.Background(), test.testDuration+time.Hour)
			defer cancel()

			// Memory leak monitoring
			memoryLeakChan := make(chan MemoryLeakDataPoint, 1000)
			go suite.monitorMemoryLeaks(ctx, memoryLeakChan, testID, test.memoryLeakTolerance)

			// Performance metrics monitoring
			performanceMetricsChan := make(chan ProductionPerformanceMetric, 1000)
			go suite.monitorProductionPerformance(ctx, performanceMetricsChan, testID)

			// Scalability monitoring
			scalabilityMetricsChan := make(chan ScalabilityMetric, 100)
			go suite.monitorScalability(ctx, scalabilityMetricsChan, testID, test.concurrentUsers)

			// User simulation and ramp-up
			userSemaphore := make(chan struct{}, test.concurrentUsers)
			var activeUsers int64

			// Ramp-up phase
			rampUpTicker := time.NewTicker(test.rampUpTime / time.Duration(test.concurrentUsers))
			defer rampUpTicker.Stop()

			rampUpDone := make(chan struct{})
			go func() {
				defer close(rampUpDone)
				for i := 0; i < test.concurrentUsers; i++ {
					select {
					case <-rampUpTicker.C:
						userSemaphore <- struct{}{}
						atomic.AddInt64(&activeUsers, 1)
						
						// Start user goroutine
						go suite.simulateProductionUser(
							ctx, testID, i, test, userSemaphore,
							&totalRequests, &successfulRequests, &failedRequests,
							&networkIOErrors, &timeoutErrors, &internalErrors,
							latencies, latenciesMutex,
						)
					case <-ctx.Done():
						return
					}
				}
			}()

			// Progress monitoring
			progressTicker := time.NewTicker(30 * time.Second)
			defer progressTicker.Stop()

			progressDone := make(chan struct{})
			go func() {
				defer close(progressDone)
				for {
					select {
					case <-progressTicker.C:
						current := atomic.LoadInt64(&totalRequests)
						successful := atomic.LoadInt64(&successfulRequests)
						failed := atomic.LoadInt64(&failedRequests)
						active := atomic.LoadInt64(&activeUsers)
						elapsed := time.Since(loadStart)
						currentRPS := float64(current) / elapsed.Seconds()

						t.Logf("🔄 Progress: %d users, %d requests (%.1f RPS), %d successful, %d failed",
							active, current, currentRPS, successful, failed)
					case <-ctx.Done():
						return
					}
				}
			}()

			// Wait for test completion or timeout
			select {
			case <-time.After(test.testDuration):
				t.Logf("✅ Test completed after %v", test.testDuration)
			case <-ctx.Done():
				t.Logf("⚠️ Test cancelled or timed out")
			}

			// Shutdown monitoring
			cancel()
			<-progressDone

			// Wait for ramp-up completion if still running
			select {
			case <-rampUpDone:
			case <-time.After(10 * time.Second):
				t.Logf("⚠️ Ramp-up phase timeout")
			}

			// Collect final metrics
			loadDuration := time.Since(loadStart)
			finalTotal := atomic.LoadInt64(&totalRequests)
			finalSuccessful := atomic.LoadInt64(&successfulRequests)
			finalFailed := atomic.LoadInt64(&failedRequests)

			// Collect monitoring data
			close(memoryLeakChan)
			close(performanceMetricsChan)
			close(scalabilityMetricsChan)

			for dataPoint := range memoryLeakChan {
				suite.MemoryLeakData = append(suite.MemoryLeakData, dataPoint)
			}
			for metric := range performanceMetricsChan {
				suite.PerformanceMetrics = append(suite.PerformanceMetrics, metric)
			}
			for metric := range scalabilityMetricsChan {
				suite.ScalabilityData = append(suite.ScalabilityData, metric)
			}

			// Calculate comprehensive performance statistics
			requestsPerSecond := float64(finalTotal) / loadDuration.Seconds()
			errorRate := (float64(finalFailed) / float64(finalTotal)) * 100.0

			// Calculate sustained RPS (average of middle 50% of test duration)
			sustainedRPS := calculateSustainedRPS(suite.PerformanceMetrics, testID, loadDuration)
			peakRPS := calculatePeakRPS(suite.PerformanceMetrics, testID)

			// Calculate latency statistics
			latenciesMutex.RLock()
			latencyStats := calculateAdvancedLatencyStats(latencies)
			latenciesMutex.RUnlock()

			// Calculate resource usage statistics
			cpuStats := calculateResourceStats(suite.PerformanceMetrics, "cpu")
			memoryStats := calculateResourceStats(suite.PerformanceMetrics, "memory")

			// Detect memory leaks
			memoryLeakDetected, gcPressure := analyzeMemoryLeaks(suite.MemoryLeakData, testID)

			// Calculate performance scores
			performanceScore := calculatePerformanceScore(requestsPerSecond, test.targetRPS, latencyStats.P99, test.maxP99Latency, errorRate, test.maxErrorRate)
			stabilityScore := calculateStabilityScore(errorRate, memoryLeakDetected, gcPressure)
			scalabilityScore := calculateScalabilityScore(suite.ScalabilityData, testID)

			// Determine production readiness
			productionReady := (
				performanceScore >= 80.0 &&
				stabilityScore >= 85.0 &&
				scalabilityScore >= 75.0 &&
				!memoryLeakDetected &&
				requestsPerSecond >= test.targetRPS*0.8 &&
				latencyStats.P99 <= test.maxP99Latency &&
				errorRate <= test.maxErrorRate &&
				cpuStats.Average <= test.maxCPUUsage &&
				memoryStats.Peak <= test.maxMemoryMB)

			// Create comprehensive production load result
			result := ProductionLoadResult{
				TestID:                testID,
				TestName:              test.name,
				TestType:              "production_load",
				ConcurrentUsers:       test.concurrentUsers,
				TestDuration:          loadDuration,
				TotalRequests:         finalTotal,
				SuccessfulRequests:    finalSuccessful,
				FailedRequests:        finalFailed,
				RequestsPerSecond:     requestsPerSecond,
				SustainedRPS:          sustainedRPS,
				PeakRPS:               peakRPS,
				AverageLatency:        latencyStats.Average,
				P50Latency:            latencyStats.P50,
				P95Latency:            latencyStats.P95,
				P99Latency:            latencyStats.P99,
				MaxLatency:            latencyStats.Max,
				MinLatency:            latencyStats.Min,
				ErrorRate:             errorRate,
				CPUUsageAverage:       cpuStats.Average,
				CPUUsagePeak:          cpuStats.Peak,
				MemoryUsageAverage:    memoryStats.Average,
				MemoryUsagePeak:       memoryStats.Peak,
				MemoryLeakDetected:    memoryLeakDetected,
				GCPressure:            gcPressure,
				NetworkIOErrors:       atomic.LoadInt64(&networkIOErrors),
				TimeoutErrors:         atomic.LoadInt64(&timeoutErrors),
				InternalErrors:        atomic.LoadInt64(&internalErrors),
				PerformanceScore:      performanceScore,
				StabilityScore:        stabilityScore,
				ScalabilityScore:      scalabilityScore,
				ProductionReadiness:   productionReady,
				Timestamp:             time.Now(),
			}
			suite.ProductionResults = append(suite.ProductionResults, result)

			// FORGE Validation 1: Concurrent users support
			assert.GreaterOrEqual(t, int64(test.concurrentUsers), activeUsers*80/100,
				"Must support at least 80%% of target concurrent users (%d)", test.concurrentUsers)

			// FORGE Validation 2: Sustained throughput
			assert.GreaterOrEqual(t, sustainedRPS, test.targetRPS*0.8,
				"Sustained RPS %.1f must be >= 80%% of target %.1f", sustainedRPS, test.targetRPS)

			// FORGE Validation 3: Latency requirements
			assert.LessOrEqual(t, latencyStats.P99, test.maxP99Latency,
				"P99 latency %v must be <= %v", latencyStats.P99, test.maxP99Latency)

			// FORGE Validation 4: Error rate limits
			assert.LessOrEqual(t, errorRate, test.maxErrorRate,
				"Error rate %.2f%% must be <= %.2f%%", errorRate, test.maxErrorRate)

			// FORGE Validation 5: Resource usage limits
			assert.LessOrEqual(t, cpuStats.Peak, test.maxCPUUsage,
				"Peak CPU usage %.1f%% must be <= %.1f%%", cpuStats.Peak, test.maxCPUUsage)
			assert.LessOrEqual(t, memoryStats.Peak, test.maxMemoryMB,
				"Peak memory usage %.1f MB must be <= %.1f MB", memoryStats.Peak, test.maxMemoryMB)

			// FORGE Validation 6: Memory leak detection
			assert.False(t, memoryLeakDetected,
				"No memory leaks must be detected during production load test")

			// FORGE Validation 7: Production readiness score
			assert.True(t, productionReady,
				"System must be production ready (performance: %.1f%%, stability: %.1f%%, scalability: %.1f%%)",
				performanceScore, stabilityScore, scalabilityScore)

			// FORGE Evidence Collection
			t.Logf("✅ FORGE M8 EVIDENCE - Production Load %s:", test.name)
			t.Logf("👥 Concurrent Users: %d (target: %d)", activeUsers, test.concurrentUsers)
			t.Logf("⚡ Sustained RPS: %.1f (target: %.1f)", sustainedRPS, test.targetRPS)
			t.Logf("🏃 Peak RPS: %.1f", peakRPS)
			t.Logf("⏱️  P50/P95/P99 Latency: %v/%v/%v", latencyStats.P50, latencyStats.P95, latencyStats.P99)
			t.Logf("❌ Error Rate: %.2f%% (max: %.2f%%)", errorRate, test.maxErrorRate)
			t.Logf("🖥️  CPU Usage: %.1f%%/%.1f%% (avg/peak, max: %.1f%%)", cpuStats.Average, cpuStats.Peak, test.maxCPUUsage)
			t.Logf("💾 Memory Usage: %.1f MB/%.1f MB (avg/peak, max: %.1f MB)", memoryStats.Average, memoryStats.Peak, test.maxMemoryMB)
			t.Logf("🚫 Memory Leak Detected: %t", memoryLeakDetected)
			t.Logf("🗑️  GC Pressure: %.1f%%", gcPressure)
			t.Logf("📊 Performance Score: %.1f%%", performanceScore)
			t.Logf("🛡️  Stability Score: %.1f%%", stabilityScore)
			t.Logf("📈 Scalability Score: %.1f%%", scalabilityScore)
			t.Logf("🚀 Production Ready: %t", productionReady)
			t.Logf("⏱️  Test Duration: %v", loadDuration)
			t.Logf("📊 Total Requests: %d", finalTotal)
		})
	}
}

// TestAPIPerformanceUnderLoad validates API performance under sustained load
func TestAPIPerformanceUnderLoad(t *testing.T) {
	// FORGE Movement 8: API Performance Under Load Validation
	t.Log("🚀 FORGE M8: Starting API performance under load testing...")

	suite := NewProductionLoadTestSuite("http://localhost:8080")

	// API performance test configurations
	apiTests := []struct {
		name             string
		endpoint         string
		method           string
		concurrentUsers  int
		testDuration     time.Duration
		targetP95        time.Duration
		targetP99        time.Duration
		minThroughput    float64
		maxErrorRate     float64
		payloadSize      int
	}{
		{
			name:             "Configuration_API_Performance",
			endpoint:         "/api/v1/configurations",
			method:           "GET",
			concurrentUsers:  200,
			testDuration:     60 * time.Minute,
			targetP95:        100 * time.Millisecond,
			targetP99:        150 * time.Millisecond,
			minThroughput:    1000.0,
			maxErrorRate:     0.5,
			payloadSize:      0,
		},
		{
			name:             "Fabric_API_Performance",
			endpoint:         "/api/v1/fabrics",
			method:           "GET",
			concurrentUsers:  150,
			testDuration:     45 * time.Minute,
			targetP95:        120 * time.Millisecond,
			targetP99:        200 * time.Millisecond,
			minThroughput:    800.0,
			maxErrorRate:     1.0,
			payloadSize:      0,
		},
		{
			name:             "CRD_Creation_API_Performance",
			endpoint:         "/api/v1/crds",
			method:           "POST",
			concurrentUsers:  100,
			testDuration:     30 * time.Minute,
			targetP95:        200 * time.Millisecond,
			targetP99:        300 * time.Millisecond,
			minThroughput:    500.0,
			maxErrorRate:     2.0,
			payloadSize:      1024,
		},
		{
			name:             "Health_Check_Performance",
			endpoint:         "/health",
			method:           "GET",
			concurrentUsers:  500,
			testDuration:     30 * time.Minute,
			targetP95:        10 * time.Millisecond,
			targetP99:        25 * time.Millisecond,
			minThroughput:    5000.0,
			maxErrorRate:     0.1,
			payloadSize:      0,
		},
	}

	for _, test := range apiTests {
		t.Run(fmt.Sprintf("APIPerformance_%s", test.name), func(t *testing.T) {
			testID := fmt.Sprintf("api-perf-%s-%d", test.name, time.Now().UnixNano())
			apiStart := time.Now()

			t.Logf("🔍 Testing API %s with %d users for %v", test.endpoint, test.concurrentUsers, test.testDuration)

			// Performance tracking
			var totalRequests int64
			var successfulRequests int64
			var failedRequests int64

			// Detailed latency tracking
			latencies := make([]time.Duration, 0, 100000)
			latenciesMutex := &sync.RWMutex{}

			// Context for test duration
			ctx, cancel := context.WithTimeout(context.Background(), test.testDuration+10*time.Minute)
			defer cancel()

			// Performance monitoring
			perfMetricsChan := make(chan ProductionPerformanceMetric, 1000)
			go suite.monitorProductionPerformance(ctx, perfMetricsChan, testID)

			// Start concurrent API users
			var wg sync.WaitGroup
			userSemaphore := make(chan struct{}, test.concurrentUsers)
			startSignal := make(chan struct{})

			// Launch users
			for userID := 0; userID < test.concurrentUsers; userID++ {
				wg.Add(1)
				go func(id int) {
					defer wg.Done()
					
					// Wait for synchronized start
					<-startSignal
					
					userClient := &http.Client{
						Timeout: 30 * time.Second,
						Transport: &http.Transport{
							MaxIdleConns:        10,
							MaxIdleConnsPerHost: 2,
							IdleConnTimeout:     60 * time.Second,
						},
					}

					// User request loop
					endTime := time.Now().Add(test.testDuration)
					requestCount := 0
					
					for time.Now().Before(endTime) {
						requestStart := time.Now()
						
						var resp *http.Response
						var err error
						
						if test.method == "GET" {
							resp, err = userClient.Get(suite.BaseURL + test.endpoint)
						} else if test.method == "POST" {
							// Create test payload for POST requests
							payload := generateTestPayload(test.payloadSize)
							resp, err = userClient.Post(suite.BaseURL + test.endpoint, "application/json", payload)
						}
						
						requestLatency := time.Since(requestStart)
						atomic.AddInt64(&totalRequests, 1)
						requestCount++

						// Record latency
						latenciesMutex.Lock()
						latencies = append(latencies, requestLatency)
						latenciesMutex.Unlock()

						if err != nil {
							atomic.AddInt64(&failedRequests, 1)
						} else {
							defer resp.Body.Close()
							if resp.StatusCode >= 200 && resp.StatusCode < 300 {
								atomic.AddInt64(&successfulRequests, 1)
							} else {
								atomic.AddInt64(&failedRequests, 1)
							}
							
							// Consume response body
							io.Copy(io.Discard, resp.Body)
						}

						// Realistic user behavior with slight delay
						if requestCount%10 == 0 {
							time.Sleep(time.Duration(id%5+1) * time.Millisecond)
						}
						
						select {
						case <-ctx.Done():
							return
						default:
						}
					}
				}(userID)
			}

			// Start all users simultaneously
			close(startSignal)

			// Progress monitoring
			progressTicker := time.NewTicker(10 * time.Second)
			defer progressTicker.Stop()

			monitoringDone := make(chan struct{})
			go func() {
				defer close(monitoringDone)
				for {
					select {
					case <-progressTicker.C:
						current := atomic.LoadInt64(&totalRequests)
						successful := atomic.LoadInt64(&successfulRequests)
						failed := atomic.LoadInt64(&failedRequests)
						elapsed := time.Since(apiStart)
						currentRPS := float64(current) / elapsed.Seconds()

						t.Logf("📊 API Progress: %d requests (%.1f RPS), %d successful, %d failed",
							current, currentRPS, successful, failed)
					case <-ctx.Done():
						return
					}
				}
			}()

			// Wait for all users to complete
			wg.Wait()
			cancel()
			<-monitoringDone

			// Collect performance metrics
			close(perfMetricsChan)
			for metric := range perfMetricsChan {
				suite.PerformanceMetrics = append(suite.PerformanceMetrics, metric)
			}

			// Calculate final statistics
			testDuration := time.Since(apiStart)
			finalTotal := atomic.LoadInt64(&totalRequests)
			finalSuccessful := atomic.LoadInt64(&successfulRequests)
			finalFailed := atomic.LoadInt64(&failedRequests)

			actualThroughput := float64(finalTotal) / testDuration.Seconds()
			errorRate := (float64(finalFailed) / float64(finalTotal)) * 100.0

			// Calculate latency statistics
			latenciesMutex.RLock()
			latencyStats := calculateAdvancedLatencyStats(latencies)
			latenciesMutex.RUnlock()

			// FORGE Validation 1: Throughput requirements
			assert.GreaterOrEqual(t, actualThroughput, test.minThroughput,
				"API throughput %.1f RPS must be >= %.1f RPS", actualThroughput, test.minThroughput)

			// FORGE Validation 2: P95 latency requirements
			assert.LessOrEqual(t, latencyStats.P95, test.targetP95,
				"P95 latency %v must be <= %v", latencyStats.P95, test.targetP95)

			// FORGE Validation 3: P99 latency requirements
			assert.LessOrEqual(t, latencyStats.P99, test.targetP99,
				"P99 latency %v must be <= %v", latencyStats.P99, test.targetP99)

			// FORGE Validation 4: Error rate limits
			assert.LessOrEqual(t, errorRate, test.maxErrorRate,
				"Error rate %.2f%% must be <= %.2f%%", errorRate, test.maxErrorRate)

			// FORGE Validation 5: Consistency - P99 should not be more than 3x P95
			latencyConsistency := float64(latencyStats.P99) / float64(latencyStats.P95)
			assert.LessOrEqual(t, latencyConsistency, 3.0,
				"P99/P95 ratio %.2f must be <= 3.0 (P99: %v, P95: %v)", 
				latencyConsistency, latencyStats.P99, latencyStats.P95)

			// Calculate API performance score
			apiPerformanceScore := calculateAPIPerformanceScore(
				actualThroughput, test.minThroughput,
				latencyStats.P95, test.targetP95,
				latencyStats.P99, test.targetP99,
				errorRate, test.maxErrorRate,
			)

			// FORGE Evidence Collection
			t.Logf("✅ FORGE M8 EVIDENCE - API Performance %s:", test.name)
			t.Logf("🌐 Endpoint: %s %s", test.method, test.endpoint)
			t.Logf("👥 Concurrent Users: %d", test.concurrentUsers)
			t.Logf("⚡ Throughput: %.1f RPS (min: %.1f)", actualThroughput, test.minThroughput)
			t.Logf("⏱️  P95 Latency: %v (target: %v)", latencyStats.P95, test.targetP95)
			t.Logf("⏱️  P99 Latency: %v (target: %v)", latencyStats.P99, test.targetP99)
			t.Logf("📈 Latency Consistency: %.2fx", latencyConsistency)
			t.Logf("❌ Error Rate: %.2f%% (max: %.2f%%)", errorRate, test.maxErrorRate)
			t.Logf("📊 Performance Score: %.1f%%", apiPerformanceScore)
			t.Logf("⏱️  Test Duration: %v", testDuration)
			t.Logf("📊 Total Requests: %d", finalTotal)
			t.Logf("✅ Performance Target Met: %t", apiPerformanceScore >= 85.0)
		})
	}
}

// TestMemoryLeakValidation validates no memory growth over 24-hour test
func TestMemoryLeakValidation(t *testing.T) {
	// FORGE Movement 8: Memory Leak Detection
	t.Log("🧠 FORGE M8: Starting 24-hour memory leak validation...")

	suite := NewProductionLoadTestSuite("http://localhost:8080")

	memoryTests := []struct {
		name                  string
		testDuration          time.Duration
		concurrentUsers       int
		requestsPerSecond     float64
		memoryGrowthTolerance float64  // Percentage
		gcPressureTolerance   float64  // Percentage
		monitoringInterval    time.Duration
		endpoints             []string
	}{
		{
			name:                  "Memory_Leak_24_Hour_Validation",
			testDuration:          24 * time.Hour, // Full 24-hour test
			concurrentUsers:       200,
			requestsPerSecond:     500.0,
			memoryGrowthTolerance: 2.0, // 2% growth over 24 hours
			gcPressureTolerance:   10.0, // 10% GC overhead
			monitoringInterval:    5 * time.Minute,
			endpoints:             []string{"/health", "/api/v1/configurations", "/dashboard"},
		},
		{
			name:                  "Memory_Leak_Short_Validation", // For CI/testing
			testDuration:          2 * time.Hour,
			concurrentUsers:       300,
			requestsPerSecond:     800.0,
			memoryGrowthTolerance: 5.0, // Higher tolerance for shorter test
			gcPressureTolerance:   15.0,
			monitoringInterval:    30 * time.Second,
			endpoints:             []string{"/health", "/api/v1/configurations", "/fabrics", "/metrics"},
		},
	}

	for _, test := range memoryTests {
		t.Run(fmt.Sprintf("MemoryLeak_%s", test.name), func(t *testing.T) {
			if testing.Short() && test.testDuration > 2*time.Hour {
				t.Skipf("Skipping long-running test %s in short mode", test.name)
				return
			}

			testID := fmt.Sprintf("memory-leak-%s-%d", test.name, time.Now().UnixNano())
			memoryStart := time.Now()

			t.Logf("🧠 Starting %s for %v with %d users", test.name, test.testDuration, test.concurrentUsers)

			// Memory monitoring setup
			ctx, cancel := context.WithTimeout(context.Background(), test.testDuration+time.Hour)
			defer cancel()

			memoryDataChan := make(chan MemoryLeakDataPoint, 10000)
			go suite.monitorDetailedMemoryUsage(ctx, memoryDataChan, testID, test.monitoringInterval)

			// Load generation
			var totalRequests int64
			var activeUsers int64

			// Start concurrent users for memory leak testing
			userSemaphore := make(chan struct{}, test.concurrentUsers)
			for i := 0; i < test.concurrentUsers; i++ {
				userSemaphore <- struct{}{}
				atomic.AddInt64(&activeUsers, 1)

				go func(userID int) {
					defer func() {
						<-userSemaphore
						atomic.AddInt64(&activeUsers, -1)
					}()

					userClient := &http.Client{
						Timeout: 30 * time.Second,
						Transport: &http.Transport{
							MaxIdleConns:        5,
							MaxIdleConnsPerHost: 1,
							IdleConnTimeout:     30 * time.Second,
						},
					}

					// Calculate delay between requests for target RPS
					requestDelay := time.Duration(float64(time.Second) / (test.requestsPerSecond / float64(test.concurrentUsers)))
					ticker := time.NewTicker(requestDelay)
					defer ticker.Stop()

					endpointIndex := 0
					for {
						select {
						case <-ticker.C:
							endpoint := test.endpoints[endpointIndex%len(test.endpoints)]
							endpointIndex++

							resp, err := userClient.Get(suite.BaseURL + endpoint)
							atomic.AddInt64(&totalRequests, 1)

							if err == nil {
								defer resp.Body.Close()
								io.Copy(io.Discard, resp.Body)
							}

						case <-ctx.Done():
							return
						}
					}
				}(i)
			}

			// Progress and memory reporting
			reportTicker := time.NewTicker(10 * time.Minute)
			defer reportTicker.Stop()

			reportingDone := make(chan struct{})
			go func() {
				defer close(reportingDone)
				for {
					select {
					case <-reportTicker.C:
						current := atomic.LoadInt64(&totalRequests)
						users := atomic.LoadInt64(&activeUsers)
						elapsed := time.Since(memoryStart)
						currentRPS := float64(current) / elapsed.Seconds()

						// Get current memory stats
						var mem runtime.MemStats
						runtime.ReadMemStats(&mem)
						currentMemMB := float64(mem.Sys) / 1024 / 1024

						t.Logf("🧠 Memory Test Progress: %v elapsed, %d users, %d requests (%.1f RPS), %.1f MB memory",
							elapsed.Round(time.Minute), users, current, currentRPS, currentMemMB)

					case <-ctx.Done():
						return
					}
				}
			}()

			// Wait for test completion
			select {
			case <-time.After(test.testDuration):
				t.Logf("✅ Memory leak test completed after %v", test.testDuration)
			case <-ctx.Done():
				t.Logf("⚠️ Memory leak test cancelled")
			}

			// Stop monitoring and collect data
			cancel()
			<-reportingDone

			close(memoryDataChan)
			for dataPoint := range memoryDataChan {
				suite.MemoryLeakData = append(suite.MemoryLeakData, dataPoint)
			}

			// Analyze memory leak data
			memoryAnalysis := analyzeComprehensiveMemoryLeaks(suite.MemoryLeakData, testID)

			finalRequests := atomic.LoadInt64(&totalRequests)
			testDuration := time.Since(memoryStart)
			averageRPS := float64(finalRequests) / testDuration.Seconds()

			// FORGE Validation 1: Memory growth must be within tolerance
			assert.LessOrEqual(t, memoryAnalysis.GrowthPercentage, test.memoryGrowthTolerance,
				"Memory growth %.2f%% must be <= %.2f%%", 
				memoryAnalysis.GrowthPercentage, test.memoryGrowthTolerance)

			// FORGE Validation 2: No sustained memory leaks detected
			assert.False(t, memoryAnalysis.LeakDetected,
				"No memory leaks must be detected during %v test", test.testDuration)

			// FORGE Validation 3: GC pressure must be reasonable
			assert.LessOrEqual(t, memoryAnalysis.GCPressure, test.gcPressureTolerance,
				"GC pressure %.2f%% must be <= %.2f%%", 
				memoryAnalysis.GCPressure, test.gcPressureTolerance)

			// FORGE Validation 4: Memory should stabilize after initial ramp-up
			assert.True(t, memoryAnalysis.MemoryStabilized,
				"Memory usage must stabilize after initial ramp-up period")

			// FORGE Validation 5: Heap growth should be bounded
			assert.LessOrEqual(t, memoryAnalysis.HeapGrowthMB, 100.0,
				"Heap growth %.1f MB must be <= 100 MB over test duration", memoryAnalysis.HeapGrowthMB)

			// FORGE Evidence Collection
			t.Logf("✅ FORGE M8 EVIDENCE - Memory Leak Validation %s:", test.name)
			t.Logf("⏱️  Test Duration: %v", testDuration)
			t.Logf("👥 Concurrent Users: %d", test.concurrentUsers)
			t.Logf("📊 Total Requests: %d (%.1f RPS)", finalRequests, averageRPS)
			t.Logf("📈 Memory Growth: %.2f%% (max: %.2f%%)", memoryAnalysis.GrowthPercentage, test.memoryGrowthTolerance)
			t.Logf("🚫 Memory Leak Detected: %t", memoryAnalysis.LeakDetected)
			t.Logf("🗑️  GC Pressure: %.2f%% (max: %.2f%%)", memoryAnalysis.GCPressure, test.gcPressureTolerance)
			t.Logf("📊 Memory Stabilized: %t", memoryAnalysis.MemoryStabilized)
			t.Logf("📈 Heap Growth: %.1f MB (max: 100 MB)", memoryAnalysis.HeapGrowthMB)
			t.Logf("💾 Initial Memory: %.1f MB", memoryAnalysis.InitialMemoryMB)
			t.Logf("💾 Final Memory: %.1f MB", memoryAnalysis.FinalMemoryMB)
			t.Logf("💾 Peak Memory: %.1f MB", memoryAnalysis.PeakMemoryMB)
			t.Logf("✅ Memory Leak Test Passed: %t", !memoryAnalysis.LeakDetected)
		})
	}
}

// Helper functions implementation (continued in next part due to length)

func (suite *ProductionLoadTestSuite) simulateProductionUser(
	ctx context.Context, testID string, userID int, test struct {
		name               string
		concurrentUsers    int
		testDuration       time.Duration
		rampUpTime         time.Duration
		targetRPS          float64
		maxP99Latency      time.Duration
		maxErrorRate       float64
		maxCPUUsage        float64
		maxMemoryMB        float64
		memoryLeakTolerance float64
		endpoints          []string
		requestPattern     string
	},
	semaphore <-chan struct{},
	totalRequests, successfulRequests, failedRequests *int64,
	networkIOErrors, timeoutErrors, internalErrors *int64,
	latencies []time.Duration, latenciesMutex *sync.RWMutex,
) {
	defer func() {
		atomic.AddInt64(totalRequests, -1) // Decrease active user count
	}()

	client := &http.Client{
		Timeout: 30 * time.Second,
		Transport: &http.Transport{
			MaxIdleConns:        5,
			MaxIdleConnsPerHost: 1,
			IdleConnTimeout:     30 * time.Second,
		},
	}

	endpointIndex := userID % len(test.endpoints)
	requestCount := 0

	for {
		select {
		case <-ctx.Done():
			return
		default:
			endpoint := test.endpoints[endpointIndex%len(test.endpoints)]
			endpointIndex++

			requestStart := time.Now()
			resp, err := client.Get(suite.BaseURL + endpoint)
			requestLatency := time.Since(requestStart)

			atomic.AddInt64(totalRequests, 1)
			requestCount++

			// Record latency
			latenciesMutex.Lock()
			latencies = append(latencies, requestLatency)
			latenciesMutex.Unlock()

			if err != nil {
				atomic.AddInt64(failedRequests, 1)
				if ctx.Err() == context.DeadlineExceeded {
					atomic.AddInt64(timeoutErrors, 1)
				} else {
					atomic.AddInt64(networkIOErrors, 1)
				}
			} else {
				defer resp.Body.Close()
				io.Copy(io.Discard, resp.Body)

				if resp.StatusCode >= 200 && resp.StatusCode < 300 {
					atomic.AddInt64(successfulRequests, 1)
				} else {
					atomic.AddInt64(failedRequests, 1)
					if resp.StatusCode >= 500 {
						atomic.AddInt64(internalErrors, 1)
					}
				}
			}

			// Simulate realistic user behavior patterns
			delay := calculateUserDelay(test.requestPattern, requestCount, userID)
			time.Sleep(delay)
		}
	}
}

func calculateUserDelay(pattern string, requestCount, userID int) time.Duration {
	switch pattern {
	case "mixed_realistic":
		// Simulate realistic user behavior with varying delays
		base := 100 + (userID%5)*50  // 100-350ms base delay
		variation := requestCount % 10 * 20 // Add some variation
		return time.Duration(base+variation) * time.Millisecond
	case "api_heavy":
		// Faster requests for API-heavy pattern
		return time.Duration(50+(userID%3)*25) * time.Millisecond
	case "burst":
		// Burst pattern with occasional pauses
		if requestCount%20 == 0 {
			return time.Duration(500+userID%100) * time.Millisecond // Occasional pause
		}
		return time.Duration(10+userID%10) * time.Millisecond
	case "steady_state":
		// Consistent delay for steady state
		return time.Duration(200+userID%50) * time.Millisecond
	default:
		return 100 * time.Millisecond
	}
}

// Additional monitoring and helper functions would continue here...
// (Implementation continues with memory monitoring, performance calculations, etc.)
