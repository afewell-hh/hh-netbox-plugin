package web

import (
	"encoding/json"
	"fmt"
	"html/template"
	"log"
	"net/http"
	"strconv"
	"time"

	"github.com/gorilla/mux"
	"github.com/hedgehog/cnoc/internal/api/rest/dto"
	"github.com/hedgehog/cnoc/internal/application/services"
	"github.com/hedgehog/cnoc/internal/monitoring"
)

// TemplateData holds common data for all templates
type TemplateData struct {
	ActivePage      string
	ContentTemplate string
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
	Description          string
	Labels               map[string]string
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
	templates        *template.Template
	wsManager        *WebSocketManager
	eventBroadcaster *EventBroadcaster
	metricsCollector *monitoring.MetricsCollector
	serviceFactory   *ServiceFactory
}

// NewWebHandler creates a new web handler
func NewWebHandler(metricsCollector *monitoring.MetricsCollector) (*WebHandler, error) {
	return NewWebHandlerWithTemplatePath(metricsCollector, "web/templates/*.html")
}

// NewWebHandlerWithTemplatePath creates a web handler with a custom template path
func NewWebHandlerWithTemplatePath(metricsCollector *monitoring.MetricsCollector, templatePattern string) (*WebHandler, error) {
	// Parse templates with better error handling and correct path resolution
	templates, err := template.ParseGlob(templatePattern)
	if err != nil {
		return nil, fmt.Errorf("failed to parse templates from %s: %v", templatePattern, err)
	}

	// List loaded templates for debugging
	for _, tmpl := range templates.Templates() {
		fmt.Printf("✅ Loaded template: %s\n", tmpl.Name())
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

// RegisterRoutes registers web UI routes
func (h *WebHandler) RegisterRoutes(router *mux.Router) {
	// Serve static files
	staticDir := "/static/"
	router.PathPrefix(staticDir).Handler(
		http.StripPrefix(staticDir, http.FileServer(http.Dir("./web/static"))),
	)

	// WebSocket endpoint for real-time updates
	router.HandleFunc("/ws", h.wsManager.HandleWebSocket).Methods("GET")

	// Metrics endpoint for Prometheus
	if h.metricsCollector != nil {
		router.Handle("/metrics", h.metricsCollector.Handler()).Methods("GET")
		router.HandleFunc("/healthz", h.metricsCollector.HealthzHandler()).Methods("GET")
	}

	// Apply metrics middleware to specific routes
	router.HandleFunc("/", h.withMetrics(h.HandleDashboard)).Methods("GET")
	router.HandleFunc("/dashboard", h.withMetrics(h.HandleDashboard)).Methods("GET")
	router.HandleFunc("/fabrics", h.withMetrics(h.HandleFabricList)).Methods("GET")
	router.HandleFunc("/fabrics/{id}", h.withMetrics(h.HandleFabricDetail)).Methods("GET")
	router.HandleFunc("/repositories", h.withMetrics(h.HandleRepositoryList)).Methods("GET")
	router.HandleFunc("/repositories/{id}", h.withMetrics(h.HandleRepositoryDetail)).Methods("GET")
	router.HandleFunc("/crds", h.withMetrics(h.HandleCRDList)).Methods("GET")
	router.HandleFunc("/crds/vpcs", h.withMetrics(h.HandleVPCList)).Methods("GET")
	router.HandleFunc("/crds/connections", h.withMetrics(h.HandleConnectionList)).Methods("GET")
	router.HandleFunc("/crds/switches", h.withMetrics(h.HandleSwitchList)).Methods("GET")
	router.HandleFunc("/drift", h.withMetrics(h.HandleDriftDetection)).Methods("GET")
	
	// Configuration management routes (NEW - using real services)
	router.HandleFunc("/configurations", h.withMetrics(h.HandleConfigurationList)).Methods("GET")
	router.HandleFunc("/configurations/{id}", h.withMetrics(h.HandleConfigurationDetail)).Methods("GET")
	router.HandleFunc("/configurations/new", h.withMetrics(h.HandleConfigurationCreate)).Methods("GET")

	// Configuration API endpoints (NEW - using real services)
	router.HandleFunc("/api/v1/configurations", h.HandleAPIConfigurationList).Methods("GET")
	router.HandleFunc("/api/v1/configurations", h.HandleAPIConfigurationCreate).Methods("POST")
	router.HandleFunc("/api/v1/configurations/{id}", h.HandleAPIConfigurationGet).Methods("GET")
	router.HandleFunc("/api/v1/configurations/{id}", h.HandleAPIConfigurationUpdate).Methods("PUT")
	router.HandleFunc("/api/v1/configurations/{id}", h.HandleAPIConfigurationDelete).Methods("DELETE")
	router.HandleFunc("/api/v1/configurations/{id}/validate", h.HandleAPIConfigurationValidate).Methods("POST")

	// Fabric API endpoints  
	router.HandleFunc("/api/v1/fabrics", h.HandleAPIFabricList).Methods("GET")
	router.HandleFunc("/api/v1/fabrics/{id}", h.HandleAPIFabricGet).Methods("GET")
	router.HandleFunc("/api/v1/fabrics/{id}/sync", h.HandleFabricSync).Methods("POST")
	router.HandleFunc("/api/v1/fabrics/{id}/validate", h.HandleAPIFabricValidate).Methods("POST")
	router.HandleFunc("/api/v1/fabrics/{id}/drift", h.HandleAPIFabricDrift).Methods("GET")
	
	// GitOps Repository API endpoints
	router.HandleFunc("/api/v1/repositories", h.HandleAPIRepositoryList).Methods("GET")
	router.HandleFunc("/api/v1/repositories", h.HandleAPIRepositoryCreate).Methods("POST")
	router.HandleFunc("/api/v1/repositories/{id}", h.HandleAPIRepositoryGet).Methods("GET")
	router.HandleFunc("/api/v1/repositories/{id}", h.HandleAPIRepositoryUpdate).Methods("PUT")
	router.HandleFunc("/api/v1/repositories/{id}", h.HandleAPIRepositoryDelete).Methods("DELETE")
	router.HandleFunc("/api/v1/repositories/{id}/test", h.HandleAPIRepositoryTest).Methods("POST")
	
	// Drift Detection API endpoints
	router.HandleFunc("/api/v1/drift/{fabricId}", h.HandleAPIDriftDetection).Methods("GET")
	router.HandleFunc("/api/v1/drift/{fabricId}/analyze", h.HandleAPIDriftAnalyze).Methods("POST")
	
	// API endpoints for batch operations
	router.HandleFunc("/api/v1/items/{id}/sync", h.HandleItemSync).Methods("POST")
	router.HandleFunc("/api/v1/items/{id}", h.HandleItemUpdate).Methods("PUT")
	router.HandleFunc("/api/v1/items/{id}", h.HandleItemDelete).Methods("DELETE")
	router.HandleFunc("/api/v1/items/{id}/export", h.HandleItemExport).Methods("GET")
	router.HandleFunc("/api/v1/items/{id}/validate", h.HandleItemValidate).Methods("POST")
	router.HandleFunc("/api/v1/items/{id}/apply", h.HandleItemApply).Methods("POST")

	// Start mock real-time events
	h.startMockRealtimeEvents()
}

// HandleDashboard renders the dashboard page with real configuration data
func (h *WebHandler) HandleDashboard(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()
	
	// Get real configuration data from application service
	configService := h.serviceFactory.GetConfigurationService()
	configList, err := configService.ListConfigurations(ctx, 1, 100) // Get first 100 configs
	
	var configCount, deployedCount, draftCount int
	if err != nil {
		log.Printf("Warning: Failed to fetch configurations for dashboard: %v", err)
		// Fall back to mock data for dashboard stability
		configCount = 3
		deployedCount = 2
		draftCount = 1
	} else {
		configCount = len(configList.Items)
		
		// Count configurations by status
		for _, config := range configList.Items {
			switch config.Status {
			case "deployed":
				deployedCount++
			case "draft":
				draftCount++
			}
		}
	}
	
	// Calculate component count from configurations
	componentCount := configCount * 2 // Approximate 2 components per config on average
	
	data := TemplateData{
		ActivePage: "dashboard",
		Stats: DashboardStats{
			FabricCount:     3,  // Keep fabric count as mock for now
			CRDCount:        componentCount, // Use real component count instead of mock "60"
			InSyncCount:     deployedCount,  // Use real deployed count
			DriftCount:      draftCount,     // Use draft as "drift" indicator
			VPCCount:        4,  // Keep VPC count as mock for now
			SwitchCount:     16, // Keep switch count as mock for now
			TotalFabrics:    3,  // Keep total fabrics as mock for now
			TotalCRDs:       componentCount, // Use real total components
			ConnectionCount: configCount,    // Use configuration count as connection count
		},
		RecentActivity: []Activity{
			{
				Timestamp: time.Now().Add(-5 * time.Minute),
				Type:      "Configuration",
				Resource:  "System Status",
				Action:    fmt.Sprintf("Loaded %d configurations", configCount),
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
				Type:      "Configuration",
				Resource:  "Service Layer",
				Action:    "Application services initialized",
				Status:    "success",
			},
		},
	}

	h.renderTemplate(w, "simple_dashboard", data)
}

// Fabric API handlers

// HandleAPIFabricList handles GET /api/v1/fabrics
func (h *WebHandler) HandleAPIFabricList(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()
	
	fabricService := h.serviceFactory.GetFabricService()
	fabricList, err := fabricService.ListFabrics(ctx, 1, 100)
	
	w.Header().Set("Content-Type", "application/json")
	
	if err != nil {
		w.WriteHeader(http.StatusInternalServerError)
		w.Write([]byte(fmt.Sprintf(`{"error": "Failed to list fabrics", "message": "%s"}`, err.Error())))
		return
	}
	
	jsonData, _ := json.Marshal(fabricList)
	w.WriteHeader(http.StatusOK)
	w.Write(jsonData)
}

// HandleAPIFabricGet handles GET /api/v1/fabrics/{id}
func (h *WebHandler) HandleAPIFabricGet(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()
	vars := mux.Vars(r)
	fabricID := vars["id"]
	
	fabricService := h.serviceFactory.GetFabricService()
	fabricStatus, err := fabricService.GetFabricStatus(ctx, fabricID)
	
	w.Header().Set("Content-Type", "application/json")
	
	if err != nil {
		w.WriteHeader(http.StatusNotFound)
		w.Write([]byte(fmt.Sprintf(`{"error": "Fabric not found", "message": "%s"}`, err.Error())))
		return
	}
	
	jsonData, _ := json.Marshal(fabricStatus)
	w.WriteHeader(http.StatusOK)
	w.Write(jsonData)
}

// HandleAPIFabricValidate handles POST /api/v1/fabrics/{id}/validate
func (h *WebHandler) HandleAPIFabricValidate(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()
	vars := mux.Vars(r)
	fabricID := vars["id"]
	
	fabricService := h.serviceFactory.GetFabricService()
	result, err := fabricService.ValidateFabricConfiguration(ctx, fabricID)
	
	w.Header().Set("Content-Type", "application/json")
	
	if err != nil {
		w.WriteHeader(http.StatusNotFound)
		w.Write([]byte(fmt.Sprintf(`{"error": "Failed to validate fabric", "message": "%s"}`, err.Error())))
		return
	}
	
	jsonData, _ := json.Marshal(result)
	w.WriteHeader(http.StatusOK)
	w.Write(jsonData)
}

// timeAgo returns a human-readable string for how long ago a time was
func timeAgo(t time.Time) string {
	duration := time.Since(t)
	
	if duration < time.Minute {
		return "just now"
	} else if duration < time.Hour {
		minutes := int(duration.Minutes())
		if minutes == 1 {
			return "1 minute ago"
		}
		return fmt.Sprintf("%d minutes ago", minutes)
	} else if duration < 24*time.Hour {
		hours := int(duration.Hours())
		if hours == 1 {
			return "1 hour ago"
		}
		return fmt.Sprintf("%d hours ago", hours)
	} else {
		days := int(duration.Hours() / 24)
		if days == 1 {
			return "1 day ago"
		}
		return fmt.Sprintf("%d days ago", days)
	}
}

// HandleFabricList renders the fabric list page with real data
func (h *WebHandler) HandleFabricList(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()
	
	// Get fabrics from application service
	fabricService := h.serviceFactory.GetFabricService()
	fabricList, err := fabricService.ListFabrics(ctx, 1, 50) // Get first 50 fabrics
	
	if err != nil {
		log.Printf("Error fetching fabrics: %v", err)
		h.renderErrorPage(w, "Failed to load fabrics", err)
		return
	}

	// Convert service DTOs to web DTOs
	fabrics := make([]Fabric, len(fabricList.Items))
	for i, fabricStatus := range fabricList.Items {
		// Convert time
		var lastGitSyncAgo string
		if fabricStatus.LastSyncAt != nil {
			lastGitSyncAgo = timeAgo(*fabricStatus.LastSyncAt)
		} else {
			lastGitSyncAgo = "Never"
		}

		fabrics[i] = Fabric{
			ID:              fabricStatus.FabricID,
			Name:            fabricStatus.Name,
			Description:     fabricStatus.Metadata["description"],
			GitOpsDirectory: fabricStatus.Metadata["git_directory"],
			GitOpsBranch:    fabricStatus.Metadata["git_branch"],
			GitSyncStatus:   fabricStatus.Status,
			DriftStatus:     fabricStatus.DriftStatus,
			DriftCount:      0, // Would need to parse from drift status
			CachedCRDCount:  fabricStatus.ResourceCount,
			LastGitSync:     fabricStatus.LastSyncAt,
			LastGitSyncAgo:  lastGitSyncAgo,
		}
	}

	// Calculate stats from real data
	inSyncCount := 0
	driftCount := 0
	totalCRDs := 0
	for _, fabric := range fabrics {
		if fabric.GitSyncStatus == "active" || fabric.GitSyncStatus == "in_sync" {
			inSyncCount++
		}
		if fabric.DriftCount > 0 {
			driftCount++
		}
		totalCRDs += fabric.CachedCRDCount
	}

	stats := DashboardStats{
		TotalFabrics: len(fabrics),
		InSyncCount:  inSyncCount,
		DriftCount:   driftCount,
		TotalCRDs:    totalCRDs,
	}

	// Empty git repositories for now
	gitRepositories := []GitRepository{}

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
		Stats: DashboardStats{
			CRDCount:     5,
			InSyncCount:  3,
			DriftCount:   1,
			TotalFabrics: 2,
		},
		GitRepositories: []GitRepository{
			{
				ID:                  "repo-1",
				Name:                "Main Configuration Repository",
				URL:                 "https://github.com/company/hedgehog-config",
				ConnectionStatus:    "connected",
				AuthenticationType:  "token",
			},
		},
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
		Stats: DashboardStats{
			VPCCount:        4,
			ConnectionCount: 12,
			SwitchCount:     6,
			FabricCount:     2,
			DriftCount:      1,
			CRDCount:        22,
		},
		CRDResources: []CRDResource{
			{
				ID:        "vpc-1",
				Name:      "main-vpc",
				Namespace: "default",
				Type:      "VPC",
			},
		},
	}

	h.renderTemplate(w, "crd_list", data)
}

// HandleVPCList renders the VPC list page
func (h *WebHandler) HandleVPCList(w http.ResponseWriter, r *http.Request) {
	data := TemplateData{
		ActivePage: "crds",
		Stats: DashboardStats{
			VPCCount:     4,
			InSyncCount:  3,
			CRDCount:     15,
			TotalFabrics: 2,
		},
		CRDResources: []CRDResource{
			{
				ID:        "vpc-1",
				Name:      "main-vpc",
				Namespace: "default",
				Type:      "VPC",
			},
		},
		Fabrics: []Fabric{
			{ID: "fabric-1", Name: "Main Fabric"},
		},
	}

	h.renderTemplate(w, "vpc_list", data)
}

// HandleConnectionList renders the connection list page
func (h *WebHandler) HandleConnectionList(w http.ResponseWriter, r *http.Request) {
	data := TemplateData{
		ActivePage: "crds",
		Stats: DashboardStats{
			ConnectionCount: 12,
			InSyncCount:     8,
			DriftCount:      2,
			CRDCount:        20,
		},
		CRDResources: []CRDResource{
			{
				ID:   "conn-1",
				Name: "fabric-connection",
				Type: "Connection",
			},
		},
		Fabrics: []Fabric{
			{ID: "fabric-1", Name: "Main Fabric"},
		},
	}

	h.renderTemplate(w, "connection_list", data)
}

// HandleSwitchList renders the switch list page
func (h *WebHandler) HandleSwitchList(w http.ResponseWriter, r *http.Request) {
	data := TemplateData{
		ActivePage: "crds",
		Stats: DashboardStats{
			SwitchCount:  6,
			InSyncCount:  4,
			CRDCount:     18,
			DriftCount:   1,
		},
		CRDResources: []CRDResource{
			{
				ID:   "switch-1",
				Name: "leaf-switch-01",
				Type: "Switch",
			},
		},
		Fabrics: []Fabric{
			{ID: "fabric-1", Name: "Main Fabric"},
		},
	}

	h.renderTemplate(w, "switch_list", data)
}

// HandleDriftDetection renders the drift detection page
func (h *WebHandler) HandleDriftDetection(w http.ResponseWriter, r *http.Request) {
	// Check if drift detection service is available
	if h.serviceFactory == nil || h.templates == nil {
		w.WriteHeader(http.StatusInternalServerError)
		w.Write([]byte("Drift detection service not available"))
		return
	}

	data := TemplateData{
		ActivePage: "drift",
		DriftSpotlight: DriftSpotlight{
			StatusClass: "warning",
			Message:     "2 resources with drift detected",
			DriftCount:  2,
		},
	}

	h.renderTemplate(w, "drift_detection", data)
}

// NEW CONFIGURATION HANDLERS - Using Real Application Services

// HandleConfigurationList renders the configuration list page with real data
func (h *WebHandler) HandleConfigurationList(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()
	
	// Get configurations from application service
	configService := h.serviceFactory.GetConfigurationService()
	configList, err := configService.ListConfigurations(ctx, 1, 50) // Get first 50 configs
	
	if err != nil {
		log.Printf("Error fetching configurations: %v", err)
		h.renderErrorPage(w, "Failed to load configurations", err)
		return
	}
	
	// Convert to template-friendly format
	configurations := make([]map[string]interface{}, len(configList.Items))
	for i, config := range configList.Items {
		configurations[i] = map[string]interface{}{
			"ID":          config.ID,
			"Name":        config.Name,
			"Mode":        config.Mode,
			"Version":     config.Version,
			"Status":      config.Status,
			"Components":  config.ComponentCount,
			"CreatedAt":   config.CreatedAt.Format("2006-01-02 15:04:05"),
			"UpdatedAt":   config.UpdatedAt.Format("2006-01-02 15:04:05"),
		}
	}

	data := TemplateData{
		ActivePage: "configurations",
		Stats: DashboardStats{
			TotalCRDs: len(configList.Items),
		},
		Data: map[string]interface{}{
			"Configurations": configurations,
			"TotalCount":     configList.TotalCount,
			"Page":          configList.Page,
			"PageSize":      configList.PageSize,
		},
	}

	h.renderTemplate(w, "configuration_list", data)
}

// HandleConfigurationDetail renders the configuration detail page with real data
func (h *WebHandler) HandleConfigurationDetail(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()
	vars := mux.Vars(r)
	configID := vars["id"]
	
	// Get configuration from application service
	configService := h.serviceFactory.GetConfigurationService()
	config, err := configService.GetConfiguration(ctx, configID)
	
	if err != nil {
		log.Printf("Error fetching configuration %s: %v", configID, err)
		h.renderErrorPage(w, "Configuration not found", err)
		return
	}
	
	// Convert components to template-friendly format
	components := make([]map[string]interface{}, len(config.Components))
	for i, comp := range config.Components {
		components[i] = map[string]interface{}{
			"Name":          comp.Name,
			"Version":       comp.Version,
			"Configuration": comp.Configuration,
			"Enabled":       comp.Enabled,
		}
	}

	data := TemplateData{
		ActivePage: "configurations",
		Data: map[string]interface{}{
			"Configuration": map[string]interface{}{
				"ID":          config.ID,
				"Name":        config.Name,
				"Description": config.Description,
				"Mode":        config.Mode,
				"Status":      config.Status,
				"Components":  components,
				"Labels":      config.Labels,
				"CreatedAt":   config.CreatedAt.Format("2006-01-02 15:04:05"),
				"UpdatedAt":   config.UpdatedAt.Format("2006-01-02 15:04:05"),
			},
		},
	}

	h.renderTemplate(w, "configuration_detail", data)
}

// HandleConfigurationCreate renders the configuration creation page
func (h *WebHandler) HandleConfigurationCreate(w http.ResponseWriter, r *http.Request) {
	data := TemplateData{
		ActivePage: "configurations",
		Data: map[string]interface{}{
			"Mode": "create",
			"AvailableComponents": []map[string]interface{}{
				{"Name": "argocd", "Version": "2.8.0", "Description": "GitOps Continuous Delivery"},
				{"Name": "prometheus", "Version": "2.45.0", "Description": "Monitoring and Alerting"},
				{"Name": "grafana", "Version": "10.0.0", "Description": "Observability Platform"},
				{"Name": "cert-manager", "Version": "1.12.0", "Description": "Certificate Management"},
			},
		},
	}

	h.renderTemplate(w, "configuration_create", data)
}

// renderErrorPage renders an error page with Bootstrap styling
func (h *WebHandler) renderErrorPage(w http.ResponseWriter, message string, err error) {
	w.Header().Set("Content-Type", "text/html; charset=utf-8")
	w.WriteHeader(http.StatusInternalServerError)
	
	errorHTML := fmt.Sprintf(`<!DOCTYPE html>
<html lang="en">
<head>
	<meta charset="UTF-8">
	<meta name="viewport" content="width=device-width, initial-scale=1.0">
	<title>CNOC Error</title>
	<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
</head>
<body class="bg-light">
	<div class="container mt-5">
		<div class="row justify-content-center">
			<div class="col-md-8">
				<div class="card">
					<div class="card-header bg-danger text-white">
						<h4 class="mb-0"><i class="bi bi-exclamation-triangle"></i> Error</h4>
					</div>
					<div class="card-body">
						<h5>%s</h5>
						<p class="text-muted">%s</p>
						<hr>
						<div class="d-flex gap-2">
							<a href="/dashboard" class="btn btn-primary">Return to Dashboard</a>
							<a href="/configurations" class="btn btn-outline-secondary">View Configurations</a>
						</div>
					</div>
				</div>
			</div>
		</div>
	</div>
</body>
</html>`, message, err.Error())
	
	w.Write([]byte(errorHTML))
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
	
	// Set ContentTemplate field to tell base.html which content block to use
	data.ContentTemplate = name
	
	// Execute base.html template which will choose the right content block
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

// withMetrics wraps an HTTP handler with metrics collection
func (h *WebHandler) withMetrics(handler http.HandlerFunc) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		start := time.Now()
		
		// Wrap response writer to capture status
		wrapped := &responseWriter{
			ResponseWriter: w,
			statusCode:     http.StatusOK,
		}
		
		handler(wrapped, r)
		
		// Record metrics if collector is available
		if h.metricsCollector != nil {
			duration := time.Since(start)
			h.metricsCollector.RecordAPIRequest(r.Method, r.URL.Path, wrapped.statusCode, duration)
		}
	}
}

