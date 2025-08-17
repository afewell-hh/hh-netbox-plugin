package middleware

import (
	"compress/gzip"
	"context"
	"fmt"
	"net/http"
	"runtime/debug"
	"strings"
	"sync"
	"time"

	"github.com/google/uuid"
	"golang.org/x/time/rate"
)

// Middleware key types for context values
type contextKey string

const (
	RequestIDKey contextKey = "request-id"
	UserIDKey    contextKey = "user-id"
	TenantIDKey  contextKey = "tenant-id"
	StartTimeKey contextKey = "start-time"
)

// RequestID middleware adds a unique request ID to each request
func RequestID(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		// Check for existing request ID in header
		requestID := r.Header.Get("X-Request-ID")
		if requestID == "" {
			requestID = uuid.New().String()
		}

		// Add request ID to context
		ctx := context.WithValue(r.Context(), RequestIDKey, requestID)
		
		// Add request ID to response header
		w.Header().Set("X-Request-ID", requestID)
		
		// Continue with updated context
		next.ServeHTTP(w, r.WithContext(ctx))
	})
}

// Logging middleware provides structured logging for all requests
func Logging(logger Logger) func(http.Handler) http.Handler {
	return func(next http.Handler) http.Handler {
		return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			startTime := time.Now()
			
			// Create response wrapper to capture status code
			wrapped := &responseWrapper{
				ResponseWriter: w,
				statusCode:    http.StatusOK,
			}
			
			// Add start time to context
			ctx := context.WithValue(r.Context(), StartTimeKey, startTime)
			
			// Log request start
			logger.Info("Request started",
				"method", r.Method,
				"path", r.URL.Path,
				"remote_addr", r.RemoteAddr,
				"request_id", GetRequestID(r.Context()),
			)
			
			// Process request
			next.ServeHTTP(wrapped, r.WithContext(ctx))
			
			// Log request completion
			duration := time.Since(startTime)
			logger.Info("Request completed",
				"method", r.Method,
				"path", r.URL.Path,
				"status", wrapped.statusCode,
				"duration_ms", duration.Milliseconds(),
				"request_id", GetRequestID(r.Context()),
			)
		})
	}
}

// Metrics middleware collects metrics for all requests
func Metrics(collector MetricsCollector) func(http.Handler) http.Handler {
	return func(next http.Handler) http.Handler {
		return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			startTime := time.Now()
			
			// Create response wrapper to capture metrics
			wrapped := &responseWrapper{
				ResponseWriter: w,
				statusCode:    http.StatusOK,
			}
			
			// Process request
			next.ServeHTTP(wrapped, r)
			
			// Record metrics
			duration := time.Since(startTime)
			collector.RecordHTTPRequest(
				r.Method,
				r.URL.Path,
				wrapped.statusCode,
				duration,
			)
		})
	}
}

// ErrorRecovery middleware handles panics and converts them to HTTP errors
func ErrorRecovery(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		defer func() {
			if err := recover(); err != nil {
				// Log the panic and stack trace
				stack := debug.Stack()
				fmt.Printf("Panic recovered: %v\n%s\n", err, stack)
				
				// Return internal server error
				w.Header().Set("Content-Type", "application/json")
				w.WriteHeader(http.StatusInternalServerError)
				w.Write([]byte(`{"error":"Internal Server Error","message":"An unexpected error occurred","code":"PANIC_RECOVERED"}`))
			}
		}()
		
		next.ServeHTTP(w, r)
	})
}

// RateLimiting middleware implements rate limiting per client
func RateLimiting(next http.Handler) http.Handler {
	// Create rate limiters per IP
	limiters := make(map[string]*rate.Limiter)
	var limitersMutex sync.RWMutex
	
	// Clean up old limiters periodically
	go func() {
		ticker := time.NewTicker(1 * time.Minute)
		defer ticker.Stop()
		
		for range ticker.C {
			limitersMutex.Lock()
			// Clean up limiters not used in last 5 minutes
			// Implementation would track last used time
			limitersMutex.Unlock()
		}
	}()
	
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		// Get client IP
		clientIP := getClientIP(r)
		
		// Get or create limiter for this IP
		limitersMutex.Lock()
		limiter, exists := limiters[clientIP]
		if !exists {
			// 100 requests per second with burst of 200
			limiter = rate.NewLimiter(100, 200)
			limiters[clientIP] = limiter
		}
		limitersMutex.Unlock()
		
		// Check rate limit
		if !limiter.Allow() {
			w.Header().Set("Content-Type", "application/json")
			w.Header().Set("X-RateLimit-Limit", "100")
			w.Header().Set("X-RateLimit-Remaining", "0")
			w.Header().Set("X-RateLimit-Reset", fmt.Sprintf("%d", time.Now().Add(time.Second).Unix()))
			w.WriteHeader(http.StatusTooManyRequests)
			w.Write([]byte(`{"error":"Too Many Requests","message":"Rate limit exceeded","code":"RATE_LIMIT_EXCEEDED"}`))
			return
		}
		
		next.ServeHTTP(w, r)
	})
}

