package evidence

import (
	"os"
	"path/filepath"
	"testing"
	"time"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
	"github.com/stretchr/testify/suite"
)

// FORGE Movement 5: Evidence Collection Framework Test Suite

type EvidenceCollectorTestSuite struct {
	suite.Suite
	collector *EvidenceCollector
	tempDir   string
}

func (suite *EvidenceCollectorTestSuite) SetupSuite() {
	// Create temporary directory for test evidence
	tempDir := os.TempDir()
	
	testDir := filepath.Join(tempDir, "forge_evidence_test")
	err := os.MkdirAll(testDir, 0755)
	require.NoError(suite.T(), err)
	
	suite.tempDir = testDir
	
	config := CollectorConfig{
		OutputDirectory:      testDir,
		MinLevel:            EvidenceDebug,
		EnableStackTrace:    true,
		MaxEntries:          1000,
		FlushInterval:       10 * time.Second,
		EnableRealTime:      false, // Disable for testing
		MetricsEnabled:      true,
		ValidateRequirements: true,
	}
	
	suite.collector = NewEvidenceCollector(config)
	suite.collector.SetCurrentTest("EvidenceCollectorTestSuite", "SetupSuite")
}

func (suite *EvidenceCollectorTestSuite) TearDownSuite() {
	// Cleanup temporary directory
	os.RemoveAll(suite.tempDir)
}

// TestEvidenceRecording - Test basic evidence recording functionality
func (suite *EvidenceCollectorTestSuite) TestEvidenceRecording() {
	suite.collector.SetCurrentTest("EvidenceCollectorTestSuite", "TestEvidenceRecording")
	
	// Record various levels of evidence
	testData := map[string]interface{}{
		"test_value":  42,
		"test_string": "FORGE evidence test",
		"test_array":  []int{1, 2, 3},
	}
	
	suite.collector.RecordEvidence(EvidenceInfo, "testing", "evidence_collector", 
		"Recording test evidence", testData)
	
	suite.collector.RecordEvidence(EvidenceWarn, "testing", "evidence_collector", 
		"Warning level evidence", map[string]interface{}{"warning": "test warning"})
	
	suite.collector.RecordEvidence(EvidenceError, "testing", "evidence_collector", 
		"Error level evidence with stack trace", map[string]interface{}{"error": "test error"})
	
	// Generate and validate report
	report, err := suite.collector.GenerateReport("TEST_EVIDENCE_RECORDING")
	assert.NoError(suite.T(), err)
	assert.NotNil(suite.T(), report)
	
	// Validate report contents
	assert.Equal(suite.T(), "FORGE", report.Framework)
	assert.Equal(suite.T(), "Movement 5: Event Orchestration", report.Movement)
	assert.GreaterOrEqual(suite.T(), len(report.Entries), 3)
	
	// Check that entries have proper test context
	for _, entry := range report.Entries {
		assert.Equal(suite.T(), "EvidenceCollectorTestSuite", entry.TestSuite)
		assert.Equal(suite.T(), "TestEvidenceRecording", entry.TestCase)
		assert.NotEmpty(suite.T(), entry.ID)
		assert.NotZero(suite.T(), entry.Timestamp)
	}
}

