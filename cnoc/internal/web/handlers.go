package web

import (
	"fmt"
	"html/template"
	"log"
	"net/http"
	"time"

	"github.com/gorilla/mux"
)

// TemplateData holds common data for all templates
type TemplateData struct {
	ActivePage      string
	Stats           DashboardStats
	RecentActivity  []Activity
	Fabrics         []Fabric
	Fabric          *Fabric
	GitRepositories []GitRepository
	CRDResources    []CRDResource
	DriftSpotlight  DriftSpotlight
	Data            interface{}
}

// DashboardStats holds dashboard statistics
type DashboardStats struct {
	FabricCount    int
	CRDCount       int
	InSyncCount    int
	DriftCount     int
	VPCCount       int
	SwitchCount    int
	TotalFabrics   int
	TotalCRDs      int
	ConnectionCount int
}

// Activity represents a recent activity item
type Activity struct {
	Timestamp time.Time
	Type      string
	Resource  string
	Action    string
	Status    string
}

// Fabric represents a fabric installation
type Fabric struct {
	ID                     string
	Name                   string
	Description            string
	GitRepository          *GitRepository
	GitOpsDirectory        string
	GitOpsBranch           string
	GitSyncStatus          string
	DriftStatus            string
	DriftCount             int
	CachedCRDCount         int
	LastGitSync            *time.Time
	LastGitSyncAgo         string
	LastGitCommitHash      string
	LastGitCommitHashShort string
}

// GitRepository represents a git repository
type GitRepository struct {
	ID                  string
	Name                string
	URL                 string
	Description         string
	ConnectionStatus    string
	LastValidated       *time.Time
	LastValidatedAgo    string
	AuthenticationType  string
}

// CRDResource represents a CRD resource
type CRDResource struct {
	ID                   string
	Name                 string
	Namespace            string
	Type                 string
	GitFilePath          string
	LastSyncedFrom       string
	GitSyncTimestamp     *time.Time
	GitSyncTimestampAgo  string
	HasDrift             bool
}

// DriftSpotlight represents drift detection status
type DriftSpotlight struct {
	StatusClass     string
	Message         string
	DriftCount      int
	TotalResources  int
	LastCheck       string
}

// WebHandler handles web UI requests
type WebHandler struct {
	templates *template.Template
	// In production, we'd inject services here
}

// NewWebHandler creates a new web handler
func NewWebHandler() (*WebHandler, error) {
	// Parse templates with better error handling and correct path resolution
	templatePattern := "../../web/templates/*.html"
	templates, err := template.ParseGlob(templatePattern)
	if err != nil {
		return nil, fmt.Errorf("failed to parse templates from %s: %v", templatePattern, err)
	}

	// List loaded templates for debugging
	for _, tmpl := range templates.Templates() {
		fmt.Printf("✅ Loaded template: %s\n", tmpl.Name())
	}

	return &WebHandler{
		templates: templates,
	}, nil
}

// RegisterRoutes registers web UI routes
func (h *WebHandler) RegisterRoutes(router *mux.Router) {
	// Serve static files
	staticDir := "/static/"
	router.PathPrefix(staticDir).Handler(
		http.StripPrefix(staticDir, http.FileServer(http.Dir("./web/static"))),
	)

	// Web UI routes
	router.HandleFunc("/", h.HandleDashboard).Methods("GET")
	router.HandleFunc("/dashboard", h.HandleDashboard).Methods("GET")
	router.HandleFunc("/fabrics", h.HandleFabricList).Methods("GET")
	router.HandleFunc("/fabrics/{id}", h.HandleFabricDetail).Methods("GET")
	router.HandleFunc("/repositories", h.HandleRepositoryList).Methods("GET")
	router.HandleFunc("/repositories/{id}", h.HandleRepositoryDetail).Methods("GET")
	router.HandleFunc("/crds", h.HandleCRDList).Methods("GET")
	router.HandleFunc("/crds/vpcs", h.HandleVPCList).Methods("GET")
	router.HandleFunc("/crds/connections", h.HandleConnectionList).Methods("GET")
	router.HandleFunc("/crds/switches", h.HandleSwitchList).Methods("GET")
	router.HandleFunc("/drift", h.HandleDriftDetection).Methods("GET")
}

