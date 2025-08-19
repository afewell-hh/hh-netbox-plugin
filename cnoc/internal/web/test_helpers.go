package web

import (
	"fmt"
	"html/template"
	"os"
	"path/filepath"
	
	"github.com/hedgehog/cnoc/internal/monitoring"
)

// NewTestWebHandler creates a web handler suitable for testing
// It handles the template path resolution for test environment
func NewTestWebHandler(metricsCollector *monitoring.MetricsCollector) (*WebHandler, error) {
	// Determine correct template path for test environment
	templatePattern, err := findTemplatePattern()
	if err != nil {
		return nil, fmt.Errorf("failed to find template pattern: %v", err)
	}

	// Parse templates with test-compatible path
	templates, err := template.ParseGlob(templatePattern)
	if err != nil {
		return nil, fmt.Errorf("failed to parse templates from %s: %v", templatePattern, err)
	}

	// List loaded templates for debugging
	for _, tmpl := range templates.Templates() {
		fmt.Printf("✅ Test Loaded template: %s\n", tmpl.Name())
	}

	// Initialize WebSocket manager
	wsManager := NewWebSocketManager()
	wsManager.Start()

	// Initialize event broadcaster
	eventBroadcaster := NewEventBroadcaster(wsManager)

	// Initialize service factory with real application services
	serviceFactory := NewServiceFactory()

	// Start mock operations if metrics collector is available
	if metricsCollector != nil {
		metricsCollector.MockBusinessOperations()
	}

	return &WebHandler{
		templates:        templates,
		wsManager:        wsManager,
		eventBroadcaster: eventBroadcaster,
		metricsCollector: metricsCollector,
		serviceFactory:   serviceFactory,
	}, nil
}

// findTemplatePattern determines the correct template path for the current environment
func findTemplatePattern() (string, error) {
	// Get current working directory
	wd, err := os.Getwd()
	if err != nil {
		return "", fmt.Errorf("failed to get working directory: %v", err)
	}

	// List of potential template paths to try
	candidatePaths := []string{
		"web/templates/*.html",                  // From project root
		"../../web/templates/*.html",            // From internal/web (test environment)
		"../../../web/templates/*.html",         // Alternative test path
		filepath.Join(wd, "web/templates/*.html"), // Absolute path attempt
	}

	// Find the first path that contains templates
	for _, pattern := range candidatePaths {
		// Check if at least one template file exists matching this pattern
		matches, err := filepath.Glob(pattern)
		if err == nil && len(matches) > 0 {
			// Verify it's actually an HTML template
			for _, match := range matches {
				if filepath.Ext(match) == ".html" {
					fmt.Printf("📁 Using template pattern: %s (found %d templates)\n", pattern, len(matches))
					return pattern, nil
				}
			}
		}
	}

	return "", fmt.Errorf("no template files found in any of the candidate paths from working directory: %s", wd)
}