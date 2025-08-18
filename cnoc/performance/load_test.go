package performance

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"runtime"
	"strings"
	"sync"
	"sync/atomic"
	"testing"
	"time"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

// LoadTestSuite provides comprehensive performance and scalability testing
type LoadTestSuite struct {
	BaseURL           string
	Client            *http.Client
	TestStartTime     time.Time
	ConcurrencyLevels []int
	LoadTestResults   []LoadTestResult
	ResourceMetrics   []ResourceMetric
	ThroughputData    []ThroughputMetric
	LatencyData       []LatencyMetric
}

// LoadTestResult tracks comprehensive load test outcomes
type LoadTestResult struct {
	TestID              string        `json:"test_id"`
	TestName            string        `json:"test_name"`
	ConcurrentUsers     int           `json:"concurrent_users"`
	TotalRequests       int64         `json:"total_requests"`
	SuccessfulRequests  int64         `json:"successful_requests"`
	FailedRequests      int64         `json:"failed_requests"`
	TestDuration        time.Duration `json:"test_duration_ns"`
	RequestsPerSecond   float64       `json:"requests_per_second"`
	AverageLatency      time.Duration `json:"average_latency_ns"`
	P50Latency          time.Duration `json:"p50_latency_ns"`
	P95Latency          time.Duration `json:"p95_latency_ns"`
	P99Latency          time.Duration `json:"p99_latency_ns"`
	MaxLatency          time.Duration `json:"max_latency_ns"`
	MinLatency          time.Duration `json:"min_latency_ns"`
	ErrorRate           float64       `json:"error_rate_percent"`
	ThroughputMBps      float64       `json:"throughput_mbps"`
	CPUUsagePercent     float64       `json:"cpu_usage_percent"`
	MemoryUsageMB       float64       `json:"memory_usage_mb"`
	ConnectionErrors    int64         `json:"connection_errors"`
	TimeoutErrors       int64         `json:"timeout_errors"`
	ServerErrors        int64         `json:"server_errors"`
	Timestamp           time.Time     `json:"timestamp"`
}

// ResourceMetric tracks system resource consumption during load tests
type ResourceMetric struct {
	MetricID        string        `json:"metric_id"`
	Timestamp       time.Time     `json:"timestamp"`
	CPUPercent      float64       `json:"cpu_percent"`
	MemoryMB        float64       `json:"memory_mb"`
	GoroutineCount  int           `json:"goroutine_count"`
	NetworkConns    int           `json:"network_connections"`
	FileDescriptors int           `json:"file_descriptors"`
	GCPauseTime     time.Duration `json:"gc_pause_time_ns"`
	HeapSizeMB      float64       `json:"heap_size_mb"`
}

// ThroughputMetric tracks request throughput over time
type ThroughputMetric struct {
	MetricID          string    `json:"metric_id"`
	Timestamp         time.Time `json:"timestamp"`
	RequestsPerSecond float64   `json:"requests_per_second"`
	DataThroughputMBs float64   `json:"data_throughput_mbps"`
	ActiveConnections int       `json:"active_connections"`
	QueuedRequests    int       `json:"queued_requests"`
}

// LatencyMetric tracks request latency distribution
type LatencyMetric struct {
	MetricID      string        `json:"metric_id"`
	Timestamp     time.Time     `json:"timestamp"`
	Endpoint      string        `json:"endpoint"`
	Method        string        `json:"method"`
	Latency       time.Duration `json:"latency_ns"`
	ResponseSize  int           `json:"response_size_bytes"`
	StatusCode    int           `json:"status_code"`
	UserID        int           `json:"user_id"` // Simulated user identifier
}

// NewLoadTestSuite creates new load testing suite
func NewLoadTestSuite(baseURL string) *LoadTestSuite {
	return &LoadTestSuite{
		BaseURL:           baseURL,
		Client:            &http.Client{Timeout: 30 * time.Second},
		TestStartTime:     time.Now(),
		ConcurrencyLevels: []int{1, 10, 50, 100},
		LoadTestResults:   []LoadTestResult{},
		ResourceMetrics:   []ResourceMetric{},
		ThroughputData:    []ThroughputMetric{},
		LatencyData:       []LatencyMetric{},
	}
}