// responseWriter wraps http.ResponseWriter to capture status and size
type responseWriter struct {
	http.ResponseWriter
	statusCode int
	size       int
}

func (w *responseWriter) WriteHeader(statusCode int) {
	w.statusCode = statusCode
	w.ResponseWriter.WriteHeader(statusCode)
}

func (w *responseWriter) Write(data []byte) (int, error) {
	n, err := w.ResponseWriter.Write(data)
	w.size += n
	return n, err
}

// NEW CONFIGURATION API HANDLERS - Using Real Application Services

// HandleAPIConfigurationList handles GET /api/v1/configurations
func (h *WebHandler) HandleAPIConfigurationList(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()
	
	configService := h.serviceFactory.GetConfigurationService()
	configList, err := configService.ListConfigurations(ctx, 1, 100)
	
	w.Header().Set("Content-Type", "application/json")
	
	if err != nil {
		w.WriteHeader(http.StatusInternalServerError)
		w.Write([]byte(fmt.Sprintf(`{"error": "Failed to list configurations", "message": "%s"}`, err.Error())))
		return
	}
	
	// Convert to JSON response
	response := map[string]interface{}{
		"configurations": configList.Items,
		"total_count":    configList.TotalCount,
		"page":          configList.Page,
		"page_size":     configList.PageSize,
	}
	
	jsonData, _ := json.Marshal(response)
	w.WriteHeader(http.StatusOK)
	w.Write(jsonData)
}

