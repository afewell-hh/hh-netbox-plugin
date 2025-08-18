package monitoring

import (
	"context"
	"fmt"
	"net/http"
	"time"

	"go.opentelemetry.io/otel"
	"go.opentelemetry.io/otel/attribute"
	"go.opentelemetry.io/otel/codes"
	"go.opentelemetry.io/otel/exporters/otlp/otlptrace/otlptracehttp"
	"go.opentelemetry.io/otel/propagation"
	"go.opentelemetry.io/otel/sdk/resource"
	sdktrace "go.opentelemetry.io/otel/sdk/trace"
	semconv "go.opentelemetry.io/otel/semconv/v1.21.0"
	"go.opentelemetry.io/otel/trace"
)

const (
	// Service name for tracing
	ServiceName = "cnoc"
	
	// Span names for common operations
	SpanNameHTTPRequest     = "http_request"
	SpanNameSyncOperation   = "sync_operation"
	SpanNameDriftDetection  = "drift_detection"
	SpanNameDatabaseQuery   = "database_query"
	SpanNameCacheOperation  = "cache_operation"
	SpanNameEventProcessing = "event_processing"
	SpanNameAPICall         = "api_call"
)

// TracingConfig holds tracing configuration
type TracingConfig struct {
	Enabled      bool
	OTLPEndpoint string
	ServiceName  string
	Environment  string
	SamplingRate float64
}

// TracingProvider manages OpenTelemetry tracing setup and lifecycle
type TracingProvider struct {
	config     *TracingConfig
	tracer     trace.Tracer
	provider   *sdktrace.TracerProvider
	propagator propagation.TextMapPropagator
}

// NewTracingProvider creates a new tracing provider with FORGE Movement 7 requirements
func NewTracingProvider(config *TracingConfig) (*TracingProvider, error) {
	if !config.Enabled {
		return &TracingProvider{
			config: config,
			tracer: otel.Tracer(config.ServiceName),
		}, nil
	}
	
	// Create OTLP exporter
	exporter, err := otlptracehttp.New(context.Background(),
		otlptracehttp.WithEndpoint(config.OTLPEndpoint),
		otlptracehttp.WithInsecure(), // For development - use TLS in production
	)
	if err != nil {
		return nil, fmt.Errorf("failed to create OTLP exporter: %w", err)
	}
	
	// Create resource
	res, err := resource.New(context.Background(),
		resource.WithAttributes(
			semconv.ServiceNameKey.String(config.ServiceName),
			semconv.ServiceVersionKey.String("1.0.0"),
			semconv.DeploymentEnvironmentKey.String(config.Environment),
			attribute.String("forge.movement", "7"),
			attribute.String("forge.category", "infrastructure"),
		),
	)
	if err != nil {
		return nil, fmt.Errorf("failed to create resource: %w", err)
	}
	
	// Create sampler based on configuration
	var sampler sdktrace.Sampler
	if config.SamplingRate >= 1.0 {
		sampler = sdktrace.AlwaysSample()
	} else if config.SamplingRate <= 0.0 {
		sampler = sdktrace.NeverSample()
	} else {
		sampler = sdktrace.TraceIDRatioBased(config.SamplingRate)
	}
	
	// Create trace provider
	provider := sdktrace.NewTracerProvider(
		sdktrace.WithBatcher(exporter),
		sdktrace.WithResource(res),
		sdktrace.WithSampler(sampler),
	)
	
	// Set global provider
	otel.SetTracerProvider(provider)
	
	// Set global propagator
	propagator := propagation.NewCompositeTextMapPropagator(
		propagation.TraceContext{},
		propagation.Baggage{},
	)
	otel.SetTextMapPropagator(propagator)
	
	// Get tracer
	tracer := provider.Tracer(config.ServiceName)
	
	tp := &TracingProvider{
		config:     config,
		tracer:     tracer,
		provider:   provider,
		propagator: propagator,
	}
	
	return tp, nil
}

// Tracer returns the OpenTelemetry tracer
func (tp *TracingProvider) Tracer() trace.Tracer {
	return tp.tracer
}

// Propagator returns the text map propagator
func (tp *TracingProvider) Propagator() propagation.TextMapPropagator {
	return tp.propagator
}

// Shutdown gracefully shuts down the tracing provider
func (tp *TracingProvider) Shutdown(ctx context.Context) error {
	if tp.provider != nil {
		return tp.provider.Shutdown(ctx)
	}
	return nil
}

// StartSpan starts a new span with common attributes
func (tp *TracingProvider) StartSpan(ctx context.Context, operationName string, opts ...trace.SpanStartOption) (context.Context, trace.Span) {
	spanOpts := []trace.SpanStartOption{
		trace.WithAttributes(
			attribute.String("service.name", tp.config.ServiceName),
			attribute.String("service.version", "1.0.0"),
			attribute.String("forge.movement", "7"),
		),
	}
	spanOpts = append(spanOpts, opts...)
	
	return tp.tracer.Start(ctx, operationName, spanOpts...)
}