// HandleDashboard renders the dashboard page
func (h *WebHandler) HandleDashboard(w http.ResponseWriter, r *http.Request) {
	data := TemplateData{
		ActivePage: "dashboard",
		Stats: DashboardStats{
			FabricCount:     3,
			CRDCount:        60,
			InSyncCount:     54,
			DriftCount:      6,
			VPCCount:        4,
			SwitchCount:     16,
			TotalFabrics:    3,
			TotalCRDs:       60,
			ConnectionCount: 40,
		},
		RecentActivity: []Activity{
			{
				Timestamp: time.Now().Add(-5 * time.Minute),
				Type:      "Fabric",
				Resource:  "HCKC",
				Action:    "Sync",
				Status:    "success",
			},
			{
				Timestamp: time.Now().Add(-15 * time.Minute),
				Type:      "Repository",
				Resource:  "gitops-test-1",
				Action:    "Connection Test",
				Status:    "success",
			},
			{
				Timestamp: time.Now().Add(-30 * time.Minute),
				Type:      "CRD",
				Resource:  "vpc-prod",
				Action:    "Create",
				Status:    "success",
			},
		},
	}

	h.renderTemplate(w, "simple_dashboard", data)
}

// HandleFabricList renders the fabric list page
func (h *WebHandler) HandleFabricList(w http.ResponseWriter, r *http.Request) {
	lastSync := time.Now().Add(-2 * time.Hour)
	lastValidated := time.Now().Add(-30 * time.Minute)
	
	gitRepo := &GitRepository{
		ID:                  "repo-1",
		Name:                "GitOps Test Repository 1",
		URL:                 "https://github.com/afewell-hh/gitops-test-1",
		Description:         "Primary GitOps repository for CNOC testing",
		ConnectionStatus:    "connected",
		LastValidated:       &lastValidated,
		LastValidatedAgo:    "30 minutes ago",
		AuthenticationType:  "personal_access_token",
	}

	fabrics := []Fabric{
		{
			ID:                     "fabric-1",
			Name:                   "HCKC",
			Description:            "Hedgehog Cloud Kubernetes Cluster",
			GitRepository:          gitRepo,
			GitOpsDirectory:        "gitops/hedgehog/fabric-1/",
			GitOpsBranch:           "main",
			GitSyncStatus:          "in_sync",
			DriftStatus:            "none",
			DriftCount:             0,
			CachedCRDCount:         36,
			LastGitSync:            &lastSync,
			LastGitSyncAgo:         "2 hours ago",
			LastGitCommitHash:      "a1b2c3d4e5f6789012345678901234567890abcd",
			LastGitCommitHashShort: "a1b2c3d",
		},
		{
			ID:                     "fabric-2",
			Name:                   "Staging",
			Description:            "Staging environment for testing",
			GitRepository:          gitRepo,
			GitOpsDirectory:        "gitops/hedgehog/staging/",
			GitOpsBranch:           "staging",
			GitSyncStatus:          "out_of_sync",
			DriftStatus:            "detected",
			DriftCount:             3,
			CachedCRDCount:         24,
			LastGitSync:            &lastSync,
			LastGitSyncAgo:         "2 hours ago",
			LastGitCommitHash:      "b2c3d4e5f6789012345678901234567890abcdef",
			LastGitCommitHashShort: "b2c3d4e",
		},
		{
			ID:              "fabric-3",
			Name:            "Production",
			Description:     "Production fabric (not configured)",
			GitRepository:   nil,
			GitSyncStatus:   "never_synced",
			DriftStatus:     "unknown",
			DriftCount:      0,
			CachedCRDCount:  0,
			LastGitSync:     nil,
			LastGitSyncAgo:  "Never",
		},
	}

	stats := DashboardStats{
		TotalFabrics: 3,
		InSyncCount:  1,
		DriftCount:   1,
		TotalCRDs:    60,
	}

	gitRepositories := []GitRepository{*gitRepo}

	data := TemplateData{
		ActivePage:      "fabrics",
		Fabrics:         fabrics,
		Stats:           stats,
		GitRepositories: gitRepositories,
	}

	h.renderTemplate(w, "fabric_list", data)
}

