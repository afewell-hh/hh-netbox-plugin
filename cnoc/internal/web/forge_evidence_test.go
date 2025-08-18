package web

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"testing"
	"time"
)

// FORGE Evidence-Based Validation Framework
// Provides comprehensive quantitative metrics and evidence collection
// for test-first development methodology

// ForgeEvidenceCollector aggregates all test evidence
type ForgeEvidenceCollector struct {
	TestSuiteStartTime     time.Time
	TestResults            []ForgeTestResult
	CoverageMetrics        ForgeCoverageMetrics
	PerformanceMetrics     ForgePerformanceMetrics
	ValidationMetrics      ForgeValidationMetrics
	MutationTestingResults ForgeMutationResults
}

// ForgeTestResult represents individual test evidence
type ForgeTestResult struct {
	TestName             string        `json:"test_name"`
	Status               string        `json:"status"` // "PASS", "FAIL", "RED_PHASE"
	ResponseSize         int           `json:"response_size_bytes"`
	ResponseTime         time.Duration `json:"response_time_ns"`
	StatusCode           int           `json:"status_code"`
	ContentType          string        `json:"content_type"`
	ValidationErrors     []string      `json:"validation_errors"`
	QuantitativeMetrics  map[string]float64 `json:"quantitative_metrics"`
	RequiredMinBytes     int           `json:"required_min_bytes"`
	ActualBytes          int           `json:"actual_bytes"`
	ByteValidationPassed bool          `json:"byte_validation_passed"`
	HTMLElementsFound    int           `json:"html_elements_found"`
	HTMLElementsRequired int           `json:"html_elements_required"`
	DataBindingAccuracy  float64       `json:"data_binding_accuracy_percent"`
	Timestamp            time.Time     `json:"timestamp"`
}

// ForgeCoverageMetrics tracks test coverage
type ForgeCoverageMetrics struct {
	TotalHandlers            int     `json:"total_handlers"`
	TestedHandlers           int     `json:"tested_handlers"`
	HandlerCoveragePercent   float64 `json:"handler_coverage_percent"`
	TotalTemplates           int     `json:"total_templates"`
	TestedTemplates          int     `json:"tested_templates"`
	TemplateCoveragePercent  float64 `json:"template_coverage_percent"`
	TotalRoutes              int     `json:"total_routes"`
	TestedRoutes             int     `json:"tested_routes"`
	RouteCoveragePercent     float64 `json:"route_coverage_percent"`
}

// ForgePerformanceMetrics tracks performance requirements
type ForgePerformanceMetrics struct {
	AverageResponseTime      time.Duration `json:"average_response_time_ns"`
	MaxResponseTime          time.Duration `json:"max_response_time_ns"`
	MinResponseTime          time.Duration `json:"min_response_time_ns"`
	ResponseTimeStdDev       float64       `json:"response_time_std_dev_ns"`
	TotalRequestsProcessed   int           `json:"total_requests_processed"`
	RequestsPerSecond        float64       `json:"requests_per_second"`
	AverageResponseSize      int           `json:"average_response_size_bytes"`
	MaxResponseSize          int           `json:"max_response_size_bytes"`
	MinResponseSize          int           `json:"min_response_size_bytes"`
	TemplateRenderingTime    time.Duration `json:"template_rendering_time_ns"`
}

// ForgeValidationMetrics tracks validation accuracy
type ForgeValidationMetrics struct {
	TotalValidations          int     `json:"total_validations"`
	PassedValidations         int     `json:"passed_validations"`
	FailedValidations         int     `json:"failed_validations"`
	ValidationAccuracyPercent float64 `json:"validation_accuracy_percent"`
	Issue72ValidationsPassed  int     `json:"issue_72_validations_passed"`
	Issue72ValidationsTotal   int     `json:"issue_72_validations_total"`
	Issue72CompliancePercent  float64 `json:"issue_72_compliance_percent"`
	HTMLValidationsPassed     int     `json:"html_validations_passed"`
	HTMLValidationsTotal      int     `json:"html_validations_total"`
	DataBindingValidationsPassed int  `json:"data_binding_validations_passed"`
	DataBindingValidationsTotal  int  `json:"data_binding_validations_total"`
}

