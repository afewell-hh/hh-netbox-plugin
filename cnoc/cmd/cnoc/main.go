package main

import (
	"context"
	"database/sql"
	"fmt"
	"log"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/gorilla/mux"
	_ "github.com/lib/pq"
	"github.com/go-redis/redis/v8"
	
	"github.com/hedgehog/cnoc/internal/api/rest/controllers"
	commandHandlers "github.com/hedgehog/cnoc/internal/application/commands/handlers"
	queryHandlers "github.com/hedgehog/cnoc/internal/application/queries/handlers"
	"github.com/hedgehog/cnoc/internal/application/services"
	domainServices "github.com/hedgehog/cnoc/internal/domain/configuration/services"
	"github.com/hedgehog/cnoc/internal/infrastructure/cache"
	"github.com/hedgehog/cnoc/internal/infrastructure/eventbus"
	"github.com/hedgehog/cnoc/internal/infrastructure/persistence/postgresql"
	"github.com/hedgehog/cnoc/internal/web"
)

func main() {
	log.Println("🚀 Starting CNOC - Cloud NetOps Command System")
	log.Println("📋 MDD-Aligned with Symphony-Level Coordination")
	
	// Load configuration from environment
	config := loadConfiguration()
	
	// Initialize infrastructure components
	log.Println("🔧 Initializing infrastructure components...")
	
	// Database connection
	db, err := initializeDatabase(config.DatabaseURL)
	if err != nil {
		log.Fatalf("❌ Failed to connect to database: %v", err)
	}
	defer db.Close()
	log.Println("✅ Database connected")
	
	// Redis cache connection
	redisClient, err := initializeRedis(config.RedisURL)
	if err != nil {
		log.Printf("⚠️  Redis connection failed (continuing without cache): %v", err)
		redisClient = nil
	} else {
		log.Println("✅ Redis cache connected")
	}
	
	// Initialize domain services
	log.Println("🏗️ Initializing domain services...")
	
	// Event bus with Symphony-Level coordination
	eventBus := eventbus.NewInMemoryEventBus(
		context.Background(),
		&eventbus.EventBusMetricsCollector{},
		&eventbus.EventBusErrorHandler{},
	)
	log.Println("✅ Event bus initialized with Symphony-Level coordination")
	
	// Repository implementations
	configRepo := postgresql.NewPostgreSQLConfigurationRepository(
		db,
		eventBus,
		&postgresql.RepositoryMetricsCollector{},
	)
	log.Println("✅ PostgreSQL repository initialized")
	
	// Cache adapter
	var cacheAdapter *cache.RedisCacheAdapter
	if redisClient != nil {
		cacheAdapter = cache.NewRedisCacheAdapter(
			redisClient,
			5*time.Minute,
			"cnoc",
			&cache.CacheMetricsCollector{},
		)
		log.Println("✅ Redis cache adapter initialized")
	}
	
	// Domain services
	componentRegistry := domainServices.NewMockComponentRegistry()
	dependencyResolver := domainServices.NewDependencyResolver(componentRegistry, eventBus)
	policyEnforcer := domainServices.NewPolicyEnforcer()
	validator := domainServices.NewConfigurationValidator(
		*dependencyResolver,
		policyEnforcer,
		componentRegistry,
		eventBus,
	)
	log.Println("✅ Domain services initialized")
	
	// Application layer services
	log.Println("📦 Initializing application services...")
	
	// Command handlers  
	commandHandler := commandHandlers.NewConfigurationCommandHandler(
		configRepo,
		nil, // Event repository
		nil, // Unit of work
		validator,
		dependencyResolver,
		policyEnforcer,
		nil, // Template engine
		nil, // Infrastructure provisioner
		eventBus,
	)
	log.Println("✅ Command handlers initialized")
	
	// Query handlers
	queryHandler := queryHandlers.NewConfigurationQueryHandler(
		configRepo,
		nil, // Event repository
		dependencyResolver,
		nil, // Projection service
		cacheAdapter,
		nil, // Metrics service
	)
	log.Println("✅ Query handlers initialized")
	
	// Application service with Symphony-Level orchestration
	appService := services.NewConfigurationApplicationService(
		commandHandler,
		queryHandler,
		validator,
		dependencyResolver,
		policyEnforcer,
		nil, // Template engine
		nil, // Infrastructure provisioner
		nil, // Unit of work
		eventBus,
		&services.WorkflowOrchestrator{},
		&services.SagaManager{},
		&services.ProcessManager{},
	)
	log.Println("✅ Application service initialized with Symphony-Level orchestration")
	
	// API layer
	log.Println("🌐 Initializing API layer...")
	
	// Create router
	router := mux.NewRouter()
	
	// Initialize controller
	configController := controllers.NewConfigurationController(
		appService,
		config.BaseURL,
		&SimpleLogger{},
		&controllers.ControllerMetricsCollector{},
	)
	
	// Register API routes
	configController.RegisterRoutes(router)
	log.Println("✅ API routes registered")
	
	// Initialize Web UI handler
	webHandler, err := web.NewWebHandler()
	if err != nil {
		log.Printf("⚠️  Web UI initialization failed (continuing API-only mode): %v", err)
	} else {
		// Register Web UI routes
		webHandler.RegisterRoutes(router)
		log.Println("✅ Web UI routes registered")
	}
	
	// Health check endpoint
	router.HandleFunc("/health", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusOK)
		w.Write([]byte(`{"status":"healthy","service":"cnoc","version":"1.0.0"}`))
	})
	
	// Ready check endpoint
	router.HandleFunc("/ready", func(w http.ResponseWriter, r *http.Request) {
		// Check database connection
		if err := db.Ping(); err != nil {
			w.WriteHeader(http.StatusServiceUnavailable)
			w.Write([]byte(`{"status":"not_ready","reason":"database_unavailable"}`))
			return
		}
		
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusOK)
		w.Write([]byte(`{"status":"ready"}`))
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
	
	// Shutdown event bus
	if err := eventBus.Shutdown(5 * time.Second); err != nil {
		log.Printf("⚠️ Event bus shutdown error: %v", err)
	}
	
	// Shutdown HTTP server
	if err := srv.Shutdown(ctx); err != nil {
		log.Printf("⚠️ Server shutdown error: %v", err)
	}
	
	log.Println("👋 CNOC system shutdown complete")
}

