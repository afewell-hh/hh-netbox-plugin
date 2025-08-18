package main

import (
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"time"
)

// FORGE Movement 5: Test Runner
// Comprehensive test execution for all CNOC test suites

func main() {
	fmt.Println("FORGE Movement 5: Event Orchestration Testing")
	fmt.Println("CNOC Comprehensive Test Suite Runner")
	fmt.Println("=====================================")
	
	startTime := time.Now()
	
	// Test suites to run in FORGE RED PHASE
	testSuites := []TestSuite{
		{
			Name:        "GitOps Integration Tests",
			Path:        "./internal/services/gitops",
			Package:     "gitops",
			Description: "GitOps repository authentication, YAML processing, drift detection",
			Requirements: []string{"FORGE_M5_003"},
			ExpectedFailures: true, // RED PHASE - expected to fail
		},
		{
			Name:        "REST API Foundation Tests", 
			Path:        "./internal/api/rest",
			Package:     "rest",
			Description: "Complete REST API test suite for fabric and CRD management",
			Requirements: []string{"FORGE_M5_002"},
			ExpectedFailures: true, // RED PHASE - expected to fail
		},
		{
			Name:        "Kubernetes Client Integration Tests",
			Path:        "./internal/infrastructure/kubernetes",
			Package:     "kubernetes", 
			Description: "Cluster connectivity and CRD resource management",
			Requirements: []string{"FORGE_M5_004"},
			ExpectedFailures: true, // RED PHASE - expected to fail
		},
		{
			Name:        "Event Orchestration Tests",
			Path:        "./internal/domain/events",
			Package:     "events",
			Description: "Complex event-driven workflows with GitOps synchronization",
			Requirements: []string{"FORGE_M5_001"},
			ExpectedFailures: true, // RED PHASE - expected to fail
		},
		{
			Name:        "Evidence Collection Framework Tests",
			Path:        "./internal/testing/evidence",
			Package:     "evidence",
			Description: "Quantitative validation and metrics collection",
			Requirements: []string{"FORGE_M5_005"},
			ExpectedFailures: false, // This should work in RED PHASE
		},
	}
	
	results := make([]TestResult, 0, len(testSuites))
	
	// Run each test suite
	for i, suite := range testSuites {
		fmt.Printf("\n[%d/%d] Running: %s\n", i+1, len(testSuites), suite.Name)
		fmt.Printf("Path: %s\n", suite.Path)
		fmt.Printf("Description: %s\n", suite.Description)
		fmt.Printf("FORGE Requirements: %s\n", strings.Join(suite.Requirements, ", "))
		
		if suite.ExpectedFailures {
			fmt.Printf("Expected Result: FAIL (RED PHASE - implementation required)\n")
		} else {
			fmt.Printf("Expected Result: PASS (framework components)\n")
		}
		
		fmt.Println(strings.Repeat("-", 60))
		
		result := runTestSuite(suite)
		results = append(results, result)
		
		printTestResult(result)
		fmt.Println()
	}
	
	// Print comprehensive summary
	printSummary(results, time.Since(startTime))
	
	// Generate FORGE Movement 5 evidence report
	generateForgeReport(results)
	
	// Exit with appropriate code
	exitCode := calculateExitCode(results)
	fmt.Printf("\nExiting with code: %d\n", exitCode)
	os.Exit(exitCode)
}

type TestSuite struct {
	Name             string
	Path             string
	Package          string
	Description      string
	Requirements     []string
	ExpectedFailures bool
}

type TestResult struct {
	Suite        TestSuite
	Passed       bool
	Duration     time.Duration
	Output       string
	Error        string
	TestCount    int
	PassedTests  int
	FailedTests  int
	SkippedTests int
}

