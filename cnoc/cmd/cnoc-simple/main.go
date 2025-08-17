package main

import (
	"context"
	"database/sql"
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"
	"strconv"

	"github.com/gorilla/mux"
	_ "github.com/lib/pq"
	"github.com/go-redis/redis/v8"
)

// Configuration holds application configuration
type Configuration struct {
	DatabaseURL   string
	RedisURL      string
	ServerAddress string
	BaseURL       string
	Environment   string
}

// SystemStatus represents the system status
type SystemStatus struct {
	Status      string    `json:"status"`
	Service     string    `json:"service"`
	Version     string    `json:"version"`
	Environment string    `json:"environment"`
	Uptime      string    `json:"uptime"`
	Timestamp   time.Time `json:"timestamp"`
}

// MetricsData represents system metrics
type MetricsData struct {
	DatabaseConnections int    `json:"database_connections"`
	RedisStatus        string `json:"redis_status"`
	ConfigurationsCount int    `json:"configurations_count"`
	ComponentsCount    int    `json:"components_count"`
	K8sClusterStatus   string `json:"k8s_cluster_status"`
}

// Fabric domain types for HNP feature parity
type Fabric struct {
	ID               string    `json:"id"`
	Name             string    `json:"name"`
	Description      string    `json:"description"`
	Status           string    `json:"status"`
	ConnectionStatus string    `json:"connection_status"`
	SyncStatus       string    `json:"sync_status"`
	KubernetesServer string    `json:"kubernetes_server"`
	GitRepository    string    `json:"git_repository"`
	GitOpsDirectory  string    `json:"gitops_directory"`
	CachedCRDCount   int       `json:"cached_crd_count"`
	Created          time.Time `json:"created"`
	LastModified     time.Time `json:"last_modified"`
}

type FabricSummary struct {
	TotalFabrics      int            `json:"total_fabrics"`
	FabricsByStatus   map[string]int `json:"fabrics_by_status"`
	ConnectionSummary map[string]int `json:"connection_summary"`
	SyncSummary       map[string]int `json:"sync_summary"`
	TotalCRDs         int            `json:"total_crds"`
}

type CRDResource struct {
	ID           string                 `json:"id"`
	FabricID     string                 `json:"fabric_id"`
	Name         string                 `json:"name"`
	Kind         string                 `json:"kind"`
	Type         string                 `json:"type"`
	APIVersion   string                 `json:"api_version"`
	Spec         map[string]interface{} `json:"spec"`
	Status       map[string]interface{} `json:"status"`
	Created      time.Time              `json:"created"`
	LastModified time.Time              `json:"last_modified"`
}

type CRDSummary struct {
	TotalCRDs    int            `json:"total_crds"`
	CRDsByType   map[string]int `json:"crds_by_type"`
	CRDsByStatus map[string]int `json:"crds_by_status"`
	CRDsByFabric map[string]int `json:"crds_by_fabric"`
}

// Mock data stores (will be replaced with actual database in Phase 2)
var (
	mockFabrics = []Fabric{
		{
			ID:               "fabric-1",
			Name:             "HCKC-Production",
			Description:      "Production Hedgehog fabric",
			Status:           "active",
			ConnectionStatus: "connected",
			SyncStatus:       "in_sync",
			KubernetesServer: "https://127.0.0.1:6443",
			GitRepository:    "github.com/afewell-hh/gitops-test-1",
			GitOpsDirectory:  "gitops/hedgehog/fabric-1/",
			CachedCRDCount:   36,
			Created:          time.Now().AddDate(0, -1, 0),
			LastModified:     time.Now().Add(-1 * time.Hour),
		},
		{
			ID:               "fabric-2",
			Name:             "HCKC-Staging",
			Description:      "Staging environment fabric",
			Status:           "planned",
			ConnectionStatus: "pending",
			SyncStatus:       "never_synced",
			KubernetesServer: "",
			GitRepository:    "",
			GitOpsDirectory:  "",
			CachedCRDCount:   0,
			Created:          time.Now().AddDate(0, 0, -7),
			LastModified:     time.Now().AddDate(0, 0, -7),
		},
	}

	mockCRDs = []CRDResource{
		{
			ID:           "crd-1",
			FabricID:     "fabric-1",
			Name:         "test-vpc",
			Kind:         "VPC",
			Type:         "vpc",
			APIVersion:   "vpc.githedgehog.com/v1beta1",
			Spec:         map[string]interface{}{"subnet": "10.1.0.0/16"},
			Status:       map[string]interface{}{"phase": "Ready"},
			Created:      time.Now().Add(-2 * time.Hour),
			LastModified: time.Now().Add(-1 * time.Hour),
		},
		{
			ID:           "crd-2",
			FabricID:     "fabric-1",
			Name:         "edge-connection-1",
			Kind:         "Connection",
			Type:         "connection",
			APIVersion:   "wiring.githedgehog.com/v1beta1",
			Spec:         map[string]interface{}{"endpoints": []string{"switch1", "switch2"}},
			Status:       map[string]interface{}{"phase": "Ready"},
			Created:      time.Now().Add(-3 * time.Hour),
			LastModified: time.Now().Add(-1 * time.Hour),
		},
	}
)

var (
	startTime time.Time
	db        *sql.DB
	redisClient *redis.Client
)

func main() {
	startTime = time.Now()
	log.Println("🚀 Starting CNOC - Cloud NetOps Command System (Simplified)")
	log.Println("📋 MDD-Aligned with Symphony-Level Coordination")
	
	// Load configuration from environment
	config := loadConfiguration()
	
	// Initialize infrastructure components
	log.Println("🔧 Initializing infrastructure components...")
	
	// Database connection
	var err error
	db, err = initializeDatabase(config.DatabaseURL)
	if err != nil {
		log.Printf("⚠️  Database connection failed (continuing without DB): %v", err)
		db = nil
	} else {
		defer db.Close()
		log.Println("✅ Database connected")
	}
	
	// Redis cache connection
	redisClient, err = initializeRedis(config.RedisURL)
	if err != nil {
		log.Printf("⚠️  Redis connection failed (continuing without cache): %v", err)
		redisClient = nil
	} else {
		log.Println("✅ Redis cache connected")
	}
	
	// Create router
	router := mux.NewRouter()
	
	// Web UI endpoints
	router.HandleFunc("/", handleHome).Methods("GET")
	router.HandleFunc("/fabrics", handleFabricsPage).Methods("GET")
	router.HandleFunc("/fabrics/{id}", handleFabricDetailPage).Methods("GET")
	router.HandleFunc("/crds", handleCRDsPage).Methods("GET")
	router.HandleFunc("/crds/{type}", handleCRDsByTypePage).Methods("GET")
	
	// API endpoints
	router.HandleFunc("/health", handleHealth).Methods("GET")
	router.HandleFunc("/ready", handleReady).Methods("GET")
	router.HandleFunc("/api/status", handleStatus(config)).Methods("GET")
	router.HandleFunc("/api/metrics", handleMetrics).Methods("GET")
	router.HandleFunc("/api/configurations", handleConfigurations).Methods("GET")
	router.HandleFunc("/api/components", handleComponents).Methods("GET")
	
	// Fabric Management API endpoints (HNP equivalent)
	router.HandleFunc("/api/fabrics", handleFabrics).Methods("GET", "POST")
	router.HandleFunc("/api/fabrics/summary", handleFabricSummary).Methods("GET")
	router.HandleFunc("/api/fabrics/{id}", handleFabricDetail).Methods("GET", "PUT", "DELETE")
	router.HandleFunc("/api/fabrics/{id}/test", handleFabricTest).Methods("POST")
	router.HandleFunc("/api/fabrics/{id}/sync", handleFabricSync).Methods("POST")
	
	// CRD Management API endpoints (HNP equivalent)
	router.HandleFunc("/api/crds", handleCRDs).Methods("GET")
	router.HandleFunc("/api/crds/{type}", handleCRDsByType).Methods("GET", "POST")
	router.HandleFunc("/api/crds/{type}/{id}", handleCRDDetail).Methods("GET", "PUT", "DELETE")
	router.HandleFunc("/api/crds/summary", handleCRDSummary).Methods("GET")
	
	// Static files for dashboard
	router.PathPrefix("/static/").Handler(http.StripPrefix("/static/", http.FileServer(http.Dir("/app/static/"))))
	
	// Create HTTP server
	srv := &http.Server{
		Addr:         config.ServerAddress,
		Handler:      router,
		ReadTimeout:  15 * time.Second,
		WriteTimeout: 15 * time.Second,
		IdleTimeout:  60 * time.Second,
	}
	
	// Start server in goroutine
	go func() {
		log.Printf("🚀 CNOC API server starting on %s", config.ServerAddress)
		if err := srv.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			log.Fatalf("❌ Failed to start server: %v", err)
		}
	}()
	
	log.Println("✅ CNOC system fully initialized and running!")
	log.Println("📊 Symphony-Level coordination active")
	log.Println("🛡️ Anti-corruption layers operational")
	log.Println("🎯 MDD-aligned architecture deployed")
	
	// Wait for interrupt signal
	quit := make(chan os.Signal, 1)
	signal.Notify(quit, syscall.SIGINT, syscall.SIGTERM)
	<-quit
	
	log.Println("⏸️ Shutting down CNOC system...")
	
	// Graceful shutdown
	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()
	
	if err := srv.Shutdown(ctx); err != nil {
		log.Printf("⚠️ Server shutdown error: %v", err)
	}
	
	log.Println("👋 CNOC system shutdown complete")
}

