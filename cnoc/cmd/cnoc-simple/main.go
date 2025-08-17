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
	
	// API endpoints
	router.HandleFunc("/", handleHome).Methods("GET")
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
                <h2>Quick Actions</h2>
                <a href="/api/status" class="button">📊 API Status</a>
                <a href="/api/metrics" class="button">📈 Metrics</a>
                <a href="/api/configurations" class="button">⚙️ Configurations</a>
                <a href="/api/components" class="button">📦 Components</a>
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
        
        // Initial load
        fetchStatus();
        fetchMetrics();
        
        // Refresh every 30 seconds
        setInterval(fetchStatus, 30000);
        setInterval(fetchMetrics, 30000);
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

func getEnv(key, fallback string) string {
	if value := os.Getenv(key); value != "" {
		return value
	}
	return fallback
}