// ForgeMutationResults tracks mutation testing effectiveness
type ForgeMutationResults struct {
	TotalMutations           int     `json:"total_mutations"`
	DetectedMutations        int     `json:"detected_mutations"`
	MissedMutations          int     `json:"missed_mutations"`
	MutationDetectionPercent float64 `json:"mutation_detection_percent"`
	TestEffectivenessScore   float64 `json:"test_effectiveness_score"`
	MutationCategories       map[string]ForgeMutationCategory `json:"mutation_categories"`
}

// ForgeMutationCategory tracks specific mutation types
type ForgeMutationCategory struct {
	CategoryName      string  `json:"category_name"`
	TotalMutations    int     `json:"total_mutations"`
	DetectedMutations int     `json:"detected_mutations"`
	DetectionPercent  float64 `json:"detection_percent"`
}

// NewForgeEvidenceCollector creates a new evidence collector
func NewForgeEvidenceCollector() *ForgeEvidenceCollector {
	return &ForgeEvidenceCollector{
		TestSuiteStartTime: time.Now(),
		TestResults:        []ForgeTestResult{},
		CoverageMetrics:    ForgeCoverageMetrics{},
		PerformanceMetrics: ForgePerformanceMetrics{
			MinResponseTime: time.Hour, // Initialize to max value
		},
		ValidationMetrics:      ForgeValidationMetrics{},
		MutationTestingResults: ForgeMutationResults{
			MutationCategories: make(map[string]ForgeMutationCategory),
		},
	}
}

// RecordTestResult records a test result with comprehensive metrics
func (fec *ForgeEvidenceCollector) RecordTestResult(result ForgeTestResult) {
	result.Timestamp = time.Now()
	fec.TestResults = append(fec.TestResults, result)
	
	// Update performance metrics
	fec.updatePerformanceMetrics(result)
	
	// Update validation metrics  
	fec.updateValidationMetrics(result)
}

// updatePerformanceMetrics updates aggregated performance metrics
func (fec *ForgeEvidenceCollector) updatePerformanceMetrics(result ForgeTestResult) {
	pm := &fec.PerformanceMetrics
	
	pm.TotalRequestsProcessed++
	
	// Update response time metrics
	if result.ResponseTime > pm.MaxResponseTime {
		pm.MaxResponseTime = result.ResponseTime
	}
	if result.ResponseTime < pm.MinResponseTime {
		pm.MinResponseTime = result.ResponseTime
	}
	
	// Calculate average response time
	totalTime := pm.AverageResponseTime * time.Duration(pm.TotalRequestsProcessed-1)
	totalTime += result.ResponseTime
	pm.AverageResponseTime = totalTime / time.Duration(pm.TotalRequestsProcessed)
	
	// Update response size metrics
	if result.ResponseSize > pm.MaxResponseSize {
		pm.MaxResponseSize = result.ResponseSize
	}
	if pm.MinResponseSize == 0 || result.ResponseSize < pm.MinResponseSize {
		pm.MinResponseSize = result.ResponseSize
	}
	
	// Calculate average response size
	totalSize := pm.AverageResponseSize * (pm.TotalRequestsProcessed - 1)
	totalSize += result.ResponseSize
	pm.AverageResponseSize = totalSize / pm.TotalRequestsProcessed
}

// updateValidationMetrics updates validation accuracy metrics
func (fec *ForgeEvidenceCollector) updateValidationMetrics(result ForgeTestResult) {
	vm := &fec.ValidationMetrics
	
	vm.TotalValidations++
	
	if result.Status == "PASS" {
		vm.PassedValidations++
	} else {
		vm.FailedValidations++
	}
	
	vm.ValidationAccuracyPercent = float64(vm.PassedValidations) / float64(vm.TotalValidations) * 100
	
	// Track Issue #72 specific validations
	if result.RequiredMinBytes > 0 {
		vm.Issue72ValidationsTotal++
		if result.ByteValidationPassed {
			vm.Issue72ValidationsPassed++
		}
		vm.Issue72CompliancePercent = float64(vm.Issue72ValidationsPassed) / float64(vm.Issue72ValidationsTotal) * 100
	}
	
	// Track HTML validations
	if result.HTMLElementsRequired > 0 {
		vm.HTMLValidationsTotal++
		if result.HTMLElementsFound >= result.HTMLElementsRequired {
			vm.HTMLValidationsPassed++
		}
	}
	
	// Track data binding validations
	if result.DataBindingAccuracy >= 0 {
		vm.DataBindingValidationsTotal++
		if result.DataBindingAccuracy >= 100.0 {
			vm.DataBindingValidationsPassed++
		}
	}
}