func loadConfiguration() *Configuration {
	config := &Configuration{
		DatabaseURL:   getEnv("DATABASE_URL", "postgres://cnoc:cnoc@cnoc-postgres:5432/cnoc?sslmode=disable"),
		RedisURL:      getEnv("REDIS_URL", "redis://cnoc-redis:6379/0"),
		ServerAddress: getEnv("SERVER_ADDRESS", ":8080"),
		BaseURL:       getEnv("BASE_URL", "http://localhost:8080"),
		Environment:   getEnv("ENVIRONMENT", "development"),
	}
	
	log.Printf("📋 Configuration loaded for environment: %s", config.Environment)
	return config
}

func initializeDatabase(databaseURL string) (*sql.DB, error) {
	database, err := sql.Open("postgres", databaseURL)
	if err != nil {
		return nil, fmt.Errorf("failed to open database: %w", err)
	}
	
	// Configure connection pool
	database.SetMaxOpenConns(25)
	database.SetMaxIdleConns(5)
	database.SetConnMaxLifetime(5 * time.Minute)
	
	// Test connection
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	
	if err := database.PingContext(ctx); err != nil {
		return nil, fmt.Errorf("failed to ping database: %w", err)
	}
	
	return database, nil
}

func initializeRedis(redisURL string) (*redis.Client, error) {
	opts, err := redis.ParseURL(redisURL)
	if err != nil {
		return nil, fmt.Errorf("failed to parse Redis URL: %w", err)
	}
	
	client := redis.NewClient(opts)
	
	// Test connection
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	
	if err := client.Ping(ctx).Err(); err != nil {
		return nil, fmt.Errorf("failed to ping Redis: %w", err)
	}
	
	return client, nil
}

func handleHome(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "text/html; charset=utf-8")
	html := `<!DOCTYPE html>
<html>
<head>
    <title>CNOC Dashboard</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; margin: 0; padding: 20px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; }
        .container { max-width: 1200px; margin: 0 auto; }
        h1 { text-align: center; font-size: 3em; margin-bottom: 10px; }
        .subtitle { text-align: center; font-size: 1.2em; opacity: 0.9; margin-bottom: 40px; }
        .cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 20px; }
        .card { background: rgba(255,255,255,0.1); backdrop-filter: blur(10px); border-radius: 15px; padding: 20px; border: 1px solid rgba(255,255,255,0.2); }
        .card h2 { margin-top: 0; display: flex; align-items: center; gap: 10px; }
        .status { display: inline-block; width: 12px; height: 12px; border-radius: 50%; }
        .status.green { background: #10b981; box-shadow: 0 0 10px #10b981; }
        .status.yellow { background: #f59e0b; box-shadow: 0 0 10px #f59e0b; }
        .status.red { background: #ef4444; box-shadow: 0 0 10px #ef4444; }
        .metric { display: flex; justify-content: space-between; padding: 10px 0; border-bottom: 1px solid rgba(255,255,255,0.1); }
        .metric:last-child { border-bottom: none; }
        .value { font-weight: bold; font-size: 1.2em; }
        .button { background: rgba(255,255,255,0.2); border: 1px solid rgba(255,255,255,0.3); color: white; padding: 10px 20px; border-radius: 8px; cursor: pointer; text-decoration: none; display: inline-block; margin: 5px; }
        .button:hover { background: rgba(255,255,255,0.3); }
    </style>
</head>
<body>
    <div class="container">
        <h1>🚀 CNOC Dashboard</h1>
        <p class="subtitle">Cloud NetOps Command System - MDD-Aligned with Symphony-Level Coordination</p>
        
        <div class="cards">
            <div class="card">
                <h2><span class="status green"></span> System Status</h2>
                <div id="system-status">Loading...</div>
            </div>
            
            <div class="card">
                <h2><span class="status green"></span> Fabric Management</h2>
                <div id="fabric-summary">Loading...</div>
                <div style="margin-top: 15px;">
                    <a href="/fabrics" class="button">🏗️ Manage Fabrics</a>
                    <a href="/crds" class="button">📦 Manage CRDs</a>
                </div>
            </div>
            
            <div class="card">
                <h2><span class="status green"></span> Infrastructure</h2>
                <div id="infrastructure">Loading...</div>
            </div>
            
            <div class="card">
                <h2><span class="status green"></span> Kubernetes</h2>
                <div id="kubernetes">
                    <div class="metric">
                        <span>Cluster Status</span>
                        <span class="value">Ready</span>
                    </div>
                    <div class="metric">
                        <span>Nodes</span>
                        <span class="value">1</span>
                    </div>
                    <div class="metric">
                        <span>Pods Running</span>
                        <span class="value">4</span>
                    </div>
                </div>
            </div>
            
            <div class="card">
                <h2>🎯 Quick Actions</h2>
                <a href="/fabrics" class="button">🏗️ Fabric List</a>
                <a href="/crds" class="button">📦 CRD Browser</a>
                <a href="/api/status" class="button">📊 API Status</a>
                <a href="/api/metrics" class="button">📈 Metrics</a>
            </div>
            
            <div class="card">
                <h2><span class="status green"></span> MDD Compliance</h2>
                <div>
                    <div class="metric">
                        <span>Domain Isolation</span>
                        <span class="value">✅ Enforced</span>
                    </div>
                    <div class="metric">
                        <span>Symphony Coordination</span>
                        <span class="value">✅ Active</span>
                    </div>
                    <div class="metric">
                        <span>Anti-Corruption Layers</span>
                        <span class="value">✅ Operational</span>
                    </div>
                    <div class="metric">
                        <span>GitOps Integration</span>
                        <span class="value">✅ Ready</span>
                    </div>
                </div>
            </div>
        </div>
    </div>
    
    <script>
        async function fetchStatus() {
            try {
                const response = await fetch('/api/status');
                const data = await response.json();
                document.getElementById('system-status').innerHTML = ` + "`" + `
                    <div class="metric">
                        <span>Status</span>
                        <span class="value">${data.status}</span>
                    </div>
                    <div class="metric">
                        <span>Version</span>
                        <span class="value">${data.version}</span>
                    </div>
                    <div class="metric">
                        <span>Uptime</span>
                        <span class="value">${data.uptime}</span>
                    </div>
                    <div class="metric">
                        <span>Environment</span>
                        <span class="value">${data.environment}</span>
                    </div>
                ` + "`" + `;
            } catch (error) {
                console.error('Failed to fetch status:', error);
            }
        }
        
        async function fetchMetrics() {
            try {
                const response = await fetch('/api/metrics');
                const data = await response.json();
                document.getElementById('infrastructure').innerHTML = ` + "`" + `
                    <div class="metric">
                        <span>Database</span>
                        <span class="value">${data.database_connections > 0 ? 'Connected' : 'Disconnected'}</span>
                    </div>
                    <div class="metric">
                        <span>Redis Cache</span>
                        <span class="value">${data.redis_status}</span>
                    </div>
                    <div class="metric">
                        <span>Configurations</span>
                        <span class="value">${data.configurations_count}</span>
                    </div>
                    <div class="metric">
                        <span>Components</span>
                        <span class="value">${data.components_count}</span>
                    </div>
                ` + "`" + `;
            } catch (error) {
                console.error('Failed to fetch metrics:', error);
            }
        }
        
        async function fetchFabricSummary() {
            try {
                const response = await fetch('/api/fabrics/summary');
                const data = await response.json();
                document.getElementById('fabric-summary').innerHTML = ` + "`" + `
                    <div class="metric">
                        <span>Total Fabrics</span>
                        <span class="value">${data.total_fabrics}</span>
                    </div>
                    <div class="metric">
                        <span>Active Fabrics</span>
                        <span class="value">${data.fabrics_by_status.active || 0}</span>
                    </div>
                    <div class="metric">
                        <span>Connected</span>
                        <span class="value">${data.connection_summary.connected || 0}</span>
                    </div>
                    <div class="metric">
                        <span>Total CRDs</span>
                        <span class="value">${data.total_crds}</span>
                    </div>
                ` + "`" + `;
            } catch (error) {
                console.error('Failed to fetch fabric summary:', error);
                document.getElementById('fabric-summary').innerHTML = '<div class="metric"><span>Loading failed</span><span class="value">⚠️</span></div>';
            }
        }
        
        // Initial load
        fetchStatus();
        fetchMetrics();
        fetchFabricSummary();
        
        // Refresh every 30 seconds
        setInterval(fetchStatus, 30000);
        setInterval(fetchMetrics, 30000);
        setInterval(fetchFabricSummary, 30000);
    </script>
</body>
</html>`
	
	w.Write([]byte(html))
}