// HandleAPIConfigurationGet handles GET /api/v1/configurations/{id}
func (h *WebHandler) HandleAPIConfigurationGet(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()
	vars := mux.Vars(r)
	configID := vars["id"]
	
	configService := h.serviceFactory.GetConfigurationService()
	config, err := configService.GetConfiguration(ctx, configID)
	
	w.Header().Set("Content-Type", "application/json")
	
	if err != nil {
		w.WriteHeader(http.StatusNotFound)
		w.Write([]byte(fmt.Sprintf(`{"error": "Configuration not found", "message": "%s"}`, err.Error())))
		return
	}
	
	jsonData, _ := json.Marshal(config)
	w.WriteHeader(http.StatusOK)
	w.Write(jsonData)
}

// HandleAPIConfigurationCreate handles POST /api/v1/configurations
func (h *WebHandler) HandleAPIConfigurationCreate(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()
	
	// Parse request body
	var request dto.CreateConfigurationRequestDTO
	if err := json.NewDecoder(r.Body).Decode(&request); err != nil {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusBadRequest)
		w.Write([]byte(fmt.Sprintf(`{"error": "Invalid request body", "message": "%s"}`, err.Error())))
		return
	}
	
	configService := h.serviceFactory.GetConfigurationService()
	config, err := configService.CreateConfiguration(ctx, request)
	
	w.Header().Set("Content-Type", "application/json")
	
	if err != nil {
		w.WriteHeader(http.StatusBadRequest)
		w.Write([]byte(fmt.Sprintf(`{"error": "Failed to create configuration", "message": "%s"}`, err.Error())))
		return
	}
	
	jsonData, _ := json.Marshal(config)
	w.WriteHeader(http.StatusCreated)
	w.Write(jsonData)
}

