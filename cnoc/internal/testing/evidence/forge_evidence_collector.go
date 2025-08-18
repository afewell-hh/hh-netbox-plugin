package evidence

import (
	"encoding/json"
	"fmt"
	"io/ioutil"
	"os"
	"path/filepath"
	"runtime"
	"sort"
	"sync"
	"time"
)

// FORGE Movement 5: Evidence Collection Framework
// Quantitative validation and metrics collection for test-first development

// EvidenceLevel represents the importance level of evidence
type EvidenceLevel int

const (
	EvidenceTrace EvidenceLevel = iota
	EvidenceDebug
	EvidenceInfo
	EvidenceWarn
	EvidenceError
	EvidenceCritical
)

func (e EvidenceLevel) String() string {
	switch e {
	case EvidenceTrace:
		return "TRACE"
	case EvidenceDebug:
		return "DEBUG"
	case EvidenceInfo:
		return "INFO"
	case EvidenceWarn:
		return "WARN"
	case EvidenceError:
		return "ERROR"
	case EvidenceCritical:
		return "CRITICAL"
	default:
		return "UNKNOWN"
	}
}

// EvidenceEntry represents a single piece of evidence
type EvidenceEntry struct {
	ID          string                 `json:"id"`
	Timestamp   time.Time              `json:"timestamp"`
	Level       EvidenceLevel          `json:"level"`
	Category    string                 `json:"category"`
	Component   string                 `json:"component"`
	TestSuite   string                 `json:"test_suite"`
	TestCase    string                 `json:"test_case"`
	Message     string                 `json:"message"`
	Data        map[string]interface{} `json:"data"`
	Metadata    map[string]interface{} `json:"metadata"`
	StackTrace  []string               `json:"stack_trace,omitempty"`
	Duration    *time.Duration         `json:"duration,omitempty"`
	Success     *bool                  `json:"success,omitempty"`
	Error       string                 `json:"error,omitempty"`
	Metrics     map[string]float64     `json:"metrics,omitempty"`
}

// PerformanceMetrics represents performance measurements
type PerformanceMetrics struct {
	ComponentName     string            `json:"component_name"`
	OperationName     string            `json:"operation_name"`
	StartTime         time.Time         `json:"start_time"`
	EndTime           time.Time         `json:"end_time"`
	Duration          time.Duration     `json:"duration"`
	ThroughputOpsPerSec float64         `json:"throughput_ops_per_sec"`
	LatencyP50        time.Duration     `json:"latency_p50"`
	LatencyP95        time.Duration     `json:"latency_p95"`
	LatencyP99        time.Duration     `json:"latency_p99"`
	ErrorRate         float64           `json:"error_rate"`
	ResourceUsage     map[string]float64 `json:"resource_usage"`
	CustomMetrics     map[string]float64 `json:"custom_metrics"`
}

// ValidationResult represents a validation outcome
type ValidationResult struct {
	TestID        string                 `json:"test_id"`
	TestName      string                 `json:"test_name"`
	Component     string                 `json:"component"`
	Timestamp     time.Time              `json:"timestamp"`
	Passed        bool                   `json:"passed"`
	Expected      interface{}            `json:"expected"`
	Actual        interface{}            `json:"actual"`
	Difference    interface{}            `json:"difference,omitempty"`
	Tolerance     interface{}            `json:"tolerance,omitempty"`
	Message       string                 `json:"message"`
	Evidence      map[string]interface{} `json:"evidence"`
	Requirements  []string               `json:"requirements"`
	Severity      EvidenceLevel          `json:"severity"`
}

// EvidenceReport represents a comprehensive evidence report
type EvidenceReport struct {
	ReportID         string                        `json:"report_id"`
	GeneratedAt      time.Time                     `json:"generated_at"`
	Framework        string                        `json:"framework"`
	Movement         string                        `json:"movement"`
	TestSuite        string                        `json:"test_suite"`
	Environment      map[string]string             `json:"environment"`
	Summary          EvidenceSummary               `json:"summary"`
	Entries          []EvidenceEntry               `json:"entries"`
	Performance      []PerformanceMetrics          `json:"performance"`
	Validations      []ValidationResult            `json:"validations"`
	Coverage         map[string]interface{}        `json:"coverage"`
	Requirements     map[string]RequirementStatus  `json:"requirements"`
	Recommendations  []string                      `json:"recommendations"`
	Artifacts        []string                      `json:"artifacts"`
}