// HTTPMiddleware provides HTTP request tracing
func (tp *TracingProvider) HTTPMiddleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if !tp.config.Enabled {
			next.ServeHTTP(w, r)
			return
		}
		
		// Extract trace context from headers
		ctx := tp.propagator.Extract(r.Context(), propagation.HeaderCarrier(r.Header))
		
		// Start HTTP span
		spanCtx, span := tp.StartSpan(ctx, SpanNameHTTPRequest,
			trace.WithAttributes(
				semconv.HTTPMethodKey.String(r.Method),
				semconv.HTTPURLKey.String(r.URL.String()),
				semconv.HTTPSchemeKey.String(r.URL.Scheme),
				semconv.HTTPTargetKey.String(r.URL.Path),
				semconv.UserAgentOriginalKey.String(r.UserAgent()),
			),
			trace.WithSpanKind(trace.SpanKindServer),
		)
		defer span.End()
		
		// Wrap response writer to capture status
		wrapped := &tracingResponseWriter{
			ResponseWriter: w,
			statusCode:     http.StatusOK,
		}
		
		// Add span context to request
		r = r.WithContext(spanCtx)
		
		// Process request
		next.ServeHTTP(wrapped, r)
		
		// Add response attributes
		span.SetAttributes(
			semconv.HTTPStatusCodeKey.Int(wrapped.statusCode),
			attribute.Int64("http.response.size", wrapped.size),
		)
		
		// Set span status based on HTTP status
		if wrapped.statusCode >= 400 {
			span.SetAttributes(attribute.Bool("error", true))
			if wrapped.statusCode >= 500 {
				span.SetStatus(codes.Error, fmt.Sprintf("HTTP %d", wrapped.statusCode))
			}
		}
	})
}

// tracingResponseWriter wraps http.ResponseWriter to capture status and size
type tracingResponseWriter struct {
	http.ResponseWriter
	statusCode int
	size       int64
}

func (w *tracingResponseWriter) WriteHeader(statusCode int) {
	w.statusCode = statusCode
	w.ResponseWriter.WriteHeader(statusCode)
}

func (w *tracingResponseWriter) Write(data []byte) (int, error) {
	n, err := w.ResponseWriter.Write(data)
	w.size += int64(n)
	return n, err
}

// SyncOperationSpan creates a span for sync operations
func (tp *TracingProvider) SyncOperationSpan(ctx context.Context, fabricName, operationType string) (context.Context, trace.Span) {
	return tp.StartSpan(ctx, SpanNameSyncOperation,
		trace.WithAttributes(
			attribute.String("fabric.name", fabricName),
			attribute.String("operation.type", operationType),
			attribute.String("component", "gitops"),
		),
	)
}

// DriftDetectionSpan creates a span for drift detection
func (tp *TracingProvider) DriftDetectionSpan(ctx context.Context, fabricName string) (context.Context, trace.Span) {
	return tp.StartSpan(ctx, SpanNameDriftDetection,
		trace.WithAttributes(
			attribute.String("fabric.name", fabricName),
			attribute.String("component", "drift-detector"),
		),
	)
}

// DatabaseQuerySpan creates a span for database queries
func (tp *TracingProvider) DatabaseQuerySpan(ctx context.Context, query, table string) (context.Context, trace.Span) {
	return tp.StartSpan(ctx, SpanNameDatabaseQuery,
		trace.WithAttributes(
			attribute.String("db.statement", query),
			attribute.String("db.table", table),
			attribute.String("db.system", "postgresql"),
			attribute.String("component", "database"),
		),
	)
}

// CacheOperationSpan creates a span for cache operations
func (tp *TracingProvider) CacheOperationSpan(ctx context.Context, operation, key string) (context.Context, trace.Span) {
	return tp.StartSpan(ctx, SpanNameCacheOperation,
		trace.WithAttributes(
			attribute.String("cache.operation", operation),
			attribute.String("cache.key", key),
			attribute.String("cache.system", "redis"),
			attribute.String("component", "cache"),
		),
	)
}

// EventProcessingSpan creates a span for event processing
func (tp *TracingProvider) EventProcessingSpan(ctx context.Context, eventType, eventID string) (context.Context, trace.Span) {
	return tp.StartSpan(ctx, SpanNameEventProcessing,
		trace.WithAttributes(
			attribute.String("event.type", eventType),
			attribute.String("event.id", eventID),
			attribute.String("component", "event-processor"),
		),
	)
}

// APICallSpan creates a span for external API calls
func (tp *TracingProvider) APICallSpan(ctx context.Context, service, endpoint, method string) (context.Context, trace.Span) {
	return tp.StartSpan(ctx, SpanNameAPICall,
		trace.WithAttributes(
			attribute.String("service.name", service),
			attribute.String("http.method", method),
			attribute.String("http.url", endpoint),
			attribute.String("component", "http-client"),
		),
		trace.WithSpanKind(trace.SpanKindClient),
	)
}

// AddSpanEvent adds an event to the current span
func (tp *TracingProvider) AddSpanEvent(ctx context.Context, name string, attributes ...attribute.KeyValue) {
	span := trace.SpanFromContext(ctx)
	if span != nil {
		span.AddEvent(name, trace.WithAttributes(attributes...))
	}
}