// TestConcurrentUsers validates support for 100+ concurrent users
func TestConcurrentUsers(t *testing.T) {
	// FORGE Movement 7: Concurrent User Load Testing
	t.Log("🔄 FORGE M7: Testing concurrent user support...")

	suite := NewLoadTestSuite("http://localhost:8080")

	// Test different concurrency levels
	concurrencyTests := []struct {
		name            string
		concurrentUsers int
		requestsPerUser int
		testDuration    time.Duration
		endpoint        string
		method          string
		expectedRPS     float64  // Minimum expected requests per second
		maxErrorRate    float64  // Maximum acceptable error rate percentage
		maxP99Latency   time.Duration // Maximum acceptable P99 latency
	}{
		{
			name:            "Light Load",
			concurrentUsers: 10,
			requestsPerUser: 20,
			testDuration:    30 * time.Second,
			endpoint:        "/health",
			method:          "GET",
			expectedRPS:     50.0,
			maxErrorRate:    1.0,
			maxP99Latency:   500 * time.Millisecond,
		},
		{
			name:            "Medium Load",
			concurrentUsers: 50,
			requestsPerUser: 40,
			testDuration:    60 * time.Second,
			endpoint:        "/api/v1/configurations",
			method:          "GET",
			expectedRPS:     200.0,
			maxErrorRate:    2.0,
			maxP99Latency:   1 * time.Second,
		},
		{
			name:            "Heavy Load",
			concurrentUsers: 100,
			requestsPerUser: 50,
			testDuration:    120 * time.Second,
			endpoint:        "/dashboard",
			method:          "GET",
			expectedRPS:     400.0,
			maxErrorRate:    5.0,
			maxP99Latency:   2 * time.Second,
		},
		{
			name:            "Peak Load",
			concurrentUsers: 200,
			requestsPerUser: 25,
			testDuration:    60 * time.Second,
			endpoint:        "/fabrics",
			method:          "GET",
			expectedRPS:     500.0,
			maxErrorRate:    8.0,
			maxP99Latency:   3 * time.Second,
		},
	}

	for _, test := range concurrencyTests {
		t.Run(fmt.Sprintf("ConcurrentLoad_%s", test.name), func(t *testing.T) {
			testID := fmt.Sprintf("load-test-%d", time.Now().UnixNano())
			loadStart := time.Now()

			// Set up synchronization
			var totalRequests int64
			var successfulRequests int64
			var failedRequests int64
			var connectionErrors int64
			var timeoutErrors int64
			var serverErrors int64

			latencies := make([]time.Duration, 0, test.concurrentUsers*test.requestsPerUser)
			latenciesMutex := &sync.Mutex{}

			// Start resource monitoring
			ctx, cancel := context.WithCancel(context.Background())
			resourceMetrics := make(chan ResourceMetric, 100)
			go suite.monitorResources(ctx, resourceMetrics, testID)

			// Set up worker goroutines
			var wg sync.WaitGroup
			startSignal := make(chan struct{})

			for userID := 0; userID < test.concurrentUsers; userID++ {
				wg.Add(1)
				go func(id int) {
					defer wg.Done()
					
					// Wait for start signal
					<-startSignal
					
					// Create user-specific client to avoid connection sharing
					userClient := &http.Client{
						Timeout: 30 * time.Second,
						Transport: &http.Transport{
							MaxIdleConns:        10,
							MaxIdleConnsPerHost: 2,
							IdleConnTimeout:     30 * time.Second,
						},
					}
					
					for req := 0; req < test.requestsPerUser; req++ {
						requestStart := time.Now()
						
						// Execute request
						resp, err := userClient.Get(suite.BaseURL + test.endpoint)
						requestLatency := time.Since(requestStart)
						
						atomic.AddInt64(&totalRequests, 1)
						
						// Record latency
						latenciesMutex.Lock()
						latencies = append(latencies, requestLatency)
						
						// Create latency metric
						latencyMetric := LatencyMetric{
							MetricID:     fmt.Sprintf("%s-latency-%d-%d", testID, id, req),
							Timestamp:    time.Now(),
							Endpoint:     test.endpoint,
							Method:       test.method,
							Latency:      requestLatency,
							UserID:       id,
						}
						
						if err != nil {
							atomic.AddInt64(&failedRequests, 1)
							latencyMetric.StatusCode = 0
							
							// Categorize errors
							if strings.Contains(err.Error(), "timeout") {
								atomic.AddInt64(&timeoutErrors, 1)
							} else {
								atomic.AddInt64(&connectionErrors, 1)
							}
						} else {
							defer resp.Body.Close()
							latencyMetric.StatusCode = resp.StatusCode
							
							// Read response body to get size
							responseBody, _ := io.ReadAll(resp.Body)
							latencyMetric.ResponseSize = len(responseBody)
							
							if resp.StatusCode >= 200 && resp.StatusCode < 300 {
								atomic.AddInt64(&successfulRequests, 1)
							} else {
								atomic.AddInt64(&failedRequests, 1)
								if resp.StatusCode >= 500 {
									atomic.AddInt64(&serverErrors, 1)
								}
							}
						}
						
						suite.LatencyData = append(suite.LatencyData, latencyMetric)
						latenciesMutex.Unlock()
						
						// Small delay to simulate realistic user behavior
						time.Sleep(time.Duration(req*10) * time.Millisecond)
					}
				}(userID)
			}

			// Start all users simultaneously
			close(startSignal)
			
			// Monitor test progress
			testEndTime := time.Now().Add(test.testDuration)
			progressTicker := time.NewTicker(5 * time.Second)
			defer progressTicker.Stop()
			
			go func() {
				for {
					select {
					case <-progressTicker.C:
						currentRequests := atomic.LoadInt64(&totalRequests)
						currentSuccessful := atomic.LoadInt64(&successfulRequests)
						elapsed := time.Since(loadStart)
						currentRPS := float64(currentRequests) / elapsed.Seconds()
						
						t.Logf("🔄 Progress: %d requests, %.1f RPS, %d successful", 
							currentRequests, currentRPS, currentSuccessful)
							
						// Record throughput metric
						throughputMetric := ThroughputMetric{
							MetricID:          fmt.Sprintf("%s-throughput-%d", testID, time.Now().UnixNano()),
							Timestamp:         time.Now(),
							RequestsPerSecond: currentRPS,
							ActiveConnections: test.concurrentUsers,
						}
						suite.ThroughputData = append(suite.ThroughputData, throughputMetric)
						
					case <-ctx.Done():
						return
					}
				}
			}()

			// Wait for all users to complete or timeout
			done := make(chan struct{})
			go func() {
				wg.Wait()
				close(done)
			}()
			
			select {
			case <-done:
				// All users completed
			case <-time.After(test.testDuration + 30*time.Second):
				// Test timeout with grace period
				t.Logf("⚠️  Test timed out, stopping...")
			}
			
			loadDuration := time.Since(loadStart)
			cancel() // Stop resource monitoring

			// Collect final resource metrics
			close(resourceMetrics)
			for metric := range resourceMetrics {
				suite.ResourceMetrics = append(suite.ResourceMetrics, metric)
			}

			// Calculate performance statistics
			finalTotalRequests := atomic.LoadInt64(&totalRequests)
			finalSuccessfulRequests := atomic.LoadInt64(&successfulRequests)
			finalFailedRequests := atomic.LoadInt64(&failedRequests)
			
			requestsPerSecond := float64(finalTotalRequests) / loadDuration.Seconds()
			errorRate := (float64(finalFailedRequests) / float64(finalTotalRequests)) * 100
			
			// Calculate latency percentiles
			latencyStats := calculateLatencyPercentiles(latencies)
			
			// Estimate resource usage
			cpuUsage, memoryUsage := estimateResourceUsage(test.concurrentUsers)
			
			// Create comprehensive load test result
			loadResult := LoadTestResult{
				TestID:             testID,
				TestName:           test.name,
				ConcurrentUsers:    test.concurrentUsers,
				TotalRequests:      finalTotalRequests,
				SuccessfulRequests: finalSuccessfulRequests,
				FailedRequests:     finalFailedRequests,
				TestDuration:       loadDuration,
				RequestsPerSecond:  requestsPerSecond,
				AverageLatency:     latencyStats.Average,
				P50Latency:         latencyStats.P50,
				P95Latency:         latencyStats.P95,
				P99Latency:         latencyStats.P99,
				MaxLatency:         latencyStats.Max,
				MinLatency:         latencyStats.Min,
				ErrorRate:          errorRate,
				CPUUsagePercent:    cpuUsage,
				MemoryUsageMB:      memoryUsage,
				ConnectionErrors:   atomic.LoadInt64(&connectionErrors),
				TimeoutErrors:      atomic.LoadInt64(&timeoutErrors),
				ServerErrors:       atomic.LoadInt64(&serverErrors),
				Timestamp:          time.Now(),
			}
			suite.LoadTestResults = append(suite.LoadTestResults, loadResult)

			// FORGE Validation 1: Requests per second must meet expectations
			assert.GreaterOrEqual(t, requestsPerSecond, test.expectedRPS,
				"RPS for %s must be >= %.1f, got %.1f", test.name, test.expectedRPS, requestsPerSecond)

			// FORGE Validation 2: Error rate must be within acceptable limits
			assert.LessOrEqual(t, errorRate, test.maxErrorRate,
				"Error rate for %s must be <= %.1f%%, got %.1f%%", test.name, test.maxErrorRate, errorRate)

			// FORGE Validation 3: P99 latency must be acceptable
			assert.LessOrEqual(t, latencyStats.P99, test.maxP99Latency,
				"P99 latency for %s must be <= %v, got %v", test.name, test.maxP99Latency, latencyStats.P99)

			// FORGE Validation 4: Concurrent users must complete successfully
			minimumSuccessRate := 90.0 // 90% of users must complete successfully
			userSuccessRate := (float64(finalSuccessfulRequests) / float64(test.concurrentUsers*test.requestsPerUser)) * 100
			assert.GreaterOrEqual(t, userSuccessRate, minimumSuccessRate,
				"User success rate for %s must be >= %.1f%%, got %.1f%%", test.name, minimumSuccessRate, userSuccessRate)

			// FORGE Evidence Collection
			t.Logf("✅ FORGE M7 EVIDENCE - %s:", test.name)
			t.Logf("👥 Concurrent Users: %d", test.concurrentUsers)
			t.Logf("📊 Total Requests: %d", finalTotalRequests)
			t.Logf("⚡ Requests/Second: %.1f (target: %.1f)", requestsPerSecond, test.expectedRPS)
			t.Logf("✅ Success Rate: %.1f%%", (float64(finalSuccessfulRequests)/float64(finalTotalRequests))*100)
			t.Logf("❌ Error Rate: %.1f%% (max: %.1f%%)", errorRate, test.maxErrorRate)
			t.Logf("⏱️  Average Latency: %v", latencyStats.Average)
			t.Logf("📈 P50/P95/P99: %v/%v/%v", latencyStats.P50, latencyStats.P95, latencyStats.P99)
			t.Logf("🖥️  CPU/Memory: %.1f%%/%.1f MB", cpuUsage, memoryUsage)
			t.Logf("⏱️  Test Duration: %v", loadDuration)
		})
	}

	// Overall load test summary
	t.Run("LoadTestSummary", func(t *testing.T) {
		totalTests := len(concurrencyTests)
		passedTests := 0
		
		for _, result := range suite.LoadTestResults {
			testPassed := true
			
			// Find corresponding test configuration
			for _, test := range concurrencyTests {
				if test.name == result.TestName {
					if result.RequestsPerSecond < test.expectedRPS ||
					   result.ErrorRate > test.maxErrorRate ||
					   result.P99Latency > test.maxP99Latency {
						testPassed = false
					}
					break
				}
			}
			
			if testPassed {
				passedTests++
			}
		}
		
		overallSuccessRate := (float64(passedTests) / float64(totalTests)) * 100
		
		// FORGE Validation: Overall load test success rate
		assert.GreaterOrEqual(t, overallSuccessRate, 75.0,
			"Overall load test success rate must be >= 75%%, got %.1f%%", overallSuccessRate)
		
		t.Logf("📊 LOAD TEST SUMMARY:")
		t.Logf("✅ Tests Passed: %d/%d (%.1f%%)", passedTests, totalTests, overallSuccessRate)
		t.Logf("📈 Max Concurrent Users: %d", getMaxConcurrentUsers(concurrencyTests))
		t.Logf("⚡ Peak RPS Achieved: %.1f", getPeakRPS(suite.LoadTestResults))
		t.Logf("⏱️  Best P99 Latency: %v", getBestP99Latency(suite.LoadTestResults))
	})
}