// TestPerformanceMetrics - Test performance measurement functionality
func (suite *EvidenceCollectorTestSuite) TestPerformanceMetrics() {
	suite.collector.SetCurrentTest("EvidenceCollectorTestSuite", "TestPerformanceMetrics")
	
	// Test performance timer functionality
	finishTimer := suite.collector.StartPerformanceTimer("test_component", "test_operation")
	
	// Simulate some work
	time.Sleep(10 * time.Millisecond)
	
	metrics := finishTimer()
	
	assert.Equal(suite.T(), "test_component", metrics.ComponentName)
	assert.Equal(suite.T(), "test_operation", metrics.OperationName)
	assert.Greater(suite.T(), metrics.Duration, 5*time.Millisecond)
	assert.Less(suite.T(), metrics.Duration, 100*time.Millisecond)
	
	// Test direct performance recording
	customMetrics := PerformanceMetrics{
		ComponentName:       "api_endpoint",
		OperationName:       "fabric_sync",
		StartTime:           time.Now().Add(-2 * time.Second),
		EndTime:             time.Now(),
		Duration:            2 * time.Second,
		ThroughputOpsPerSec: 50.0,
		LatencyP50:          100 * time.Millisecond,
		LatencyP95:          200 * time.Millisecond,
		LatencyP99:          300 * time.Millisecond,
		ErrorRate:           0.02,
		ResourceUsage: map[string]float64{
			"cpu_percent":    25.5,
			"memory_mb":      128.0,
			"disk_io_mbps":   10.2,
		},
		CustomMetrics: map[string]float64{
			"crds_processed":  42.0,
			"files_processed": 15.0,
		},
	}
	
	suite.collector.RecordPerformance(customMetrics)
	
	// Generate report and validate performance metrics
	report, err := suite.collector.GenerateReport("TEST_PERFORMANCE_METRICS")
	assert.NoError(suite.T(), err)
	assert.GreaterOrEqual(suite.T(), len(report.Performance), 2)
	
	// Find our custom metrics in the report
	found := false
	for _, perf := range report.Performance {
		if perf.ComponentName == "api_endpoint" && perf.OperationName == "fabric_sync" {
			found = true
			assert.Equal(suite.T(), 50.0, perf.ThroughputOpsPerSec)
			assert.Equal(suite.T(), 0.02, perf.ErrorRate)
			assert.Equal(suite.T(), 25.5, perf.ResourceUsage["cpu_percent"])
			assert.Equal(suite.T(), 42.0, perf.CustomMetrics["crds_processed"])
			break
		}
	}
	assert.True(suite.T(), found, "Custom performance metrics should be found in report")
}

// TestValidationResults - Test validation recording and assertion functionality
func (suite *EvidenceCollectorTestSuite) TestValidationResults() {
	suite.collector.SetCurrentTest("EvidenceCollectorTestSuite", "TestValidationResults")
	
	// Test successful validation
	passed := suite.collector.ValidateAssert(
		"test_successful_validation",
		"validation_component",
		"expected_value",
		"expected_value",
		"Values should match",
		[]string{"FORGE_M5_001"},
	)
	assert.True(suite.T(), passed)
	
	// Test failed validation
	failed := suite.collector.ValidateAssert(
		"test_failed_validation",
		"validation_component",
		"expected_value",
		"actual_different_value",
		"Values should not match",
		[]string{"FORGE_M5_002"},
	)
	assert.False(suite.T(), failed)
	
	// Test numeric validation
	numericPassed := suite.collector.ValidateAssert(
		"test_numeric_validation",
		"numeric_component",
		42,
		42,
		"Numbers should be equal",
		[]string{"FORGE_M5_003"},
	)
	assert.True(suite.T(), numericPassed)
	
	// Generate report and validate results
	report, err := suite.collector.GenerateReport("TEST_VALIDATION_RESULTS")
	assert.NoError(suite.T(), err)
	assert.GreaterOrEqual(suite.T(), len(report.Validations), 3)
	
	// Check validation statistics
	assert.Equal(suite.T(), len(report.Validations), report.Summary.TotalValidations)
	assert.Equal(suite.T(), 2, report.Summary.PassedValidations) // 2 passed, 1 failed
	assert.Equal(suite.T(), 1, report.Summary.FailedValidations)
	assert.Equal(suite.T(), 66.7, report.Summary.SuccessRate) // 2/3 * 100, rounded
	
	// Validate individual validation results
	for _, validation := range report.Validations {
		assert.NotEmpty(suite.T(), validation.TestID)
		assert.NotEmpty(suite.T(), validation.TestName)
		assert.NotEmpty(suite.T(), validation.Component)
		assert.NotZero(suite.T(), validation.Timestamp)
		assert.NotNil(suite.T(), validation.Expected)
		assert.NotNil(suite.T(), validation.Actual)
		
		if !validation.Passed {
			assert.NotNil(suite.T(), validation.Difference)
			assert.Equal(suite.T(), EvidenceError, validation.Severity)
		}
	}
}

