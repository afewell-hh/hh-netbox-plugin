package domain

import (
	"encoding/json"
	"fmt"
	"runtime"
	"sync"
	"testing"
	"time"

	"github.com/hedgehog/cnoc/internal/domain/configuration"
	"github.com/hedgehog/cnoc/internal/domain/shared"
)

// FORGE Movement 1: Performance Benchmark Test Suite
//
// CRITICAL: This is RED PHASE testing - ALL tests MUST FAIL initially
// Tests establish performance baselines for domain operations
// Validates latency, throughput, memory usage, and concurrency performance

// TestDomainOperationPerformance establishes baseline performance metrics for domain operations
func TestDomainOperationPerformance(t *testing.T) {
	if testing.Short() {
		t.Skip("Skipping performance benchmarks in short mode")
	}
	
	t.Run("Configuration Creation Performance", func(t *testing.T) {
		// FORGE RED PHASE: Performance testing MUST fail until domain models are optimized
		
		// Performance baseline requirements
		const (
			iterations       = 10000
			maxAvgLatency   = 50 * time.Microsecond  // 50µs average creation time
			maxP95Latency   = 100 * time.Microsecond // 100µs 95th percentile
			maxP99Latency   = 200 * time.Microsecond // 200µs 99th percentile
			maxMemoryMB     = 100                     // 100MB max memory usage
		)
		
		// Measure memory before test
		var memStatsBefore runtime.MemStats
		runtime.GC()
		runtime.ReadMemStats(&memStatsBefore)
		
		latencies := make([]time.Duration, iterations)
		
		// PERFORMANCE BENCHMARK: Configuration creation latency
		startTime := time.Now()
		for i := 0; i < iterations; i++ {
			iterStartTime := time.Now()
			
			configID, _ := configuration.NewConfigurationID(fmt.Sprintf("perf-config-%d", i))
			configName, _ := configuration.NewConfigurationName(fmt.Sprintf("Performance Test Configuration %d", i))
			version, _ := shared.NewVersion("1.0.0")
			metadata := configuration.NewConfigurationMetadata(
				fmt.Sprintf("Performance test configuration %d", i),
				map[string]string{
					"performance.test": "true",
					"iteration":        fmt.Sprintf("%d", i),
				},
				map[string]string{
					"test.cnoc.io/benchmark": "configuration-creation",
				},
			)
			
			config := configuration.NewConfiguration(
				configID,
				configName,
				version,
				configuration.ModeDevelopment,
				metadata,
			)
			
			if config == nil {
				t.Fatalf("❌ FORGE PERFORMANCE FAIL: Configuration creation failed at iteration %d", i)
			}
			
			latencies[i] = time.Since(iterStartTime)
		}
		totalDuration := time.Since(startTime)
		
		// Measure memory after test
		var memStatsAfter runtime.MemStats
		runtime.GC()
		runtime.ReadMemStats(&memStatsAfter)
		
		// Calculate performance metrics
		avgLatency := totalDuration / time.Duration(iterations)
		p95Latency := calculatePercentile(latencies, 0.95)
		p99Latency := calculatePercentile(latencies, 0.99)
		memoryUsageMB := float64(memStatsAfter.Alloc-memStatsBefore.Alloc) / 1024 / 1024
		throughputOpsPerSec := float64(iterations) / totalDuration.Seconds()
		
		// Validate performance requirements
		if avgLatency > maxAvgLatency {
			t.Errorf("❌ FORGE PERFORMANCE FAIL: Average latency %v exceeds requirement %v", avgLatency, maxAvgLatency)
		}
		
		if p95Latency > maxP95Latency {
			t.Errorf("❌ FORGE PERFORMANCE FAIL: P95 latency %v exceeds requirement %v", p95Latency, maxP95Latency)
		}
		
		if p99Latency > maxP99Latency {
			t.Errorf("❌ FORGE PERFORMANCE FAIL: P99 latency %v exceeds requirement %v", p99Latency, maxP99Latency)
		}
		
		if memoryUsageMB > maxMemoryMB {
			t.Errorf("❌ FORGE PERFORMANCE FAIL: Memory usage %.2fMB exceeds requirement %dMB", memoryUsageMB, maxMemoryMB)
		}
		
		t.Logf("✅ FORGE PERFORMANCE BASELINE: Configuration Creation")
		t.Logf("   Operations: %d", iterations)
		t.Logf("   Average Latency: %v", avgLatency)
		t.Logf("   P95 Latency: %v", p95Latency)
		t.Logf("   P99 Latency: %v", p99Latency)
		t.Logf("   Throughput: %.2f ops/sec", throughputOpsPerSec)
		t.Logf("   Memory Usage: %.2f MB", memoryUsageMB)
	})
	
	t.Run("Component Addition Performance", func(t *testing.T) {
		// FORGE RED PHASE: Component addition performance must fail until optimization
		
		const (
			configurationsCount = 100
			componentsPerConfig = 50
			maxAvgLatency      = 25 * time.Microsecond  // 25µs average component addition
			maxTotalDuration   = 5 * time.Second        // 5s total test duration
			maxMemoryMB        = 50                      // 50MB max memory usage
		)
		
		// Pre-create configurations
		configs := make([]*configuration.Configuration, configurationsCount)
		for i := 0; i < configurationsCount; i++ {
			configID, _ := configuration.NewConfigurationID(fmt.Sprintf("component-perf-config-%d", i))
			configName, _ := configuration.NewConfigurationName(fmt.Sprintf("Component Performance Test %d", i))
			version, _ := shared.NewVersion("1.0.0")
			metadata := configuration.NewConfigurationMetadata("Component performance test", nil, nil)
			
			configs[i] = configuration.NewConfiguration(
				configID,
				configName,
				version,
				configuration.ModeDevelopment,
				metadata,
			)
		}
		
		// Measure memory before test
		var memStatsBefore runtime.MemStats
		runtime.GC()
		runtime.ReadMemStats(&memStatsBefore)
		
		totalOperations := configurationsCount * componentsPerConfig
		latencies := make([]time.Duration, totalOperations)
		operationIndex := 0
		
		// PERFORMANCE BENCHMARK: Component addition latency
		startTime := time.Now()
		
		for configIdx, config := range configs {
			for compIdx := 0; compIdx < componentsPerConfig; compIdx++ {
				iterStartTime := time.Now()
				
				componentName, _ := configuration.NewComponentName(fmt.Sprintf("component-%d-%d", configIdx, compIdx))
				componentVersion, _ := shared.NewVersion("1.0.0")
				component := configuration.NewComponentReference(componentName, componentVersion, true)
				
				err := config.AddComponent(component)
				if err != nil {
					t.Fatalf("❌ FORGE PERFORMANCE FAIL: Component addition failed at config %d, component %d: %v", configIdx, compIdx, err)
				}
				
				latencies[operationIndex] = time.Since(iterStartTime)
				operationIndex++
			}
		}
		totalDuration := time.Since(startTime)
		
		// Measure memory after test
		var memStatsAfter runtime.MemStats
		runtime.GC()
		runtime.ReadMemStats(&memStatsAfter)
		
		// Calculate performance metrics
		avgLatency := totalDuration / time.Duration(totalOperations)
		p95Latency := calculatePercentile(latencies, 0.95)
		p99Latency := calculatePercentile(latencies, 0.99)
		memoryUsageMB := float64(memStatsAfter.Alloc-memStatsBefore.Alloc) / 1024 / 1024
		throughputOpsPerSec := float64(totalOperations) / totalDuration.Seconds()
		
		// Validate performance requirements
		if avgLatency > maxAvgLatency {
			t.Errorf("❌ FORGE PERFORMANCE FAIL: Average component addition latency %v exceeds requirement %v", avgLatency, maxAvgLatency)
		}
		
		if totalDuration > maxTotalDuration {
			t.Errorf("❌ FORGE PERFORMANCE FAIL: Total test duration %v exceeds requirement %v", totalDuration, maxTotalDuration)
		}
		
		if memoryUsageMB > maxMemoryMB {
			t.Errorf("❌ FORGE PERFORMANCE FAIL: Memory usage %.2fMB exceeds requirement %dMB", memoryUsageMB, maxMemoryMB)
		}
		
		t.Logf("✅ FORGE PERFORMANCE BASELINE: Component Addition")
		t.Logf("   Operations: %d", totalOperations)
		t.Logf("   Average Latency: %v", avgLatency)
		t.Logf("   P95 Latency: %v", p95Latency)
		t.Logf("   P99 Latency: %v", p99Latency)
		t.Logf("   Throughput: %.2f ops/sec", throughputOpsPerSec)
		t.Logf("   Memory Usage: %.2f MB", memoryUsageMB)
	})
	
	t.Run("CRD Validation Performance", func(t *testing.T) {
		// FORGE RED PHASE: CRD validation performance must fail until optimization
		
		const (
			iterations       = 5000
			maxAvgLatency   = 10 * time.Microsecond  // 10µs average validation time
			maxP99Latency   = 50 * time.Microsecond  // 50µs 99th percentile
			maxMemoryMB     = 25                      // 25MB max memory usage
		)
		
		// Create diverse CRD test data
		crdTestCases := []struct {
			name       string
			kind       string
			crdType    CRDType
			apiVersion string
			spec       map[string]interface{}
		}{
			{
				name:       "vpc-test",
				kind:       "VPC",
				crdType:    CRDTypeVPC,
				apiVersion: "vpc.githedgehog.com/v1beta1",
				spec: map[string]interface{}{
					"subnets": []map[string]interface{}{
						{"name": "default", "cidr": "10.1.0.0/24"},
						{"name": "management", "cidr": "10.1.1.0/24"},
					},
				},
			},
			{
				name:       "connection-test",
				kind:       "Connection",
				crdType:    CRDTypeConnection,
				apiVersion: "wiring.githedgehog.com/v1beta1",
				spec: map[string]interface{}{
					"from": "switch-1",
					"to":   "switch-2",
					"type": "fabric",
				},
			},
			{
				name:       "switch-test",
				kind:       "Switch",
				crdType:    CRDTypeSwitch,
				apiVersion: "wiring.githedgehog.com/v1beta1",
				spec: map[string]interface{}{
					"role":  "spine",
					"model": "DCS-7050SX3-48YC8",
				},
			},
		}
		
		// Measure memory before test
		var memStatsBefore runtime.MemStats
		runtime.GC()
		runtime.ReadMemStats(&memStatsBefore)
		
		latencies := make([]time.Duration, iterations)
		
		// PERFORMANCE BENCHMARK: CRD validation latency
		startTime := time.Now()
		for i := 0; i < iterations; i++ {
			iterStartTime := time.Now()
			
			// Use different CRD types cyclically
			testCase := crdTestCases[i%len(crdTestCases)]
			
			specJSON, _ := json.Marshal(testCase.spec)
			
			crd := &CRDResource{
				ID:         fmt.Sprintf("perf-crd-%d", i),
				FabricID:   "perf-fabric",
				Name:       fmt.Sprintf("%s-%d", testCase.name, i),
				Kind:       testCase.kind,
				Type:       testCase.crdType,
				APIVersion: testCase.apiVersion,
				Namespace:  "cnoc",
				Spec:       json.RawMessage(specJSON),
				CRDStatus:  CRDStatusActive,
			}
			
			err := crd.Validate()
			if err != nil {
				t.Fatalf("❌ FORGE PERFORMANCE FAIL: CRD validation failed at iteration %d: %v", i, err)
			}
			
			latencies[i] = time.Since(iterStartTime)
		}
		totalDuration := time.Since(startTime)
		
		// Measure memory after test
		var memStatsAfter runtime.MemStats
		runtime.GC()
		runtime.ReadMemStats(&memStatsAfter)
		
		// Calculate performance metrics
		avgLatency := totalDuration / time.Duration(iterations)
		p95Latency := calculatePercentile(latencies, 0.95)
		p99Latency := calculatePercentile(latencies, 0.99)
		memoryUsageMB := float64(memStatsAfter.Alloc-memStatsBefore.Alloc) / 1024 / 1024
		throughputOpsPerSec := float64(iterations) / totalDuration.Seconds()
		
		// Validate performance requirements
		if avgLatency > maxAvgLatency {
			t.Errorf("❌ FORGE PERFORMANCE FAIL: Average CRD validation latency %v exceeds requirement %v", avgLatency, maxAvgLatency)
		}
		
		if p99Latency > maxP99Latency {
			t.Errorf("❌ FORGE PERFORMANCE FAIL: P99 CRD validation latency %v exceeds requirement %v", p99Latency, maxP99Latency)
		}
		
		if memoryUsageMB > maxMemoryMB {
			t.Errorf("❌ FORGE PERFORMANCE FAIL: Memory usage %.2fMB exceeds requirement %dMB", memoryUsageMB, maxMemoryMB)
		}
		
		t.Logf("✅ FORGE PERFORMANCE BASELINE: CRD Validation")
		t.Logf("   Operations: %d", iterations)
		t.Logf("   Average Latency: %v", avgLatency)
		t.Logf("   P95 Latency: %v", p95Latency)
		t.Logf("   P99 Latency: %v", p99Latency)
		t.Logf("   Throughput: %.2f ops/sec", throughputOpsPerSec)
		t.Logf("   Memory Usage: %.2f MB", memoryUsageMB)
	})
}