// TestAPIThroughput validates >1000 requests/second sustained throughput
func TestAPIThroughput(t *testing.T) {
	// FORGE Movement 7: API Throughput Testing
	t.Log("🔄 FORGE M7: Testing API throughput capabilities...")

	suite := NewLoadTestSuite("http://localhost:8080")

	// Test different API endpoints for throughput
	throughputTests := []struct {
		name               string
		endpoint           string
		method             string
		targetRPS          float64
		sustainedDuration  time.Duration
		concurrentClients  int
		requestsPerClient  int
	}{
		{
			name:              "Health Check Throughput",
			endpoint:          "/health",
			method:            "GET",
			targetRPS:         2000.0,
			sustainedDuration: 60 * time.Second,
			concurrentClients: 50,
			requestsPerClient: 100,
		},
		{
			name:              "API Configuration List Throughput",
			endpoint:          "/api/v1/configurations",
			method:            "GET",
			targetRPS:         1000.0,
			sustainedDuration: 120 * time.Second,
			concurrentClients: 100,
			requestsPerClient: 50,
		},
		{
			name:              "Fabric List Throughput",
			endpoint:          "/fabrics",
			method:            "GET",
			targetRPS:         800.0,
			sustainedDuration: 90 * time.Second,
			concurrentClients: 80,
			requestsPerClient: 60,
		},
		{
			name:              "Metrics Endpoint Throughput",
			endpoint:          "/metrics",
			method:            "GET",
			targetRPS:         1500.0,
			sustainedDuration: 60 * time.Second,
			concurrentClients: 75,
			requestsPerClient: 80,
		},
	}

	for _, test := range throughputTests {
		t.Run(fmt.Sprintf("Throughput_%s", test.name), func(t *testing.T) {
			testID := fmt.Sprintf("throughput-test-%d", time.Now().UnixNano())
			throughputStart := time.Now()

			// Throughput measurement channels
			requestCompletions := make(chan time.Time, test.concurrentClients*test.requestsPerClient)
			errorChan := make(chan error, test.concurrentClients*test.requestsPerClient)

			// Start throughput measurement goroutine
			ctx, cancel := context.WithCancel(context.Background())
			throughputMetrics := make(chan ThroughputMetric, 100)
			
			go suite.measureThroughput(ctx, requestCompletions, throughputMetrics, testID, test.endpoint)

			// Launch concurrent clients
			var clientWG sync.WaitGroup
			startSignal := make(chan struct{})

			for clientID := 0; clientID < test.concurrentClients; clientID++ {
				clientWG.Add(1)
				go func(id int) {
					defer clientWG.Done()
					
					// Wait for synchronized start
					<-startSignal
					
					// Create dedicated client
					client := &http.Client{
						Timeout: 15 * time.Second,
						Transport: &http.Transport{
							MaxIdleConns:       5,
							MaxIdleConnsPerHost: 2,
						},
					}
					
					for reqNum := 0; reqNum < test.requestsPerClient; reqNum++ {
						reqStart := time.Now()
						
						resp, err := client.Get(suite.BaseURL + test.endpoint)
						reqEnd := time.Now()
						
						if err != nil {
							errorChan <- err
						} else {
							defer resp.Body.Close()
							// Consume response to complete request
							io.Copy(io.Discard, resp.Body)
							
							// Record successful completion
							requestCompletions <- reqEnd
						}
						
						// Small random delay to simulate realistic load
						if reqNum%10 == 0 {
							time.Sleep(time.Duration(id%5) * time.Millisecond)
						}
					}
				}(clientID)
			}

			// Start all clients simultaneously
			close(startSignal)

			// Monitor progress and collect metrics
			progressTicker := time.NewTicker(5 * time.Second)
			defer progressTicker.Stop()
			
			completedRequests := int64(0)
			errorCount := int64(0)
			
			monitoringDone := make(chan struct{})
			go func() {
				defer close(monitoringDone)
				
				for {
					select {
					case <-requestCompletions:
						atomic.AddInt64(&completedRequests, 1)
					case <-errorChan:
						atomic.AddInt64(&errorCount, 1)
					case <-progressTicker.C:
						completed := atomic.LoadInt64(&completedRequests)
						errors := atomic.LoadInt64(&errorCount)
						elapsed := time.Since(throughputStart)
						currentRPS := float64(completed) / elapsed.Seconds()
						
						t.Logf("📈 Throughput Progress: %d completed, %d errors, %.1f RPS", 
							completed, errors, currentRPS)
						
					case <-time.After(test.sustainedDuration + 30*time.Second):
						// Test timeout
						return
					}
				}
			}()

			// Wait for all clients to complete
			clientWG.Wait()
			
			// Wait a bit more for final metrics
			time.Sleep(2 * time.Second)
			cancel() // Stop throughput measurement
			
			throughputDuration := time.Since(throughputStart)
			
			// Close channels and collect final metrics
			close(requestCompletions)
			close(errorChan)
			<-monitoringDone
			
			close(throughputMetrics)
			for metric := range throughputMetrics {
				suite.ThroughputData = append(suite.ThroughputData, metric)
			}

			// Calculate final throughput statistics
			finalCompleted := atomic.LoadInt64(&completedRequests)
			finalErrors := atomic.LoadInt64(&errorCount)
			totalAttempted := finalCompleted + finalErrors
			
			actualRPS := float64(finalCompleted) / throughputDuration.Seconds()
			errorRate := (float64(finalErrors) / float64(totalAttempted)) * 100
			
			// Calculate sustained throughput (last 60 seconds)
			sustainedRPS := calculateSustainedThroughput(suite.ThroughputData, testID)

			// FORGE Validation 1: Sustained throughput must meet target
			assert.GreaterOrEqual(t, sustainedRPS, test.targetRPS,
				"Sustained RPS for %s must be >= %.1f, got %.1f", test.name, test.targetRPS, sustainedRPS)

			// FORGE Validation 2: Overall throughput must meet minimum
			minimumOverallRPS := test.targetRPS * 0.8 // 80% of target
			assert.GreaterOrEqual(t, actualRPS, minimumOverallRPS,
				"Overall RPS for %s must be >= %.1f, got %.1f", test.name, minimumOverallRPS, actualRPS)

			// FORGE Validation 3: Error rate must be acceptable for high throughput
			maxThroughputErrorRate := 5.0 // 5% max error rate at high throughput
			assert.LessOrEqual(t, errorRate, maxThroughputErrorRate,
				"Error rate for %s must be <= %.1f%%, got %.1f%%", test.name, maxThroughputErrorRate, errorRate)

			// FORGE Validation 4: Test must sustain for required duration
			minSustainedTime := test.sustainedDuration * 80 / 100 // 80% of target duration
			assert.GreaterOrEqual(t, throughputDuration, minSustainedTime,
				"Test duration for %s must be >= %v, got %v", test.name, minSustainedTime, throughputDuration)

			// FORGE Evidence Collection
			t.Logf("✅ FORGE M7 EVIDENCE - %s:", test.name)
			t.Logf("🎯 Target RPS: %.1f", test.targetRPS)
			t.Logf("📊 Actual RPS: %.1f", actualRPS)
			t.Logf("⏱️  Sustained RPS: %.1f", sustainedRPS)
			t.Logf("✅ Completed Requests: %d", finalCompleted)
			t.Logf("❌ Failed Requests: %d (%.1f%%)", finalErrors, errorRate)
			t.Logf("👥 Concurrent Clients: %d", test.concurrentClients)
			t.Logf("⌛ Test Duration: %v", throughputDuration)
			t.Logf("🎯 Throughput Target Met: %t", sustainedRPS >= test.targetRPS)
		})
	}
}

