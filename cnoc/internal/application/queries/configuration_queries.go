package queries

import (
	"errors"
	"time"
)

// ConfigurationQuery represents the base interface for all configuration queries
// Following CQRS pattern with read model optimization
type ConfigurationQuery interface {
	QueryType() string
	RequestID() string
	Validate() error
}

// GetConfigurationByIDQuery retrieves a configuration by its ID
type GetConfigurationByIDQuery struct {
	ID               string            `json:"id" validate:"required,uuid"`
	IncludeComponents bool             `json:"include_components"`
	IncludeEvents    bool             `json:"include_events"`
	IncludeMetrics   bool             `json:"include_metrics"`
	ProjectionLevel  ProjectionLevel  `json:"projection_level"`
	QueryContext     QueryContext     `json:"query_context"`
}

// ProjectionLevel defines the depth of data projection in query responses
type ProjectionLevel string

const (
	ProjectionLevelMinimal    ProjectionLevel = "minimal"    // Basic info only
	ProjectionLevelStandard   ProjectionLevel = "standard"   // Standard details
	ProjectionLevelDetailed   ProjectionLevel = "detailed"   // Full details
	ProjectionLevelComplete   ProjectionLevel = "complete"   // All available data
)

// QueryContext provides context for query execution
type QueryContext struct {
	UserID          string                 `json:"user_id" validate:"required,uuid"`
	RequestID       string                 `json:"request_id" validate:"required,uuid"`
	Source          string                 `json:"source" validate:"required,oneof=api cli web dashboard"`
	CacheStrategy   CacheStrategy          `json:"cache_strategy"`
	Timeout         int64                  `json:"timeout_ms" validate:"min=100,max=30000"`
	IncludeDebug    bool                   `json:"include_debug"`
	Context         map[string]interface{} `json:"context,omitempty"`
}

// CacheStrategy defines caching behavior for queries
type CacheStrategy string

const (
	CacheStrategyNone     CacheStrategy = "none"      // No caching
	CacheStrategyStandard CacheStrategy = "standard"  // Standard TTL caching
	CacheStrategyAggressive CacheStrategy = "aggressive" // Longer TTL caching
	CacheStrategyForce    CacheStrategy = "force"     // Force cache refresh
)

// QueryType returns the query type
func (q GetConfigurationByIDQuery) QueryType() string {
	return "GetConfigurationByID"
}

// RequestID returns the request identifier
func (q GetConfigurationByIDQuery) RequestID() string {
	return q.QueryContext.RequestID
}

// Validate validates the query
func (q GetConfigurationByIDQuery) Validate() error {
	if q.ID == "" {
		return ErrInvalidQueryData.WithField("id", "required")
	}
	if q.QueryContext.UserID == "" {
		return ErrInvalidQueryData.WithField("query_context.user_id", "required")
	}
	if q.QueryContext.RequestID == "" {
		return ErrInvalidQueryData.WithField("query_context.request_id", "required")
	}
	if q.QueryContext.Timeout <= 0 {
		return ErrInvalidQueryData.WithField("query_context.timeout_ms", "must be positive")
	}
	return nil
}

// GetConfigurationByNameQuery retrieves a configuration by its name
type GetConfigurationByNameQuery struct {
	Name            string           `json:"name" validate:"required,min=1,max=100"`
	IncludeComponents bool           `json:"include_components"`
	IncludeHistory  bool           `json:"include_history"`
	ProjectionLevel ProjectionLevel `json:"projection_level"`
	QueryContext    QueryContext    `json:"query_context"`
}

// QueryType returns the query type
func (q GetConfigurationByNameQuery) QueryType() string {
	return "GetConfigurationByName"
}

// RequestID returns the request identifier
func (q GetConfigurationByNameQuery) RequestID() string {
	return q.QueryContext.RequestID
}

// Validate validates the query
func (q GetConfigurationByNameQuery) Validate() error {
	if q.Name == "" {
		return ErrInvalidQueryData.WithField("name", "required")
	}
	if q.QueryContext.UserID == "" {
		return ErrInvalidQueryData.WithField("query_context.user_id", "required")
	}
	if q.QueryContext.RequestID == "" {
		return ErrInvalidQueryData.WithField("query_context.request_id", "required")
	}
	return nil
}

// ListConfigurationsQuery retrieves configurations with filtering and pagination
type ListConfigurationsQuery struct {
	Filter          ConfigurationFilter `json:"filter"`
	Pagination      PaginationOptions   `json:"pagination"`
	Sorting         SortingOptions      `json:"sorting"`
	ProjectionLevel ProjectionLevel     `json:"projection_level"`
	QueryContext    QueryContext        `json:"query_context"`
}