// EvidenceSummary provides high-level statistics
type EvidenceSummary struct {
	TotalEntries      int                     `json:"total_entries"`
	EntriesByLevel    map[EvidenceLevel]int   `json:"entries_by_level"`
	TotalValidations  int                     `json:"total_validations"`
	PassedValidations int                     `json:"passed_validations"`
	FailedValidations int                     `json:"failed_validations"`
	TestDuration      time.Duration           `json:"test_duration"`
	ComponentsCovered []string                `json:"components_covered"`
	SuccessRate       float64                 `json:"success_rate"`
	CoveragePercent   float64                 `json:"coverage_percent"`
}

// RequirementStatus represents the status of a FORGE requirement
type RequirementStatus struct {
	ID          string    `json:"id"`
	Name        string    `json:"name"`
	Description string    `json:"description"`
	Status      string    `json:"status"` // not_started, in_progress, completed, failed
	Evidence    []string  `json:"evidence"`
	Timestamp   time.Time `json:"timestamp"`
	Priority    string    `json:"priority"` // low, medium, high, critical
}

// EvidenceCollector manages evidence collection and reporting
type EvidenceCollector struct {
	mu              sync.RWMutex
	entries         []EvidenceEntry
	performance     []PerformanceMetrics
	validations     []ValidationResult
	requirements    map[string]RequirementStatus
	config          CollectorConfig
	startTime       time.Time
	outputDir       string
	currentTestCase string
	currentSuite    string
}

// CollectorConfig configures the evidence collector
type CollectorConfig struct {
	OutputDirectory   string        `json:"output_directory"`
	MinLevel          EvidenceLevel `json:"min_level"`
	EnableStackTrace  bool          `json:"enable_stack_trace"`
	MaxEntries        int           `json:"max_entries"`
	FlushInterval     time.Duration `json:"flush_interval"`
	EnableRealTime    bool          `json:"enable_real_time"`
	MetricsEnabled    bool          `json:"metrics_enabled"`
	ValidateRequirements bool       `json:"validate_requirements"`
}

// NewEvidenceCollector creates a new evidence collector
func NewEvidenceCollector(config CollectorConfig) *EvidenceCollector {
	if config.OutputDirectory == "" {
		config.OutputDirectory = "./evidence"
	}
	if config.MaxEntries <= 0 {
		config.MaxEntries = 10000
	}
	if config.FlushInterval <= 0 {
		config.FlushInterval = 30 * time.Second
	}
	
	// Ensure output directory exists
	os.MkdirAll(config.OutputDirectory, 0755)
	
	collector := &EvidenceCollector{
		entries:      make([]EvidenceEntry, 0),
		performance:  make([]PerformanceMetrics, 0),
		validations:  make([]ValidationResult, 0),
		requirements: make(map[string]RequirementStatus),
		config:       config,
		startTime:    time.Now(),
		outputDir:    config.OutputDirectory,
	}
	
	// Initialize FORGE Movement 5 requirements
	collector.initializeForgeRequirements()
	
	return collector
}