// RecordCoverageMetrics records test coverage metrics
func (fec *ForgeEvidenceCollector) RecordCoverageMetrics(
	totalHandlers, testedHandlers,
	totalTemplates, testedTemplates,
	totalRoutes, testedRoutes int) {
	
	cm := &fec.CoverageMetrics
	cm.TotalHandlers = totalHandlers
	cm.TestedHandlers = testedHandlers
	cm.TotalTemplates = totalTemplates
	cm.TestedTemplates = testedTemplates
	cm.TotalRoutes = totalRoutes
	cm.TestedRoutes = testedRoutes
	
	// Calculate coverage percentages
	if totalHandlers > 0 {
		cm.HandlerCoveragePercent = float64(testedHandlers) / float64(totalHandlers) * 100
	}
	if totalTemplates > 0 {
		cm.TemplateCoveragePercent = float64(testedTemplates) / float64(totalTemplates) * 100
	}
	if totalRoutes > 0 {
		cm.RouteCoveragePercent = float64(testedRoutes) / float64(totalRoutes) * 100
	}
}

// RecordMutationTestingResult records mutation testing results
func (fec *ForgeEvidenceCollector) RecordMutationTestingResult(
	category string, totalMutations, detectedMutations int) {
	
	mutationCategory := ForgeMutationCategory{
		CategoryName:      category,
		TotalMutations:    totalMutations,
		DetectedMutations: detectedMutations,
		DetectionPercent:  float64(detectedMutations) / float64(totalMutations) * 100,
	}
	
	fec.MutationTestingResults.MutationCategories[category] = mutationCategory
	
	// Update overall mutation metrics
	mr := &fec.MutationTestingResults
	mr.TotalMutations += totalMutations
	mr.DetectedMutations += detectedMutations
	mr.MissedMutations = mr.TotalMutations - mr.DetectedMutations
	
	if mr.TotalMutations > 0 {
		mr.MutationDetectionPercent = float64(mr.DetectedMutations) / float64(mr.TotalMutations) * 100
		mr.TestEffectivenessScore = mr.MutationDetectionPercent
	}
}

// GenerateEvidenceReport generates comprehensive FORGE evidence report
func (fec *ForgeEvidenceCollector) GenerateEvidenceReport() ForgeEvidenceReport {
	totalDuration := time.Since(fec.TestSuiteStartTime)
	
	return ForgeEvidenceReport{
		GeneratedAt:            time.Now(),
		TestSuiteDuration:      totalDuration,
		TotalTests:             len(fec.TestResults),
		PassedTests:            fec.countPassedTests(),
		FailedTests:            fec.countFailedTests(),
		RedPhaseTests:          fec.countRedPhaseTests(),
		OverallSuccessRate:     fec.calculateOverallSuccessRate(),
		CoverageMetrics:        fec.CoverageMetrics,
		PerformanceMetrics:     fec.PerformanceMetrics,
		ValidationMetrics:      fec.ValidationMetrics,
		MutationTestingResults: fec.MutationTestingResults,
		TestResults:            fec.TestResults,
		ForgeCompliance:        fec.calculateForgeCompliance(),
	}
}

// ForgeEvidenceReport comprehensive evidence report
type ForgeEvidenceReport struct {
	GeneratedAt            time.Time              `json:"generated_at"`
	TestSuiteDuration      time.Duration          `json:"test_suite_duration_ns"`
	TotalTests             int                    `json:"total_tests"`
	PassedTests            int                    `json:"passed_tests"`
	FailedTests            int                    `json:"failed_tests"`
	RedPhaseTests          int                    `json:"red_phase_tests"`
	OverallSuccessRate     float64                `json:"overall_success_rate_percent"`
	CoverageMetrics        ForgeCoverageMetrics   `json:"coverage_metrics"`
	PerformanceMetrics     ForgePerformanceMetrics `json:"performance_metrics"`
	ValidationMetrics      ForgeValidationMetrics `json:"validation_metrics"`
	MutationTestingResults ForgeMutationResults   `json:"mutation_testing_results"`
	TestResults            []ForgeTestResult      `json:"test_results"`
	ForgeCompliance        ForgeComplianceScore   `json:"forge_compliance"`
}