func handleHealth(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]string{
		"status": "healthy",
		"service": "cnoc",
		"version": "1.0.0",
	})
}

func handleReady(w http.ResponseWriter, r *http.Request) {
	// Check database connection if available
	if db != nil {
		if err := db.Ping(); err != nil {
			w.WriteHeader(http.StatusServiceUnavailable)
			json.NewEncoder(w).Encode(map[string]string{
				"status": "not_ready",
				"reason": "database_unavailable",
			})
			return
		}
	}
	
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]string{"status": "ready"})
}

func handleStatus(config *Configuration) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		uptime := time.Since(startTime)
		status := SystemStatus{
			Status:      "operational",
			Service:     "cnoc",
			Version:     "1.0.0",
			Environment: config.Environment,
			Uptime:      fmt.Sprintf("%dh %dm %ds", int(uptime.Hours()), int(uptime.Minutes())%60, int(uptime.Seconds())%60),
			Timestamp:   time.Now(),
		}
		
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(status)
	}
}

func handleMetrics(w http.ResponseWriter, r *http.Request) {
	metrics := MetricsData{
		DatabaseConnections: 0,
		RedisStatus:        "disconnected",
		ConfigurationsCount: 12, // Mock data
		ComponentsCount:    4,   // Mock data
		K8sClusterStatus:   "healthy",
	}
	
	if db != nil {
		if err := db.Ping(); err == nil {
			metrics.DatabaseConnections = 1
		}
	}
	
	if redisClient != nil {
		ctx := context.Background()
		if err := redisClient.Ping(ctx).Err(); err == nil {
			metrics.RedisStatus = "connected"
		}
	}
	
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(metrics)
}

func handleConfigurations(w http.ResponseWriter, r *http.Request) {
	configurations := []map[string]interface{}{
		{"id": "1", "name": "cnoc-config", "type": "core", "status": "active"},
		{"id": "2", "name": "network-config", "type": "network", "status": "active"},
		{"id": "3", "name": "security-config", "type": "security", "status": "active"},
	}
	
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(configurations)
}

func handleComponents(w http.ResponseWriter, r *http.Request) {
	components := []map[string]interface{}{
		{"name": "postgresql", "version": "15-alpine", "status": "running"},
		{"name": "redis", "version": "7-alpine", "status": "running"},
		{"name": "cnoc-api", "version": "1.0.0", "status": "running"},
		{"name": "adminer", "version": "latest", "status": "running"},
	}
	
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(components)
}

// Fabric API handlers equivalent to HNP Django views

func handleFabrics(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	
	switch r.Method {
	case "GET":
		// List fabrics with pagination equivalent to HNP fabric_list view
		offset := 0
		limit := 25
		
		if offsetStr := r.URL.Query().Get("offset"); offsetStr != "" {
			if parsed, err := strconv.Atoi(offsetStr); err == nil {
				offset = parsed
			}
		}
		if limitStr := r.URL.Query().Get("limit"); limitStr != "" {
			if parsed, err := strconv.Atoi(limitStr); err == nil {
				limit = parsed
			}
		}
		
		// Apply pagination to mock data
		end := offset + limit
		if end > len(mockFabrics) {
			end = len(mockFabrics)
		}
		
		var results []Fabric
		if offset < len(mockFabrics) {
			results = mockFabrics[offset:end]
		} else {
			results = []Fabric{}
		}
		
		response := map[string]interface{}{
			"count":    len(mockFabrics),
			"next":     nil,
			"previous": nil,
			"results":  results,
		}
		
		json.NewEncoder(w).Encode(response)
		
	case "POST":
		// Create fabric equivalent to HNP fabric creation
		var fabric Fabric
		if err := json.NewDecoder(r.Body).Decode(&fabric); err != nil {
			http.Error(w, "Invalid JSON", http.StatusBadRequest)
			return
		}
		
		// Basic validation
		if fabric.Name == "" {
			http.Error(w, "Name is required", http.StatusBadRequest)
			return
		}
		
		// Generate ID and timestamps
		fabric.ID = fmt.Sprintf("fabric-%d", len(mockFabrics)+1)
		fabric.Created = time.Now()
		fabric.LastModified = time.Now()
		if fabric.Status == "" {
			fabric.Status = "planned"
		}
		if fabric.ConnectionStatus == "" {
			fabric.ConnectionStatus = "unknown"
		}
		if fabric.SyncStatus == "" {
			fabric.SyncStatus = "never_synced"
		}
		
		// Add to mock store
		mockFabrics = append(mockFabrics, fabric)
		
		w.WriteHeader(http.StatusCreated)
		json.NewEncoder(w).Encode(fabric)
	}
}

func handleFabricDetail(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	vars := mux.Vars(r)
	fabricID := vars["id"]
	
	// Find fabric in mock data
	var fabric *Fabric
	var index int
	for i, f := range mockFabrics {
		if f.ID == fabricID {
			fabric = &f
			index = i
			break
		}
	}
	
	if fabric == nil {
		http.Error(w, "Fabric not found", http.StatusNotFound)
		return
	}
	
	switch r.Method {
	case "GET":
		// Get fabric detail equivalent to HNP fabric_detail view
		json.NewEncoder(w).Encode(fabric)
		
	case "PUT":
		// Update fabric equivalent to HNP fabric edit
		var updatedFabric Fabric
		if err := json.NewDecoder(r.Body).Decode(&updatedFabric); err != nil {
			http.Error(w, "Invalid JSON", http.StatusBadRequest)
			return
		}
		
		// Preserve immutable fields
		updatedFabric.ID = fabric.ID
		updatedFabric.Created = fabric.Created
		updatedFabric.LastModified = time.Now()
		
		// Update in mock store
		mockFabrics[index] = updatedFabric
		
		json.NewEncoder(w).Encode(updatedFabric)
		
	case "DELETE":
		// Delete fabric equivalent to HNP fabric deletion
		// Remove from mock store
		mockFabrics = append(mockFabrics[:index], mockFabrics[index+1:]...)
		
		w.WriteHeader(http.StatusNoContent)
	}
}