// initializeForgeRequirements sets up the FORGE Movement 5 requirements
func (ec *EvidenceCollector) initializeForgeRequirements() {
	requirements := map[string]RequirementStatus{
		"FORGE_M5_001": {
			ID:          "FORGE_M5_001",
			Name:        "Event Orchestration Testing",
			Description: "Complex event-driven workflows with GitOps synchronization",
			Status:      "not_started",
			Priority:    "critical",
			Timestamp:   time.Now(),
		},
		"FORGE_M5_002": {
			ID:          "FORGE_M5_002",
			Name:        "API Layer Test-First Development",
			Description: "Complete REST API test suite before implementation",
			Status:      "not_started",
			Priority:    "critical",
			Timestamp:   time.Now(),
		},
		"FORGE_M5_003": {
			ID:          "FORGE_M5_003",
			Name:        "GitOps Integration Testing",
			Description: "Repository authentication, YAML processing, drift detection",
			Status:      "not_started",
			Priority:    "high",
			Timestamp:   time.Now(),
		},
		"FORGE_M5_004": {
			ID:          "FORGE_M5_004",
			Name:        "Kubernetes Client Testing",
			Description: "Cluster connectivity and CRD resource management",
			Status:      "not_started",
			Priority:    "high",
			Timestamp:   time.Now(),
		},
		"FORGE_M5_005": {
			ID:          "FORGE_M5_005",
			Name:        "Evidence-Based Validation",
			Description: "Quantitative metrics for all GitOps operations",
			Status:      "in_progress",
			Priority:    "critical",
			Timestamp:   time.Now(),
		},
	}
	
	ec.mu.Lock()
	defer ec.mu.Unlock()
	ec.requirements = requirements
}

// SetCurrentTest sets the current test context
func (ec *EvidenceCollector) SetCurrentTest(suite, testCase string) {
	ec.mu.Lock()
	defer ec.mu.Unlock()
	ec.currentSuite = suite
	ec.currentTestCase = testCase
}

// RecordEvidence records a piece of evidence
func (ec *EvidenceCollector) RecordEvidence(level EvidenceLevel, category, component, message string, data map[string]interface{}) {
	if level < ec.config.MinLevel {
		return
	}
	
	entry := EvidenceEntry{
		ID:        generateEvidenceID(),
		Timestamp: time.Now(),
		Level:     level,
		Category:  category,
		Component: component,
		Message:   message,
		Data:      data,
		Metadata:  make(map[string]interface{}),
	}
	
	// Add test context
	ec.mu.RLock()
	entry.TestSuite = ec.currentSuite
	entry.TestCase = ec.currentTestCase
	ec.mu.RUnlock()
	
	// Add stack trace if configured
	if ec.config.EnableStackTrace && level >= EvidenceError {
		entry.StackTrace = captureStackTrace()
	}
	
	// Add runtime metadata
	entry.Metadata["go_version"] = runtime.Version()
	entry.Metadata["goos"] = runtime.GOOS
	entry.Metadata["goarch"] = runtime.GOARCH
	entry.Metadata["goroutines"] = runtime.NumGoroutine()
	
	ec.mu.Lock()
	defer ec.mu.Unlock()
	
	ec.entries = append(ec.entries, entry)
	
	// Trim entries if exceeding max
	if len(ec.entries) > ec.config.MaxEntries {
		ec.entries = ec.entries[len(ec.entries)-ec.config.MaxEntries:]
	}
	
	// Real-time output if enabled
	if ec.config.EnableRealTime {
		ec.outputRealTimeEntry(entry)
	}
}

// RecordPerformance records performance metrics
func (ec *EvidenceCollector) RecordPerformance(metrics PerformanceMetrics) {
	ec.mu.Lock()
	defer ec.mu.Unlock()
	ec.performance = append(ec.performance, metrics)
}

// RecordValidation records a validation result
func (ec *EvidenceCollector) RecordValidation(result ValidationResult) {
	ec.mu.Lock()
	defer ec.mu.Unlock()
	ec.validations = append(ec.validations, result)
}

// UpdateRequirement updates the status of a FORGE requirement
func (ec *EvidenceCollector) UpdateRequirement(reqID, status string, evidence []string) {
	ec.mu.Lock()
	defer ec.mu.Unlock()
	
	if req, exists := ec.requirements[reqID]; exists {
		req.Status = status
		req.Evidence = append(req.Evidence, evidence...)
		req.Timestamp = time.Now()
		ec.requirements[reqID] = req
	}
}

// StartPerformanceTimer starts a performance measurement
func (ec *EvidenceCollector) StartPerformanceTimer(component, operation string) func() PerformanceMetrics {
	startTime := time.Now()
	
	return func() PerformanceMetrics {
		endTime := time.Now()
		duration := endTime.Sub(startTime)
		
		metrics := PerformanceMetrics{
			ComponentName: component,
			OperationName: operation,
			StartTime:     startTime,
			EndTime:       endTime,
			Duration:      duration,
		}
		
		ec.RecordPerformance(metrics)
		return metrics
	}
}