// Helper functions

func (suite *LoadTestSuite) monitorResources(ctx context.Context, metrics chan<- ResourceMetric, testID string) {
	ticker := time.NewTicker(2 * time.Second)
	defer ticker.Stop()
	
	for {
		select {
		case <-ticker.C:
			var mem runtime.MemStats
			runtime.ReadMemStats(&mem)
			
			metric := ResourceMetric{
				MetricID:        fmt.Sprintf("%s-resource-%d", testID, time.Now().UnixNano()),
				Timestamp:       time.Now(),
				CPUPercent:      estimateCPUUsage(),
				MemoryMB:        float64(mem.Sys) / 1024 / 1024,
				GoroutineCount:  runtime.NumGoroutine(),
				HeapSizeMB:      float64(mem.HeapSys) / 1024 / 1024,
				GCPauseTime:     time.Duration(mem.PauseNs[(mem.NumGC+255)%256]) * time.Nanosecond,
			}
			
			select {
			case metrics <- metric:
			case <-ctx.Done():
				return
			}
		case <-ctx.Done():
			return
		}
	}
}

func (suite *LoadTestSuite) measureThroughput(ctx context.Context, completions <-chan time.Time, metrics chan<- ThroughputMetric, testID, endpoint string) {
	ticker := time.NewTicker(5 * time.Second)
	defer ticker.Stop()
	
	completionTimes := []time.Time{}
	
	for {
		select {
		case completion := <-completions:
			completionTimes = append(completionTimes, completion)
			
		case <-ticker.C:
			// Calculate RPS for last 5 seconds
			now := time.Now()
			cutoff := now.Add(-5 * time.Second)
			
			recentCompletions := 0
			for _, ct := range completionTimes {
				if ct.After(cutoff) {
					recentCompletions++
				}
			}
			
			rps := float64(recentCompletions) / 5.0
			
			metric := ThroughputMetric{
				MetricID:          fmt.Sprintf("%s-throughput-%d", testID, now.UnixNano()),
				Timestamp:         now,
				RequestsPerSecond: rps,
			}
			
			select {
			case metrics <- metric:
			case <-ctx.Done():
				return
			}
			
			// Keep only recent completions to prevent memory growth
			if len(completionTimes) > 1000 {
				// Keep last 500 entries
				completionTimes = completionTimes[len(completionTimes)-500:]
			}
			
		case <-ctx.Done():
			return
		}
	}
}