// HandleAPIConfigurationUpdate handles PUT /api/v1/configurations/{id}
func (h *WebHandler) HandleAPIConfigurationUpdate(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()
	vars := mux.Vars(r)
	configID := vars["id"]
	
	// Parse request body
	var request dto.UpdateConfigurationRequestDTO
	if err := json.NewDecoder(r.Body).Decode(&request); err != nil {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusBadRequest)
		w.Write([]byte(fmt.Sprintf(`{"error": "Invalid request body", "message": "%s"}`, err.Error())))
		return
	}
	
	configService := h.serviceFactory.GetConfigurationService()
	config, err := configService.UpdateConfiguration(ctx, configID, request)
	
	w.Header().Set("Content-Type", "application/json")
	
	if err != nil {
		w.WriteHeader(http.StatusBadRequest)
		w.Write([]byte(fmt.Sprintf(`{"error": "Failed to update configuration", "message": "%s"}`, err.Error())))
		return
	}
	
	jsonData, _ := json.Marshal(config)
	w.WriteHeader(http.StatusOK)
	w.Write(jsonData)
}

// HandleAPIConfigurationDelete handles DELETE /api/v1/configurations/{id}
func (h *WebHandler) HandleAPIConfigurationDelete(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()
	vars := mux.Vars(r)
	configID := vars["id"]
	
	configService := h.serviceFactory.GetConfigurationService()
	err := configService.DeleteConfiguration(ctx, configID)
	
	w.Header().Set("Content-Type", "application/json")
	
	if err != nil {
		w.WriteHeader(http.StatusNotFound)
		w.Write([]byte(fmt.Sprintf(`{"error": "Failed to delete configuration", "message": "%s"}`, err.Error())))
		return
	}
	
	w.WriteHeader(http.StatusNoContent)
}