// ValidateAssert validates an assertion with evidence
func (ec *EvidenceCollector) ValidateAssert(testName, component string, expected, actual interface{}, message string, requirements []string) bool {
	passed := compareValues(expected, actual)
	
	result := ValidationResult{
		TestID:       generateEvidenceID(),
		TestName:     testName,
		Component:    component,
		Timestamp:    time.Now(),
		Passed:       passed,
		Expected:     expected,
		Actual:       actual,
		Message:      message,
		Evidence:     make(map[string]interface{}),
		Requirements: requirements,
		Severity:     EvidenceInfo,
	}
	
	if !passed {
		result.Severity = EvidenceError
		result.Difference = calculateDifference(expected, actual)
	}
	
	// Add evidence context
	result.Evidence["test_suite"] = ec.currentSuite
	result.Evidence["test_case"] = ec.currentTestCase
	result.Evidence["assertion_time"] = time.Now()
	
	ec.RecordValidation(result)
	
	// Update related requirements
	for _, reqID := range requirements {
		status := "in_progress"
		if passed {
			status = "completed"
		}
		ec.UpdateRequirement(reqID, status, []string{testName})
	}
	
	return passed
}

// GenerateReport generates a comprehensive evidence report
func (ec *EvidenceCollector) GenerateReport(reportID string) (*EvidenceReport, error) {
	ec.mu.RLock()
	defer ec.mu.RUnlock()
	
	totalDuration := time.Since(ec.startTime)
	
	// Calculate summary statistics
	summary := ec.calculateSummary(totalDuration)
	
	// Create comprehensive report
	report := &EvidenceReport{
		ReportID:    reportID,
		GeneratedAt: time.Now(),
		Framework:   "FORGE",
		Movement:    "Movement 5: Event Orchestration",
		TestSuite:   ec.currentSuite,
		Environment: ec.captureEnvironment(),
		Summary:     summary,
		Entries:     make([]EvidenceEntry, len(ec.entries)),
		Performance: make([]PerformanceMetrics, len(ec.performance)),
		Validations: make([]ValidationResult, len(ec.validations)),
		Coverage:    ec.calculateCoverage(),
		Requirements: make(map[string]RequirementStatus),
		Recommendations: ec.generateRecommendations(),
		Artifacts:   []string{},
	}
	
	// Copy data to avoid race conditions
	copy(report.Entries, ec.entries)
	copy(report.Performance, ec.performance)
	copy(report.Validations, ec.validations)
	
	for k, v := range ec.requirements {
		report.Requirements[k] = v
	}
	
	return report, nil
}

// SaveReport saves the evidence report to disk
func (ec *EvidenceCollector) SaveReport(report *EvidenceReport) error {
	filename := fmt.Sprintf("forge_evidence_report_%s.json", 
		time.Now().Format("20060102_150405"))
	filePath := filepath.Join(ec.outputDir, filename)
	
	jsonData, err := json.MarshalIndent(report, "", "  ")
	if err != nil {
		return fmt.Errorf("failed to marshal report: %w", err)
	}
	
	err = ioutil.WriteFile(filePath, jsonData, 0644)
	if err != nil {
		return fmt.Errorf("failed to write report file: %w", err)
	}
	
	// Also save a human-readable summary
	summaryFile := filepath.Join(ec.outputDir, 
		fmt.Sprintf("forge_summary_%s.txt", time.Now().Format("20060102_150405")))
	summary := ec.generateHumanReadableSummary(report)
	
	err = ioutil.WriteFile(summaryFile, []byte(summary), 0644)
	if err != nil {
		return fmt.Errorf("failed to write summary file: %w", err)
	}
	
	ec.RecordEvidence(EvidenceInfo, "reporting", "evidence_collector", 
		"Evidence report saved", map[string]interface{}{
			"report_file": filePath,
			"summary_file": summaryFile,
			"entries": len(report.Entries),
			"validations": len(report.Validations),
			"performance_metrics": len(report.Performance),
		})
	
	return nil
}