// AddSpanAttributes adds attributes to the current span
func (tp *TracingProvider) AddSpanAttributes(ctx context.Context, attributes ...attribute.KeyValue) {
	span := trace.SpanFromContext(ctx)
	if span != nil {
		span.SetAttributes(attributes...)
	}
}

// SetSpanError marks the current span as an error
func (tp *TracingProvider) SetSpanError(ctx context.Context, err error) {
	span := trace.SpanFromContext(ctx)
	if span != nil {
		span.SetAttributes(attribute.Bool("error", true))
		span.SetStatus(codes.Error, err.Error())
		span.RecordError(err)
	}
}

// TraceableHTTPClient creates an HTTP client with tracing
func (tp *TracingProvider) TraceableHTTPClient() *http.Client {
	return &http.Client{
		Transport: &tracingTransport{
			base:     http.DefaultTransport,
			provider: tp,
		},
		Timeout: 30 * time.Second,
	}
}

// tracingTransport wraps http.RoundTripper to add tracing
type tracingTransport struct {
	base     http.RoundTripper
	provider *TracingProvider
}

func (t *tracingTransport) RoundTrip(req *http.Request) (*http.Response, error) {
	if !t.provider.config.Enabled {
		return t.base.RoundTrip(req)
	}
	
	ctx, span := t.provider.APICallSpan(req.Context(), 
		req.URL.Host, req.URL.String(), req.Method)
	defer span.End()
	
	// Inject trace context into request headers
	t.provider.propagator.Inject(ctx, propagation.HeaderCarrier(req.Header))
	
	// Update request with traced context
	req = req.WithContext(ctx)
	
	// Execute request
	resp, err := t.base.RoundTrip(req)
	
	if err != nil {
		t.provider.SetSpanError(ctx, err)
		return resp, err
	}
	
	// Add response attributes
	span.SetAttributes(
		semconv.HTTPStatusCodeKey.Int(resp.StatusCode),
		attribute.Int64("http.response.size", resp.ContentLength),
	)
	
	if resp.StatusCode >= 400 {
		span.SetAttributes(attribute.Bool("error", true))
		if resp.StatusCode >= 500 {
			span.SetStatus(codes.Error, fmt.Sprintf("HTTP %d", resp.StatusCode))
		}
	}
	
	return resp, nil
}

// MockTracingOperations provides mock tracing operations for testing
func (tp *TracingProvider) MockTracingOperations(ctx context.Context) {
	if !tp.config.Enabled {
		return
	}
	
	go func() {
		ticker := time.NewTicker(5 * time.Second)
		defer ticker.Stop()
		
		for range ticker.C {
			// Mock sync operation
			syncCtx, syncSpan := tp.SyncOperationSpan(ctx, "test-fabric", "sync")
			time.Sleep(100 * time.Millisecond) // Simulate work
			tp.AddSpanEvent(syncCtx, "sync.started")
			time.Sleep(200 * time.Millisecond) // Simulate work
			tp.AddSpanEvent(syncCtx, "sync.completed", 
				attribute.Int("crds.processed", 36),
				attribute.String("status", "success"),
			)
			syncSpan.End()
			
			// Mock drift detection
			driftCtx, driftSpan := tp.DriftDetectionSpan(ctx, "test-fabric")
			time.Sleep(50 * time.Millisecond) // Simulate work
			tp.AddSpanEvent(driftCtx, "drift.analysis.started")
			time.Sleep(150 * time.Millisecond) // Simulate work
			tp.AddSpanEvent(driftCtx, "drift.analysis.completed",
				attribute.Bool("drift.detected", false),
				attribute.Int("resources.checked", 36),
			)
			driftSpan.End()
			
			// Mock database operation
			dbCtx, dbSpan := tp.DatabaseQuerySpan(ctx, "SELECT * FROM configurations", "configurations")
			time.Sleep(25 * time.Millisecond) // Simulate query
			tp.AddSpanEvent(dbCtx, "query.executed",
				attribute.Int("rows.affected", 12),
			)
			dbSpan.End()
			
			// Mock cache operation
			cacheCtx, cacheSpan := tp.CacheOperationSpan(ctx, "GET", "fabric:test-fabric:config")
			time.Sleep(5 * time.Millisecond) // Simulate cache lookup
			tp.AddSpanEvent(cacheCtx, "cache.hit")
			cacheSpan.End()
		}
	}()
}

// DefaultTracingConfig returns default tracing configuration
func DefaultTracingConfig() *TracingConfig {
	return &TracingConfig{
		Enabled:      true,
		OTLPEndpoint: "http://localhost:4318/v1/traces",
		ServiceName:  ServiceName,
		Environment:  "development", 
		SamplingRate: 0.1, // 10% sampling for development
	}
}

// ProductionTracingConfig returns production-ready tracing configuration
func ProductionTracingConfig() *TracingConfig {
	return &TracingConfig{
		Enabled:      true,
		OTLPEndpoint: "http://otel-collector:4318/v1/traces",
		ServiceName:  ServiceName,
		Environment:  "production",
		SamplingRate: 0.01, // 1% sampling for high volume production
	}
}