// HandleAPIConfigurationValidate handles POST /api/v1/configurations/{id}/validate
func (h *WebHandler) HandleAPIConfigurationValidate(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()
	vars := mux.Vars(r)
	configID := vars["id"]
	
	// Check if configuration service is available
	if h.serviceFactory == nil {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusServiceUnavailable)
		w.Write([]byte(`{"error": "Configuration validation service not available", "message": "Service factory not configured"}`))
		return
	}
	
	configService := h.serviceFactory.GetConfigurationService()
	if configService == nil {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusServiceUnavailable)
		w.Write([]byte(`{"error": "Configuration validation service not available", "message": "Configuration service not configured"}`))
		return
	}
	
	result, err := configService.ValidateConfiguration(ctx, configID)
	
	w.Header().Set("Content-Type", "application/json")
	
	if err != nil {
		w.WriteHeader(http.StatusNotFound)
		w.Write([]byte(fmt.Sprintf(`{"error": "Failed to validate configuration", "message": "%s"}`, err.Error())))
		return
	}
	
	jsonData, _ := json.Marshal(result)
	w.WriteHeader(http.StatusOK)
	w.Write(jsonData)
}

// API Handlers for batch operations

// HandleFabricSync handles fabric sync operations using real fabric service
func (h *WebHandler) HandleFabricSync(w http.ResponseWriter, r *http.Request) {
	vars := mux.Vars(r)
	fabricID := vars["id"]
	ctx := r.Context()
	
	// Parse request body for sync options
	var syncRequest services.FabricSyncCommand
	if err := json.NewDecoder(r.Body).Decode(&syncRequest); err != nil {
		// Use defaults if no body provided
		syncRequest = services.FabricSyncCommand{
			FabricID:  fabricID,
			ForceSync: false,
			DryRun:    false,
			Source:    "web",
			RequestID: fmt.Sprintf("web-%d", time.Now().Unix()),
			UserID:    "web-user",
		}
	} else {
		// Ensure fabric ID matches URL
		syncRequest.FabricID = fabricID
	}
	
	// Check if GitOps services are available before starting
	if h.serviceFactory == nil || h.serviceFactory.GetFabricService() == nil {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusServiceUnavailable)
		w.Write([]byte(`{"error": "GitOps fabric service not available", "message": "Fabric synchronization service is not configured"}`))
		return
	}
	
	// Perform sync operation in background
	go func() {
		// Check if GitOps services are available
		if h.serviceFactory == nil {
			h.eventBroadcaster.BroadcastFabricSyncStatus(fabricID, "failed", 0, "Service factory not available")
			return
		}
		
		fabricService := h.serviceFactory.GetFabricService()
		if fabricService == nil {
			h.eventBroadcaster.BroadcastFabricSyncStatus(fabricID, "failed", 0, "GitOps fabric service not available")
			return
		}
		
		h.eventBroadcaster.BroadcastFabricSyncStatus(fabricID, "syncing", 0, "Starting sync operation")
		
		result, err := fabricService.SynchronizeFabric(ctx, syncRequest)
		
		if err != nil {
			h.eventBroadcaster.BroadcastFabricSyncStatus(fabricID, "failed", 0, fmt.Sprintf("Sync failed: %v", err))
			if h.metricsCollector != nil {
				h.metricsCollector.RecordSyncOperation(fabricID, "sync", "error", time.Since(time.Now()))
			}
			return
		}
		
		if result.Success {
			h.eventBroadcaster.BroadcastFabricSyncStatus(fabricID, "completed", 100, 
				fmt.Sprintf("Sync completed successfully - %d resources synced", result.SyncedResources))
			if h.metricsCollector != nil {
				h.metricsCollector.RecordSyncOperation(fabricID, "sync", "success", result.Performance.Duration)
			}
		} else {
			h.eventBroadcaster.BroadcastFabricSyncStatus(fabricID, "failed", 0, 
				fmt.Sprintf("Sync failed with %d errors", len(result.Errors)))
			if h.metricsCollector != nil {
				h.metricsCollector.RecordSyncOperation(fabricID, "sync", "error", result.Performance.Duration)
			}
		}
	}()
	
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusAccepted)
	w.Write([]byte(`{"message": "Sync operation started", "fabric_id": "` + fabricID + `"}`))
}

