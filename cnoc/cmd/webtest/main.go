package main

import (
	"log"
	"net/http"

	"github.com/gorilla/mux"
	"github.com/hedgehog/cnoc/internal/web"
)

func main() {
	log.Println("🚀 Starting CNOC Web Test Server")
	log.Println("📊 Phase 2: Fabric Management Interface Testing")

	// Initialize web handler
	webHandler, err := web.NewWebHandler()
	if err != nil {
		log.Fatalf("❌ Failed to initialize web handler: %v", err)
	}

	// Create router
	router := mux.NewRouter()

	// Register web routes
	webHandler.RegisterRoutes(router)

	// Health check endpoint
	router.HandleFunc("/health", func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
		w.Write([]byte("CNOC Web Interface - Phase 2 Active"))
	}).Methods("GET")

	// Start server
	port := ":8083"
	log.Printf("🌐 Web interface available at http://localhost%s", port)
	log.Printf("📋 Dashboard: http://localhost%s/", port)
	log.Printf("🏭 Fabrics: http://localhost%s/fabrics", port)
	log.Printf("🔧 Health: http://localhost%s/health", port)
	
	log.Printf("✅ CNOC Web Test Server starting on port %s", port)
	
	if err := http.ListenAndServe(port, router); err != nil {
		log.Fatalf("❌ Server failed to start: %v", err)
	}
}