func runTestSuite(suite TestSuite) TestResult {
	result := TestResult{
		Suite: suite,
	}
	
	startTime := time.Now()
	
	// Change to the project root directory
	projectRoot, err := getProjectRoot()
	if err != nil {
		result.Error = fmt.Sprintf("Failed to find project root: %v", err)
		return result
	}
	
	// Build the test command
	cmd := exec.Command("go", "test", "-v", "-count=1", suite.Path)
	cmd.Dir = projectRoot
	cmd.Env = append(os.Environ(),
		"FORGE_MODE=red_phase",
		"CNOC_ENV=testing",
		"TEST_TIMEOUT=30s",
	)
	
	// Execute the tests
	output, err := cmd.CombinedOutput()
	result.Duration = time.Since(startTime)
	result.Output = string(output)
	
	// Parse test results
	result.TestCount, result.PassedTests, result.FailedTests, result.SkippedTests = parseTestOutput(result.Output)
	
	if err != nil {
		result.Error = err.Error()
		result.Passed = false
	} else {
		result.Passed = true
	}
	
	// Adjust expectation for RED PHASE
	if suite.ExpectedFailures {
		// In RED PHASE, we expect failures - this is correct behavior
		result.Passed = result.FailedTests > 0 || result.Error != ""
	}
	
	return result
}

func parseTestOutput(output string) (total, passed, failed, skipped int) {
	lines := strings.Split(output, "\n")
	
	for _, line := range lines {
		line = strings.TrimSpace(line)
		
		// Count individual test results
		if strings.Contains(line, "--- PASS:") {
			passed++
			total++
		} else if strings.Contains(line, "--- FAIL:") {
			failed++
			total++
		} else if strings.Contains(line, "--- SKIP:") {
			skipped++
			total++
		}
		
		// Look for summary lines
		if strings.Contains(line, "PASS") && strings.Contains(line, "ok") {
			// Test suite passed overall
		} else if strings.Contains(line, "FAIL") {
			// Test suite failed overall
		}
	}
	
	return
}

func printTestResult(result TestResult) {
	fmt.Printf("Result: ")
	if result.Passed {
		if result.Suite.ExpectedFailures {
			fmt.Printf("✅ EXPECTED FAILURE (RED PHASE CORRECT)\n")
		} else {
			fmt.Printf("✅ PASSED\n")
		}
	} else {
		if result.Suite.ExpectedFailures {
			fmt.Printf("❌ UNEXPECTED PASS (should fail in RED PHASE)\n")
		} else {
			fmt.Printf("❌ FAILED\n")
		}
	}
	
	fmt.Printf("Duration: %s\n", result.Duration)
	fmt.Printf("Tests: %d total, %d passed, %d failed, %d skipped\n", 
		result.TestCount, result.PassedTests, result.FailedTests, result.SkippedTests)
	
	if result.Error != "" {
		fmt.Printf("Error: %s\n", result.Error)
	}
	
	// Show relevant output excerpts
	if result.Output != "" {
		outputLines := strings.Split(result.Output, "\n")
		relevantLines := make([]string, 0)
		
		for _, line := range outputLines {
			if strings.Contains(line, "FORGE") || 
			   strings.Contains(line, "RED PHASE") ||
			   strings.Contains(line, "FAIL:") ||
			   strings.Contains(line, "ERROR:") ||
			   strings.Contains(line, "not implemented") {
				relevantLines = append(relevantLines, line)
			}
		}
		
		if len(relevantLines) > 0 {
			fmt.Printf("Key Output:\n")
			for _, line := range relevantLines[:min(len(relevantLines), 5)] {
				fmt.Printf("  %s\n", strings.TrimSpace(line))
			}
			if len(relevantLines) > 5 {
				fmt.Printf("  ... (%d more lines)\n", len(relevantLines)-5)
			}
		}
	}
}