// Authentication middleware validates authentication tokens
func Authentication(validator TokenValidator) func(http.Handler) http.Handler {
	return func(next http.Handler) http.Handler {
		return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			// Extract token from header
			authHeader := r.Header.Get("Authorization")
			if authHeader == "" {
				unauthorized(w, "Missing authorization header")
				return
			}
			
			// Validate Bearer token format
			parts := strings.Split(authHeader, " ")
			if len(parts) != 2 || parts[0] != "Bearer" {
				unauthorized(w, "Invalid authorization format")
				return
			}
			
			token := parts[1]
			
			// Validate token
			claims, err := validator.ValidateToken(token)
			if err != nil {
				unauthorized(w, "Invalid token")
				return
			}
			
			// Add user info to context
			ctx := context.WithValue(r.Context(), UserIDKey, claims.UserID)
			ctx = context.WithValue(ctx, TenantIDKey, claims.TenantID)
			
			next.ServeHTTP(w, r.WithContext(ctx))
		})
	}
}

// Authorization middleware checks permissions for the requested resource
func Authorization(checker PermissionChecker) func(http.Handler) http.Handler {
	return func(next http.Handler) http.Handler {
		return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			// Get user ID from context
			userID := GetUserID(r.Context())
			if userID == "" {
				forbidden(w, "User not authenticated")
				return
			}
			
			// Check permission for resource and action
			resource := extractResource(r.URL.Path)
			action := mapMethodToAction(r.Method)
			
			allowed, err := checker.CheckPermission(userID, resource, action)
			if err != nil {
				internalError(w, "Permission check failed")
				return
			}
			
			if !allowed {
				forbidden(w, "Insufficient permissions")
				return
			}
			
			next.ServeHTTP(w, r)
		})
	}
}

// CORS middleware handles Cross-Origin Resource Sharing
func CORS(allowedOrigins []string) func(http.Handler) http.Handler {
	return func(next http.Handler) http.Handler {
		return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			origin := r.Header.Get("Origin")
			
			// Check if origin is allowed
			allowed := false
			for _, allowedOrigin := range allowedOrigins {
				if allowedOrigin == "*" || allowedOrigin == origin {
					allowed = true
					break
				}
			}
			
			if allowed {
				w.Header().Set("Access-Control-Allow-Origin", origin)
				w.Header().Set("Access-Control-Allow-Credentials", "true")
				w.Header().Set("Access-Control-Allow-Methods", "GET, POST, PUT, PATCH, DELETE, OPTIONS")
				w.Header().Set("Access-Control-Allow-Headers", "Accept, Authorization, Content-Type, X-Request-ID")
				w.Header().Set("Access-Control-Max-Age", "3600")
			}
			
			// Handle preflight requests
			if r.Method == "OPTIONS" {
				w.WriteHeader(http.StatusNoContent)
				return
			}
			
			next.ServeHTTP(w, r)
		})
	}
}

// Compression middleware compresses responses
func Compression(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		// Check if client accepts gzip
		if !strings.Contains(r.Header.Get("Accept-Encoding"), "gzip") {
			next.ServeHTTP(w, r)
			return
		}
		
		// Create gzip response writer
		gz := &gzipResponseWriter{
			ResponseWriter: w,
		}
		defer gz.Close()
		
		// Set encoding header
		w.Header().Set("Content-Encoding", "gzip")
		
		next.ServeHTTP(gz, r)
	})
}

// Timeout middleware adds request timeout
func Timeout(duration time.Duration) func(http.Handler) http.Handler {
	return func(next http.Handler) http.Handler {
		return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			ctx, cancel := context.WithTimeout(r.Context(), duration)
			defer cancel()
			
			done := make(chan struct{})
			
			go func() {
				next.ServeHTTP(w, r.WithContext(ctx))
				close(done)
			}()
			
			select {
			case <-done:
				// Request completed
			case <-ctx.Done():
				// Timeout occurred
				w.Header().Set("Content-Type", "application/json")
				w.WriteHeader(http.StatusGatewayTimeout)
				w.Write([]byte(`{"error":"Gateway Timeout","message":"Request timeout","code":"REQUEST_TIMEOUT"}`))
			}
		})
	}
}

