package monitoring

import (
	"context"
	"fmt"
	"net/http"
	"runtime"
	"sync"
	"time"

	"github.com/prometheus/client_golang/prometheus"
	"github.com/prometheus/client_golang/prometheus/promauto"
	"github.com/prometheus/client_golang/prometheus/promhttp"
)

// MetricsCollector provides comprehensive Prometheus metrics collection
type MetricsCollector struct {
	registry *prometheus.Registry
	
	// Business metrics - required by FORGE Movement 7 tests
	apiRequestsTotal       *prometheus.CounterVec
	syncOperationsTotal    *prometheus.CounterVec
	syncDuration          *prometheus.HistogramVec
	fabricCount           prometheus.Gauge
	crdCount              prometheus.Gauge
	driftDetectionsTotal  *prometheus.CounterVec
	
	// HTTP metrics
	httpRequestDuration   *prometheus.HistogramVec
	httpRequestsTotal     *prometheus.CounterVec
	httpRequestSize       *prometheus.HistogramVec
	httpResponseSize      *prometheus.HistogramVec
	
	// System metrics
	memoryUsageBytes      prometheus.Gauge
	cpuUsageSeconds       prometheus.Counter
	goroutineCount        prometheus.Gauge
	
	// Application metrics
	configurationCount    prometheus.Gauge
	eventProcessingTotal  *prometheus.CounterVec
	cacheHitTotal         *prometheus.CounterVec
	
	// Startup metrics
	startupTimeSeconds    prometheus.Gauge
	lastStartupTime       time.Time
	
	mu sync.RWMutex
}

// NewMetricsCollector creates a new metrics collector with all required metrics
func NewMetricsCollector() *MetricsCollector {
	registry := prometheus.NewRegistry()
	
	mc := &MetricsCollector{
		registry:        registry,
		lastStartupTime: time.Now(),
		
		// Business metrics - FORGE Movement 7 requirements
		apiRequestsTotal: promauto.With(registry).NewCounterVec(
			prometheus.CounterOpts{
				Name: "cnoc_api_requests_total",
				Help: "Total number of API requests processed",
			},
			[]string{"method", "endpoint", "status_code"},
		),
		
		syncOperationsTotal: promauto.With(registry).NewCounterVec(
			prometheus.CounterOpts{
				Name: "cnoc_sync_operations_total", 
				Help: "Total number of GitOps sync operations",
			},
			[]string{"fabric_name", "operation_type", "status"},
		),
		
		syncDuration: promauto.With(registry).NewHistogramVec(
			prometheus.HistogramOpts{
				Name:    "cnoc_sync_duration_seconds",
				Help:    "Duration of sync operations in seconds",
				Buckets: prometheus.DefBuckets,
			},
			[]string{"fabric_name", "operation_type"},
		),
		
		fabricCount: promauto.With(registry).NewGauge(
			prometheus.GaugeOpts{
				Name: "cnoc_fabric_count",
				Help: "Total number of managed fabrics",
			},
		),
		
		crdCount: promauto.With(registry).NewGauge(
			prometheus.GaugeOpts{
				Name: "cnoc_crd_count",
				Help: "Total number of managed CRDs",
			},
		),
		
		driftDetectionsTotal: promauto.With(registry).NewCounterVec(
			prometheus.CounterOpts{
				Name: "cnoc_drift_detections_total",
				Help: "Total number of drift detection operations",
			},
			[]string{"fabric_name", "severity", "status"},
		),
		
		// HTTP metrics
		httpRequestDuration: promauto.With(registry).NewHistogramVec(
			prometheus.HistogramOpts{
				Name:    "cnoc_http_request_duration_seconds",
				Help:    "HTTP request duration in seconds",
				Buckets: []float64{.005, .01, .025, .05, .1, .25, .5, 1, 2.5, 5, 10},
			},
			[]string{"method", "endpoint"},
		),
		
		httpRequestsTotal: promauto.With(registry).NewCounterVec(
			prometheus.CounterOpts{
				Name: "cnoc_http_requests_total",
				Help: "Total number of HTTP requests",
			},
			[]string{"method", "endpoint", "status_code"},
		),
		
		httpRequestSize: promauto.With(registry).NewHistogramVec(
			prometheus.HistogramOpts{
				Name:    "cnoc_http_request_size_bytes",
				Help:    "HTTP request size in bytes",
				Buckets: prometheus.ExponentialBuckets(100, 10, 8),
			},
			[]string{"method", "endpoint"},
		),
		
		httpResponseSize: promauto.With(registry).NewHistogramVec(
			prometheus.HistogramOpts{
				Name:    "cnoc_http_response_size_bytes",
				Help:    "HTTP response size in bytes",
				Buckets: prometheus.ExponentialBuckets(100, 10, 8),
			},
			[]string{"method", "endpoint"},
		),
		
		// System metrics
		memoryUsageBytes: promauto.With(registry).NewGauge(
			prometheus.GaugeOpts{
				Name: "cnoc_memory_usage_bytes",
				Help: "Current memory usage in bytes",
			},
		),
		
		cpuUsageSeconds: promauto.With(registry).NewCounter(
			prometheus.CounterOpts{
				Name: "cnoc_cpu_usage_seconds_total",
				Help: "Total CPU usage in seconds",
			},
		),
		
		goroutineCount: promauto.With(registry).NewGauge(
			prometheus.GaugeOpts{
				Name: "cnoc_goroutines",
				Help: "Current number of goroutines",
			},
		),
		
		// Application metrics
		configurationCount: promauto.With(registry).NewGauge(
			prometheus.GaugeOpts{
				Name: "cnoc_configurations_total",
				Help: "Total number of configurations",
			},
		),
		
		eventProcessingTotal: promauto.With(registry).NewCounterVec(
			prometheus.CounterOpts{
				Name: "cnoc_events_processed_total",
				Help: "Total number of events processed",
			},
			[]string{"event_type", "status"},
		),
		
		cacheHitTotal: promauto.With(registry).NewCounterVec(
			prometheus.CounterOpts{
				Name: "cnoc_cache_operations_total", 
				Help: "Total number of cache operations",
			},
			[]string{"operation", "result"},
		),
		
		startupTimeSeconds: promauto.With(registry).NewGauge(
			prometheus.GaugeOpts{
				Name: "cnoc_startup_time_seconds",
				Help: "Application startup time in seconds",
			},
		),
	}
	
	// Register standard Go metrics
	registry.MustRegister(prometheus.NewGoCollector())
	registry.MustRegister(prometheus.NewProcessCollector(prometheus.ProcessCollectorOpts{}))
	
	// Initialize startup time
	mc.startupTimeSeconds.Set(time.Since(mc.lastStartupTime).Seconds())
	
	// Start background metrics collection
	go mc.collectSystemMetrics()
	
	return mc
}