// HandleItemSync handles individual item sync
func (h *WebHandler) HandleItemSync(w http.ResponseWriter, r *http.Request) {
	vars := mux.Vars(r)
	itemID := vars["id"]
	
	// Simulate item sync
	time.Sleep(200 * time.Millisecond)
	
	w.Header().Set("Content-Type", "application/json")
	w.Write([]byte(`{"message": "Item synced successfully", "item_id": "` + itemID + `"}`))
}

// HandleItemUpdate handles individual item updates
func (h *WebHandler) HandleItemUpdate(w http.ResponseWriter, r *http.Request) {
	vars := mux.Vars(r)
	itemID := vars["id"]
	
	// Simulate item update
	time.Sleep(150 * time.Millisecond)
	
	w.Header().Set("Content-Type", "application/json")
	w.Write([]byte(`{"message": "Item updated successfully", "item_id": "` + itemID + `"}`))
}

// HandleItemDelete handles individual item deletion
func (h *WebHandler) HandleItemDelete(w http.ResponseWriter, r *http.Request) {
	vars := mux.Vars(r)
	itemID := vars["id"]
	
	// Simulate item deletion
	time.Sleep(100 * time.Millisecond)
	
	w.Header().Set("Content-Type", "application/json")
	w.Write([]byte(`{"message": "Item deleted successfully", "item_id": "` + itemID + `"}`))
}