// ForgeComplianceScore represents FORGE methodology compliance
type ForgeComplianceScore struct {
	OverallScore                    float64 `json:"overall_score"`
	TestFirstDevelopmentScore       float64 `json:"test_first_development_score"`
	RedGreenRefactorScore           float64 `json:"red_green_refactor_score"`
	EvidenceBasedValidationScore    float64 `json:"evidence_based_validation_score"`
	QuantitativeMetricsScore        float64 `json:"quantitative_metrics_score"`
	MutationTestingEffectivenessScore float64 `json:"mutation_testing_effectiveness_score"`
	Issue72ComplianceScore          float64 `json:"issue_72_compliance_score"`
}

// Helper methods for evidence collection
func (fec *ForgeEvidenceCollector) countPassedTests() int {
	count := 0
	for _, result := range fec.TestResults {
		if result.Status == "PASS" {
			count++
		}
	}
	return count
}

func (fec *ForgeEvidenceCollector) countFailedTests() int {
	count := 0
	for _, result := range fec.TestResults {
		if result.Status == "FAIL" {
			count++
		}
	}
	return count
}

func (fec *ForgeEvidenceCollector) countRedPhaseTests() int {
	count := 0
	for _, result := range fec.TestResults {
		if result.Status == "RED_PHASE" {
			count++
		}
	}
	return count
}

func (fec *ForgeEvidenceCollector) calculateOverallSuccessRate() float64 {
	if len(fec.TestResults) == 0 {
		return 0
	}
	return float64(fec.countPassedTests()) / float64(len(fec.TestResults)) * 100
}

func (fec *ForgeEvidenceCollector) calculateForgeCompliance() ForgeComplianceScore {
	// Calculate FORGE compliance scores
	testFirstScore := float64(fec.countRedPhaseTests()) / float64(len(fec.TestResults)) * 100
	evidenceScore := fec.ValidationMetrics.ValidationAccuracyPercent
	quantitativeScore := fec.calculateQuantitativeMetricsScore()
	mutationScore := fec.MutationTestingResults.TestEffectivenessScore
	issue72Score := fec.ValidationMetrics.Issue72CompliancePercent
	
	redGreenScore := fec.calculateRedGreenRefactorScore()
	
	overallScore := (testFirstScore + evidenceScore + quantitativeScore + 
		mutationScore + issue72Score + redGreenScore) / 6
	
	return ForgeComplianceScore{
		OverallScore:                      overallScore,
		TestFirstDevelopmentScore:         testFirstScore,
		RedGreenRefactorScore:             redGreenScore,
		EvidenceBasedValidationScore:      evidenceScore,
		QuantitativeMetricsScore:          quantitativeScore,
		MutationTestingEffectivenessScore: mutationScore,
		Issue72ComplianceScore:            issue72Score,
	}
}

func (fec *ForgeEvidenceCollector) calculateQuantitativeMetricsScore() float64 {
	// Score based on comprehensive quantitative validation
	totalMetrics := 0
	validMetrics := 0
	
	for _, result := range fec.TestResults {
		totalMetrics += len(result.QuantitativeMetrics)
		for _, value := range result.QuantitativeMetrics {
			if value >= 0 { // Valid metric value
				validMetrics++
			}
		}
	}
	
	if totalMetrics == 0 {
		return 0
	}
	return float64(validMetrics) / float64(totalMetrics) * 100
}

func (fec *ForgeEvidenceCollector) calculateRedGreenRefactorScore() float64 {
	// Score based on proper red-green-refactor cycle evidence
	redPhase := float64(fec.countRedPhaseTests())
	passed := float64(fec.countPassedTests())
	total := float64(len(fec.TestResults))
	
	if total == 0 {
		return 0
	}
	
	// Ideal: Start with red phase tests, then pass them
	redPhaseRatio := redPhase / total * 100
	passRatio := passed / total * 100
	
	// Balance between having red phase tests and passing tests
	return (redPhaseRatio + passRatio) / 2
}