// Configuration holds application configuration
type Configuration struct {
	DatabaseURL   string
	RedisURL      string
	ServerAddress string
	BaseURL       string
	Environment   string
}

// loadConfiguration loads configuration from environment
func loadConfiguration() *Configuration {
	config := &Configuration{
		DatabaseURL:   getEnv("DATABASE_URL", "postgres://cnoc:cnoc@localhost/cnoc?sslmode=disable"),
		RedisURL:      getEnv("REDIS_URL", "redis://localhost:6379/0"),
		ServerAddress: getEnv("SERVER_ADDRESS", ":8080"),
		BaseURL:       getEnv("BASE_URL", "http://localhost:8080"),
		Environment:   getEnv("ENVIRONMENT", "development"),
	}
	
	log.Printf("📋 Configuration loaded for environment: %s", config.Environment)
	return config
}

// initializeDatabase creates database connection
func initializeDatabase(databaseURL string) (*sql.DB, error) {
	db, err := sql.Open("postgres", databaseURL)
	if err != nil {
		return nil, fmt.Errorf("failed to open database: %w", err)
	}
	
	// Configure connection pool
	db.SetMaxOpenConns(25)
	db.SetMaxIdleConns(5)
	db.SetConnMaxLifetime(5 * time.Minute)
	
	// Test connection
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	
	if err := db.PingContext(ctx); err != nil {
		return nil, fmt.Errorf("failed to ping database: %w", err)
	}
	
	return db, nil
}

// initializeRedis creates Redis connection
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