// Helper methods

func (ec *EvidenceCollector) calculateSummary(totalDuration time.Duration) EvidenceSummary {
	entriesByLevel := make(map[EvidenceLevel]int)
	components := make(map[string]bool)
	
	for _, entry := range ec.entries {
		entriesByLevel[entry.Level]++
		if entry.Component != "" {
			components[entry.Component] = true
		}
	}
	
	componentList := make([]string, 0, len(components))
	for comp := range components {
		componentList = append(componentList, comp)
	}
	sort.Strings(componentList)
	
	passed := 0
	for _, validation := range ec.validations {
		if validation.Passed {
			passed++
		}
	}
	
	var successRate float64
	if len(ec.validations) > 0 {
		successRate = float64(passed) / float64(len(ec.validations)) * 100
	}
	
	return EvidenceSummary{
		TotalEntries:      len(ec.entries),
		EntriesByLevel:    entriesByLevel,
		TotalValidations:  len(ec.validations),
		PassedValidations: passed,
		FailedValidations: len(ec.validations) - passed,
		TestDuration:      totalDuration,
		ComponentsCovered: componentList,
		SuccessRate:       successRate,
		CoveragePercent:   ec.calculateCoveragePercent(),
	}
}

func (ec *EvidenceCollector) calculateCoverage() map[string]interface{} {
	coverage := make(map[string]interface{})
	
	// Component coverage
	componentTests := make(map[string]int)
	for _, validation := range ec.validations {
		if validation.Component != "" {
			componentTests[validation.Component]++
		}
	}
	coverage["component_tests"] = componentTests
	
	// Requirement coverage
	reqCoverage := make(map[string]string)
	for reqID, req := range ec.requirements {
		reqCoverage[reqID] = req.Status
	}
	coverage["requirements"] = reqCoverage
	
	// Test category coverage
	categories := make(map[string]int)
	for _, entry := range ec.entries {
		if entry.Category != "" {
			categories[entry.Category]++
		}
	}
	coverage["categories"] = categories
	
	return coverage
}

func (ec *EvidenceCollector) calculateCoveragePercent() float64 {
	totalReqs := len(ec.requirements)
	if totalReqs == 0 {
		return 0
	}
	
	completed := 0
	for _, req := range ec.requirements {
		if req.Status == "completed" {
			completed++
		}
	}
	
	return float64(completed) / float64(totalReqs) * 100
}

func (ec *EvidenceCollector) captureEnvironment() map[string]string {
	env := make(map[string]string)
	env["go_version"] = runtime.Version()
	env["goos"] = runtime.GOOS
	env["goarch"] = runtime.GOARCH
	env["gomaxprocs"] = fmt.Sprintf("%d", runtime.GOMAXPROCS(0))
	env["num_cpu"] = fmt.Sprintf("%d", runtime.NumCPU())
	
	// Add relevant environment variables
	envVars := []string{
		"KUBECONFIG",
		"CNOC_ENV",
		"FORGE_MODE",
		"TEST_TIMEOUT",
		"GO_ENV",
	}
	
	for _, envVar := range envVars {
		if value := os.Getenv(envVar); value != "" {
			env[envVar] = value
		}
	}
	
	return env
}