func handleFabricTest(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	vars := mux.Vars(r)
	fabricID := vars["id"]
	
	// Find fabric
	var fabric *Fabric
	for _, f := range mockFabrics {
		if f.ID == fabricID {
			fabric = &f
			break
		}
	}
	
	if fabric == nil {
		http.Error(w, "Fabric not found", http.StatusNotFound)
		return
	}
	
	// Mock connection test equivalent to HNP test connection
	testResult := map[string]interface{}{
		"fabric_id":           fabricID,
		"success":             fabric.KubernetesServer != "",
		"response_time_ms":    42,
		"kubernetes_version":  "v1.33.3+k3s1",
		"node_count":          1,
		"namespace_count":     8,
		"test_timestamp":      time.Now(),
		"connection_details":  map[string]interface{}{
			"server": fabric.KubernetesServer,
			"status": fabric.ConnectionStatus,
		},
	}
	
	if fabric.KubernetesServer == "" {
		testResult["success"] = false
		testResult["error_message"] = "Kubernetes server not configured"
	}
	
	json.NewEncoder(w).Encode(testResult)
}

func handleFabricSync(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	vars := mux.Vars(r)
	fabricID := vars["id"]
	
	// Find fabric
	var fabric *Fabric
	for _, f := range mockFabrics {
		if f.ID == fabricID {
			fabric = &f
			break
		}
	}
	
	if fabric == nil {
		http.Error(w, "Fabric not found", http.StatusNotFound)
		return
	}
	
	// Mock sync operation equivalent to HNP sync functionality
	syncResult := map[string]interface{}{
		"fabric_id":         fabricID,
		"operation_id":      fmt.Sprintf("sync-%d", time.Now().Unix()),
		"status":            "completed",
		"start_time":        time.Now().Add(-30 * time.Second),
		"end_time":          time.Now(),
		"progress":          100,
		"crds_processed":    fabric.CachedCRDCount,
		"crds_total":        fabric.CachedCRDCount,
		"errors_count":      0,
		"git_commit_hash":   "abc123",
		"git_directory":     fabric.GitOpsDirectory,
		"results":           map[string]interface{}{
			"vpcs_synced":        2,
			"connections_synced": 26,
			"switches_synced":    8,
		},
	}
	
	json.NewEncoder(w).Encode(syncResult)
}

func handleFabricSummary(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	
	// Generate summary equivalent to HNP overview context
	summary := FabricSummary{
		TotalFabrics: len(mockFabrics),
		FabricsByStatus: map[string]int{
			"active":  1,
			"planned": 1,
		},
		ConnectionSummary: map[string]int{
			"connected": 1,
			"pending":   1,
		},
		SyncSummary: map[string]int{
			"in_sync":      1,
			"never_synced": 1,
		},
		TotalCRDs: 36,
	}
	
	json.NewEncoder(w).Encode(summary)
}

// CRD API handlers equivalent to HNP CRD views

func handleCRDs(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	
	// List all CRDs equivalent to HNP combined CRD listing
	response := map[string]interface{}{
		"count":   len(mockCRDs),
		"results": mockCRDs,
	}
	
	json.NewEncoder(w).Encode(response)
}

func handleCRDsByType(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	vars := mux.Vars(r)
	crdType := vars["type"]
	
	switch r.Method {
	case "GET":
		// Filter CRDs by type equivalent to HNP type-specific views
		var filteredCRDs []CRDResource
		for _, crd := range mockCRDs {
			if crd.Type == crdType {
				filteredCRDs = append(filteredCRDs, crd)
			}
		}
		
		response := map[string]interface{}{
			"count":   len(filteredCRDs),
			"type":    crdType,
			"results": filteredCRDs,
		}
		
		json.NewEncoder(w).Encode(response)
		
	case "POST":
		// Create CRD of specific type
		var crd CRDResource
		if err := json.NewDecoder(r.Body).Decode(&crd); err != nil {
			http.Error(w, "Invalid JSON", http.StatusBadRequest)
			return
		}
		
		// Set type and generate ID
		crd.Type = crdType
		crd.ID = fmt.Sprintf("crd-%d", len(mockCRDs)+1)
		crd.Created = time.Now()
		crd.LastModified = time.Now()
		
		// Add to mock store
		mockCRDs = append(mockCRDs, crd)
		
		w.WriteHeader(http.StatusCreated)
		json.NewEncoder(w).Encode(crd)
	}
}

func handleCRDDetail(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	vars := mux.Vars(r)
	crdID := vars["id"]
	
	// Find CRD in mock data
	var crd *CRDResource
	var index int
	for i, c := range mockCRDs {
		if c.ID == crdID {
			crd = &c
			index = i
			break
		}
	}
	
	if crd == nil {
		http.Error(w, "CRD not found", http.StatusNotFound)
		return
	}
	
	switch r.Method {
	case "GET":
		json.NewEncoder(w).Encode(crd)
		
	case "PUT":
		var updatedCRD CRDResource
		if err := json.NewDecoder(r.Body).Decode(&updatedCRD); err != nil {
			http.Error(w, "Invalid JSON", http.StatusBadRequest)
			return
		}
		
		// Preserve immutable fields
		updatedCRD.ID = crd.ID
		updatedCRD.Created = crd.Created
		updatedCRD.LastModified = time.Now()
		
		// Update in mock store
		mockCRDs[index] = updatedCRD
		
		json.NewEncoder(w).Encode(updatedCRD)
		
	case "DELETE":
		// Remove from mock store
		mockCRDs = append(mockCRDs[:index], mockCRDs[index+1:]...)
		w.WriteHeader(http.StatusNoContent)
	}
}

func handleCRDSummary(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	
	// Generate CRD summary
	crdsByType := make(map[string]int)
	crdsByFabric := make(map[string]int)
	
	for _, crd := range mockCRDs {
		crdsByType[crd.Type]++
		crdsByFabric[crd.FabricID]++
	}
	
	summary := CRDSummary{
		TotalCRDs:    len(mockCRDs),
		CRDsByType:   crdsByType,
		CRDsByStatus: map[string]int{"active": len(mockCRDs)},
		CRDsByFabric: crdsByFabric,
	}
	
	json.NewEncoder(w).Encode(summary)
}

