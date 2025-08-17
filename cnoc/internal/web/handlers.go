package web

import (
	"embed"
	"html/template"
	"net/http"
	"path/filepath"
	"time"

	"github.com/gorilla/mux"
)

// TemplateData holds common data for all templates
type TemplateData struct {
	ActivePage     string
	Stats          DashboardStats
	RecentActivity []Activity
	Data           interface{}
}

// DashboardStats holds dashboard statistics
type DashboardStats struct {
	FabricCount int
	CRDCount    int
	InSyncCount int
	DriftCount  int
	VPCCount    int
	SwitchCount int
}

// Activity represents a recent activity item
type Activity struct {
	Timestamp time.Time
	Type      string
	Resource  string
	Action    string
	Status    string
}

// WebHandler handles web UI requests
type WebHandler struct {
	templates *template.Template
	// In production, we'd inject services here
}

// NewWebHandler creates a new web handler
func NewWebHandler() (*WebHandler, error) {
	// Parse templates
	templates, err := template.ParseGlob("web/templates/*.html")
	if err != nil {
		return nil, err
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
			FabricCount: 3,
			CRDCount:    36,
			InSyncCount: 30,
			DriftCount:  6,
			VPCCount:    2,
			SwitchCount: 8,
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

	h.renderTemplate(w, "dashboard", data)
}

// HandleFabricList renders the fabric list page
func (h *WebHandler) HandleFabricList(w http.ResponseWriter, r *http.Request) {
	data := TemplateData{
		ActivePage: "fabrics",
		// In production, fetch from service
	}

	h.renderTemplate(w, "fabric_list", data)
}

// HandleFabricDetail renders the fabric detail page
func (h *WebHandler) HandleFabricDetail(w http.ResponseWriter, r *http.Request) {
	vars := mux.Vars(r)
	fabricID := vars["id"]

	data := TemplateData{
		ActivePage: "fabrics",
		Data:       fabricID,
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
	// First try to render the specific template
	err := h.templates.ExecuteTemplate(w, name+".html", data)
	if err != nil {
		// If template doesn't exist, render the base template with dashboard
		err = h.templates.ExecuteTemplate(w, "dashboard.html", data)
		if err != nil {
			// Fall back to base template
			err = h.templates.ExecuteTemplate(w, "base.html", data)
			if err != nil {
				http.Error(w, "Error rendering template: "+err.Error(), http.StatusInternalServerError)
			}
		}
	}
}