// Helper functions

// GetRequestID retrieves request ID from context
func GetRequestID(ctx context.Context) string {
	if id, ok := ctx.Value(RequestIDKey).(string); ok {
		return id
	}
	return ""
}

// GetUserID retrieves user ID from context
func GetUserID(ctx context.Context) string {
	if id, ok := ctx.Value(UserIDKey).(string); ok {
		return id
	}
	return ""
}

// GetTenantID retrieves tenant ID from context
func GetTenantID(ctx context.Context) string {
	if id, ok := ctx.Value(TenantIDKey).(string); ok {
		return id
	}
	return ""
}

// getClientIP extracts client IP from request
func getClientIP(r *http.Request) string {
	// Check X-Forwarded-For header
	if xff := r.Header.Get("X-Forwarded-For"); xff != "" {
		parts := strings.Split(xff, ",")
		return strings.TrimSpace(parts[0])
	}
	
	// Check X-Real-IP header
	if xri := r.Header.Get("X-Real-IP"); xri != "" {
		return xri
	}
	
	// Fall back to RemoteAddr
	parts := strings.Split(r.RemoteAddr, ":")
	return parts[0]
}

// extractResource extracts resource name from path
func extractResource(path string) string {
	parts := strings.Split(path, "/")
	if len(parts) >= 4 {
		return parts[3] // e.g., /api/v1/configurations -> configurations
	}
	return ""
}

// mapMethodToAction maps HTTP method to action
func mapMethodToAction(method string) string {
	switch method {
	case "GET":
		return "read"
	case "POST":
		return "create"
	case "PUT", "PATCH":
		return "update"
	case "DELETE":
		return "delete"
	default:
		return ""
	}
}

// Error response helpers

func unauthorized(w http.ResponseWriter, message string) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusUnauthorized)
	w.Write([]byte(fmt.Sprintf(`{"error":"Unauthorized","message":"%s","code":"UNAUTHORIZED"}`, message)))
}

func forbidden(w http.ResponseWriter, message string) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusForbidden)
	w.Write([]byte(fmt.Sprintf(`{"error":"Forbidden","message":"%s","code":"FORBIDDEN"}`, message)))
}

func internalError(w http.ResponseWriter, message string) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusInternalServerError)
	w.Write([]byte(fmt.Sprintf(`{"error":"Internal Server Error","message":"%s","code":"INTERNAL_ERROR"}`, message)))
}

// responseWrapper wraps http.ResponseWriter to capture status code
type responseWrapper struct {
	http.ResponseWriter
	statusCode int
	written    bool
}

func (w *responseWrapper) WriteHeader(statusCode int) {
	if !w.written {
		w.statusCode = statusCode
		w.written = true
		w.ResponseWriter.WriteHeader(statusCode)
	}
}

func (w *responseWrapper) Write(b []byte) (int, error) {
	if !w.written {
		w.WriteHeader(http.StatusOK)
	}
	return w.ResponseWriter.Write(b)
}

// gzipResponseWriter implements gzip compression
type gzipResponseWriter struct {
	http.ResponseWriter
	writer *gzip.Writer
}

func (w *gzipResponseWriter) Write(b []byte) (int, error) {
	if w.writer == nil {
		w.writer = gzip.NewWriter(w.ResponseWriter)
	}
	return w.writer.Write(b)
}

func (w *gzipResponseWriter) Close() error {
	if w.writer != nil {
		return w.writer.Close()
	}
	return nil
}

// Interfaces for dependency injection

// Logger interface for logging
type Logger interface {
	Debug(msg string, args ...interface{})
	Info(msg string, args ...interface{})
	Warn(msg string, args ...interface{})
	Error(msg string, args ...interface{})
}

// MetricsCollector interface for metrics collection
type MetricsCollector interface {
	RecordHTTPRequest(method, path string, statusCode int, duration time.Duration)
}

// TokenValidator interface for token validation
type TokenValidator interface {
	ValidateToken(token string) (*TokenClaims, error)
}

// TokenClaims represents validated token claims
type TokenClaims struct {
	UserID   string
	TenantID string
	Roles    []string
	Exp      int64
}

// PermissionChecker interface for authorization
type PermissionChecker interface {
	CheckPermission(userID, resource, action string) (bool, error)
}