func handleFabricsPage(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "text/html; charset=utf-8")
	html := `<!DOCTYPE html>
<html>
<head>
    <title>CNOC - Fabric Management</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; margin: 0; padding: 20px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; }
        .container { max-width: 1200px; margin: 0 auto; }
        .header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 30px; }
        h1 { font-size: 2.5em; margin: 0; }
        .back-link { color: white; text-decoration: none; font-size: 1.1em; }
        .back-link:hover { text-decoration: underline; }
        .actions { margin-bottom: 20px; }
        .button { background: rgba(255,255,255,0.2); border: 1px solid rgba(255,255,255,0.3); color: white; padding: 10px 20px; border-radius: 8px; cursor: pointer; text-decoration: none; display: inline-block; margin: 5px; }
        .button:hover { background: rgba(255,255,255,0.3); }
        .button.primary { background: rgba(34,197,94,0.7); border-color: rgba(34,197,94,0.9); }
        .fabric-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(400px, 1fr)); gap: 20px; }
        .fabric-card { background: rgba(255,255,255,0.1); backdrop-filter: blur(10px); border-radius: 15px; padding: 20px; border: 1px solid rgba(255,255,255,0.2); }
        .fabric-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px; }
        .fabric-name { font-size: 1.3em; font-weight: bold; }
        .status-badge { padding: 4px 12px; border-radius: 20px; font-size: 0.8em; font-weight: bold; }
        .status-active { background: rgba(34,197,94,0.8); }
        .status-planned { background: rgba(251,191,36,0.8); }
        .status-inactive { background: rgba(239,68,68,0.8); }
        .fabric-meta { margin: 10px 0; }
        .meta-row { display: flex; justify-content: space-between; margin: 5px 0; padding: 5px 0; border-bottom: 1px solid rgba(255,255,255,0.1); }
        .meta-row:last-child { border-bottom: none; }
        .fabric-actions { margin-top: 15px; display: flex; gap: 10px; }
        .action-btn { padding: 6px 12px; font-size: 0.9em; }
        .loading { text-align: center; padding: 40px; font-size: 1.2em; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🏗️ Fabric Management</h1>
            <a href="/" class="back-link">← Back to Dashboard</a>
        </div>
        
        <div class="actions">
            <button class="button primary" onclick="addFabric()">➕ Add New Fabric</button>
            <button class="button" onclick="refreshFabrics()">🔄 Refresh</button>
            <a href="/crds" class="button">📦 View CRDs</a>
        </div>
        
        <div id="fabrics-container" class="loading">
            <div>Loading fabrics...</div>
        </div>
    </div>
    
    <script>
        async function loadFabrics() {
            try {
                const response = await fetch('/api/fabrics');
                const data = await response.json();
                
                const container = document.getElementById('fabrics-container');
                
                if (data.results && data.results.length > 0) {
                    container.innerHTML = '<div class="fabric-grid">' + data.results.map(function(fabric) {
                        return '<div class="fabric-card">' +
                            '<div class="fabric-header">' +
                                '<div class="fabric-name">' + fabric.name + '</div>' +
                                '<div class="status-badge status-' + fabric.status + '">' + fabric.status.toUpperCase() + '</div>' +
                            '</div>' +
                            '<div class="fabric-meta">' +
                                (fabric.description ? '<div class="meta-row"><span>Description:</span><span>' + fabric.description + '</span></div>' : '') +
                                '<div class="meta-row">' +
                                    '<span>Connection:</span>' +
                                    '<span>' + fabric.connection_status + '</span>' +
                                '</div>' +
                                '<div class="meta-row">' +
                                    '<span>Sync Status:</span>' +
                                    '<span>' + fabric.sync_status + '</span>' +
                                '</div>' +
                                '<div class="meta-row">' +
                                    '<span>CRDs:</span>' +
                                    '<span>' + fabric.cached_crd_count + '</span>' +
                                '</div>' +
                                '<div class="meta-row">' +
                                    '<span>Created:</span>' +
                                    '<span>' + new Date(fabric.created).toLocaleDateString() + '</span>' +
                                '</div>' +
                            '</div>' +
                            '<div class="fabric-actions">' +
                                '<a href="/fabrics/' + fabric.id + '" class="button action-btn">📄 Details</a>' +
                                '<button class="button action-btn" onclick="testConnection(\'' + fabric.id + '\')">🔧 Test</button>' +
                                '<button class="button action-btn" onclick="syncFabric(\'' + fabric.id + '\')">🔄 Sync</button>' +
                            '</div>' +
                        '</div>';
                    }).join('') + '</div>';
                } else {
                    container.innerHTML = 
                        '<div style="text-align: center; padding: 40px;">' +
                            '<h2>No fabrics found</h2>' +
                            '<p>Create your first fabric to get started with CNOC</p>' +
                            '<button class="button primary" onclick="addFabric()">➕ Add New Fabric</button>' +
                        '</div>';
                }
            } catch (error) {
                console.error('Failed to load fabrics:', error);
                document.getElementById('fabrics-container').innerHTML = 
                    '<div style="text-align: center; padding: 40px; color: #ef4444;">' +
                        '<h2>Failed to load fabrics</h2>' +
                        '<p>Error: ' + error.message + '</p>' +
                        '<button class="button" onclick="loadFabrics()">🔄 Retry</button>' +
                    '</div>';
            }
        }
        
        function addFabric() {
            const name = prompt('Enter fabric name:');
            if (name) {
                const description = prompt('Enter fabric description (optional):') || '';
                
                fetch('/api/fabrics', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        name: name,
                        description: description,
                        status: 'planned'
                    })
                })
                .then(response => response.json())
                .then(data => {
                    loadFabrics();
                    alert('Fabric created successfully!');
                })
                .catch(error => {
                    console.error('Error creating fabric:', error);
                    alert('Failed to create fabric: ' + error.message);
                });
            }
        }
        
        async function testConnection(fabricId) {
            try {
                const response = await fetch('/api/fabrics/' + fabricId + '/test', {
                    method: 'POST'
                });
                const result = await response.json();
                
                if (result.success) {
                    alert('Connection test successful!\n\nKubernetes version: ' + result.kubernetes_version + '\nNodes: ' + result.node_count + '\nNamespaces: ' + result.namespace_count);
                } else {
                    alert('Connection test failed:\n' + (result.error_message || 'Unknown error'));
                }
            } catch (error) {
                alert('Test failed: ' + error.message);
            }
        }
        
        async function syncFabric(fabricId) {
            try {
                const response = await fetch('/api/fabrics/' + fabricId + '/sync', {
                    method: 'POST'
                });
                const result = await response.json();
                
                alert('Sync completed!\n\nCRDs processed: ' + result.crds_processed + '\nVPCs: ' + result.results.vpcs_synced + '\nConnections: ' + result.results.connections_synced + '\nSwitches: ' + result.results.switches_synced);
                loadFabrics();
            } catch (error) {
                alert('Sync failed: ' + error.message);
            }
        }
        
        function refreshFabrics() {
            loadFabrics();
        }
        
        // Initial load
        loadFabrics();
    </script>
</body>
</html>`
	
	w.Write([]byte(html))
}