// RecordAPIRequest records an API request with method, endpoint, and status
func (mc *MetricsCollector) RecordAPIRequest(method, endpoint string, statusCode int, duration time.Duration) {
	statusStr := fmt.Sprintf("%d", statusCode)
	
	mc.apiRequestsTotal.WithLabelValues(method, endpoint, statusStr).Inc()
	mc.httpRequestsTotal.WithLabelValues(method, endpoint, statusStr).Inc()
	mc.httpRequestDuration.WithLabelValues(method, endpoint).Observe(duration.Seconds())
}

// RecordSyncOperation records a GitOps sync operation
func (mc *MetricsCollector) RecordSyncOperation(fabricName, operationType, status string, duration time.Duration) {
	mc.syncOperationsTotal.WithLabelValues(fabricName, operationType, status).Inc()
	mc.syncDuration.WithLabelValues(fabricName, operationType).Observe(duration.Seconds())
}

// RecordDriftDetection records a drift detection operation
func (mc *MetricsCollector) RecordDriftDetection(fabricName, severity, status string) {
	mc.driftDetectionsTotal.WithLabelValues(fabricName, severity, status).Inc()
}

// RecordHttpRequestSize records HTTP request size
func (mc *MetricsCollector) RecordHttpRequestSize(method, endpoint string, size float64) {
	mc.httpRequestSize.WithLabelValues(method, endpoint).Observe(size)
}

// RecordHttpResponseSize records HTTP response size
func (mc *MetricsCollector) RecordHttpResponseSize(method, endpoint string, size float64) {
	mc.httpResponseSize.WithLabelValues(method, endpoint).Observe(size)
}

// UpdateFabricCount updates the total fabric count
func (mc *MetricsCollector) UpdateFabricCount(count float64) {
	mc.fabricCount.Set(count)
}

// UpdateCRDCount updates the total CRD count
func (mc *MetricsCollector) UpdateCRDCount(count float64) {
	mc.crdCount.Set(count)
}

// UpdateConfigurationCount updates the total configuration count
func (mc *MetricsCollector) UpdateConfigurationCount(count float64) {
	mc.configurationCount.Set(count)
}

// RecordEventProcessing records event processing
func (mc *MetricsCollector) RecordEventProcessing(eventType, status string) {
	mc.eventProcessingTotal.WithLabelValues(eventType, status).Inc()
}

// RecordCacheOperation records cache operations
func (mc *MetricsCollector) RecordCacheOperation(operation, result string) {
	mc.cacheHitTotal.WithLabelValues(operation, result).Inc()
}