// TestRequirementTracking - Test FORGE requirement status tracking
func (suite *EvidenceCollectorTestSuite) TestRequirementTracking() {
	suite.collector.SetCurrentTest("EvidenceCollectorTestSuite", "TestRequirementTracking")
	
	// Update requirement status
	suite.collector.UpdateRequirement("FORGE_M5_001", "in_progress", 
		[]string{"event_orchestration_test_started"})
	
	suite.collector.UpdateRequirement("FORGE_M5_001", "completed", 
		[]string{"event_orchestration_test_passed", "all_events_processed"})
	
	suite.collector.UpdateRequirement("FORGE_M5_002", "in_progress", 
		[]string{"api_tests_started"})
	
	// Generate report and validate requirements
	report, err := suite.collector.GenerateReport("TEST_REQUIREMENT_TRACKING")
	assert.NoError(suite.T(), err)
	
	// Check requirement status
	req1, exists := report.Requirements["FORGE_M5_001"]
	assert.True(suite.T(), exists)
	assert.Equal(suite.T(), "completed", req1.Status)
	assert.Contains(suite.T(), req1.Evidence, "event_orchestration_test_passed")
	assert.Contains(suite.T(), req1.Evidence, "all_events_processed")
	
	req2, exists := report.Requirements["FORGE_M5_002"]
	assert.True(suite.T(), exists)
	assert.Equal(suite.T(), "in_progress", req2.Status)
	
	// Validate coverage calculation
	assert.Greater(suite.T(), report.Summary.CoveragePercent, 0.0)
	assert.LessOrEqual(suite.T(), report.Summary.CoveragePercent, 100.0)
}

// TestReportGeneration - Test comprehensive report generation and saving
func (suite *EvidenceCollectorTestSuite) TestReportGeneration() {
	suite.collector.SetCurrentTest("EvidenceCollectorTestSuite", "TestReportGeneration")
	
	// Add comprehensive test data
	suite.collector.RecordEvidence(EvidenceInfo, "setup", "test_framework", 
		"Test setup complete", map[string]interface{}{
			"test_duration": "5s",
			"components":    []string{"api", "database", "cache"},
		})
	
	// Add performance data
	perf := PerformanceMetrics{
		ComponentName:       "report_generation",
		OperationName:       "full_report",
		Duration:            500 * time.Millisecond,
		ThroughputOpsPerSec: 100.0,
		ErrorRate:           0.0,
	}
	suite.collector.RecordPerformance(perf)
	
	// Add validation
	suite.collector.ValidateAssert("report_generation_test", "reporting", 
		true, true, "Report should be generated successfully", []string{"FORGE_M5_005"})
	
	// Generate and save report
	report, err := suite.collector.GenerateReport("COMPREHENSIVE_TEST_REPORT")
	assert.NoError(suite.T(), err)
	assert.NotNil(suite.T(), report)
	
	err = suite.collector.SaveReport(report)
	assert.NoError(suite.T(), err)
	
	// Validate report structure
	assert.Equal(suite.T(), "COMPREHENSIVE_TEST_REPORT", report.ReportID)
	assert.Equal(suite.T(), "FORGE", report.Framework)
	assert.Equal(suite.T(), "Movement 5: Event Orchestration", report.Movement)
	assert.NotEmpty(suite.T(), report.Environment)
	assert.Greater(suite.T(), len(report.Entries), 0)
	assert.Greater(suite.T(), len(report.Performance), 0)
	assert.Greater(suite.T(), len(report.Validations), 0)
	assert.Greater(suite.T(), len(report.Requirements), 0)
	
	// Validate environment capture
	assert.Contains(suite.T(), report.Environment, "go_version")
	assert.Contains(suite.T(), report.Environment, "goos")
	assert.Contains(suite.T(), report.Environment, "goarch")
	
	// Validate summary statistics
	assert.Equal(suite.T(), len(report.Entries), report.Summary.TotalEntries)
	assert.NotEmpty(suite.T(), report.Summary.ComponentsCovered)
	assert.Greater(suite.T(), report.Summary.TestDuration, time.Duration(0))
	
	// Check that files were created
	files, err := os.ReadDir(suite.tempDir)
	assert.NoError(suite.T(), err)
	
	jsonFound := false
	txtFound := false
	for _, file := range files {
		if filepath.Ext(file.Name()) == ".json" {
			jsonFound = true
		}
		if filepath.Ext(file.Name()) == ".txt" {
			txtFound = true
		}
	}
	assert.True(suite.T(), jsonFound, "JSON report file should be created")
	assert.True(suite.T(), txtFound, "Text summary file should be created")
}