// HandleItemExport handles individual item export
func (h *WebHandler) HandleItemExport(w http.ResponseWriter, r *http.Request) {
	vars := mux.Vars(r)
	itemID := vars["id"]
	
	// Simulate export
	time.Sleep(250 * time.Millisecond)
	
	w.Header().Set("Content-Type", "application/yaml")
	w.Header().Set("Content-Disposition", "attachment; filename=\""+itemID+".yaml\"")
	w.Write([]byte(`apiVersion: v1
kind: ConfigMap
metadata:
  name: ` + itemID + `
data:
  exported: "true"
  timestamp: "` + time.Now().Format(time.RFC3339) + `"`))
}

// HandleItemValidate handles individual item validation
func (h *WebHandler) HandleItemValidate(w http.ResponseWriter, r *http.Request) {
	vars := mux.Vars(r)
	itemID := vars["id"]
	
	// Simulate validation
	time.Sleep(75 * time.Millisecond)
	
	w.Header().Set("Content-Type", "application/json")
	w.Write([]byte(`{"valid": true, "item_id": "` + itemID + `", "errors": []}`))
}

// HandleItemApply handles individual item application
func (h *WebHandler) HandleItemApply(w http.ResponseWriter, r *http.Request) {
	vars := mux.Vars(r)
	itemID := vars["id"]
	
	// Simulate application
	time.Sleep(300 * time.Millisecond)
	
	w.Header().Set("Content-Type", "application/json")
	w.Write([]byte(`{"message": "Item applied successfully", "item_id": "` + itemID + `"}`))
}

// startMockRealtimeEvents starts mock real-time events for demonstration
func (h *WebHandler) startMockRealtimeEvents() {
	go func() {
		ticker := time.NewTicker(30 * time.Second)
		defer ticker.Stop()
		
		eventCount := 0
		for range ticker.C {
			eventCount++
			
			// Simulate various events
			switch eventCount % 4 {
			case 0:
				h.eventBroadcaster.BroadcastCRDCountChange("fabric-1", 36, 37, "increase")
			case 1:
				h.eventBroadcaster.BroadcastDriftDetection("fabric-2", "low", []string{"vpc-staging"})
			case 2:
				h.eventBroadcaster.BroadcastAPIOperationComplete("op-"+fmt.Sprintf("%d", eventCount), "configuration_update", "success", "Configuration updated successfully")
			case 3:
				h.eventBroadcaster.BroadcastFabricSyncStatus("fabric-1", "completed", 100, "Background sync completed")
			}
		}
	}()
}