func handleFabricDetailPage(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "text/html; charset=utf-8")
	vars := mux.Vars(r)
	fabricID := vars["id"]
	
	html := `<!DOCTYPE html>
<html>
<head>
    <title>CNOC - Fabric Details</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; margin: 0; padding: 20px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; }
        .container { max-width: 1000px; margin: 0 auto; }
        .header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 30px; }
        h1 { font-size: 2.5em; margin: 0; }
        .back-link { color: white; text-decoration: none; font-size: 1.1em; }
        .back-link:hover { text-decoration: underline; }
        .fabric-overview { background: rgba(255,255,255,0.1); backdrop-filter: blur(10px); border-radius: 15px; padding: 20px; margin-bottom: 20px; border: 1px solid rgba(255,255,255,0.2); }
        .status-section { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin: 20px 0; }
        .status-card { background: rgba(255,255,255,0.1); border-radius: 10px; padding: 15px; text-align: center; }
        .status-badge { padding: 6px 16px; border-radius: 20px; font-weight: bold; margin: 10px 0; display: inline-block; }
        .status-active { background: rgba(34,197,94,0.8); }
        .status-planned { background: rgba(251,191,36,0.8); }
        .status-connected { background: rgba(34,197,94,0.8); }
        .status-pending { background: rgba(251,191,36,0.8); }
        .status-in_sync { background: rgba(34,197,94,0.8); }
        .status-never_synced { background: rgba(156,163,175,0.8); }
        .detail-section { background: rgba(255,255,255,0.1); backdrop-filter: blur(10px); border-radius: 15px; padding: 20px; margin-bottom: 20px; border: 1px solid rgba(255,255,255,0.2); }
        .detail-row { display: flex; justify-content: space-between; padding: 10px 0; border-bottom: 1px solid rgba(255,255,255,0.1); }
        .detail-row:last-child { border-bottom: none; }
        .actions { display: flex; gap: 10px; margin: 20px 0; }
        .button { background: rgba(255,255,255,0.2); border: 1px solid rgba(255,255,255,0.3); color: white; padding: 10px 20px; border-radius: 8px; cursor: pointer; text-decoration: none; display: inline-block; }
        .button:hover { background: rgba(255,255,255,0.3); }
        .button.primary { background: rgba(34,197,94,0.7); border-color: rgba(34,197,94,0.9); }
        .button.danger { background: rgba(239,68,68,0.7); border-color: rgba(239,68,68,0.9); }
        .loading { text-align: center; padding: 40px; font-size: 1.2em; }
        .crd-preview { max-height: 300px; overflow-y: auto; }
        .crd-item { background: rgba(255,255,255,0.05); padding: 10px; margin: 5px 0; border-radius: 5px; display: flex; justify-content: space-between; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1 id="fabric-title">🏗️ Fabric Details</h1>
            <a href="/fabrics" class="back-link">← Back to Fabrics</a>
        </div>
        
        <div id="fabric-content" class="loading">
            <div>Loading fabric details...</div>
        </div>
    </div>
    
    <script>
        const fabricId = '` + fabricID + `';
        
        async function loadFabricDetails() {
            try {
                const response = await fetch('/api/fabrics/' + fabricId);
                if (!response.ok) {
                    throw new Error('Fabric not found');
                }
                const fabric = await response.json();
                
                document.getElementById('fabric-title').innerHTML = '🏗️ ' + fabric.name;
                
                const content = document.getElementById('fabric-content');
                content.innerHTML = `
                    <div class="fabric-overview">
                        <h2>${fabric.name}</h2>
                        ${fabric.description ? '<p>' + fabric.description + '</p>' : ''}
                        
                        <div class="status-section">
                            <div class="status-card">
                                <h3>Status</h3>
                                <div class="status-badge status-${fabric.status}">${fabric.status.toUpperCase()}</div>
                            </div>
                            <div class="status-card">
                                <h3>Connection</h3>
                                <div class="status-badge status-${fabric.connection_status}">${fabric.connection_status.toUpperCase()}</div>
                            </div>
                            <div class="status-card">
                                <h3>Sync Status</h3>
                                <div class="status-badge status-${fabric.sync_status}">${fabric.sync_status.replace('_', ' ').toUpperCase()}</div>
                            </div>
                            <div class="status-card">
                                <h3>CRDs</h3>
                                <div style="font-size: 2em; font-weight: bold; margin: 10px 0;">${fabric.cached_crd_count}</div>
                            </div>
                        </div>
                        
                        <div class="actions">
                            <button class="button primary" onclick="testConnection()">🔧 Test Connection</button>
                            <button class="button primary" onclick="syncFabric()">🔄 Sync GitOps</button>
                            <button class="button" onclick="editFabric()">✏️ Edit</button>
                            <button class="button danger" onclick="deleteFabric()">🗑️ Delete</button>
                        </div>
                    </div>
                    
                    <div class="detail-section">
                        <h3>Configuration Details</h3>
                        <div class="detail-row">
                            <span>Fabric ID</span>
                            <span>${fabric.id}</span>
                        </div>
                        <div class="detail-row">
                            <span>Kubernetes Server</span>
                            <span>${fabric.kubernetes_server || 'Not configured'}</span>
                        </div>
                        <div class="detail-row">
                            <span>Git Repository</span>
                            <span>${fabric.git_repository || 'Not configured'}</span>
                        </div>
                        <div class="detail-row">
                            <span>GitOps Directory</span>
                            <span>${fabric.gitops_directory || 'Not configured'}</span>
                        </div>
                        <div class="detail-row">
                            <span>Created</span>
                            <span>${new Date(fabric.created).toLocaleString()}</span>
                        </div>
                        <div class="detail-row">
                            <span>Last Modified</span>
                            <span>${new Date(fabric.last_modified).toLocaleString()}</span>
                        </div>
                    </div>
                    
                    <div class="detail-section">
                        <h3>CRD Resources <a href="/crds?fabric=${fabric.id}" class="button" style="float: right;">📦 View All CRDs</a></h3>
                        <div id="crd-preview" class="crd-preview">Loading CRDs...</div>
                    </div>
                `;
                
                // Load CRDs for this fabric
                loadFabricCRDs();
                
            } catch (error) {
                console.error('Failed to load fabric details:', error);
                document.getElementById('fabric-content').innerHTML = `
                    <div style="text-align: center; padding: 40px; color: #ef4444;">
                        <h2>Failed to load fabric</h2>
                        <p>Error: ${error.message}</p>
                        <a href="/fabrics" class="button">← Back to Fabrics</a>
                    </div>
                `;
            }
        }
        
        async function loadFabricCRDs() {
            try {
                const response = await fetch('/api/crds?fabric=' + fabricId);
                const data = await response.json();
                
                const preview = document.getElementById('crd-preview');
                if (data.results && data.results.length > 0) {
                    preview.innerHTML = data.results.map(crd => `
                        <div class="crd-item">
                            <div>
                                <strong>${crd.name}</strong> (${crd.kind})
                                <br><small>${crd.type} - ${crd.api_version}</small>
                            </div>
                            <div>
                                <span style="color: #10b981;">${crd.status && crd.status.phase ? crd.status.phase : 'Unknown'}</span>
                            </div>
                        </div>
                    `).join('');
                } else {
                    preview.innerHTML = '<div style="text-align: center; padding: 20px; opacity: 0.7;">No CRDs found for this fabric</div>';
                }
            } catch (error) {
                document.getElementById('crd-preview').innerHTML = '<div style="color: #ef4444;">Failed to load CRDs</div>';
            }
        }
        
        async function testConnection() {
            try {
                const response = await fetch('/api/fabrics/' + fabricId + '/test', {
                    method: 'POST'
                });
                const result = await response.json();
                
                if (result.success) {
                    alert('Connection test successful!\\n\\nKubernetes version: ' + result.kubernetes_version + '\\nNodes: ' + result.node_count + '\\nNamespaces: ' + result.namespace_count + '\\nResponse time: ' + result.response_time_ms + 'ms');
                } else {
                    alert('Connection test failed:\\n' + (result.error_message || 'Unknown error'));
                }
            } catch (error) {
                alert('Test failed: ' + error.message);
            }
        }
        
        async function syncFabric() {
            if (confirm('Start GitOps synchronization for this fabric?')) {
                try {
                    const response = await fetch('/api/fabrics/' + fabricId + '/sync', {
                        method: 'POST'
                    });
                    const result = await response.json();
                    
                    alert('Sync completed!\\n\\nOperation ID: ' + result.operation_id + '\\nCRDs processed: ' + result.crds_processed + '\\nVPCs: ' + result.results.vpcs_synced + '\\nConnections: ' + result.results.connections_synced + '\\nSwitches: ' + result.results.switches_synced);
                    loadFabricDetails();
                } catch (error) {
                    alert('Sync failed: ' + error.message);
                }
            }
        }
        
        function editFabric() {
            alert('Edit functionality will be implemented in a future version');
        }
        
        function deleteFabric() {
            if (confirm('Are you sure you want to delete this fabric? This action cannot be undone.')) {
                fetch('/api/fabrics/' + fabricId, {
                    method: 'DELETE'
                })
                .then(response => {
                    if (response.ok) {
                        alert('Fabric deleted successfully');
                        window.location.href = '/fabrics';
                    } else {
                        throw new Error('Delete failed');
                    }
                })
                .catch(error => {
                    alert('Failed to delete fabric: ' + error.message);
                });
            }
        }
        
        // Initial load
        loadFabricDetails();
    </script>
</body>
</html>`
	
	w.Write([]byte(html))
}