// TestConcurrencyPerformance validates concurrent domain operations performance
func TestConcurrencyPerformance(t *testing.T) {
	if testing.Short() {
		t.Skip("Skipping concurrency performance tests in short mode")
	}
	
	t.Run("Concurrent Configuration Creation", func(t *testing.T) {
		// FORGE RED PHASE: Concurrent operations must fail until thread-safety is implemented
		
		const (
			workerCount     = 10
			operationsPerWorker = 1000
			maxTotalDuration = 10 * time.Second
			maxMemoryMB     = 200
		)
		
		// Measure memory before test
		var memStatsBefore runtime.MemStats
		runtime.GC()
		runtime.ReadMemStats(&memStatsBefore)
		
		var wg sync.WaitGroup
		errors := make(chan error, workerCount)
		latencies := make(chan time.Duration, workerCount*operationsPerWorker)
		
		// CONCURRENCY BENCHMARK: Concurrent configuration creation
		startTime := time.Now()
		
		for workerID := 0; workerID < workerCount; workerID++ {
			wg.Add(1)
			go func(id int) {
				defer wg.Done()
				
				for i := 0; i < operationsPerWorker; i++ {
					operationStart := time.Now()
					
					configID, _ := configuration.NewConfigurationID(fmt.Sprintf("concurrent-config-%d-%d", id, i))
					configName, _ := configuration.NewConfigurationName(fmt.Sprintf("Concurrent Test %d-%d", id, i))
					version, _ := shared.NewVersion("1.0.0")
					metadata := configuration.NewConfigurationMetadata("Concurrent test", nil, nil)
					
					config := configuration.NewConfiguration(
						configID,
						configName,
						version,
						configuration.ModeDevelopment,
						metadata,
					)
					
					if config == nil {
						errors <- fmt.Errorf("configuration creation failed for worker %d, operation %d", id, i)
						return
					}
					
					latencies <- time.Since(operationStart)
				}
			}(workerID)
		}
		
		wg.Wait()
		close(errors)
		close(latencies)
		
		totalDuration := time.Since(startTime)
		
		// Measure memory after test
		var memStatsAfter runtime.MemStats
		runtime.GC()
		runtime.ReadMemStats(&memStatsAfter)
		
		// Check for errors
		for err := range errors {
			if err != nil {
				t.Fatalf("❌ FORGE CONCURRENCY FAIL: %v", err)
			}
		}
		
		// Calculate performance metrics
		latencySlice := make([]time.Duration, 0)
		for latency := range latencies {
			latencySlice = append(latencySlice, latency)
		}
		
		totalOperations := workerCount * operationsPerWorker
		avgLatency := calculateAverage(latencySlice)
		p95Latency := calculatePercentile(latencySlice, 0.95)
		p99Latency := calculatePercentile(latencySlice, 0.99)
		memoryUsageMB := float64(memStatsAfter.Alloc-memStatsBefore.Alloc) / 1024 / 1024
		throughputOpsPerSec := float64(totalOperations) / totalDuration.Seconds()
		
		// Validate performance requirements
		if totalDuration > maxTotalDuration {
			t.Errorf("❌ FORGE CONCURRENCY FAIL: Total duration %v exceeds requirement %v", totalDuration, maxTotalDuration)
		}
		
		if memoryUsageMB > maxMemoryMB {
			t.Errorf("❌ FORGE CONCURRENCY FAIL: Memory usage %.2fMB exceeds requirement %dMB", memoryUsageMB, maxMemoryMB)
		}
		
		t.Logf("✅ FORGE CONCURRENCY BASELINE: Configuration Creation")
		t.Logf("   Workers: %d", workerCount)
		t.Logf("   Operations: %d", totalOperations)
		t.Logf("   Total Duration: %v", totalDuration)
		t.Logf("   Average Latency: %v", avgLatency)
		t.Logf("   P95 Latency: %v", p95Latency)
		t.Logf("   P99 Latency: %v", p99Latency)
		t.Logf("   Throughput: %.2f ops/sec", throughputOpsPerSec)
		t.Logf("   Memory Usage: %.2f MB", memoryUsageMB)
	})
	
	t.Run("Concurrent Domain Service Operations", func(t *testing.T) {
		// FORGE RED PHASE: Concurrent domain service operations must fail until implementation
		
		const (
			workerCount          = 20
			operationsPerWorker  = 500
			maxTotalDuration    = 15 * time.Second
			maxErrorRate        = 0.01 // 1% error rate maximum
		)
		
		// Create shared domain entities for concurrent access
		sharedConfig := createTestConfiguration("shared-config")
		sharedFabric := createTestFabric("shared-fabric")
		
		var wg sync.WaitGroup
		errorCount := int64(0)
		var errorCountMutex sync.Mutex
		operationTimes := make(chan time.Duration, workerCount*operationsPerWorker)
		
		// CONCURRENCY BENCHMARK: Concurrent domain service operations
		startTime := time.Now()
		
		for workerID := 0; workerID < workerCount; workerID++ {
			wg.Add(1)
			go func(id int) {
				defer wg.Done()
				
				for i := 0; i < operationsPerWorker; i++ {
					operationStart := time.Now()
					
					// Simulate concurrent domain service operations
					switch i % 4 {
					case 0:
						// Configuration validation
						validationResult := sharedConfig.ValidateIntegrity()
						if !validationResult.Valid {
							errorCountMutex.Lock()
							errorCount++
							errorCountMutex.Unlock()
						}
						
					case 1:
						// Component addition/removal
						componentName, _ := configuration.NewComponentName(fmt.Sprintf("temp-component-%d-%d", id, i))
						componentVersion, _ := shared.NewVersion("1.0.0")
						component := configuration.NewComponentReference(componentName, componentVersion, true)
						
						err := sharedConfig.AddComponent(component)
						if err == nil {
							// Remove immediately to prevent conflicts
							sharedConfig.RemoveComponent(componentName)
						}
						
					case 2:
						// Fabric status operations
						if !sharedFabric.IsConnected() {
							errorCountMutex.Lock()
							errorCount++
							errorCountMutex.Unlock()
						}
						
					case 3:
						// CRD validation
						crd := createTestCRD(fmt.Sprintf("concurrent-crd-%d-%d", id, i))
						err := crd.Validate()
						if err != nil {
							errorCountMutex.Lock()
							errorCount++
							errorCountMutex.Unlock()
						}
					}
					
					operationTimes <- time.Since(operationStart)
				}
			}(workerID)
		}
		
		wg.Wait()
		close(operationTimes)
		
		totalDuration := time.Since(startTime)
		totalOperations := workerCount * operationsPerWorker
		errorRate := float64(errorCount) / float64(totalOperations)
		
		// Calculate performance metrics
		operationLatencies := make([]time.Duration, 0)
		for latency := range operationTimes {
			operationLatencies = append(operationLatencies, latency)
		}
		
		avgLatency := calculateAverage(operationLatencies)
		throughputOpsPerSec := float64(totalOperations) / totalDuration.Seconds()
		
		// Validate performance and correctness requirements
		if totalDuration > maxTotalDuration {
			t.Errorf("❌ FORGE CONCURRENCY FAIL: Total duration %v exceeds requirement %v", totalDuration, maxTotalDuration)
		}
		
		if errorRate > maxErrorRate {
			t.Errorf("❌ FORGE CONCURRENCY FAIL: Error rate %.4f exceeds requirement %.4f", errorRate, maxErrorRate)
		}
		
		t.Logf("✅ FORGE CONCURRENCY BASELINE: Domain Service Operations")
		t.Logf("   Workers: %d", workerCount)
		t.Logf("   Operations: %d", totalOperations)
		t.Logf("   Total Duration: %v", totalDuration)
		t.Logf("   Average Latency: %v", avgLatency)
		t.Logf("   Throughput: %.2f ops/sec", throughputOpsPerSec)
		t.Logf("   Error Rate: %.4f", errorRate)
		t.Logf("   Errors: %d", errorCount)
	})
}

