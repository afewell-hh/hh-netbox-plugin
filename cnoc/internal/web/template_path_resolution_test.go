package web

import (
	"fmt"
	"html/template"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/hedgehog/cnoc/internal/monitoring"
)

// TestTemplatePathResolutionFromDifferentWorkingDirectories tests template path resolution
// from different working directories to identify path resolution issues.
// This test MUST FAIL initially (RED phase) to demonstrate the issue.
func TestTemplatePathResolutionFromDifferentWorkingDirectories(t *testing.T) {
	// FORGE TDD: RED PHASE - This test MUST fail to demonstrate template path issues
	
	// Test data for template execution validation
	testData := TemplateData{
		ActivePage: "test",
		Stats: DashboardStats{
			FabricCount: 1,
			CRDCount:    5,
		},
	}
	
	t.Run("template_path_resolution_from_cnoc_directory", func(t *testing.T) {
		// Change to cnoc directory (typical working directory when running from cnoc/)
		originalDir, err := os.Getwd()
		if err != nil {
			t.Fatalf("Failed to get current directory: %v", err)
		}
		defer func() {
			if err := os.Chdir(originalDir); err != nil {
				t.Errorf("Failed to restore directory: %v", err)
			}
		}()
		
		// Ensure we're in the cnoc directory
		cnocDir := "/home/ubuntu/cc/hedgehog-netbox-plugin/cnoc"
		if err := os.Chdir(cnocDir); err != nil {
			t.Fatalf("Failed to change to cnoc directory: %v", err)
		}
		
		currentDir, _ := os.Getwd()
		t.Logf("Testing from directory: %s", currentDir)
		
		// Test template path resolution with relative path
		templatePattern := "web/templates/*.html"
		t.Logf("Attempting to parse templates with pattern: %s", templatePattern)
		
		templates, err := template.ParseGlob(templatePattern)
		if err != nil {
			t.Errorf("EXPECTED FAILURE (RED PHASE): Failed to parse templates from %s: %v", templatePattern, err)
			// This is expected to fail initially - document the failure
			t.Logf("❌ Template parsing failed as expected for RED phase validation")
			return
		}
		
		// Validate template count
		templateCount := len(templates.Templates())
		expectedMinTemplates := 5 // At least base.html, simple_dashboard.html, fabric_list.html, etc.
		
		if templateCount < expectedMinTemplates {
			t.Errorf("TEMPLATE COUNT VALIDATION FAILED: Expected at least %d templates, got %d", expectedMinTemplates, templateCount)
		}
		
		t.Logf("✅ Loaded %d templates successfully", templateCount)
		
		// List all loaded templates for evidence
		for _, tmpl := range templates.Templates() {
			t.Logf("  - Template: %s", tmpl.Name())
		}
		
		// Test template compilation and execution
		testTemplateExecution(t, templates, testData)
	})
	
	t.Run("template_path_resolution_from_root_directory", func(t *testing.T) {
		// Test from project root directory (common when running tests from IDE)
		originalDir, err := os.Getwd()
		if err != nil {
			t.Fatalf("Failed to get current directory: %v", err)
		}
		defer func() {
			if err := os.Chdir(originalDir); err != nil {
				t.Errorf("Failed to restore directory: %v", err)
			}
		}()
		
		// Change to project root
		rootDir := "/home/ubuntu/cc/hedgehog-netbox-plugin"
		if err := os.Chdir(rootDir); err != nil {
			t.Fatalf("Failed to change to root directory: %v", err)
		}
		
		currentDir, _ := os.Getwd()
		t.Logf("Testing from directory: %s", currentDir)
		
		// Test template path resolution with path from root
		templatePattern := "cnoc/web/templates/*.html"
		t.Logf("Attempting to parse templates with pattern: %s", templatePattern)
		
		templates, err := template.ParseGlob(templatePattern)
		if err != nil {
			t.Errorf("EXPECTED FAILURE (RED PHASE): Failed to parse templates from %s: %v", templatePattern, err)
			t.Logf("❌ Template parsing failed from root directory")
			return
		}
		
		// Validate template count
		templateCount := len(templates.Templates())
		expectedMinTemplates := 5
		
		if templateCount < expectedMinTemplates {
			t.Errorf("TEMPLATE COUNT VALIDATION FAILED: Expected at least %d templates, got %d", expectedMinTemplates, templateCount)
		}
		
		t.Logf("✅ Loaded %d templates from root directory", templateCount)
		
		// Test template execution
		testTemplateExecution(t, templates, testData)
	})
	
	t.Run("absolute_template_path_resolution", func(t *testing.T) {
		// Test with absolute path - this should work regardless of working directory
		absoluteTemplatePath := "/home/ubuntu/cc/hedgehog-netbox-plugin/cnoc/web/templates/*.html"
		t.Logf("Testing absolute template path: %s", absoluteTemplatePath)
		
		templates, err := template.ParseGlob(absoluteTemplatePath)
		if err != nil {
			t.Errorf("ABSOLUTE PATH FAILED: Failed to parse templates from %s: %v", absoluteTemplatePath, err)
			return
		}
		
		templateCount := len(templates.Templates())
		t.Logf("✅ Absolute path loaded %d templates", templateCount)
		
		// This should be our baseline - absolute paths should always work
		if templateCount < 5 {
			t.Errorf("ABSOLUTE PATH INSUFFICIENT TEMPLATES: Expected at least 5, got %d", templateCount)
		}
		
		// Test template execution with absolute path
		testTemplateExecution(t, templates, testData)
	})
	
	t.Run("web_handler_template_path_validation", func(t *testing.T) {
		// Test the actual WebHandler template loading behavior
		originalDir, err := os.Getwd()
		if err != nil {
			t.Fatalf("Failed to get current directory: %v", err)
		}
		defer func() {
			if err := os.Chdir(originalDir); err != nil {
				t.Errorf("Failed to restore directory: %v", err)
			}
		}()
		
		// Test from cnoc directory
		cnocDir := "/home/ubuntu/cc/hedgehog-netbox-plugin/cnoc"
		if err := os.Chdir(cnocDir); err != nil {
			t.Fatalf("Failed to change to cnoc directory: %v", err)
		}
		
		// Create WebHandler with default template path
		metricsCollector := monitoring.NewMetricsCollector()
		handler, err := NewWebHandler(metricsCollector)
		
		if err != nil {
			t.Errorf("WEBHANDLER CREATION FAILED: %v", err)
			t.Logf("❌ WebHandler failed to create - this demonstrates the template path issue")
			
			// Try with different template paths to identify the issue
			testAlternativeTemplatePaths(t, metricsCollector)
			return
		}
		
		if handler.templates == nil {
			t.Error("WEBHANDLER TEMPLATES NIL: WebHandler created but templates are nil")
			return
		}
		
		templateCount := len(handler.templates.Templates())
		t.Logf("✅ WebHandler loaded %d templates", templateCount)
		
		if templateCount == 0 {
			t.Error("WEBHANDLER NO TEMPLATES: WebHandler loaded 0 templates")
		}
	})
}