// ConfigurationFilter provides filtering options for configuration queries
type ConfigurationFilter struct {
	// Basic filters
	IDs     []string `json:"ids,omitempty" validate:"dive,uuid"`
	Names   []string `json:"names,omitempty" validate:"dive,min=1,max=100"`
	Modes   []string `json:"modes,omitempty" validate:"dive,oneof=development staging production enterprise"`
	Statuses []string `json:"statuses,omitempty" validate:"dive,oneof=draft validated deployed failed archived"`

	// Version filters
	VersionFrom string `json:"version_from,omitempty" validate:"omitempty,semver"`
	VersionTo   string `json:"version_to,omitempty" validate:"omitempty,semver"`

	// Time-based filters
	CreatedAfter  *time.Time `json:"created_after,omitempty"`
	CreatedBefore *time.Time `json:"created_before,omitempty"`
	UpdatedAfter  *time.Time `json:"updated_after,omitempty"`
	UpdatedBefore *time.Time `json:"updated_before,omitempty"`

	// Component filters
	HasComponent    string              `json:"has_component,omitempty" validate:"omitempty,min=1,max=100"`
	ComponentCount  *ComponentCountFilter `json:"component_count,omitempty"`
	EnabledOnly     bool                `json:"enabled_only"`
	DisabledOnly    bool                `json:"disabled_only"`

	// Enterprise filters
	ComplianceFramework string `json:"compliance_framework,omitempty" validate:"omitempty,oneof=SOC2 HIPAA PCI-DSS ISO27001 FedRAMP"`
	SecurityLevel       string `json:"security_level,omitempty" validate:"omitempty,oneof=basic standard high critical"`
	AuditEnabled        *bool  `json:"audit_enabled,omitempty"`
	EncryptionRequired  *bool  `json:"encryption_required,omitempty"`

	// Metadata filters
	Labels      map[string]string `json:"labels,omitempty" validate:"dive,keys,alphanum,endkeys,alphanum"`
	Annotations map[string]string `json:"annotations,omitempty" validate:"dive,keys,alphanum,endkeys,printascii"`

	// Search filters
	SearchTerm string   `json:"search_term,omitempty" validate:"omitempty,max=200"`
	SearchFields []string `json:"search_fields,omitempty" validate:"omitempty,dive,oneof=name description labels annotations"`

	// Advanced filters
	CustomFilters map[string]interface{} `json:"custom_filters,omitempty"`
}

// ComponentCountFilter provides component count filtering
type ComponentCountFilter struct {
	Min *int `json:"min,omitempty" validate:"omitempty,min=0"`
	Max *int `json:"max,omitempty" validate:"omitempty,min=0"`
}

// PaginationOptions provides pagination control
type PaginationOptions struct {
	Offset    int  `json:"offset" validate:"min=0"`
	Limit     int  `json:"limit" validate:"min=1,max=1000"`
	Cursor    string `json:"cursor,omitempty"`
	UseCursor bool `json:"use_cursor"`
}

// SortingOptions provides sorting control
type SortingOptions struct {
	SortBy    []SortField `json:"sort_by" validate:"dive"`
	SortOrder SortOrder   `json:"sort_order" validate:"oneof=asc desc"`
}

// SortField defines a field to sort by
type SortField struct {
	Field     string    `json:"field" validate:"required,oneof=name version created_at updated_at status mode component_count"`
	Direction SortOrder `json:"direction" validate:"oneof=asc desc"`
}

// SortOrder defines sort direction
type SortOrder string

const (
	SortOrderAsc  SortOrder = "asc"
	SortOrderDesc SortOrder = "desc"
)

// QueryType returns the query type
func (q ListConfigurationsQuery) QueryType() string {
	return "ListConfigurations"
}

// RequestID returns the request identifier
func (q ListConfigurationsQuery) RequestID() string {
	return q.QueryContext.RequestID
}

// Validate validates the query
func (q ListConfigurationsQuery) Validate() error {
	if q.Pagination.Limit <= 0 {
		return ErrInvalidQueryData.WithField("pagination.limit", "must be positive")
	}
	if q.Pagination.Limit > 1000 {
		return ErrInvalidQueryData.WithField("pagination.limit", "must not exceed 1000")
	}
	if q.Pagination.Offset < 0 {
		return ErrInvalidQueryData.WithField("pagination.offset", "must be non-negative")
	}
	if q.QueryContext.UserID == "" {
		return ErrInvalidQueryData.WithField("query_context.user_id", "required")
	}
	if q.QueryContext.RequestID == "" {
		return ErrInvalidQueryData.WithField("query_context.request_id", "required")
	}
	return nil
}