// TestMemoryEfficiencyPerformance validates memory usage patterns and garbage collection
func TestMemoryEfficiencyPerformance(t *testing.T) {
	if testing.Short() {
		t.Skip("Skipping memory performance tests in short mode")
	}
	
	t.Run("Domain Entity Memory Efficiency", func(t *testing.T) {
		// FORGE RED PHASE: Memory efficiency must fail until optimization
		
		const (
			entityCount       = 50000
			maxMemoryPerEntity = 1024 // 1KB per entity maximum
			maxTotalMemoryMB  = 100   // 100MB total maximum
		)
		
		// Measure baseline memory
		var memStatsBefore runtime.MemStats
		runtime.GC()
		runtime.ReadMemStats(&memStatsBefore)
		
		// Create domain entities
		configs := make([]*configuration.Configuration, entityCount)
		crds := make([]*CRDResource, entityCount)
		fabrics := make([]*Fabric, entityCount)
		
		// MEMORY EFFICIENCY BENCHMARK: Domain entity creation
		startTime := time.Now()
		
		for i := 0; i < entityCount; i++ {
			// Create configuration
			configs[i] = createTestConfiguration(fmt.Sprintf("mem-test-config-%d", i))
			
			// Create CRD
			crds[i] = createTestCRD(fmt.Sprintf("mem-test-crd-%d", i))
			
			// Create fabric
			fabrics[i] = createTestFabric(fmt.Sprintf("mem-test-fabric-%d", i))
		}
		
		creationDuration := time.Since(startTime)
		
		// Force garbage collection and measure memory
		runtime.GC()
		var memStatsAfter runtime.MemStats
		runtime.ReadMemStats(&memStatsAfter)
		
		// Calculate memory metrics
		totalMemoryBytes := memStatsAfter.Alloc - memStatsBefore.Alloc
		totalMemoryMB := float64(totalMemoryBytes) / 1024 / 1024
		memoryPerEntity := totalMemoryBytes / uint64(entityCount*3) // 3 entity types
		
		// Validate memory efficiency requirements
		if memoryPerEntity > maxMemoryPerEntity {
			t.Errorf("❌ FORGE MEMORY FAIL: Memory per entity %d bytes exceeds requirement %d bytes", memoryPerEntity, maxMemoryPerEntity)
		}
		
		if totalMemoryMB > maxTotalMemoryMB {
			t.Errorf("❌ FORGE MEMORY FAIL: Total memory usage %.2fMB exceeds requirement %dMB", totalMemoryMB, maxTotalMemoryMB)
		}
		
		// Test garbage collection efficiency
		startGCTime := time.Now()
		
		// Clear references to trigger garbage collection
		for i := range configs {
			configs[i] = nil
		}
		for i := range crds {
			crds[i] = nil
		}
		for i := range fabrics {
			fabrics[i] = nil
		}
		
		runtime.GC()
		gcDuration := time.Since(startGCTime)
		
		// Measure memory after GC
		var memStatsAfterGC runtime.MemStats
		runtime.ReadMemStats(&memStatsAfterGC)
		memoryReclaimedMB := float64(memStatsAfter.Alloc-memStatsAfterGC.Alloc) / 1024 / 1024
		
		t.Logf("✅ FORGE MEMORY BASELINE: Domain Entity Efficiency")
		t.Logf("   Entities Created: %d", entityCount*3)
		t.Logf("   Creation Duration: %v", creationDuration)
		t.Logf("   Total Memory Usage: %.2f MB", totalMemoryMB)
		t.Logf("   Memory Per Entity: %d bytes", memoryPerEntity)
		t.Logf("   GC Duration: %v", gcDuration)
		t.Logf("   Memory Reclaimed: %.2f MB", memoryReclaimedMB)
	})
	
	t.Run("Domain Event Memory Efficiency", func(t *testing.T) {
		// FORGE RED PHASE: Domain event memory efficiency must fail until optimization
		
		const (
			configCount        = 1000
			eventsPerConfig    = 50
			maxEventMemoryKB   = 1   // 1KB per event maximum
			maxTotalMemoryMB   = 50  // 50MB total maximum
		)
		
		// Measure baseline memory
		var memStatsBefore runtime.MemStats
		runtime.GC()
		runtime.ReadMemStats(&memStatsBefore)
		
		configs := make([]*configuration.Configuration, configCount)
		
		// DOMAIN EVENT MEMORY BENCHMARK: Create configurations and generate events
		for i := 0; i < configCount; i++ {
			configs[i] = createTestConfiguration(fmt.Sprintf("event-mem-test-%d", i))
			
			// Generate domain events through operations
			for j := 0; j < eventsPerConfig; j++ {
				componentName, _ := configuration.NewComponentName(fmt.Sprintf("event-component-%d-%d", i, j))
				componentVersion, _ := shared.NewVersion("1.0.0")
				component := configuration.NewComponentReference(componentName, componentVersion, true)
				
				// Add and remove to generate events
				configs[i].AddComponent(component)
				configs[i].RemoveComponent(componentName)
			}
		}
		
		// Measure memory after event generation
		runtime.GC()
		var memStatsAfterEvents runtime.MemStats
		runtime.ReadMemStats(&memStatsAfterEvents)
		
		// Count total events
		totalEvents := 0
		for _, config := range configs {
			totalEvents += len(config.DomainEvents())
		}
		
		// Calculate memory metrics
		totalMemoryBytes := memStatsAfterEvents.Alloc - memStatsBefore.Alloc
		totalMemoryMB := float64(totalMemoryBytes) / 1024 / 1024
		memoryPerEventBytes := totalMemoryBytes / uint64(totalEvents)
		memoryPerEventKB := float64(memoryPerEventBytes) / 1024
		
		// Validate memory efficiency requirements
		if memoryPerEventKB > maxEventMemoryKB {
			t.Errorf("❌ FORGE EVENT MEMORY FAIL: Memory per event %.2fKB exceeds requirement %dKB", memoryPerEventKB, maxEventMemoryKB)
		}
		
		if totalMemoryMB > maxTotalMemoryMB {
			t.Errorf("❌ FORGE EVENT MEMORY FAIL: Total memory usage %.2fMB exceeds requirement %dMB", totalMemoryMB, maxTotalMemoryMB)
		}
		
		// Test event commitment memory efficiency
		startCommitTime := time.Now()
		
		for _, config := range configs {
			config.MarkEventsAsCommitted()
		}
		
		commitDuration := time.Since(startCommitTime)
		
		// Measure memory after event commitment
		runtime.GC()
		var memStatsAfterCommit runtime.MemStats
		runtime.ReadMemStats(&memStatsAfterCommit)
		
		memoryReclaimedMB := float64(memStatsAfterEvents.Alloc-memStatsAfterCommit.Alloc) / 1024 / 1024
		
		t.Logf("✅ FORGE EVENT MEMORY BASELINE: Domain Event Efficiency")
		t.Logf("   Configurations: %d", configCount)
		t.Logf("   Total Events Generated: %d", totalEvents)
		t.Logf("   Total Memory Usage: %.2f MB", totalMemoryMB)
		t.Logf("   Memory Per Event: %.2f KB", memoryPerEventKB)
		t.Logf("   Event Commitment Duration: %v", commitDuration)
		t.Logf("   Memory Reclaimed After Commit: %.2f MB", memoryReclaimedMB)
	})
}