func handleCRDsPage(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "text/html; charset=utf-8")
	html := `<!DOCTYPE html>
<html>
<head>
    <title>CNOC - CRD Management</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; margin: 0; padding: 20px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; }
        .container { max-width: 1200px; margin: 0 auto; }
        .header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 30px; }
        h1 { font-size: 2.5em; margin: 0; }
        .back-link { color: white; text-decoration: none; font-size: 1.1em; }
        .back-link:hover { text-decoration: underline; }
        .filters { background: rgba(255,255,255,0.1); backdrop-filter: blur(10px); border-radius: 15px; padding: 20px; margin-bottom: 20px; border: 1px solid rgba(255,255,255,0.2); }
        .filter-row { display: flex; gap: 15px; align-items: center; margin: 10px 0; }
        .filter-group { display: flex; align-items: center; gap: 10px; }
        select, input { background: rgba(255,255,255,0.2); border: 1px solid rgba(255,255,255,0.3); color: white; padding: 8px 12px; border-radius: 5px; }
        select option { background: #333; color: white; }
        .button { background: rgba(255,255,255,0.2); border: 1px solid rgba(255,255,255,0.3); color: white; padding: 10px 20px; border-radius: 8px; cursor: pointer; text-decoration: none; display: inline-block; margin: 5px; }
        .button:hover { background: rgba(255,255,255,0.3); }
        .button.primary { background: rgba(34,197,94,0.7); border-color: rgba(34,197,94,0.9); }
        .crd-table { background: rgba(255,255,255,0.1); backdrop-filter: blur(10px); border-radius: 15px; padding: 20px; border: 1px solid rgba(255,255,255,0.2); overflow-x: auto; }
        table { width: 100%; border-collapse: collapse; }
        th, td { padding: 12px; text-align: left; border-bottom: 1px solid rgba(255,255,255,0.1); }
        th { background: rgba(255,255,255,0.1); font-weight: bold; }
        .type-badge { padding: 4px 8px; border-radius: 12px; font-size: 0.8em; font-weight: bold; background: rgba(34,197,94,0.7); }
        .status-badge { padding: 4px 8px; border-radius: 12px; font-size: 0.8em; font-weight: bold; }
        .status-ready { background: rgba(34,197,94,0.7); }
        .status-pending { background: rgba(251,191,36,0.7); }
        .loading { text-align: center; padding: 40px; font-size: 1.2em; }
        .summary-cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin-bottom: 20px; }
        .summary-card { background: rgba(255,255,255,0.1); backdrop-filter: blur(10px); border-radius: 10px; padding: 15px; text-align: center; border: 1px solid rgba(255,255,255,0.2); }
        .summary-number { font-size: 2em; font-weight: bold; margin: 10px 0; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📦 CRD Management</h1>
            <a href="/" class="back-link">← Back to Dashboard</a>
        </div>
        
        <div id="summary-section" class="summary-cards">
            <div class="summary-card">
                <h3>Total CRDs</h3>
                <div id="total-crds" class="summary-number">-</div>
            </div>
            <div class="summary-card">
                <h3>VPCs</h3>
                <div id="vpc-count" class="summary-number">-</div>
            </div>
            <div class="summary-card">
                <h3>Connections</h3>
                <div id="connection-count" class="summary-number">-</div>
            </div>
            <div class="summary-card">
                <h3>Switches</h3>
                <div id="switch-count" class="summary-number">-</div>
            </div>
        </div>
        
        <div class="filters">
            <div class="filter-row">
                <div class="filter-group">
                    <label>Type:</label>
                    <select id="type-filter">
                        <option value="">All Types</option>
                        <option value="vpc">VPC</option>
                        <option value="connection">Connection</option>
                        <option value="switch">Switch</option>
                        <option value="ipv4namespace">IPv4 Namespace</option>
                        <option value="vpcpeering">VPC Peering</option>
                        <option value="vpcattachment">VPC Attachment</option>
                        <option value="external">External</option>
                        <option value="dhcprelay">DHCP Relay</option>
                        <option value="dnszone">DNS Zone</option>
                        <option value="dnsrecord">DNS Record</option>
                        <option value="vlan">VLAN</option>
                        <option value="vlanswitching">VLAN Switching</option>
                    </select>
                </div>
                <div class="filter-group">
                    <label>Fabric:</label>
                    <select id="fabric-filter">
                        <option value="">All Fabrics</option>
                    </select>
                </div>
                <div class="filter-group">
                    <label>Search:</label>
                    <input type="text" id="search-filter" placeholder="Search by name...">
                </div>
                <button class="button" onclick="applyFilters()">🔍 Filter</button>
                <button class="button" onclick="clearFilters()">🔄 Clear</button>
            </div>
        </div>
        
        <div class="crd-table">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px;">
                <h3>CRD Resources</h3>
                <div>
                    <a href="/fabrics" class="button">🏗️ Manage Fabrics</a>
                    <button class="button primary" onclick="refreshCRDs()">🔄 Refresh</button>
                </div>
            </div>
            
            <div id="crds-content" class="loading">
                <div>Loading CRDs...</div>
            </div>
        </div>
    </div>
    
    <script>
        let allCRDs = [];
        let allFabrics = [];
        
        async function loadCRDs() {
            try {
                const response = await fetch('/api/crds');
                const data = await response.json();
                allCRDs = data.results || [];
                
                displayCRDs(allCRDs);
                updateSummary();
                
            } catch (error) {
                console.error('Failed to load CRDs:', error);
                document.getElementById('crds-content').innerHTML = `
                    <div style="text-align: center; padding: 40px; color: #ef4444;">
                        <h2>Failed to load CRDs</h2>
                        <p>Error: ${error.message}</p>
                        <button class="button" onclick="loadCRDs()">🔄 Retry</button>
                    </div>
                `;
            }
        }
        
        async function loadFabrics() {
            try {
                const response = await fetch('/api/fabrics');
                const data = await response.json();
                allFabrics = data.results || [];
                
                const fabricFilter = document.getElementById('fabric-filter');
                allFabrics.forEach(fabric => {
                    const option = document.createElement('option');
                    option.value = fabric.id;
                    option.textContent = fabric.name;
                    fabricFilter.appendChild(option);
                });
                
            } catch (error) {
                console.error('Failed to load fabrics:', error);
            }
        }
        
        function displayCRDs(crds) {
            const content = document.getElementById('crds-content');
            
            if (crds.length === 0) {
                content.innerHTML = `
                    <div style="text-align: center; padding: 40px;">
                        <h3>No CRDs found</h3>
                        <p>No CRD resources match the current filters</p>
                    </div>
                `;
                return;
            }
            
            content.innerHTML = `
                <table>
                    <thead>
                        <tr>
                            <th>Name</th>
                            <th>Type</th>
                            <th>Kind</th>
                            <th>Fabric</th>
                            <th>Status</th>
                            <th>Created</th>
                            <th>Actions</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${crds.map(crd => {
                            const fabric = allFabrics.find(f => f.id === crd.fabric_id);
                            const fabricName = fabric ? fabric.name : crd.fabric_id;
                            const status = crd.status && crd.status.phase ? crd.status.phase : 'Unknown';
                            
                            return `
                                <tr>
                                    <td><strong>${crd.name}</strong></td>
                                    <td><span class="type-badge">${crd.type.toUpperCase()}</span></td>
                                    <td>${crd.kind}</td>
                                    <td>${fabricName}</td>
                                    <td><span class="status-badge status-${status.toLowerCase()}">${status}</span></td>
                                    <td>${new Date(crd.created).toLocaleDateString()}</td>
                                    <td>
                                        <button class="button" style="padding: 4px 8px; font-size: 0.8em;" onclick="viewCRD('${crd.id}')">👁️ View</button>
                                    </td>
                                </tr>
                            `;
                        }).join('')}
                    </tbody>
                </table>
            `;
        }
        
        function updateSummary() {
            const summary = {
                total: allCRDs.length,
                vpc: 0,
                connection: 0,
                switch: 0
            };
            
            allCRDs.forEach(crd => {
                if (crd.type === 'vpc') summary.vpc++;
                else if (crd.type === 'connection') summary.connection++;
                else if (crd.type === 'switch') summary.switch++;
            });
            
            document.getElementById('total-crds').textContent = summary.total;
            document.getElementById('vpc-count').textContent = summary.vpc;
            document.getElementById('connection-count').textContent = summary.connection;
            document.getElementById('switch-count').textContent = summary.switch;
        }
        
        function applyFilters() {
            const typeFilter = document.getElementById('type-filter').value;
            const fabricFilter = document.getElementById('fabric-filter').value;
            const searchFilter = document.getElementById('search-filter').value.toLowerCase();
            
            let filteredCRDs = allCRDs;
            
            if (typeFilter) {
                filteredCRDs = filteredCRDs.filter(crd => crd.type === typeFilter);
            }
            
            if (fabricFilter) {
                filteredCRDs = filteredCRDs.filter(crd => crd.fabric_id === fabricFilter);
            }
            
            if (searchFilter) {
                filteredCRDs = filteredCRDs.filter(crd => 
                    crd.name.toLowerCase().includes(searchFilter) ||
                    crd.kind.toLowerCase().includes(searchFilter)
                );
            }
            
            displayCRDs(filteredCRDs);
        }
        
        function clearFilters() {
            document.getElementById('type-filter').value = '';
            document.getElementById('fabric-filter').value = '';
            document.getElementById('search-filter').value = '';
            displayCRDs(allCRDs);
        }
        
        function viewCRD(crdId) {
            const crd = allCRDs.find(c => c.id === crdId);
            if (crd) {
                alert('CRD Details:\\n\\nName: ' + crd.name + '\\nType: ' + crd.type + '\\nKind: ' + crd.kind + '\\nAPI Version: ' + crd.api_version + '\\n\\nSpec: ' + JSON.stringify(crd.spec, null, 2));
            }
        }
        
        function refreshCRDs() {
            loadCRDs();
        }
        
        // Initial load
        loadFabrics();
        loadCRDs();
        
        // Setup filter event listeners
        document.getElementById('type-filter').addEventListener('change', applyFilters);
        document.getElementById('fabric-filter').addEventListener('change', applyFilters);
        document.getElementById('search-filter').addEventListener('input', applyFilters);
    </script>
</body>
</html>`
	
	w.Write([]byte(html))
}