// HandleFabricDetail renders the fabric detail page
func (h *WebHandler) HandleFabricDetail(w http.ResponseWriter, r *http.Request) {
	vars := mux.Vars(r)
	fabricID := vars["id"]

	lastSync := time.Now().Add(-2 * time.Hour)
	lastValidated := time.Now().Add(-30 * time.Minute)
	crdSyncTime := time.Now().Add(-1 * time.Hour)
	
	gitRepo := &GitRepository{
		ID:                  "repo-1",
		Name:                "GitOps Test Repository 1",
		URL:                 "https://github.com/afewell-hh/gitops-test-1",
		Description:         "Primary GitOps repository for CNOC testing",
		ConnectionStatus:    "connected",
		LastValidated:       &lastValidated,
		LastValidatedAgo:    "30 minutes ago",
		AuthenticationType:  "personal_access_token",
	}

	fabric := &Fabric{
		ID:                     fabricID,
		Name:                   "HCKC",
		Description:            "Hedgehog Cloud Kubernetes Cluster - Production Environment",
		GitRepository:          gitRepo,
		GitOpsDirectory:        "gitops/hedgehog/fabric-1/",
		GitOpsBranch:           "main",
		GitSyncStatus:          "in_sync",
		DriftStatus:            "none",
		DriftCount:             0,
		CachedCRDCount:         36,
		LastGitSync:            &lastSync,
		LastGitSyncAgo:         "2 hours ago",
		LastGitCommitHash:      "a1b2c3d4e5f6789012345678901234567890abcd",
		LastGitCommitHashShort: "a1b2c3d",
	}

	// Adjust fabric data based on ID for variety
	switch fabricID {
	case "fabric-2":
		fabric.Name = "Staging"
		fabric.Description = "Staging environment for testing"
		fabric.GitSyncStatus = "out_of_sync"
		fabric.DriftStatus = "detected"
		fabric.DriftCount = 3
		fabric.CachedCRDCount = 24
	case "fabric-3":
		fabric.Name = "Production"
		fabric.Description = "Production fabric (not configured)"
		fabric.GitRepository = nil
		fabric.GitSyncStatus = "never_synced"
		fabric.DriftStatus = "unknown"
		fabric.DriftCount = 0
		fabric.CachedCRDCount = 0
		fabric.LastGitSync = nil
		fabric.LastGitSyncAgo = "Never"
	}

	driftSpotlight := DriftSpotlight{
		StatusClass:    "in-sync",
		Message:        "All resources are synchronized with Git repository. No configuration drift detected.",
		DriftCount:     fabric.DriftCount,
		TotalResources: fabric.CachedCRDCount,
		LastCheck:      "2 hours ago",
	}

	if fabric.DriftStatus == "detected" {
		driftSpotlight.StatusClass = "drift-detected"
		driftSpotlight.Message = "Configuration drift detected. Some resources differ from Git repository."
	} else if fabric.DriftStatus == "unknown" {
		driftSpotlight.StatusClass = "critical"
		driftSpotlight.Message = "Unable to determine drift status. Git repository not configured."
	}

	stats := DashboardStats{
		TotalCRDs:       fabric.CachedCRDCount,
		VPCCount:        2,
		ConnectionCount: 26,
		SwitchCount:     8,
	}

	crdResources := []CRDResource{
		{
			ID:                  "crd-1",
			Name:                "vpc-prod",
			Namespace:           "default",
			Type:                "vpc",
			GitFilePath:         "gitops/hedgehog/fabric-1/test-vpc.yaml",
			LastSyncedFrom:      "git",
			GitSyncTimestamp:    &crdSyncTime,
			GitSyncTimestampAgo: "1 hour ago",
			HasDrift:            false,
		},
		{
			ID:                  "crd-2",
			Name:                "vpc-staging",
			Namespace:           "staging",
			Type:                "vpc",
			GitFilePath:         "gitops/hedgehog/fabric-1/test-vpc-2.yaml",
			LastSyncedFrom:      "git",
			GitSyncTimestamp:    &crdSyncTime,
			GitSyncTimestampAgo: "1 hour ago",
			HasDrift:            fabric.DriftStatus == "detected",
		},
		{
			ID:                  "crd-3",
			Name:                "connection-main",
			Namespace:           "default",
			Type:                "connection",
			GitFilePath:         "gitops/hedgehog/fabric-1/prepop.yaml",
			LastSyncedFrom:      "git",
			GitSyncTimestamp:    &crdSyncTime,
			GitSyncTimestampAgo: "1 hour ago",
			HasDrift:            false,
		},
		{
			ID:                  "crd-4",
			Name:                "switch-leaf-01",
			Namespace:           "default",
			Type:                "switch",
			GitFilePath:         "gitops/hedgehog/fabric-1/prepop.yaml",
			LastSyncedFrom:      "kubernetes",
			GitSyncTimestamp:    &crdSyncTime,
			GitSyncTimestampAgo: "1 hour ago",
			HasDrift:            false,
		},
	}

	recentActivity := []Activity{
		{
			Timestamp: time.Now().Add(-5 * time.Minute),
			Type:      "sync",
			Resource:  "GitOps Sync",
			Action:    "Completed successfully",
			Status:    "success",
		},
		{
			Timestamp: time.Now().Add(-1 * time.Hour),
			Type:      "test_connection",
			Resource:  "Git Repository",
			Action:    "Connection test",
			Status:    "success",
		},
		{
			Timestamp: time.Now().Add(-2 * time.Hour),
			Type:      "detect_drift",
			Resource:  "Drift Detection",
			Action:    "Analyzed 36 resources",
			Status:    "completed",
		},
	}

	data := TemplateData{
		ActivePage:     "fabrics",
		Fabric:         fabric,
		Stats:          stats,
		DriftSpotlight: driftSpotlight,
		CRDResources:   crdResources,
		RecentActivity: recentActivity,
	}

	h.renderTemplate(w, "fabric_detail", data)
}