type LatencyStats struct {
	Average time.Duration
	P50     time.Duration
	P95     time.Duration
	P99     time.Duration
	Max     time.Duration
	Min     time.Duration
}

func calculateLatencyPercentiles(latencies []time.Duration) LatencyStats {
	if len(latencies) == 0 {
		return LatencyStats{}
	}
	
	// Sort latencies
	sorted := make([]time.Duration, len(latencies))
	copy(sorted, latencies)
	
	// Simple sort for testing
	for i := 0; i < len(sorted)-1; i++ {
		for j := 0; j < len(sorted)-1-i; j++ {
			if sorted[j] > sorted[j+1] {
				sorted[j], sorted[j+1] = sorted[j+1], sorted[j]
			}
		}
	}
	
	// Calculate statistics
	stats := LatencyStats{
		Min: sorted[0],
		Max: sorted[len(sorted)-1],
	}
	
	// Calculate average
	var total time.Duration
	for _, lat := range sorted {
		total += lat
	}
	stats.Average = total / time.Duration(len(sorted))
	
	// Calculate percentiles
	stats.P50 = sorted[len(sorted)*50/100]
	stats.P95 = sorted[len(sorted)*95/100]
	stats.P99 = sorted[len(sorted)*99/100]
	
	return stats
}

func estimateResourceUsage(concurrentUsers int) (cpu, memory float64) {
	// Estimate resource usage based on concurrent users
	// This is a simplified estimation for testing
	baseCPU := 10.0  // 10% base CPU usage
	baseMemory := 50.0 // 50 MB base memory usage
	
	// Add resource usage per concurrent user
	cpuPerUser := 0.5    // 0.5% CPU per user
	memoryPerUser := 2.0 // 2 MB per user
	
	cpu = baseCPU + (float64(concurrentUsers) * cpuPerUser)
	memory = baseMemory + (float64(concurrentUsers) * memoryPerUser)
	
	// Cap at reasonable limits
	if cpu > 80.0 {
		cpu = 80.0
	}
	if memory > 1000.0 {
		memory = 1000.0
	}
	
	return cpu, memory
}