// GetConfigurationEventsQuery retrieves events for a configuration
type GetConfigurationEventsQuery struct {
	ConfigurationID string           `json:"configuration_id" validate:"required,uuid"`
	EventFilter     EventFilter      `json:"event_filter"`
	Pagination      PaginationOptions `json:"pagination"`
	ProjectionLevel ProjectionLevel  `json:"projection_level"`
	QueryContext    QueryContext     `json:"query_context"`
}

// EventFilter provides filtering for configuration events
type EventFilter struct {
	EventTypes     []string   `json:"event_types,omitempty" validate:"dive,min=1"`
	OccurredAfter  *time.Time `json:"occurred_after,omitempty"`
	OccurredBefore *time.Time `json:"occurred_before,omitempty"`
	Severity       []string   `json:"severity,omitempty" validate:"dive,oneof=info warning error critical"`
	Source         string     `json:"source,omitempty" validate:"omitempty,min=1"`
	UserID         string     `json:"user_id,omitempty" validate:"omitempty,uuid"`
}

// QueryType returns the query type
func (q GetConfigurationEventsQuery) QueryType() string {
	return "GetConfigurationEvents"
}

// RequestID returns the request identifier
func (q GetConfigurationEventsQuery) RequestID() string {
	return q.QueryContext.RequestID
}

// Validate validates the query
func (q GetConfigurationEventsQuery) Validate() error {
	if q.ConfigurationID == "" {
		return ErrInvalidQueryData.WithField("configuration_id", "required")
	}
	if q.QueryContext.UserID == "" {
		return ErrInvalidQueryData.WithField("query_context.user_id", "required")
	}
	if q.QueryContext.RequestID == "" {
		return ErrInvalidQueryData.WithField("query_context.request_id", "required")
	}
	return nil
}

// GetConfigurationMetricsQuery retrieves performance and usage metrics
type GetConfigurationMetricsQuery struct {
	ConfigurationID string           `json:"configuration_id" validate:"required,uuid"`
	MetricTypes     []string         `json:"metric_types" validate:"dive,oneof=performance usage resource_utilization deployment_frequency"`
	TimeRange       TimeRange        `json:"time_range"`
	Aggregation     AggregationOptions `json:"aggregation"`
	ProjectionLevel ProjectionLevel  `json:"projection_level"`
	QueryContext    QueryContext     `json:"query_context"`
}

// TimeRange defines a time range for metrics queries
type TimeRange struct {
	StartTime time.Time `json:"start_time" validate:"required"`
	EndTime   time.Time `json:"end_time" validate:"required,gtfield=StartTime"`
	Interval  string    `json:"interval" validate:"required,oneof=1m 5m 15m 30m 1h 6h 12h 24h"`
}

// AggregationOptions defines aggregation behavior for metrics
type AggregationOptions struct {
	Function string   `json:"function" validate:"required,oneof=avg sum min max count p50 p95 p99"`
	GroupBy  []string `json:"group_by,omitempty" validate:"dive,oneof=component mode environment time"`
}

// QueryType returns the query type
func (q GetConfigurationMetricsQuery) QueryType() string {
	return "GetConfigurationMetrics"
}

// RequestID returns the request identifier
func (q GetConfigurationMetricsQuery) RequestID() string {
	return q.QueryContext.RequestID
}

// Validate validates the query
func (q GetConfigurationMetricsQuery) Validate() error {
	if q.ConfigurationID == "" {
		return ErrInvalidQueryData.WithField("configuration_id", "required")
	}
	if q.TimeRange.StartTime.IsZero() {
		return ErrInvalidQueryData.WithField("time_range.start_time", "required")
	}
	if q.TimeRange.EndTime.IsZero() {
		return ErrInvalidQueryData.WithField("time_range.end_time", "required")
	}
	if q.TimeRange.EndTime.Before(q.TimeRange.StartTime) {
		return ErrInvalidQueryData.WithField("time_range.end_time", "must be after start_time")
	}
	if q.QueryContext.UserID == "" {
		return ErrInvalidQueryData.WithField("query_context.user_id", "required")
	}
	if q.QueryContext.RequestID == "" {
		return ErrInvalidQueryData.WithField("query_context.request_id", "required")
	}
	return nil
}