// SaveEvidenceReport saves evidence report to file
func (fec *ForgeEvidenceCollector) SaveEvidenceReport(outputDir string) error {
	report := fec.GenerateEvidenceReport()
	
	// Ensure output directory exists
	if err := os.MkdirAll(outputDir, 0755); err != nil {
		return fmt.Errorf("failed to create output directory: %w", err)
	}
	
	// Generate timestamped filename
	timestamp := time.Now().Format("20060102_150405")
	filename := fmt.Sprintf("forge_evidence_report_%s.json", timestamp)
	filepath := filepath.Join(outputDir, filename)
	
	// Marshal report to JSON
	jsonData, err := json.MarshalIndent(report, "", "  ")
	if err != nil {
		return fmt.Errorf("failed to marshal evidence report: %w", err)
	}
	
	// Write to file
	if err := os.WriteFile(filepath, jsonData, 0644); err != nil {
		return fmt.Errorf("failed to write evidence report: %w", err)
	}
	
	return nil
}

// TestForgeEvidenceCollection demonstrates evidence collection usage
func TestForgeEvidenceCollection(t *testing.T) {
	// Initialize evidence collector
	evidenceCollector := NewForgeEvidenceCollector()
	
	// Record example test result
	testResult := ForgeTestResult{
		TestName:             "Example Template Rendering Test",
		Status:               "RED_PHASE", // Initially failing
		ResponseSize:         2, // Fails Issue #72 requirement
		ResponseTime:         100 * time.Millisecond,
		StatusCode:           200,
		ContentType:          "text/html; charset=utf-8",
		ValidationErrors:     []string{"Response size too small: 2 bytes (minimum: 6099 bytes)"},
		RequiredMinBytes:     6099,
		ActualBytes:          2,
		ByteValidationPassed: false,
		HTMLElementsFound:    0,
		HTMLElementsRequired: 5,
		DataBindingAccuracy:  0,
		QuantitativeMetrics: map[string]float64{
			"response_size_compliance": 0,
			"html_elements_found":      0,
			"data_binding_accuracy":    0,
		},
	}
	
	evidenceCollector.RecordTestResult(testResult)
	
	// Record coverage metrics
	evidenceCollector.RecordCoverageMetrics(
		10, 3, // 10 total handlers, 3 tested
		5, 2,  // 5 total templates, 2 tested
		15, 8, // 15 total routes, 8 tested
	)
	
	// Record mutation testing results
	evidenceCollector.RecordMutationTestingResult("template_rendering", 20, 18)
	evidenceCollector.RecordMutationTestingResult("data_binding", 15, 14)
	
	// Generate and validate evidence report
	report := evidenceCollector.GenerateEvidenceReport()
	
	// FORGE Validation: Ensure evidence collection is working
	if report.TotalTests != 1 {
		t.Errorf("Expected 1 test recorded, got %d", report.TotalTests)
	}
	
	if report.RedPhaseTests != 1 {
		t.Errorf("Expected 1 red phase test, got %d", report.RedPhaseTests)
	}
	
	if report.ValidationMetrics.Issue72CompliancePercent > 0 {
		t.Errorf("Expected 0%% Issue #72 compliance, got %.1f%%", 
			report.ValidationMetrics.Issue72CompliancePercent)
	}
	
	// Save evidence report for review
	err := evidenceCollector.SaveEvidenceReport("./test_evidence")
	if err != nil {
		t.Logf("Warning: Could not save evidence report: %v", err)
	}
	
	t.Logf("✅ FORGE Evidence Collection Test Completed")
	t.Logf("📊 Total Tests: %d", report.TotalTests)
	t.Logf("🔴 Red Phase Tests: %d", report.RedPhaseTests)
	t.Logf("📈 Overall FORGE Compliance: %.1f%%", report.ForgeCompliance.OverallScore)
	t.Logf("🎯 Issue #72 Compliance: %.1f%%", report.ForgeCompliance.Issue72ComplianceScore)
}