func printSummary(results []TestResult, totalDuration time.Duration) {
	fmt.Println("\n" + strings.Repeat("=", 70))
	fmt.Println("FORGE Movement 5: Test Execution Summary")
	fmt.Println(strings.Repeat("=", 70))
	
	expectedCorrect := 0
	unexpectedResults := 0
	totalTests := 0
	totalPassed := 0
	totalFailed := 0
	totalSkipped := 0
	
	for _, result := range results {
		totalTests += result.TestCount
		totalPassed += result.PassedTests
		totalFailed += result.FailedTests
		totalSkipped += result.SkippedTests
		
		expectedBehavior := (result.Suite.ExpectedFailures && !result.Passed) ||
		                   (!result.Suite.ExpectedFailures && result.Passed)
		
		if expectedBehavior {
			expectedCorrect++
		} else {
			unexpectedResults++
		}
	}
	
	fmt.Printf("Test Suites: %d total\n", len(results))
	fmt.Printf("Expected Behavior: %d suites\n", expectedCorrect)
	fmt.Printf("Unexpected Results: %d suites\n", unexpectedResults)
	fmt.Printf("Individual Tests: %d total, %d passed, %d failed, %d skipped\n", 
		totalTests, totalPassed, totalFailed, totalSkipped)
	fmt.Printf("Total Duration: %s\n", totalDuration)
	fmt.Printf("Average per Suite: %s\n", time.Duration(int64(totalDuration)/int64(len(results))))
	
	fmt.Println("\nDetailed Results:")
	for _, result := range results {
		status := "❌"
		expectedBehavior := (result.Suite.ExpectedFailures && !result.Passed) ||
		                   (!result.Suite.ExpectedFailures && result.Passed)
		if expectedBehavior {
			status = "✅"
		}
		
		fmt.Printf("%s %-40s (%s)\n", status, result.Suite.Name, result.Duration)
	}
	
	fmt.Println("\nFORGE Movement 5 Status:")
	if expectedCorrect == len(results) {
		fmt.Println("✅ All test suites behaving as expected for RED PHASE")
		fmt.Println("   - Implementation-dependent tests are correctly failing")
		fmt.Println("   - Framework tests are passing")
		fmt.Println("   - Ready for FORGE Movement 6: Implementation")
	} else {
		fmt.Println("⚠️  Some test suites have unexpected behavior")
		fmt.Println("   - Review failed/passed tests that should behave differently")
		fmt.Println("   - Verify RED PHASE expectations are correct")
	}
}

func generateForgeReport(results []TestResult) {
	fmt.Println("\nGenerating FORGE Movement 5 Evidence Report...")
	
	// Create evidence directory
	evidenceDir := "./evidence"
	os.MkdirAll(evidenceDir, 0755)
	
	timestamp := time.Now().Format("20060102_150405")
	reportFile := filepath.Join(evidenceDir, fmt.Sprintf("forge_movement5_report_%s.md", timestamp))
	
	report := generateMarkdownReport(results)
	
	err := os.WriteFile(reportFile, []byte(report), 0644)
	if err != nil {
		fmt.Printf("Warning: Failed to save FORGE report: %v\n", err)
		return
	}
	
	fmt.Printf("FORGE Evidence Report saved: %s\n", reportFile)
}