// TestEvidenceLevelsAndFiltering - Test evidence level filtering
func (suite *EvidenceCollectorTestSuite) TestEvidenceLevelsAndFiltering() {
	// Create collector with higher minimum level
	config := CollectorConfig{
		OutputDirectory: suite.tempDir,
		MinLevel:        EvidenceWarn,
		MaxEntries:      100,
	}
	
	filteredCollector := NewEvidenceCollector(config)
	filteredCollector.SetCurrentTest("EvidenceCollectorTestSuite", "TestEvidenceLevelsAndFiltering")
	
	// Record evidence at different levels
	filteredCollector.RecordEvidence(EvidenceTrace, "test", "component", "Trace message", nil)
	filteredCollector.RecordEvidence(EvidenceDebug, "test", "component", "Debug message", nil)
	filteredCollector.RecordEvidence(EvidenceInfo, "test", "component", "Info message", nil)
	filteredCollector.RecordEvidence(EvidenceWarn, "test", "component", "Warn message", nil)
	filteredCollector.RecordEvidence(EvidenceError, "test", "component", "Error message", nil)
	filteredCollector.RecordEvidence(EvidenceCritical, "test", "component", "Critical message", nil)
	
	report, err := filteredCollector.GenerateReport("LEVEL_FILTERING_TEST")
	assert.NoError(suite.T(), err)
	
	// Should only have entries at WARN level and above (WARN, ERROR, CRITICAL = 3 entries)
	assert.Equal(suite.T(), 3, len(report.Entries))
	
	for _, entry := range report.Entries {
		assert.GreaterOrEqual(suite.T(), entry.Level, EvidenceWarn)
	}
	
	// Check level distribution in summary
	assert.Equal(suite.T(), 1, report.Summary.EntriesByLevel[EvidenceWarn])
	assert.Equal(suite.T(), 1, report.Summary.EntriesByLevel[EvidenceError])
	assert.Equal(suite.T(), 1, report.Summary.EntriesByLevel[EvidenceCritical])
	assert.Equal(suite.T(), 0, report.Summary.EntriesByLevel[EvidenceTrace])
	assert.Equal(suite.T(), 0, report.Summary.EntriesByLevel[EvidenceDebug])
	assert.Equal(suite.T(), 0, report.Summary.EntriesByLevel[EvidenceInfo])
}

// TestEvidenceCollectorIntegration - Integration test with all features
func (suite *EvidenceCollectorTestSuite) TestEvidenceCollectorIntegration() {
	suite.collector.SetCurrentTest("EvidenceCollectorTestSuite", "TestEvidenceCollectorIntegration")
	
	// Simulate a complete FORGE Movement 5 test scenario
	
	// 1. Start performance timing
	finishGitOps := suite.collector.StartPerformanceTimer("gitops_service", "fabric_sync")
	
	// 2. Record test start
	suite.collector.RecordEvidence(EvidenceInfo, "integration", "test_framework", 
		"Starting FORGE Movement 5 integration test", map[string]interface{}{
			"test_type":    "integration",
			"components":   []string{"gitops", "k8s", "api", "events"},
			"requirements": []string{"FORGE_M5_001", "FORGE_M5_002", "FORGE_M5_003", "FORGE_M5_004", "FORGE_M5_005"},
		})
	
	// 3. Simulate GitOps operations
	time.Sleep(20 * time.Millisecond) // Simulate work
	
	suite.collector.RecordEvidence(EvidenceInfo, "gitops", "repository_sync", 
		"GitOps repository synchronization started", map[string]interface{}{
			"repository": "https://github.com/test/gitops.git",
			"directory":  "gitops/fabric-1/",
			"files":      []string{"vpc.yaml", "connection.yaml", "switch.yaml"},
		})
	
	// 4. Record successful validation
	suite.collector.ValidateAssert("gitops_sync_success", "gitops_service", 
		"completed", "completed", "GitOps sync should complete successfully", 
		[]string{"FORGE_M5_003"})
	
	// 5. Finish GitOps timing
	gitOpsMetrics := finishGitOps()
	
	// 6. Start API testing
	finishAPI := suite.collector.StartPerformanceTimer("rest_api", "fabric_crud")
	time.Sleep(15 * time.Millisecond) // Simulate API work
	
	suite.collector.ValidateAssert("api_response_time", "rest_api", 
		true, gitOpsMetrics.Duration < 200*time.Millisecond, 
		"API response time should be acceptable", 
		[]string{"FORGE_M5_002"})
	
	finishAPI()
	
	// 7. Test Kubernetes integration
	finishK8s := suite.collector.StartPerformanceTimer("k8s_client", "crd_operations")
	time.Sleep(25 * time.Millisecond) // Simulate K8s work
	
	suite.collector.RecordEvidence(EvidenceInfo, "kubernetes", "crd_manager", 
		"CRD resources processed successfully", map[string]interface{}{
			"crds_created": 5,
			"crds_updated": 3,
			"crds_deleted": 0,
			"namespaces":   []string{"hedgehog-fabric-1", "hedgehog-fabric-2"},
		})
	
	suite.collector.ValidateAssert("k8s_crd_operations", "k8s_client", 
		8, 8, "Should process all CRDs successfully", 
		[]string{"FORGE_M5_004"})
	
	finishK8s()
	
	// 8. Test event orchestration
	suite.collector.RecordEvidence(EvidenceInfo, "events", "event_bus", 
		"Event orchestration workflow completed", map[string]interface{}{
			"events_published": 15,
			"events_processed": 15,
			"events_failed":    0,
			"workflow_id":      "fabric_sync_workflow_001",
		})
	
	suite.collector.ValidateAssert("event_orchestration", "event_bus", 
		15, 15, "All events should be processed successfully", 
		[]string{"FORGE_M5_001"})
	
	// 9. Update all requirements to completed
	requirements := []string{"FORGE_M5_001", "FORGE_M5_002", "FORGE_M5_003", "FORGE_M5_004"}
	for _, req := range requirements {
		suite.collector.UpdateRequirement(req, "completed", 
			[]string{"integration_test_passed"})
	}
	
	// 10. Record test completion
	suite.collector.RecordEvidence(EvidenceInfo, "integration", "test_framework", 
		"FORGE Movement 5 integration test completed successfully", map[string]interface{}{
			"total_validations": 4,
			"passed_validations": 4,
			"success_rate":      100.0,
			"all_requirements_met": true,
		})
	
	// 11. Generate final report
	report, err := suite.collector.GenerateReport("FORGE_M5_INTEGRATION_COMPLETE")
	assert.NoError(suite.T(), err)
	assert.NotNil(suite.T(), report)
	
	// 12. Validate comprehensive integration results
	assert.GreaterOrEqual(suite.T(), len(report.Entries), 5)
	assert.GreaterOrEqual(suite.T(), len(report.Performance), 3)
	assert.GreaterOrEqual(suite.T(), len(report.Validations), 4)
	assert.Equal(suite.T(), 100.0, report.Summary.SuccessRate)
	assert.Greater(suite.T(), report.Summary.CoveragePercent, 80.0)
	
	// All critical requirements should be completed
	for _, reqID := range requirements {
		req, exists := report.Requirements[reqID]
		assert.True(suite.T(), exists)
		assert.Equal(suite.T(), "completed", req.Status)
	}
	
	// Should have comprehensive recommendations for next phase
	assert.NotEmpty(suite.T(), report.Recommendations)
	
	// Save the comprehensive integration report
	err = suite.collector.SaveReport(report)
	assert.NoError(suite.T(), err)
}