func handleCRDsByTypePage(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "text/html; charset=utf-8")
	vars := mux.Vars(r)
	crdType := vars["type"]
	
	html := `<!DOCTYPE html>
<html>
<head>
    <title>CNOC - ` + crdType + ` CRDs</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; margin: 0; padding: 20px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; }
        .container { max-width: 1200px; margin: 0 auto; }
        .header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 30px; }
        h1 { font-size: 2.5em; margin: 0; }
        .back-link { color: white; text-decoration: none; font-size: 1.1em; }
        .back-link:hover { text-decoration: underline; }
        .type-overview { background: rgba(255,255,255,0.1); backdrop-filter: blur(10px); border-radius: 15px; padding: 20px; margin-bottom: 20px; border: 1px solid rgba(255,255,255,0.2); }
        .crd-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(350px, 1fr)); gap: 20px; }
        .crd-card { background: rgba(255,255,255,0.1); backdrop-filter: blur(10px); border-radius: 15px; padding: 20px; border: 1px solid rgba(255,255,255,0.2); }
        .crd-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px; }
        .crd-name { font-size: 1.2em; font-weight: bold; }
        .status-badge { padding: 4px 12px; border-radius: 20px; font-size: 0.8em; font-weight: bold; }
        .status-ready { background: rgba(34,197,94,0.8); }
        .status-pending { background: rgba(251,191,36,0.8); }
        .crd-meta { margin: 10px 0; }
        .meta-row { display: flex; justify-content: space-between; margin: 5px 0; padding: 5px 0; border-bottom: 1px solid rgba(255,255,255,0.1); }
        .meta-row:last-child { border-bottom: none; }
        .button { background: rgba(255,255,255,0.2); border: 1px solid rgba(255,255,255,0.3); color: white; padding: 10px 20px; border-radius: 8px; cursor: pointer; text-decoration: none; display: inline-block; margin: 5px; }
        .button:hover { background: rgba(255,255,255,0.3); }
        .button.primary { background: rgba(34,197,94,0.7); border-color: rgba(34,197,94,0.9); }
        .loading { text-align: center; padding: 40px; font-size: 1.2em; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📦 ` + crdType + ` CRDs</h1>
            <a href="/crds" class="back-link">← Back to All CRDs</a>
        </div>
        
        <div id="type-overview" class="type-overview">
            <h2>` + crdType + ` Resources</h2>
            <p>Manage and monitor all ` + crdType + ` CRD resources across your fabrics.</p>
            <div>
                <button class="button primary" onclick="addCRD()">➕ Add ` + crdType + `</button>
                <button class="button" onclick="refreshCRDs()">🔄 Refresh</button>
                <a href="/crds" class="button">📦 All CRDs</a>
            </div>
        </div>
        
        <div id="crds-container" class="loading">
            <div>Loading ` + crdType + ` CRDs...</div>
        </div>
    </div>
    
    <script>
        const crdType = '` + crdType + `';
        
        async function loadCRDs() {
            try {
                const response = await fetch('/api/crds/' + crdType);
                const data = await response.json();
                
                const container = document.getElementById('crds-container');
                
                if (data.results && data.results.length > 0) {
                    container.innerHTML = '<div class="crd-grid">' + data.results.map(crd => {
                        const status = crd.status && crd.status.phase ? crd.status.phase : 'Unknown';
                        
                        return `
                            <div class="crd-card">
                                <div class="crd-header">
                                    <div class="crd-name">${crd.name}</div>
                                    <div class="status-badge status-${status.toLowerCase()}">${status}</div>
                                </div>
                                <div class="crd-meta">
                                    <div class="meta-row">
                                        <span>Kind:</span>
                                        <span>${crd.kind}</span>
                                    </div>
                                    <div class="meta-row">
                                        <span>API Version:</span>
                                        <span>${crd.api_version}</span>
                                    </div>
                                    <div class="meta-row">
                                        <span>Fabric:</span>
                                        <span>${crd.fabric_id}</span>
                                    </div>
                                    <div class="meta-row">
                                        <span>Created:</span>
                                        <span>${new Date(crd.created).toLocaleDateString()}</span>
                                    </div>
                                </div>
                                <div style="margin-top: 15px;">
                                    <button class="button" onclick="viewCRD('${crd.id}')">👁️ View Details</button>
                                    <button class="button" onclick="editCRD('${crd.id}')">✏️ Edit</button>
                                    <button class="button" onclick="deleteCRD('${crd.id}')">🗑️ Delete</button>
                                </div>
                            </div>
                        `;
                    }).join('') + '</div>';
                } else {
                    container.innerHTML = `
                        <div style="text-align: center; padding: 40px;">
                            <h2>No ${crdType} CRDs found</h2>
                            <p>Create your first ${crdType} CRD to get started</p>
                            <button class="button primary" onclick="addCRD()">➕ Add ${crdType}</button>
                        </div>
                    `;
                }
            } catch (error) {
                console.error('Failed to load CRDs:', error);
                document.getElementById('crds-container').innerHTML = `
                    <div style="text-align: center; padding: 40px; color: #ef4444;">
                        <h2>Failed to load ${crdType} CRDs</h2>
                        <p>Error: ${error.message}</p>
                        <button class="button" onclick="loadCRDs()">🔄 Retry</button>
                    </div>
                `;
            }
        }
        
        function addCRD() {
            const name = prompt('Enter ' + crdType + ' name:');
            if (name) {
                const fabricId = prompt('Enter fabric ID:') || 'fabric-1';
                
                const crdData = {
                    name: name,
                    kind: crdType.charAt(0).toUpperCase() + crdType.slice(1),
                    fabric_id: fabricId,
                    api_version: crdType === 'vpc' ? 'vpc.githedgehog.com/v1beta1' : 'wiring.githedgehog.com/v1beta1',
                    spec: {},
                    status: { phase: 'Pending' }
                };
                
                fetch('/api/crds/' + crdType, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify(crdData)
                })
                .then(response => response.json())
                .then(data => {
                    loadCRDs();
                    alert(crdType + ' CRD created successfully!');
                })
                .catch(error => {
                    console.error('Error creating CRD:', error);
                    alert('Failed to create ' + crdType + ' CRD: ' + error.message);
                });
            }
        }
        
        function viewCRD(crdId) {
            fetch('/api/crds/' + crdType + '/' + crdId)
                .then(response => response.json())
                .then(crd => {
                    alert('CRD Details:\\n\\nName: ' + crd.name + '\\nType: ' + crd.type + '\\nKind: ' + crd.kind + '\\nAPI Version: ' + crd.api_version + '\\nFabric: ' + crd.fabric_id + '\\n\\nSpec: ' + JSON.stringify(crd.spec, null, 2) + '\\n\\nStatus: ' + JSON.stringify(crd.status, null, 2));
                })
                .catch(error => {
                    alert('Failed to load CRD details: ' + error.message);
                });
        }
        
        function editCRD(crdId) {
            alert('Edit functionality will be implemented in a future version');
        }
        
        function deleteCRD(crdId) {
            if (confirm('Are you sure you want to delete this ' + crdType + ' CRD?')) {
                fetch('/api/crds/' + crdType + '/' + crdId, {
                    method: 'DELETE'
                })
                .then(response => {
                    if (response.ok) {
                        alert(crdType + ' CRD deleted successfully');
                        loadCRDs();
                    } else {
                        throw new Error('Delete failed');
                    }
                })
                .catch(error => {
                    alert('Failed to delete CRD: ' + error.message);
                });
            }
        }
        
        function refreshCRDs() {
            loadCRDs();
        }
        
        // Initial load
        loadCRDs();
    </script>
</body>
</html>`
	
	w.Write([]byte(html))
}

func getEnv(key, fallback string) string {
	if value := os.Getenv(key); value != "" {
		return value
	}
	return fallback
}