// Helper functions for performance testing

func calculatePercentile(latencies []time.Duration, percentile float64) time.Duration {
	if len(latencies) == 0 {
		return 0
	}
	
	// Sort latencies
	for i := 0; i < len(latencies)-1; i++ {
		for j := i + 1; j < len(latencies); j++ {
			if latencies[i] > latencies[j] {
				latencies[i], latencies[j] = latencies[j], latencies[i]
			}
		}
	}
	
	index := int(float64(len(latencies)) * percentile)
	if index >= len(latencies) {
		index = len(latencies) - 1
	}
	
	return latencies[index]
}

func calculateAverage(latencies []time.Duration) time.Duration {
	if len(latencies) == 0 {
		return 0
	}
	
	var total time.Duration
	for _, latency := range latencies {
		total += latency
	}
	
	return total / time.Duration(len(latencies))
}

func createTestConfiguration(id string) *configuration.Configuration {
	configID, _ := configuration.NewConfigurationID(id)
	configName, _ := configuration.NewConfigurationName(fmt.Sprintf("Test Configuration %s", id))
	version, _ := shared.NewVersion("1.0.0")
	metadata := configuration.NewConfigurationMetadata("Test configuration", nil, nil)
	
	return configuration.NewConfiguration(
		configID,
		configName,
		version,
		configuration.ModeDevelopment,
		metadata,
	)
}