func generateMarkdownReport(results []TestResult) string {
	var sb strings.Builder
	
	sb.WriteString("# FORGE Movement 5: Event Orchestration Testing Report\n\n")
	sb.WriteString(fmt.Sprintf("**Generated**: %s\n", time.Now().Format("2006-01-02 15:04:05")))
	sb.WriteString(fmt.Sprintf("**Framework**: FORGE Methodology\n"))
	sb.WriteString(fmt.Sprintf("**Phase**: RED PHASE (Test-First Development)\n"))
	sb.WriteString(fmt.Sprintf("**Test Suites**: %d\n\n", len(results)))
	
	sb.WriteString("## Executive Summary\n\n")
	sb.WriteString("This report documents the execution of FORGE Movement 5 test infrastructure ")
	sb.WriteString("for the CNOC (Cloud NetOps Command) system. All tests are designed to fail ")
	sb.WriteString("in the RED PHASE until implementations are provided in Movement 6.\n\n")
	
	sb.WriteString("## Test Suite Results\n\n")
	
	for i, result := range results {
		sb.WriteString(fmt.Sprintf("### %d. %s\n\n", i+1, result.Suite.Name))
		sb.WriteString(fmt.Sprintf("- **Package**: `%s`\n", result.Suite.Package))
		sb.WriteString(fmt.Sprintf("- **Description**: %s\n", result.Suite.Description))
		sb.WriteString(fmt.Sprintf("- **FORGE Requirements**: %s\n", strings.Join(result.Suite.Requirements, ", ")))
		sb.WriteString(fmt.Sprintf("- **Duration**: %s\n", result.Duration))
		sb.WriteString(fmt.Sprintf("- **Tests**: %d total, %d passed, %d failed, %d skipped\n", 
			result.TestCount, result.PassedTests, result.FailedTests, result.SkippedTests))
		
		expectedBehavior := (result.Suite.ExpectedFailures && !result.Passed) ||
		                   (!result.Suite.ExpectedFailures && result.Passed)
		
		if expectedBehavior {
			sb.WriteString("- **Status**: ✅ Expected behavior for RED PHASE\n")
		} else {
			sb.WriteString("- **Status**: ❌ Unexpected behavior\n")
		}
		
		if result.Error != "" {
			sb.WriteString(fmt.Sprintf("- **Error**: `%s`\n", result.Error))
		}
		
		sb.WriteString("\n")
	}
	
	sb.WriteString("## FORGE Movement 5 Requirements Coverage\n\n")
	sb.WriteString("| Requirement | Description | Status |\n")
	sb.WriteString("|-------------|-------------|--------|\n")
	sb.WriteString("| FORGE_M5_001 | Event Orchestration Testing | 🔄 Test Infrastructure Ready |\n")
	sb.WriteString("| FORGE_M5_002 | API Layer Test-First Development | 🔄 Test Infrastructure Ready |\n")
	sb.WriteString("| FORGE_M5_003 | GitOps Integration Testing | 🔄 Test Infrastructure Ready |\n")
	sb.WriteString("| FORGE_M5_004 | Kubernetes Client Testing | 🔄 Test Infrastructure Ready |\n")
	sb.WriteString("| FORGE_M5_005 | Evidence-Based Validation | ✅ Framework Implemented |\n")
	
	sb.WriteString("\n## Next Steps\n\n")
	sb.WriteString("1. **FORGE Movement 6**: Begin implementation of failing test cases\n")
	sb.WriteString("2. **GitOps Service**: Implement repository authentication and YAML processing\n")
	sb.WriteString("3. **REST API Layer**: Implement fabric and CRD management endpoints\n")
	sb.WriteString("4. **Kubernetes Client**: Implement cluster connectivity and CRD operations\n")
	sb.WriteString("5. **Event Orchestration**: Implement event bus and workflow management\n")
	sb.WriteString("6. **Continuous Integration**: All tests should pass after implementation\n\n")
	
	sb.WriteString("## Evidence Files\n\n")
	sb.WriteString("Additional evidence and detailed test outputs are available in:\n")
	sb.WriteString("- `./cnoc/internal/services/gitops/gitops_service_test.go`\n")
	sb.WriteString("- `./cnoc/internal/api/rest/fabric_api_test.go`\n")
	sb.WriteString("- `./cnoc/internal/api/rest/crd_api_test.go`\n")
	sb.WriteString("- `./cnoc/internal/infrastructure/kubernetes/k8s_client_test.go`\n")
	sb.WriteString("- `./cnoc/internal/domain/events/event_orchestration_test.go`\n")
	sb.WriteString("- `./cnoc/internal/testing/evidence/forge_evidence_collector_test.go`\n")
	
	return sb.String()
}

func calculateExitCode(results []TestResult) int {
	// In RED PHASE, we expect failures for implementation-dependent tests
	// Exit code 0 if all tests behave as expected
	// Exit code 1 if any tests have unexpected behavior
	
	for _, result := range results {
		expectedBehavior := (result.Suite.ExpectedFailures && !result.Passed) ||
		                   (!result.Suite.ExpectedFailures && result.Passed)
		
		if !expectedBehavior {
			return 1 // Unexpected behavior
		}
	}
	
	return 0 // All tests behaving as expected for RED PHASE
}

func getProjectRoot() (string, error) {
	wd, err := os.Getwd()
	if err != nil {
		return "", err
	}
	
	// Look for go.mod file to find project root
	for {
		if _, err := os.Stat(filepath.Join(wd, "go.mod")); err == nil {
			return wd, nil
		}
		
		parent := filepath.Dir(wd)
		if parent == wd {
			break
		}
		wd = parent
	}
	
	return "", fmt.Errorf("could not find project root (no go.mod found)")
}

func min(a, b int) int {
	if a < b {
		return a
	}
	return b
}