// testTemplateExecution validates that loaded templates can be compiled and executed
func testTemplateExecution(t *testing.T, templates *template.Template, data TemplateData) {
	if templates == nil {
		t.Error("TEMPLATE EXECUTION TEST FAILED: templates is nil")
		return
	}
	
	// Test execution of key templates
	templateTests := []string{
		"simple_dashboard.html",
		"base.html",
		"fabric_list.html",
	}
	
	for _, templateName := range templateTests {
		t.Run(fmt.Sprintf("execute_%s", templateName), func(t *testing.T) {
			// Try to execute the template
			var buf strings.Builder
			err := templates.ExecuteTemplate(&buf, templateName, data)
			
			if err != nil {
				t.Errorf("TEMPLATE EXECUTION FAILED for %s: %v", templateName, err)
				return
			}
			
			output := buf.String()
			if len(output) == 0 {
				t.Errorf("TEMPLATE OUTPUT EMPTY for %s", templateName)
				return
			}
			
			// Validate HTML structure
			if !strings.Contains(output, "<html") {
				t.Errorf("TEMPLATE OUTPUT INVALID for %s: missing <html> tag", templateName)
			}
			
			t.Logf("✅ Template %s executed successfully (%d bytes)", templateName, len(output))
		})
	}
}

// testAlternativeTemplatePaths tests various template path patterns to identify working solutions
func testAlternativeTemplatePaths(t *testing.T, metricsCollector *monitoring.MetricsCollector) {
	alternativePaths := []string{
		"web/templates/*.html",                                                    // Default relative path
		"./web/templates/*.html",                                                  // Explicit current directory
		"/home/ubuntu/cc/hedgehog-netbox-plugin/cnoc/web/templates/*.html",        // Absolute path
		"../cnoc/web/templates/*.html",                                            // From parent directory
		"*/web/templates/*.html",                                                  // Wildcard path
	}
	
	for _, path := range alternativePaths {
		t.Run(fmt.Sprintf("alternative_path_%s", filepath.Base(path)), func(t *testing.T) {
			handler, err := NewWebHandlerWithTemplatePath(metricsCollector, path)
			
			if err != nil {
				t.Logf("❌ Alternative path failed: %s - %v", path, err)
				return
			}
			
			if handler.templates == nil {
				t.Logf("❌ Alternative path loaded but templates nil: %s", path)
				return
			}
			
			templateCount := len(handler.templates.Templates())
			t.Logf("✅ Alternative path worked: %s - loaded %d templates", path, templateCount)
		})
	}
}