// collectSystemMetrics runs background collection of system metrics
func (mc *MetricsCollector) collectSystemMetrics() {
	ticker := time.NewTicker(15 * time.Second)
	defer ticker.Stop()
	
	var lastCPUTime time.Duration
	
	for range ticker.C {
		// Memory metrics
		var m runtime.MemStats
		runtime.ReadMemStats(&m)
		mc.memoryUsageBytes.Set(float64(m.Alloc))
		
		// Goroutine count
		mc.goroutineCount.Set(float64(runtime.NumGoroutine()))
		
		// CPU usage estimation (simplified)
		currentCPUTime := time.Duration(m.Sys)
		if lastCPUTime > 0 {
			cpuDelta := currentCPUTime - lastCPUTime
			mc.cpuUsageSeconds.Add(cpuDelta.Seconds())
		}
		lastCPUTime = currentCPUTime
	}
}

// Handler returns the HTTP handler for Prometheus metrics
func (mc *MetricsCollector) Handler() http.Handler {
	return promhttp.HandlerFor(
		mc.registry,
		promhttp.HandlerOpts{
			EnableOpenMetrics: true,
		},
	)
}

// Registry returns the Prometheus registry
func (mc *MetricsCollector) Registry() *prometheus.Registry {
	return mc.registry
}

// HTTPMiddleware provides HTTP request/response metrics collection
func (mc *MetricsCollector) HTTPMiddleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		start := time.Now()
		
		// Wrap response writer to capture status and size
		wrapped := &responseWriter{
			ResponseWriter: w,
			statusCode:     http.StatusOK,
			size:          0,
		}
		
		// Record request size
		if r.ContentLength > 0 {
			mc.RecordHttpRequestSize(r.Method, r.URL.Path, float64(r.ContentLength))
		}
		
		// Process request
		next.ServeHTTP(wrapped, r)
		
		// Record metrics
		duration := time.Since(start)
		mc.RecordAPIRequest(r.Method, r.URL.Path, wrapped.statusCode, duration)
		mc.RecordHttpResponseSize(r.Method, r.URL.Path, float64(wrapped.size))
	})
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

// HealthzHandler provides health check endpoint that doesn't affect metrics
func (mc *MetricsCollector) HealthzHandler() http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusOK)
		w.Write([]byte(`{"status":"healthy","service":"cnoc-metrics","version":"1.0.0"}`))
	}
}

// MetricsServer provides a standalone metrics server
type MetricsServer struct {
	collector *MetricsCollector
	server    *http.Server
	mu        sync.RWMutex
}

// NewMetricsServer creates a new metrics server
func NewMetricsServer(addr string, collector *MetricsCollector) *MetricsServer {
	mux := http.NewServeMux()
	
	// Metrics endpoint
	mux.Handle("/metrics", collector.Handler())
	
	// Health check endpoint (doesn't count towards metrics)
	mux.HandleFunc("/healthz", collector.HealthzHandler())
	
	server := &http.Server{
		Addr:         addr,
		Handler:      mux,
		ReadTimeout:  10 * time.Second,
		WriteTimeout: 10 * time.Second,
		IdleTimeout:  60 * time.Second,
	}
	
	return &MetricsServer{
		collector: collector,
		server:    server,
	}
}

// Start starts the metrics server
func (ms *MetricsServer) Start() error {
	ms.mu.Lock()
	defer ms.mu.Unlock()
	
	go func() {
		if err := ms.server.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			fmt.Printf("Metrics server error: %v\n", err)
		}
	}()
	
	return nil
}

// Stop stops the metrics server gracefully
func (ms *MetricsServer) Stop(ctx context.Context) error {
	ms.mu.Lock()
	defer ms.mu.Unlock()
	
	return ms.server.Shutdown(ctx)
}

// MockBusinessOperations provides mock business operations for testing
func (mc *MetricsCollector) MockBusinessOperations() {
	// Simulate some initial business state
	mc.UpdateFabricCount(5)
	mc.UpdateCRDCount(36)
	mc.UpdateConfigurationCount(12)
	
	// Simulate some operations
	go func() {
		ticker := time.NewTicker(10 * time.Second)
		defer ticker.Stop()
		
		operationCount := 0
		for range ticker.C {
			operationCount++
			
			// Simulate sync operations
			mc.RecordSyncOperation("test-fabric", "sync", "success", time.Duration(operationCount%3)*time.Second)
			
			// Simulate drift detections
			if operationCount%5 == 0 {
				mc.RecordDriftDetection("test-fabric", "low", "detected")
			}
			
			// Simulate events
			mc.RecordEventProcessing("configuration_changed", "success")
			mc.RecordCacheOperation("get", "hit")
			
			// Update counts occasionally
			if operationCount%10 == 0 {
				mc.UpdateCRDCount(36 + float64(operationCount%10))
			}
		}
	}()
}