// GetConfigurationDependenciesQuery retrieves dependency information
type GetConfigurationDependenciesQuery struct {
	ConfigurationID   string           `json:"configuration_id" validate:"required,uuid"`
	DependencyType    string           `json:"dependency_type" validate:"required,oneof=direct transitive all reverse"`
	IncludeResolution bool             `json:"include_resolution"`
	IncludeConflicts  bool             `json:"include_conflicts"`
	Depth             int              `json:"depth" validate:"min=1,max=10"`
	ProjectionLevel   ProjectionLevel  `json:"projection_level"`
	QueryContext      QueryContext     `json:"query_context"`
}

// QueryType returns the query type
func (q GetConfigurationDependenciesQuery) QueryType() string {
	return "GetConfigurationDependencies"
}

// RequestID returns the request identifier
func (q GetConfigurationDependenciesQuery) RequestID() string {
	return q.QueryContext.RequestID
}

// Validate validates the query
func (q GetConfigurationDependenciesQuery) Validate() error {
	if q.ConfigurationID == "" {
		return ErrInvalidQueryData.WithField("configuration_id", "required")
	}
	if q.DependencyType == "" {
		return ErrInvalidQueryData.WithField("dependency_type", "required")
	}
	if q.Depth < 1 || q.Depth > 10 {
		return ErrInvalidQueryData.WithField("depth", "must be between 1 and 10")
	}
	if q.QueryContext.UserID == "" {
		return ErrInvalidQueryData.WithField("query_context.user_id", "required")
	}
	if q.QueryContext.RequestID == "" {
		return ErrInvalidQueryData.WithField("query_context.request_id", "required")
	}
	return nil
}

// GetConfigurationComplianceQuery retrieves compliance status and details
type GetConfigurationComplianceQuery struct {
	ConfigurationID string           `json:"configuration_id" validate:"required,uuid"`
	Framework       string           `json:"framework" validate:"required,oneof=SOC2 HIPAA PCI-DSS ISO27001 FedRAMP all"`
	IncludeDetails  bool             `json:"include_details"`
	IncludeHistory  bool             `json:"include_history"`
	ProjectionLevel ProjectionLevel  `json:"projection_level"`
	QueryContext    QueryContext     `json:"query_context"`
}

// QueryType returns the query type
func (q GetConfigurationComplianceQuery) QueryType() string {
	return "GetConfigurationCompliance"
}

// RequestID returns the request identifier
func (q GetConfigurationComplianceQuery) RequestID() string {
	return q.QueryContext.RequestID
}

// Validate validates the query
func (q GetConfigurationComplianceQuery) Validate() error {
	if q.ConfigurationID == "" {
		return ErrInvalidQueryData.WithField("configuration_id", "required")
	}
	if q.Framework == "" {
		return ErrInvalidQueryData.WithField("framework", "required")
	}
	if q.QueryContext.UserID == "" {
		return ErrInvalidQueryData.WithField("query_context.user_id", "required")
	}
	if q.QueryContext.RequestID == "" {
		return ErrInvalidQueryData.WithField("query_context.request_id", "required")
	}
	return nil
}

// QueryResult represents the result of query execution
type QueryResult[T any] struct {
	Success     bool                   `json:"success"`
	Data        T                      `json:"data,omitempty"`
	Metadata    QueryResultMetadata    `json:"metadata"`
	Pagination  *PaginationResult      `json:"pagination,omitempty"`
	Cache       CacheInfo              `json:"cache_info"`
	Performance PerformanceMetrics     `json:"performance"`
	Warnings    []QueryWarning         `json:"warnings,omitempty"`
	Errors      []QueryError           `json:"errors,omitempty"`
	RequestID   string                 `json:"request_id"`
}

// QueryResultMetadata provides metadata about query execution
type QueryResultMetadata struct {
	QueryType       string                 `json:"query_type"`
	ExecutedAt      time.Time              `json:"executed_at"`
	UserID          string                 `json:"user_id"`
	Source          string                 `json:"source"`
	ProjectionLevel ProjectionLevel        `json:"projection_level"`
	TotalCount      int64                  `json:"total_count,omitempty"`
	FilteredCount   int64                  `json:"filtered_count,omitempty"`
	Context         map[string]interface{} `json:"context,omitempty"`
}

// PaginationResult provides pagination information
type PaginationResult struct {
	CurrentOffset int     `json:"current_offset"`
	CurrentLimit  int     `json:"current_limit"`
	TotalCount    int64   `json:"total_count"`
	HasMore       bool    `json:"has_more"`
	NextCursor    string  `json:"next_cursor,omitempty"`
	PrevCursor    string  `json:"prev_cursor,omitempty"`
}