// TestTemplateGlobPatternMatching tests glob pattern matching specifically
func TestTemplateGlobPatternMatching(t *testing.T) {
	// Test various glob patterns from cnoc directory
	originalDir, err := os.Getwd()
	if err != nil {
		t.Fatalf("Failed to get current directory: %v", err)
	}
	defer func() {
		if err := os.Chdir(originalDir); err != nil {
			t.Errorf("Failed to restore directory: %v", err)
		}
	}()
	
	cnocDir := "/home/ubuntu/cc/hedgehog-netbox-plugin/cnoc"
	if err := os.Chdir(cnocDir); err != nil {
		t.Fatalf("Failed to change to cnoc directory: %v", err)
	}
	
	// Test different glob patterns
	patterns := []struct {
		pattern  string
		expected int
		shouldWork bool
	}{
		{"web/templates/*.html", 10, true},                    // Standard pattern
		{"web/templates/**/*.html", 10, true},                 // Recursive pattern
		{"web/templates/base.html", 1, true},                  // Single file
		{"web/templates/simple_*.html", 1, true},              // Wildcard pattern
		{"nonexistent/templates/*.html", 0, false},            // Non-existent path
		{"/absolute/nonexistent/*.html", 0, false},            // Non-existent absolute
	}
	
	for _, test := range patterns {
		t.Run(fmt.Sprintf("pattern_%s", filepath.Base(test.pattern)), func(t *testing.T) {
			matches, err := filepath.Glob(test.pattern)
			
			if !test.shouldWork && err == nil && len(matches) == 0 {
				t.Logf("✅ Pattern correctly failed: %s", test.pattern)
				return
			}
			
			if err != nil {
				if test.shouldWork {
					t.Errorf("GLOB PATTERN FAILED: %s - %v", test.pattern, err)
				} else {
					t.Logf("✅ Pattern failed as expected: %s - %v", test.pattern, err)
				}
				return
			}
			
			if len(matches) != test.expected && test.shouldWork {
				t.Errorf("GLOB MATCH COUNT MISMATCH: pattern %s expected %d matches, got %d", 
					test.pattern, test.expected, len(matches))
			}
			
			t.Logf("✅ Pattern matched %d files: %s", len(matches), test.pattern)
			for _, match := range matches {
				t.Logf("  - %s", match)
			}
		})
	}
}