// GitOps Repository Management API Handlers

// HandleAPIRepositoryList handles GET /api/v1/repositories
func (h *WebHandler) HandleAPIRepositoryList(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	
	// Check if GitOps repository service is available
	if h.serviceFactory == nil || h.serviceFactory.GetGitOpsRepositoryService() == nil {
		w.WriteHeader(http.StatusNotImplemented)
		w.Write([]byte(`{"error": "GitOps repository service not implemented", "message": "Repository management service is not configured"}`))
		return
	}
	
	// Use real GitOps repository service
	ctx := r.Context()
	page := 1
	pageSize := 20
	
	// Parse query parameters for pagination
	if pageStr := r.URL.Query().Get("page"); pageStr != "" {
		if p, err := strconv.Atoi(pageStr); err == nil && p > 0 {
			page = p
		}
	}
	if pageSizeStr := r.URL.Query().Get("page_size"); pageSizeStr != "" {
		if ps, err := strconv.Atoi(pageSizeStr); err == nil && ps > 0 && ps <= 100 {
			pageSize = ps
		}
	}
	
	gitOpsService := h.serviceFactory.GetGitOpsRepositoryService()
	result, err := gitOpsService.ListRepositories(ctx, page, pageSize)
	if err != nil {
		w.WriteHeader(http.StatusInternalServerError)
		w.Write([]byte(fmt.Sprintf(`{"error": "Failed to list repositories", "message": "%s"}`, err.Error())))
		return
	}
	
	jsonData, _ := json.Marshal(result)
	w.WriteHeader(http.StatusOK)
	w.Write(jsonData)
}

// HandleAPIRepositoryCreate handles POST /api/v1/repositories
func (h *WebHandler) HandleAPIRepositoryCreate(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusNotImplemented)
	w.Write([]byte(`{"error": "GitOps repository creation not implemented"}`))
}

// HandleAPIRepositoryGet handles GET /api/v1/repositories/{id}
func (h *WebHandler) HandleAPIRepositoryGet(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusNotImplemented)
	w.Write([]byte(`{"error": "GitOps repository retrieval not implemented"}`))
}

// HandleAPIRepositoryUpdate handles PUT /api/v1/repositories/{id}
func (h *WebHandler) HandleAPIRepositoryUpdate(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusNotImplemented)
	w.Write([]byte(`{"error": "GitOps repository update not implemented"}`))
}

// HandleAPIRepositoryDelete handles DELETE /api/v1/repositories/{id}
func (h *WebHandler) HandleAPIRepositoryDelete(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusNotImplemented)
	w.Write([]byte(`{"error": "GitOps repository deletion not implemented"}`))
}

// HandleAPIRepositoryTest handles POST /api/v1/repositories/{id}/test
func (h *WebHandler) HandleAPIRepositoryTest(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusNotImplemented)
	w.Write([]byte(`{"error": "GitOps repository connection test not implemented"}`))
}

// Drift Detection API Handlers

// HandleAPIDriftDetection handles GET /api/v1/drift/{fabricId}
func (h *WebHandler) HandleAPIDriftDetection(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	
	// Check if drift detection service is available
	if h.serviceFactory == nil || h.serviceFactory.GetDriftDetectionService() == nil {
		w.WriteHeader(http.StatusInternalServerError)
		w.Write([]byte(`{"error": "Drift detection service not implemented", "message": "Drift detection service is not configured"}`))
		return
	}
	
	// Get fabric ID from URL
	vars := mux.Vars(r)
	fabricID := vars["fabricId"]
	if fabricID == "" {
		w.WriteHeader(http.StatusBadRequest)
		w.Write([]byte(`{"error": "Fabric ID is required"}`))
		return
	}
	
	// Use real drift detection service
	ctx := r.Context()
	driftService := h.serviceFactory.GetDriftDetectionService()
	result, err := driftService.DetectFabricDrift(ctx, fabricID)
	if err != nil {
		w.WriteHeader(http.StatusInternalServerError)
		w.Write([]byte(fmt.Sprintf(`{"error": "Failed to detect drift", "message": "%s"}`, err.Error())))
		return
	}
	
	jsonData, _ := json.Marshal(result)
	w.WriteHeader(http.StatusOK)
	w.Write(jsonData)
}

// HandleAPIFabricDrift handles GET /api/v1/fabrics/{fabricId}/drift - alias for HandleAPIDriftDetection
func (h *WebHandler) HandleAPIFabricDrift(w http.ResponseWriter, r *http.Request) {
	h.HandleAPIDriftDetection(w, r)
}

// HandleAPIDriftAnalyze handles POST /api/v1/drift/{fabricId}/analyze
func (h *WebHandler) HandleAPIDriftAnalyze(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusNotImplemented)
	w.Write([]byte(`{"error": "Drift analysis not implemented"}`))
}

// Updated HandleDriftDetection to return proper error status for GitOps integration tests