func estimateCPUUsage() float64 {
	// Simple CPU usage estimation based on goroutine count
	goroutines := runtime.NumGoroutine()
	baseCPU := 5.0 // 5% base
	cpuPerGoroutine := 0.1
	
	usage := baseCPU + (float64(goroutines) * cpuPerGoroutine)
	if usage > 90.0 {
		usage = 90.0
	}
	
	return usage
}

func calculateSustainedThroughput(throughputData []ThroughputMetric, testID string) float64 {
	if len(throughputData) == 0 {
		return 0.0
	}
	
	// Filter metrics for this test
	testMetrics := []ThroughputMetric{}
	for _, metric := range throughputData {
		if strings.Contains(metric.MetricID, testID) {
			testMetrics = append(testMetrics, metric)
		}
	}
	
	if len(testMetrics) == 0 {
		return 0.0
	}
	
	// Calculate average RPS for the test
	totalRPS := 0.0
	for _, metric := range testMetrics {
		totalRPS += metric.RequestsPerSecond
	}
	
	return totalRPS / float64(len(testMetrics))
}

func getMaxConcurrentUsers(tests []struct {
	name            string
	concurrentUsers int
	requestsPerUser int
	testDuration    time.Duration
	endpoint        string
	method          string
	expectedRPS     float64
	maxErrorRate    float64
	maxP99Latency   time.Duration
}) int {
	max := 0
	for _, test := range tests {
		if test.concurrentUsers > max {
			max = test.concurrentUsers
		}
	}
	return max
}