// TestTemplatePathResolutionQuantitativeMetrics provides quantitative evidence
func TestTemplatePathResolutionQuantitativeMetrics(t *testing.T) {
	metrics := struct {
		TotalTemplatesExpected int
		TemplatesFound        map[string]int
		PathsAttempted        []string
		PathsSuccessful       []string
		PathsFailed           []string
		ErrorMessages         []string
	}{
		TotalTemplatesExpected: 10, // Expected template count based on file listing
		TemplatesFound:        make(map[string]int),
		PathsAttempted:        []string{},
		PathsSuccessful:       []string{},
		PathsFailed:           []string{},
		ErrorMessages:         []string{},
	}
	
	// Test paths from different working directories
	testCases := []struct {
		workingDir string
		pattern    string
	}{
		{"/home/ubuntu/cc/hedgehog-netbox-plugin/cnoc", "web/templates/*.html"},
		{"/home/ubuntu/cc/hedgehog-netbox-plugin", "cnoc/web/templates/*.html"},
		{"/tmp", "/home/ubuntu/cc/hedgehog-netbox-plugin/cnoc/web/templates/*.html"},
	}
	
	originalDir, _ := os.Getwd()
	defer os.Chdir(originalDir)
	
	for _, test := range testCases {
		metrics.PathsAttempted = append(metrics.PathsAttempted, fmt.Sprintf("%s:%s", test.workingDir, test.pattern))
		
		os.Chdir(test.workingDir)
		templates, err := template.ParseGlob(test.pattern)
		
		if err != nil {
			metrics.PathsFailed = append(metrics.PathsFailed, fmt.Sprintf("%s:%s", test.workingDir, test.pattern))
			metrics.ErrorMessages = append(metrics.ErrorMessages, err.Error())
		} else {
			pathKey := fmt.Sprintf("%s:%s", test.workingDir, test.pattern)
			templateCount := len(templates.Templates())
			metrics.TemplatesFound[pathKey] = templateCount
			
			if templateCount > 0 {
				metrics.PathsSuccessful = append(metrics.PathsSuccessful, pathKey)
			}
		}
	}
	
	// Report quantitative metrics
	t.Logf("=== TEMPLATE PATH RESOLUTION QUANTITATIVE METRICS ===")
	t.Logf("Expected templates: %d", metrics.TotalTemplatesExpected)
	t.Logf("Paths attempted: %d", len(metrics.PathsAttempted))
	t.Logf("Paths successful: %d", len(metrics.PathsSuccessful))
	t.Logf("Paths failed: %d", len(metrics.PathsFailed))
	t.Logf("Success rate: %.1f%%", float64(len(metrics.PathsSuccessful))/float64(len(metrics.PathsAttempted))*100)
	
	t.Logf("\n--- SUCCESSFUL PATHS ---")
	for _, path := range metrics.PathsSuccessful {
		t.Logf("✅ %s (loaded %d templates)", path, metrics.TemplatesFound[path])
	}
	
	t.Logf("\n--- FAILED PATHS ---")
	for _, path := range metrics.PathsFailed {
		t.Logf("❌ %s", path)
	}
	
	t.Logf("\n--- ERROR MESSAGES ---")
	for i, err := range metrics.ErrorMessages {
		t.Logf("%d. %s", i+1, err)
	}
	
	// Validate that at least one path works (for baseline)
	if len(metrics.PathsSuccessful) == 0 {
		t.Error("CRITICAL FAILURE: No template paths work from any working directory")
	}
	
	// Check if the default WebHandler path works
	defaultPathExists := false
	for path, count := range metrics.TemplatesFound {
		if strings.Contains(path, "web/templates/*.html") && count >= metrics.TotalTemplatesExpected {
			defaultPathExists = true
			break
		}
	}
	
	if !defaultPathExists {
		t.Error("DEFAULT PATH FAILURE: Default WebHandler template path does not work correctly")
	}
}

// TestTemplateLoadingFromWebHandlerConstructor validates the actual WebHandler behavior
func TestTemplateLoadingFromWebHandlerConstructor(t *testing.T) {
	// This test validates the exact behavior that users experience
	
	originalDir, _ := os.Getwd()
	defer os.Chdir(originalDir)
	
	// Test from various directories to identify the specific failure scenario
	testCases := []struct {
		name         string
		workingDir   string
		shouldFail   bool
		description  string
	}{
		{
			name:        "from_cnoc_directory",
			workingDir:  "/home/ubuntu/cc/hedgehog-netbox-plugin/cnoc",
			shouldFail:  false,
			description: "This should work - templates are relative to cnoc/",
		},
		{
			name:        "from_project_root",
			workingDir:  "/home/ubuntu/cc/hedgehog-netbox-plugin",
			shouldFail:  true,
			description: "This should FAIL - template path 'web/templates/*.html' doesn't exist from root",
		},
		{
			name:        "from_parent_directory",
			workingDir:  "/home/ubuntu/cc/hedgehog-netbox-plugin/..",
			shouldFail:  true,
			description: "This should FAIL - template path is completely wrong",
		},
		{
			name:        "from_tmp_directory",
			workingDir:  "/tmp",
			shouldFail:  true,
			description: "This should FAIL - template path doesn't exist from /tmp",
		},
	}
	
	for _, testCase := range testCases {
		t.Run(testCase.name, func(t *testing.T) {
			t.Logf("Testing from directory: %s", testCase.workingDir)
			t.Logf("Description: %s", testCase.description)
			
			if err := os.Chdir(testCase.workingDir); err != nil {
				t.Fatalf("Failed to change to directory %s: %v", testCase.workingDir, err)
			}
			
			currentDir, _ := os.Getwd()
			t.Logf("Current working directory: %s", currentDir)
			
			metricsCollector := monitoring.NewMetricsCollector()
			
			// Attempt to create WebHandler - this is where users see the failure
			handler, err := NewWebHandler(metricsCollector)
			
			if err != nil {
				if testCase.shouldFail {
					t.Logf("✅ EXPECTED RED PHASE FAILURE from %s: %v", testCase.workingDir, err)
					t.Logf("✅ This demonstrates the template path resolution issue")
					
					// Document the specific error type for evidence
					if strings.Contains(err.Error(), "no such file or directory") {
						t.Logf("✅ ERROR TYPE: File not found - template path resolution issue confirmed")
					} else if strings.Contains(err.Error(), "pattern matches no files") {
						t.Logf("✅ ERROR TYPE: Pattern matching issue - glob pattern fails as expected")
					} else {
						t.Logf("✅ ERROR TYPE: Other - %s", err.Error())
					}
				} else {
					t.Errorf("❌ UNEXPECTED FAILURE from %s: %v", testCase.workingDir, err)
					t.Errorf("❌ This directory should have worked but didn't")
				}
				return
			}
			
			// If we get here, WebHandler was created successfully
			if testCase.shouldFail {
				t.Errorf("❌ UNEXPECTED SUCCESS from %s: WebHandler should have failed but didn't", testCase.workingDir)
			} else {
				t.Logf("✅ EXPECTED SUCCESS from %s: WebHandler created successfully", testCase.workingDir)
			}
			
			if handler.templates == nil {
				t.Error("HANDLER TEMPLATES NIL: WebHandler created but templates not loaded")
				return
			}
			
			templateCount := len(handler.templates.Templates())
			t.Logf("Templates loaded: %d", templateCount)
			
			if templateCount == 0 {
				t.Error("NO TEMPLATES LOADED: WebHandler loaded zero templates")
			}
		})
	}
}