// CacheInfo provides information about cache usage
type CacheInfo struct {
	CacheHit       bool          `json:"cache_hit"`
	CacheStrategy  CacheStrategy `json:"cache_strategy"`
	TTL            int64         `json:"ttl_seconds,omitempty"`
	CacheKey       string        `json:"cache_key,omitempty"`
	CacheTimestamp *time.Time    `json:"cache_timestamp,omitempty"`
}

// PerformanceMetrics provides query performance information
type PerformanceMetrics struct {
	ExecutionTime   int64   `json:"execution_time_ms"`
	DatabaseTime    int64   `json:"database_time_ms"`
	CacheTime       int64   `json:"cache_time_ms"`
	SerializationTime int64 `json:"serialization_time_ms"`
	TotalTime       int64   `json:"total_time_ms"`
	MemoryUsage     int64   `json:"memory_usage_bytes,omitempty"`
	IndexesUsed     []string `json:"indexes_used,omitempty"`
	QueryPlan       string   `json:"query_plan,omitempty"`
}

// QueryWarning represents a warning from query execution
type QueryWarning struct {
	Code        string                 `json:"code"`
	Message     string                 `json:"message"`
	Field       string                 `json:"field,omitempty"`
	Severity    string                 `json:"severity"`
	Suggestion  string                 `json:"suggestion,omitempty"`
	Context     map[string]interface{} `json:"context,omitempty"`
}

// QueryError represents an error from query execution
type QueryError struct {
	Code        string                 `json:"code"`
	Message     string                 `json:"message"`
	Field       string                 `json:"field,omitempty"`
	Details     map[string]interface{} `json:"details,omitempty"`
	Retryable   bool                   `json:"retryable"`
	Timestamp   time.Time              `json:"timestamp"`
}

// Query validation errors
var (
	ErrInvalidQueryData = &QueryValidationError{
		Type:    "invalid_query_data",
		Message: "query data validation failed",
		Fields:  make(map[string]string),
	}
	
	ErrQueryTimeout = &QueryValidationError{
		Type:    "query_timeout",
		Message: "query execution timeout",
	}
	
	ErrInsufficientPermissions = &QueryValidationError{
		Type:    "insufficient_permissions",
		Message: "insufficient permissions to execute query",
	}
	
	ErrResourceNotFound = &QueryValidationError{
		Type:    "resource_not_found",
		Message: "requested resource not found",
	}
	
	ErrTooManyResults = &QueryValidationError{
		Type:    "too_many_results",
		Message: "query returned too many results",
	}
)

// QueryValidationError represents query validation errors
type QueryValidationError struct {
	Type    string            `json:"type"`
	Message string            `json:"message"`
	Fields  map[string]string `json:"fields,omitempty"`
	Cause   error             `json:"-"`
}

// Error implements the error interface
func (e *QueryValidationError) Error() string {
	return e.Message
}

// WithField adds field-specific error information
func (e *QueryValidationError) WithField(field, message string) *QueryValidationError {
	newErr := &QueryValidationError{
		Type:    e.Type,
		Message: e.Message,
		Fields:  make(map[string]string),
		Cause:   e.Cause,
	}
	
	// Copy existing fields
	for k, v := range e.Fields {
		newErr.Fields[k] = v
	}
	
	// Add new field
	newErr.Fields[field] = message
	
	return newErr
}

// WithCause adds underlying cause
func (e *QueryValidationError) WithCause(cause error) *QueryValidationError {
	return &QueryValidationError{
		Type:    e.Type,
		Message: e.Message,
		Fields:  e.Fields,
		Cause:   cause,
	}
}

// Unwrap returns the underlying error
func (e *QueryValidationError) Unwrap() error {
	return e.Cause
}

// Helper functions for error checking

// IsValidationError checks if error is a validation error
func IsValidationError(err error) bool {
	var validationErr *QueryValidationError
	return errors.As(err, &validationErr)
}

// IsTimeoutError checks if error is a timeout error
func IsTimeoutError(err error) bool {
	var validationErr *QueryValidationError
	return errors.As(err, &validationErr) && validationErr.Type == "query_timeout"
}

// IsNotFoundError checks if error is a not found error
func IsNotFoundError(err error) bool {
	var validationErr *QueryValidationError
	return errors.As(err, &validationErr) && validationErr.Type == "resource_not_found"
}

// IsTooManyResultsError checks if error is a too many results error
func IsTooManyResultsError(err error) bool {
	var validationErr *QueryValidationError
	return errors.As(err, &validationErr) && validationErr.Type == "too_many_results"
}