// HandleRepositoryList renders the repository list page
func (h *WebHandler) HandleRepositoryList(w http.ResponseWriter, r *http.Request) {
	data := TemplateData{
		ActivePage: "repositories",
	}

	h.renderTemplate(w, "repository_list", data)
}

// HandleRepositoryDetail renders the repository detail page
func (h *WebHandler) HandleRepositoryDetail(w http.ResponseWriter, r *http.Request) {
	vars := mux.Vars(r)
	repoID := vars["id"]

	data := TemplateData{
		ActivePage: "repositories",
		Data:       repoID,
	}

	h.renderTemplate(w, "repository_detail", data)
}

// HandleCRDList renders the CRD list page
func (h *WebHandler) HandleCRDList(w http.ResponseWriter, r *http.Request) {
	data := TemplateData{
		ActivePage: "crds",
	}

	h.renderTemplate(w, "crd_list", data)
}

// HandleVPCList renders the VPC list page
func (h *WebHandler) HandleVPCList(w http.ResponseWriter, r *http.Request) {
	data := TemplateData{
		ActivePage: "crds",
	}

	h.renderTemplate(w, "vpc_list", data)
}

// HandleConnectionList renders the connection list page
func (h *WebHandler) HandleConnectionList(w http.ResponseWriter, r *http.Request) {
	data := TemplateData{
		ActivePage: "crds",
	}

	h.renderTemplate(w, "connection_list", data)
}

// HandleSwitchList renders the switch list page
func (h *WebHandler) HandleSwitchList(w http.ResponseWriter, r *http.Request) {
	data := TemplateData{
		ActivePage: "crds",
	}

	h.renderTemplate(w, "switch_list", data)
}

// HandleDriftDetection renders the drift detection page
func (h *WebHandler) HandleDriftDetection(w http.ResponseWriter, r *http.Request) {
	data := TemplateData{
		ActivePage: "drift",
	}

	h.renderTemplate(w, "drift_detection", data)
}

// renderTemplate renders a template with the base layout
func (h *WebHandler) renderTemplate(w http.ResponseWriter, name string, data TemplateData) {
	log.Printf("🎯 Attempting to render template: %s", name+".html")
	
	// Set content type for HTML
	w.Header().Set("Content-Type", "text/html; charset=utf-8")
	
	// For templates that use the template system (base.html + defines), execute base.html
	// For standalone templates like simple_dashboard.html, execute directly
	templateName := name + ".html"
	
	// Check if this is a standalone template (like simple_dashboard.html)
	if name == "simple_dashboard" {
		err := h.templates.ExecuteTemplate(w, templateName, data)
		if err != nil {
			log.Printf("❌ Standalone template execution failed for %s: %v", templateName, err)
			h.renderErrorFallback(w, name, err)
		} else {
			log.Printf("✅ Standalone template %s rendered successfully", templateName)
		}
		return
	}
	
	// For templates that extend base.html, execute base.html
	err := h.templates.ExecuteTemplate(w, "base.html", data)
	if err != nil {
		log.Printf("❌ Base template execution failed: %v", err)
		
		// Try to execute the template directly as fallback
		log.Printf("🔄 Trying direct template execution for %s", templateName)
		err = h.templates.ExecuteTemplate(w, templateName, data)
		if err != nil {
			log.Printf("❌ Direct template execution also failed: %v", err)
			h.renderErrorFallback(w, name, err)
		} else {
			log.Printf("✅ Direct template %s rendered successfully", templateName)
		}
	} else {
		log.Printf("✅ Base template rendered successfully for %s", name)
	}
}

// renderErrorFallback renders a simple error page when template rendering fails
func (h *WebHandler) renderErrorFallback(w http.ResponseWriter, name string, err error) {
	log.Printf("❌ Rendering error fallback for %s", name)
	
	fallbackHTML := fmt.Sprintf(`<!DOCTYPE html>
<html lang="en">
<head>
	<meta charset="UTF-8">
	<meta name="viewport" content="width=device-width, initial-scale=1.0">
	<title>CNOC Template Error</title>
	<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
</head>
<body>
	<div class="container mt-5">
		<div class="alert alert-danger">
			<h1><i class="bi bi-exclamation-triangle"></i> Template Error</h1>
			<p><strong>Failed to render template:</strong> %s</p>
			<p><strong>Error:</strong> %s</p>
			<hr>
			<p>This error occurred during template rendering. Please check the template files and try again.</p>
		</div>
	</div>
</body>
</html>`, name, err.Error())
	
	w.Write([]byte(fallbackHTML))
}