// TestTemplatePathResolutionWithDifferentExecutablePaths simulates running the executable from different paths
func TestTemplatePathResolutionWithDifferentExecutablePaths(t *testing.T) {
	// This test simulates the actual issue that occurs when the cnoc executable
	// is run from different working directories
	
	originalDir, _ := os.Getwd()
	defer os.Chdir(originalDir)
	
	// Create a test that proves the hardcoded relative path "web/templates/*.html" fails
	// when the working directory is not the cnoc directory
	
	t.Run("simulate_executable_from_project_root", func(t *testing.T) {
		// This simulates running ./cnoc/cnoc from the project root directory
		rootDir := "/home/ubuntu/cc/hedgehog-netbox-plugin"
		os.Chdir(rootDir)
		
		// The NewWebHandler uses hardcoded "web/templates/*.html"
		// This should fail because web/templates doesn't exist in the root directory
		templatePattern := "web/templates/*.html"
		
		_, err := template.ParseGlob(templatePattern)
		if err != nil {
			t.Logf("✅ EXPECTED RED PHASE FAILURE: Template pattern %s fails from %s", templatePattern, rootDir)
			t.Logf("✅ Error: %v", err)
			t.Logf("✅ This proves the template path resolution issue exists")
		} else {
			t.Errorf("❌ UNEXPECTED SUCCESS: Template pattern should have failed from project root")
		}
	})
	
	t.Run("validate_correct_path_from_project_root", func(t *testing.T) {
		// This shows what the path SHOULD be when running from project root
		rootDir := "/home/ubuntu/cc/hedgehog-netbox-plugin"
		os.Chdir(rootDir)
		
		correctPattern := "cnoc/web/templates/*.html"
		templates, err := template.ParseGlob(correctPattern)
		
		if err != nil {
			t.Errorf("❌ CORRECT PATH FAILED: %s should work from %s: %v", correctPattern, rootDir, err)
		} else {
			templateCount := len(templates.Templates())
			t.Logf("✅ CORRECT PATH SUCCESS: %s loaded %d templates from %s", correctPattern, templateCount, rootDir)
		}
	})
	
	t.Run("demonstrate_solution_with_absolute_path", func(t *testing.T) {
		// This demonstrates that absolute paths solve the issue
		anyDir := "/tmp"
		os.Chdir(anyDir)
		
		absolutePath := "/home/ubuntu/cc/hedgehog-netbox-plugin/cnoc/web/templates/*.html"
		templates, err := template.ParseGlob(absolutePath)
		
		if err != nil {
			t.Errorf("❌ ABSOLUTE PATH FAILED: %s should work from any directory: %v", absolutePath, err)
		} else {
			templateCount := len(templates.Templates())
			t.Logf("✅ ABSOLUTE PATH SUCCESS: %s loaded %d templates from %s", absolutePath, templateCount, anyDir)
		}
	})
}