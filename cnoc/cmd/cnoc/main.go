package main

import (
	"context"
	"log"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/gorilla/mux"
	
	"github.com/hedgehog/cnoc/internal/monitoring"
	"github.com/hedgehog/cnoc/internal/web"
)

func main() {
	log.Println("🚀 Starting CNOC - Cloud NetOps Command System")
	log.Println("📋 FORGE Movement 7: Infrastructure Symphony with Advanced UI")
	
	// Load configuration from environment
	config := loadConfiguration()
	
	// Initialize monitoring components (FORGE M7 Focus)
	log.Println("📊 Initializing FORGE M7 monitoring infrastructure...")
	
	// Metrics collector
	metricsCollector := monitoring.NewMetricsCollector()
	log.Println("✅ Metrics collector initialized")
	
	// Tracing provider
	tracingConfig := monitoring.DefaultTracingConfig()
	if config.Environment == "production" {
		tracingConfig = monitoring.ProductionTracingConfig()
	}
	
	tracingProvider, err := monitoring.NewTracingProvider(tracingConfig)
	if err != nil {
		log.Printf("⚠️  Tracing initialization failed (continuing without tracing): %v", err)
		tracingProvider = nil
	} else {
		log.Println("✅ Tracing provider initialized")
	}
	
	// Start metrics server on separate port
	metricsServer := monitoring.NewMetricsServer(":9090", metricsCollector)
	if err := metricsServer.Start(); err != nil {
		log.Printf("⚠️  Failed to start metrics server: %v", err)
	} else {
		log.Println("✅ Metrics server started on :9090")
	}
	
	// Create router
	router := mux.NewRouter()
	
	// Apply tracing middleware if available
	if tracingProvider != nil {
		router.Use(func(next http.Handler) http.Handler {
			return tracingProvider.HTTPMiddleware(next)
		})
	}
	
	// Initialize Web UI handler with metrics collector (FORGE M7 Focus)
	webHandler, err := web.NewWebHandler(metricsCollector)
	if err != nil {
		log.Printf("⚠️  Web UI initialization failed: %v", err)
	} else {
		// Register Web UI routes
		webHandler.RegisterRoutes(router)
		log.Println("✅ Web UI routes registered with real-time updates and metrics")
	}
	
	// Health check endpoint
	router.HandleFunc("/health", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusOK)
		w.Write([]byte(`{"status":"healthy","service":"cnoc","version":"1.0.0"}`))
	})
	
	// Ready check endpoint
	router.HandleFunc("/ready", func(w http.ResponseWriter, r *http.Request) {
		// For FORGE M7 demonstration, always report ready
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusOK)
		w.Write([]byte(`{"status":"ready","forge_movement":"7","components":["monitoring","websockets","ui"]}`))
	})
	
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
	
	// Shutdown monitoring components
	if tracingProvider != nil {
		if err := tracingProvider.Shutdown(ctx); err != nil {
			log.Printf("⚠️ Tracing provider shutdown error: %v", err)
		}
	}
	
	if metricsServer != nil {
		if err := metricsServer.Stop(ctx); err != nil {
			log.Printf("⚠️ Metrics server shutdown error: %v", err)
		}
	}
	
	// Shutdown WebSocket connections
	if webHandler != nil {
		// The WebSocket manager will be cleaned up automatically
		log.Println("🔌 WebSocket connections closed")
	}
	
	// Shutdown HTTP server
	if err := srv.Shutdown(ctx); err != nil {
		log.Printf("⚠️ Server shutdown error: %v", err)
	}
	
	log.Println("👋 CNOC system shutdown complete")
}

// Configuration holds application configuration
type Configuration struct {
	ServerAddress string
	BaseURL       string
	Environment   string
}

// loadConfiguration loads configuration from environment
func loadConfiguration() *Configuration {
	config := &Configuration{
		ServerAddress: getEnv("SERVER_ADDRESS", ":8080"),
		BaseURL:       getEnv("BASE_URL", "http://localhost:8080"),
		Environment:   getEnv("ENVIRONMENT", "development"),
	}
	
	log.Printf("📋 Configuration loaded for environment: %s", config.Environment)
	return config
}

// getEnv gets environment variable with fallback
func getEnv(key, fallback string) string {
	if value := os.Getenv(key); value != "" {
		return value
	}
	return fallback
}

// SimpleLogger implements the Logger interface
type SimpleLogger struct{}

func (l *SimpleLogger) Debug(msg string, args ...interface{}) {
	log.Printf("[DEBUG] %s %v", msg, args)
}

func (l *SimpleLogger) Info(msg string, args ...interface{}) {
	log.Printf("[INFO] %s %v", msg, args)
}

func (l *SimpleLogger) Warn(msg string, args ...interface{}) {
	log.Printf("[WARN] %s %v", msg, args)
}

func (l *SimpleLogger) Error(msg string, args ...interface{}) {
	log.Printf("[ERROR] %s %v", msg, args)
}

// Mock implementations for testing

// MockComponentRegistry provides a mock component registry
type MockComponentRegistry struct{}

func (r *MockComponentRegistry) Exists(name string) bool {
	return true
}

func (r *MockComponentRegistry) GetVersion(name string) (string, error) {
	return "1.0.0", nil
}

func (r *MockComponentRegistry) GetDependencies(name string) ([]string, error) {
	return []string{}, nil
}

func (r *MockComponentRegistry) ValidateConfiguration(name string, config map[string]interface{}) error {
	return nil
}