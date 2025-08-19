package web

import (
	"os"
	"testing"
)

func TestWorkingDirectory(t *testing.T) {
	wd, err := os.Getwd()
	if err != nil {
		t.Fatalf("Failed to get working directory: %v", err)
	}
	t.Logf("Current working directory: %s", wd)
	
	// Check if templates exist relative to current working directory
	templatePaths := []string{
		"web/templates/simple_dashboard.html",
		"../../../web/templates/simple_dashboard.html", // From internal/web test location
		"../../web/templates/simple_dashboard.html",    // Alternative path
	}
	
	for _, path := range templatePaths {
		if _, err := os.Stat(path); err == nil {
			t.Logf("✅ Templates found at: %s", path)
		} else {
			t.Logf("❌ Templates not found at: %s", path)
		}
	}
}