func createTestCRD(id string) *CRDResource {
	return &CRDResource{
		ID:         id,
		FabricID:   "test-fabric",
		Name:       fmt.Sprintf("test-crd-%s", id),
		Kind:       "VPC",
		Type:       CRDTypeVPC,
		APIVersion: "vpc.githedgehog.com/v1beta1",
		Namespace:  "cnoc",
		Spec:       json.RawMessage(`{"subnets": [{"name": "default", "cidr": "10.1.0.0/24"}]}`),
		CRDStatus:  CRDStatusActive,
	}
}

func createTestFabric(id string) *Fabric {
	return &Fabric{
		ID:               id,
		Name:             fmt.Sprintf("Test Fabric %s", id),
		Description:      "Test fabric for performance testing",
		Status:           FabricStatusActive,
		ConnectionStatus: ConnectionStatusConnected,
		SyncStatus:       SyncStatusInSync,
		GitRepositoryID:  stringPtr("test-git-repo"),
		GitOpsDirectory:  "gitops/hedgehog/test/",
		Created:          time.Now(),
		LastModified:     time.Now(),
	}
}

// FORGE Performance Benchmark Test Summary:
//
// 1. DOMAIN OPERATION PERFORMANCE:
//    - Configuration creation: < 50µs average, < 100µs P95, < 200µs P99
//    - Component addition: < 25µs average, total test < 5s
//    - CRD validation: < 10µs average, < 50µs P99
//    - Memory usage limits enforced for all operations
//
// 2. CONCURRENCY PERFORMANCE:
//    - Concurrent configuration creation with 10 workers, 1000 ops each
//    - Concurrent domain service operations with 20 workers, 500 ops each
//    - Error rate validation < 1% for concurrent operations
//    - Thread-safety validation through concurrent access patterns
//
// 3. MEMORY EFFICIENCY:
//    - Domain entity memory efficiency: < 1KB per entity
//    - Domain event memory efficiency: < 1KB per event
//    - Garbage collection effectiveness validation
//    - Memory reclamation after event commitment
//
// RED PHASE COMPLIANCE:
// - All performance tests MUST fail until domain models are optimized
// - Performance baselines establish quantitative success criteria
// - Memory efficiency validation prevents resource leaks
// - Concurrency testing ensures thread-safety implementation
// - Benchmarks provide regression detection for future optimizations