func TestEvidenceCollectorTestSuite(t *testing.T) {
	suite.Run(t, new(EvidenceCollectorTestSuite))
}

// Benchmark tests for evidence collection performance
func BenchmarkEvidenceRecording(b *testing.B) {
	tempDir := b.TempDir()
	config := CollectorConfig{
		OutputDirectory: tempDir,
		MinLevel:       EvidenceInfo,
		EnableRealTime: false,
	}
	
	collector := NewEvidenceCollector(config)
	testData := map[string]interface{}{
		"benchmark": true,
		"iteration": 0,
	}
	
	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		testData["iteration"] = i
		collector.RecordEvidence(EvidenceInfo, "benchmark", "evidence_collector", 
			"Benchmark evidence entry", testData)
	}
}

func BenchmarkPerformanceTimer(b *testing.B) {
	tempDir := b.TempDir()
	config := CollectorConfig{
		OutputDirectory: tempDir,
		MinLevel:       EvidenceInfo,
		EnableRealTime: false,
	}
	
	collector := NewEvidenceCollector(config)
	
	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		finishTimer := collector.StartPerformanceTimer("benchmark_component", "benchmark_operation")
		time.Sleep(time.Microsecond) // Minimal work
		finishTimer()
	}
}

func BenchmarkReportGeneration(b *testing.B) {
	tempDir := b.TempDir()
	config := CollectorConfig{
		OutputDirectory: tempDir,
		MinLevel:       EvidenceInfo,
		EnableRealTime: false,
	}
	
	collector := NewEvidenceCollector(config)
	
	// Pre-populate with test data
	for i := 0; i < 100; i++ {
		collector.RecordEvidence(EvidenceInfo, "benchmark", "component", 
			"Benchmark evidence", map[string]interface{}{"iteration": i})
	}
	
	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		report, _ := collector.GenerateReport("BENCHMARK_REPORT")
		_ = report // Use the report to prevent optimization
	}
}