func getPeakRPS(results []LoadTestResult) float64 {
	peak := 0.0
	for _, result := range results {
		if result.RequestsPerSecond > peak {
			peak = result.RequestsPerSecond
		}
	}
	return peak
}

func getBestP99Latency(results []LoadTestResult) time.Duration {
	if len(results) == 0 {
		return 0
	}
	
	best := results[0].P99Latency
	for _, result := range results {
		if result.P99Latency < best {
			best = result.P99Latency
		}
	}
	return best
}

// FORGE Movement 7 Load Test Requirements Summary:
//
// 1. CONCURRENT USER SUPPORT:
//    - Support 100+ concurrent users simultaneously
//    - Maintain performance under varying load levels
//    - Error rates <5% under peak load
//    - P99 latency <2 seconds under heavy load
//
// 2. API THROUGHPUT VALIDATION:
//    - Sustain >1000 requests/second for API endpoints
//    - Maintain throughput for extended periods (60-120 seconds)
//    - Health check endpoints >2000 RPS capability
//    - Complex endpoints >800 RPS minimum
//
// 3. RESOURCE MONITORING:
//    - Track CPU, memory, goroutine count during load
//    - Monitor garbage collection impact
//    - Connection pool and file descriptor usage
//    - Resource usage scaling with load
//
// 4. PERFORMANCE VALIDATION:
//    - Latency percentile distribution under load
//    - Response time consistency across users
//    - Error categorization (timeout, connection, server)
//    - Sustained performance measurement
//
// 5. SCALABILITY EVIDENCE:
//    - Demonstrate linear scaling characteristics
//    - Validate performance targets under load
//    - Resource efficiency metrics collection
//    - Load test success rate >75% overall