func (ec *EvidenceCollector) generateRecommendations() []string {
	recommendations := make([]string, 0)
	
	// Analyze failure patterns
	errorCount := 0
	for _, entry := range ec.entries {
		if entry.Level >= EvidenceError {
			errorCount++
		}
	}
	
	if errorCount > 0 {
		recommendations = append(recommendations, 
			fmt.Sprintf("Address %d error-level issues found in evidence", errorCount))
	}
	
	// Analyze validation failures
	failedValidations := 0
	for _, validation := range ec.validations {
		if !validation.Passed {
			failedValidations++
		}
	}
	
	if failedValidations > 0 {
		recommendations = append(recommendations, 
			fmt.Sprintf("Fix %d failed validations to improve success rate", failedValidations))
	}
	
	// Analyze requirement completion
	incompleteReqs := 0
	for _, req := range ec.requirements {
		if req.Status != "completed" {
			incompleteReqs++
		}
	}
	
	if incompleteReqs > 0 {
		recommendations = append(recommendations, 
			fmt.Sprintf("Complete %d remaining FORGE Movement 5 requirements", incompleteReqs))
	}
	
	// Performance recommendations
	if len(ec.performance) > 0 {
		slowOperations := 0
		for _, perf := range ec.performance {
			if perf.Duration > 5*time.Second {
				slowOperations++
			}
		}
		
		if slowOperations > 0 {
			recommendations = append(recommendations, 
				fmt.Sprintf("Optimize %d slow operations (>5s duration)", slowOperations))
		}
	}
	
	if len(recommendations) == 0 {
		recommendations = append(recommendations, 
			"All FORGE Movement 5 requirements satisfied - ready for implementation phase")
	}
	
	return recommendations
}

func (ec *EvidenceCollector) generateHumanReadableSummary(report *EvidenceReport) string {
	summary := fmt.Sprintf(`FORGE Movement 5: Event Orchestration - Evidence Report
Generated: %s
Test Suite: %s
Report ID: %s

=== SUMMARY ===
Total Evidence Entries: %d
Total Validations: %d
Passed Validations: %d
Failed Validations: %d
Success Rate: %.1f%%
Test Duration: %s
Coverage: %.1f%%

=== FORGE REQUIREMENTS STATUS ===
`, 
		report.GeneratedAt.Format("2006-01-02 15:04:05"),
		report.TestSuite,
		report.ReportID,
		report.Summary.TotalEntries,
		report.Summary.TotalValidations,
		report.Summary.PassedValidations,
		report.Summary.FailedValidations,
		report.Summary.SuccessRate,
		report.Summary.TestDuration,
		report.Summary.CoveragePercent,
	)
	
	// Add requirements status
	for reqID, req := range report.Requirements {
		status := "❌"
		if req.Status == "completed" {
			status = "✅"
		} else if req.Status == "in_progress" {
			status = "🔄"
		}
		
		summary += fmt.Sprintf("%s %s: %s\n", status, reqID, req.Name)
	}
	
	// Add recommendations
	if len(report.Recommendations) > 0 {
		summary += "\n=== RECOMMENDATIONS ===\n"
		for i, rec := range report.Recommendations {
			summary += fmt.Sprintf("%d. %s\n", i+1, rec)
		}
	}
	
	return summary
}

func (ec *EvidenceCollector) outputRealTimeEntry(entry EvidenceEntry) {
	timestamp := entry.Timestamp.Format("15:04:05.000")
	fmt.Printf("[%s] %s [%s/%s] %s: %s\n", 
		timestamp, 
		entry.Level.String(),
		entry.Component,
		entry.Category,
		entry.TestCase,
		entry.Message,
	)
}

// Utility functions

func generateEvidenceID() string {
	return fmt.Sprintf("EVIDENCE_%d_%d", time.Now().UnixNano(), os.Getpid())
}

func captureStackTrace() []string {
	const maxStackSize = 10
	stack := make([]uintptr, maxStackSize)
	n := runtime.Callers(3, stack) // Skip captureStackTrace, RecordEvidence, and caller
	stack = stack[:n]
	
	frames := runtime.CallersFrames(stack)
	var traces []string
	
	for {
		frame, more := frames.Next()
		traces = append(traces, fmt.Sprintf("%s:%d %s", frame.File, frame.Line, frame.Function))
		if !more {
			break
		}
	}
	
	return traces
}

func compareValues(expected, actual interface{}) bool {
	// Simple comparison - can be enhanced for complex types
	return fmt.Sprintf("%v", expected) == fmt.Sprintf("%v", actual)
}

func calculateDifference(expected, actual interface{}) interface{} {
	// Return a simple difference representation
	return map[string]interface{}{
		"expected": expected,
		"actual":   actual,
		"type":     "value_mismatch",
	}
}