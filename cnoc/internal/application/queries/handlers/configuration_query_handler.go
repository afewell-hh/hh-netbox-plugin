package handlers

import (
	"context"
	"fmt"
	"time"

	"github.com/hedgehog/cnoc/internal/application/queries"
	"github.com/hedgehog/cnoc/internal/domain/configuration"
	"github.com/hedgehog/cnoc/internal/domain/configuration/repositories"
	"github.com/hedgehog/cnoc/internal/domain/configuration/services"
	"github.com/hedgehog/cnoc/internal/domain/events"
)

// ConfigurationQueryHandler handles configuration-related queries
// Following CQRS pattern with read model optimization and Symphony-Level coordination
type ConfigurationQueryHandler struct {
	configRepo         repositories.ConfigurationRepository
	eventRepository    repositories.EventRepository
	dependencyResolver *services.DependencyResolver
	projectionService  *ProjectionService
	cacheService       *CacheService
	metricsService     *MetricsService
}

// NewConfigurationQueryHandler creates a new configuration query handler
func NewConfigurationQueryHandler(
	configRepo repositories.ConfigurationRepository,
	eventRepository repositories.EventRepository,
	dependencyResolver *services.DependencyResolver,
	projectionService *ProjectionService,
	cacheService *CacheService,
	metricsService *MetricsService,
) *ConfigurationQueryHandler {
	return &ConfigurationQueryHandler{
		configRepo:         configRepo,
		eventRepository:    eventRepository,
		dependencyResolver: dependencyResolver,
		projectionService:  projectionService,
		cacheService:       cacheService,
		metricsService:     metricsService,
	}
}

// HandleGetConfigurationByID handles get configuration by ID query
func (h *ConfigurationQueryHandler) HandleGetConfigurationByID(
	ctx context.Context,
	query queries.GetConfigurationByIDQuery,
) (*queries.QueryResult[*ConfigurationReadModel], error) {
	startTime := time.Now()
	
	// Validate query
	if err := query.Validate(); err != nil {
		return buildErrorResult[*ConfigurationReadModel](query.RequestID(), 
			"query_validation_failed", err, startTime), nil
	}

	// Check cache first
	cacheKey := h.buildCacheKey("config_by_id", query.ID, query.ProjectionLevel)
	var result *ConfigurationReadModel
	var cacheHit bool
	
	if query.QueryContext.CacheStrategy != queries.CacheStrategyNone &&
	   query.QueryContext.CacheStrategy != queries.CacheStrategyForce {
		cachedResult, err := h.cacheService.Get(ctx, cacheKey)
		if err == nil && cachedResult != nil {
			result = cachedResult.(*ConfigurationReadModel)
			cacheHit = true
		}
	}

	if result == nil {
		// Fetch from repository
		configID, err := configuration.NewConfigurationID(query.ID)
		if err != nil {
			return buildErrorResult[*ConfigurationReadModel](query.RequestID(),
				"invalid_configuration_id", err, startTime), nil
		}

		config, err := h.configRepo.FindByID(ctx, configID)
		if err != nil {
			if repositories.IsNotFound(err) {
				return buildErrorResult[*ConfigurationReadModel](query.RequestID(),
					"configuration_not_found", err, startTime), nil
			}
			return buildErrorResult[*ConfigurationReadModel](query.RequestID(),
				"repository_error", err, startTime), nil
		}

		// Project to read model
		result, err = h.projectionService.ProjectConfiguration(ctx, config, ConfigurationProjectionOptions{
			Level:             query.ProjectionLevel,
			IncludeComponents: query.IncludeComponents,
			IncludeEvents:     query.IncludeEvents,
			IncludeMetrics:    query.IncludeMetrics,
		})
		if err != nil {
			return buildErrorResult[*ConfigurationReadModel](query.RequestID(),
				"projection_failed", err, startTime), nil
		}

		// Cache the result
		if query.QueryContext.CacheStrategy != queries.CacheStrategyNone {
			ttl := h.calculateCacheTTL(query.QueryContext.CacheStrategy, query.ProjectionLevel)
			h.cacheService.Set(ctx, cacheKey, result, ttl)
		}
	}

	// Build success result
	return &queries.QueryResult[*ConfigurationReadModel]{
		Success: true,
		Data:    result,
		Metadata: queries.QueryResultMetadata{
			QueryType:       query.QueryType(),
			ExecutedAt:      time.Now(),
			UserID:          query.QueryContext.UserID,
			Source:          query.QueryContext.Source,
			ProjectionLevel: query.ProjectionLevel,
			TotalCount:      1,
		},
		Cache: queries.CacheInfo{
			CacheHit:      cacheHit,
			CacheStrategy: query.QueryContext.CacheStrategy,
			CacheKey:      cacheKey,
		},
		Performance: h.buildPerformanceMetrics(startTime, cacheHit),
		RequestID:   query.RequestID(),
	}, nil
}

// HandleGetConfigurationByName handles get configuration by name query
func (h *ConfigurationQueryHandler) HandleGetConfigurationByName(
	ctx context.Context,
	query queries.GetConfigurationByNameQuery,
) (*queries.QueryResult[*ConfigurationReadModel], error) {
	startTime := time.Now()
	
	// Validate query
	if err := query.Validate(); err != nil {
		return buildErrorResult[*ConfigurationReadModel](query.RequestID(),
			"query_validation_failed", err, startTime), nil
	}

	// Check cache
	cacheKey := h.buildCacheKey("config_by_name", query.Name, query.ProjectionLevel)
	var result *ConfigurationReadModel
	var cacheHit bool
	
	if query.QueryContext.CacheStrategy != queries.CacheStrategyNone {
		cachedResult, err := h.cacheService.Get(ctx, cacheKey)
		if err == nil && cachedResult != nil {
			result = cachedResult.(*ConfigurationReadModel)
			cacheHit = true
		}
	}

	if result == nil {
		// Fetch from repository
		configName, err := configuration.NewConfigurationName(query.Name)
		if err != nil {
			return buildErrorResult[*ConfigurationReadModel](query.RequestID(),
				"invalid_configuration_name", err, startTime), nil
		}

		config, err := h.configRepo.FindByName(ctx, configName)
		if err != nil {
			if repositories.IsNotFound(err) {
				return buildErrorResult[*ConfigurationReadModel](query.RequestID(),
					"configuration_not_found", err, startTime), nil
			}
			return buildErrorResult[*ConfigurationReadModel](query.RequestID(),
				"repository_error", err, startTime), nil
		}

		// Project to read model
		result, err = h.projectionService.ProjectConfiguration(ctx, config, ConfigurationProjectionOptions{
			Level:             query.ProjectionLevel,
			IncludeComponents: query.IncludeComponents,
			IncludeEvents:     query.IncludeHistory, // Map IncludeHistory to IncludeEvents
		})
		if err != nil {
			return buildErrorResult[*ConfigurationReadModel](query.RequestID(),
				"projection_failed", err, startTime), nil
		}

		// Cache the result
		if query.QueryContext.CacheStrategy != queries.CacheStrategyNone {
			ttl := h.calculateCacheTTL(query.QueryContext.CacheStrategy, query.ProjectionLevel)
			h.cacheService.Set(ctx, cacheKey, result, ttl)
		}
	}

	return &queries.QueryResult[*ConfigurationReadModel]{
		Success: true,
		Data:    result,
		Metadata: queries.QueryResultMetadata{
			QueryType:       query.QueryType(),
			ExecutedAt:      time.Now(),
			UserID:          query.QueryContext.UserID,
			Source:          query.QueryContext.Source,
			ProjectionLevel: query.ProjectionLevel,
			TotalCount:      1,
		},
		Cache: queries.CacheInfo{
			CacheHit:      cacheHit,
			CacheStrategy: query.QueryContext.CacheStrategy,
			CacheKey:      cacheKey,
		},
		Performance: h.buildPerformanceMetrics(startTime, cacheHit),
		RequestID:   query.RequestID(),
	}, nil
}

// HandleListConfigurations handles list configurations query with advanced filtering
func (h *ConfigurationQueryHandler) HandleListConfigurations(
	ctx context.Context,
	query queries.ListConfigurationsQuery,
) (*queries.QueryResult[[]*ConfigurationListItem], error) {
	startTime := time.Now()
	
	// Validate query
	if err := query.Validate(); err != nil {
		return buildErrorResult[[]*ConfigurationListItem](query.RequestID(),
			"query_validation_failed", err, startTime), nil
	}

	// Build repository filter
	repoFilter := h.buildRepositoryFilter(query.Filter)
	
	// Check cache for list queries
	cacheKey := h.buildListCacheKey(query)
	var result []*ConfigurationListItem
	var totalCount int64
	var cacheHit bool
	
	if query.QueryContext.CacheStrategy != queries.CacheStrategyNone {
		cachedData, err := h.cacheService.GetList(ctx, cacheKey)
		if err == nil && cachedData != nil {
			result = cachedData.Items.([]*ConfigurationListItem)
			totalCount = cachedData.TotalCount
			cacheHit = true
		}
	}

	if result == nil {
		// Fetch from repository
		configs, err := h.configRepo.FindAll(ctx, repoFilter)
		if err != nil {
			return buildErrorResult[[]*ConfigurationListItem](query.RequestID(),
				"repository_error", err, startTime), nil
		}

		// Get total count
		totalCount, err = h.configRepo.Count(ctx, repoFilter)
		if err != nil {
			return buildErrorResult[[]*ConfigurationListItem](query.RequestID(),
				"count_error", err, startTime), nil
		}

		// Project to list items
		result = make([]*ConfigurationListItem, len(configs))
		for i, config := range configs {
			item, err := h.projectionService.ProjectConfigurationListItem(ctx, config, ConfigurationListProjectionOptions{
				Level: query.ProjectionLevel,
			})
			if err != nil {
				return buildErrorResult[[]*ConfigurationListItem](query.RequestID(),
					"projection_failed", err, startTime), nil
			}
			result[i] = item
		}

		// Cache the result
		if query.QueryContext.CacheStrategy != queries.CacheStrategyNone {
			ttl := h.calculateCacheTTL(query.QueryContext.CacheStrategy, query.ProjectionLevel)
			h.cacheService.SetList(ctx, cacheKey, CachedListData{
				Items:      result,
				TotalCount: totalCount,
			}, ttl)
		}
	}

	// Build pagination result
	pagination := &queries.PaginationResult{
		CurrentOffset: query.Pagination.Offset,
		CurrentLimit:  query.Pagination.Limit,
		TotalCount:    totalCount,
		HasMore:       int64(query.Pagination.Offset+len(result)) < totalCount,
	}

	// Build warnings
	warnings := h.buildListQueryWarnings(query, len(result), totalCount)

	return &queries.QueryResult[[]*ConfigurationListItem]{
		Success: true,
		Data:    result,
		Metadata: queries.QueryResultMetadata{
			QueryType:       query.QueryType(),
			ExecutedAt:      time.Now(),
			UserID:          query.QueryContext.UserID,
			Source:          query.QueryContext.Source,
			ProjectionLevel: query.ProjectionLevel,
			TotalCount:      totalCount,
			FilteredCount:   int64(len(result)),
		},
		Pagination: pagination,
		Cache: queries.CacheInfo{
			CacheHit:      cacheHit,
			CacheStrategy: query.QueryContext.CacheStrategy,
			CacheKey:      cacheKey,
		},
		Performance: h.buildPerformanceMetrics(startTime, cacheHit),
		Warnings:    warnings,
		RequestID:   query.RequestID(),
	}, nil
}

// HandleGetConfigurationEvents handles get configuration events query
func (h *ConfigurationQueryHandler) HandleGetConfigurationEvents(
	ctx context.Context,
	query queries.GetConfigurationEventsQuery,
) (*queries.QueryResult[[]*ConfigurationEventReadModel], error) {
	startTime := time.Now()
	
	// Validate query
	if err := query.Validate(); err != nil {
		return buildErrorResult[[]*ConfigurationEventReadModel](query.RequestID(),
			"query_validation_failed", err, startTime), nil
	}

	// Build event filter
	eventFilter := h.buildEventFilter(query.EventFilter)
	
	// Fetch events from repository
	domainEvents, err := h.eventRepository.GetEventsByType(ctx, query.ConfigurationID, eventFilter)
	if err != nil {
		return buildErrorResult[[]*ConfigurationEventReadModel](query.RequestID(),
			"event_repository_error", err, startTime), nil
	}

	// Project to read models
	result := make([]*ConfigurationEventReadModel, len(domainEvents))
	for i, event := range domainEvents {
		eventModel, err := h.projectionService.ProjectConfigurationEvent(ctx, event, EventProjectionOptions{
			Level: query.ProjectionLevel,
		})
		if err != nil {
			return buildErrorResult[[]*ConfigurationEventReadModel](query.RequestID(),
				"event_projection_failed", err, startTime), nil
		}
		result[i] = eventModel
	}

	// Build pagination
	totalCount := int64(len(result))
	pagination := &queries.PaginationResult{
		CurrentOffset: query.Pagination.Offset,
		CurrentLimit:  query.Pagination.Limit,
		TotalCount:    totalCount,
		HasMore:       int64(query.Pagination.Offset+len(result)) < totalCount,
	}

	return &queries.QueryResult[[]*ConfigurationEventReadModel]{
		Success: true,
		Data:    result,
		Metadata: queries.QueryResultMetadata{
			QueryType:       query.QueryType(),
			ExecutedAt:      time.Now(),
			UserID:          query.QueryContext.UserID,
			Source:          query.QueryContext.Source,
			ProjectionLevel: query.ProjectionLevel,
			TotalCount:      totalCount,
		},
		Pagination:  pagination,
		Performance: h.buildPerformanceMetrics(startTime, false),
		RequestID:   query.RequestID(),
	}, nil
}

// HandleGetConfigurationMetrics handles get configuration metrics query
func (h *ConfigurationQueryHandler) HandleGetConfigurationMetrics(
	ctx context.Context,
	query queries.GetConfigurationMetricsQuery,
) (*queries.QueryResult[*ConfigurationMetricsReadModel], error) {
	startTime := time.Now()
	
	// Validate query
	if err := query.Validate(); err != nil {
		return buildErrorResult[*ConfigurationMetricsReadModel](query.RequestID(),
			"query_validation_failed", err, startTime), nil
	}

	// Fetch metrics
	metrics, err := h.metricsService.GetConfigurationMetrics(ctx, MetricsQuery{
		ConfigurationID: query.ConfigurationID,
		MetricTypes:     query.MetricTypes,
		TimeRange:       query.TimeRange,
		Aggregation:     query.Aggregation,
	})
	if err != nil {
		return buildErrorResult[*ConfigurationMetricsReadModel](query.RequestID(),
			"metrics_service_error", err, startTime), nil
	}

	// Project to read model
	result, err := h.projectionService.ProjectConfigurationMetrics(ctx, metrics, MetricsProjectionOptions{
		Level: query.ProjectionLevel,
	})
	if err != nil {
		return buildErrorResult[*ConfigurationMetricsReadModel](query.RequestID(),
			"metrics_projection_failed", err, startTime), nil
	}

	return &queries.QueryResult[*ConfigurationMetricsReadModel]{
		Success: true,
		Data:    result,
		Metadata: queries.QueryResultMetadata{
			QueryType:       query.QueryType(),
			ExecutedAt:      time.Now(),
			UserID:          query.QueryContext.UserID,
			Source:          query.QueryContext.Source,
			ProjectionLevel: query.ProjectionLevel,
		},
		Performance: h.buildPerformanceMetrics(startTime, false),
		RequestID:   query.RequestID(),
	}, nil
}

// HandleGetConfigurationDependencies handles get configuration dependencies query
func (h *ConfigurationQueryHandler) HandleGetConfigurationDependencies(
	ctx context.Context,
	query queries.GetConfigurationDependenciesQuery,
) (*queries.QueryResult[*ConfigurationDependenciesReadModel], error) {
	startTime := time.Now()
	
	// Validate query
	if err := query.Validate(); err != nil {
		return buildErrorResult[*ConfigurationDependenciesReadModel](query.RequestID(),
			"query_validation_failed", err, startTime), nil
	}

	// Fetch configuration
	configID, err := configuration.NewConfigurationID(query.ConfigurationID)
	if err != nil {
		return buildErrorResult[*ConfigurationDependenciesReadModel](query.RequestID(),
			"invalid_configuration_id", err, startTime), nil
	}

	config, err := h.configRepo.FindByID(ctx, configID)
	if err != nil {
		if repositories.IsNotFound(err) {
			return buildErrorResult[*ConfigurationDependenciesReadModel](query.RequestID(),
				"configuration_not_found", err, startTime), nil
		}
		return buildErrorResult[*ConfigurationDependenciesReadModel](query.RequestID(),
			"repository_error", err, startTime), nil
	}

	// Get dependency information based on type
	var dependencyInfo DependencyInfo
	
	switch query.DependencyType {
	case "direct":
		dependencyInfo, err = h.getDirectDependencies(ctx, config)
	case "transitive":
		dependencyInfo, err = h.getTransitiveDependencies(ctx, config, query.Depth)
	case "all":
		dependencyInfo, err = h.getAllDependencies(ctx, config, query.Depth)
	case "reverse":
		dependencyInfo, err = h.getReverseDependencies(ctx, config)
	default:
		return buildErrorResult[*ConfigurationDependenciesReadModel](query.RequestID(),
			"invalid_dependency_type", fmt.Errorf("invalid dependency type: %s", query.DependencyType), startTime), nil
	}

	if err != nil {
		return buildErrorResult[*ConfigurationDependenciesReadModel](query.RequestID(),
			"dependency_resolution_failed", err, startTime), nil
	}

	// Include resolution and conflicts if requested
	if query.IncludeResolution {
		componentNames := h.extractComponentNames(config)
		resolutionResult := h.dependencyResolver.ResolveDependencies(ctx, componentNames)
		dependencyInfo.Resolution = &resolutionResult
	}

	// Project to read model
	result, err := h.projectionService.ProjectConfigurationDependencies(ctx, dependencyInfo, DependencyProjectionOptions{
		Level:             query.ProjectionLevel,
		IncludeResolution: query.IncludeResolution,
		IncludeConflicts:  query.IncludeConflicts,
	})
	if err != nil {
		return buildErrorResult[*ConfigurationDependenciesReadModel](query.RequestID(),
			"dependency_projection_failed", err, startTime), nil
	}

	return &queries.QueryResult[*ConfigurationDependenciesReadModel]{
		Success: true,
		Data:    result,
		Metadata: queries.QueryResultMetadata{
			QueryType:       query.QueryType(),
			ExecutedAt:      time.Now(),
			UserID:          query.QueryContext.UserID,
			Source:          query.QueryContext.Source,
			ProjectionLevel: query.ProjectionLevel,
		},
		Performance: h.buildPerformanceMetrics(startTime, false),
		RequestID:   query.RequestID(),
	}, nil
}

// Helper methods for query processing

func (h *ConfigurationQueryHandler) buildCacheKey(prefix, id string, level queries.ProjectionLevel) string {
	return fmt.Sprintf("%s:%s:%s", prefix, id, string(level))
}

func (h *ConfigurationQueryHandler) buildListCacheKey(query queries.ListConfigurationsQuery) string {
	// Create a deterministic cache key based on filter criteria
	return fmt.Sprintf("list_configs:%s:%d:%d:%s", 
		h.hashFilter(query.Filter), 
		query.Pagination.Offset, 
		query.Pagination.Limit,
		string(query.ProjectionLevel))
}

func (h *ConfigurationQueryHandler) calculateCacheTTL(strategy queries.CacheStrategy, level queries.ProjectionLevel) time.Duration {
	baseTTL := time.Duration(0)
	
	switch strategy {
	case queries.CacheStrategyStandard:
		baseTTL = 5 * time.Minute
	case queries.CacheStrategyAggressive:
		baseTTL = 30 * time.Minute
	default:
		baseTTL = 1 * time.Minute
	}
	
	// Adjust TTL based on projection level
	switch level {
	case queries.ProjectionLevelMinimal:
		return baseTTL * 2 // Cache longer for minimal data
	case queries.ProjectionLevelComplete:
		return baseTTL / 2 // Cache shorter for complete data
	default:
		return baseTTL
	}
}

func (h *ConfigurationQueryHandler) buildRepositoryFilter(filter queries.ConfigurationFilter) repositories.ConfigurationFilter {
	repoFilter := repositories.ConfigurationFilter{
		Limit:  filter.ComponentCount.Max,
		Offset: filter.ComponentCount.Min,
	}
	
	// Convert query filter to repository filter
	if len(filter.IDs) > 0 {
		configIDs := make([]configuration.ConfigurationID, len(filter.IDs))
		for i, id := range filter.IDs {
			if configID, err := configuration.NewConfigurationID(id); err == nil {
				configIDs[i] = configID
			}
		}
		repoFilter.IDs = configIDs
	}
	
	if len(filter.Names) > 0 {
		configNames := make([]configuration.ConfigurationName, len(filter.Names))
		for i, name := range filter.Names {
			if configName, err := configuration.NewConfigurationName(name); err == nil {
				configNames[i] = configName
			}
		}
		repoFilter.Names = configNames
	}
	
	// Convert other filter fields...
	
	return repoFilter
}

func (h *ConfigurationQueryHandler) buildEventFilter(filter queries.EventFilter) repositories.EventFilter {
	repoFilter := repositories.EventFilter{
		EventTypes: filter.EventTypes,
	}
	
	if filter.OccurredAfter != nil {
		timestamp := filter.OccurredAfter.Unix()
		repoFilter.OccurredAfter = &timestamp
	}
	
	if filter.OccurredBefore != nil {
		timestamp := filter.OccurredBefore.Unix()
		repoFilter.OccurredBefore = &timestamp
	}
	
	return repoFilter
}

func (h *ConfigurationQueryHandler) buildPerformanceMetrics(startTime time.Time, cacheHit bool) queries.PerformanceMetrics {
	totalTime := time.Since(startTime).Milliseconds()
	
	metrics := queries.PerformanceMetrics{
		TotalTime: totalTime,
	}
	
	if cacheHit {
		metrics.CacheTime = totalTime
	} else {
		metrics.DatabaseTime = totalTime * 70 / 100 // Estimate 70% database time
		metrics.SerializationTime = totalTime * 20 / 100 // Estimate 20% serialization
		metrics.ExecutionTime = totalTime * 10 / 100 // Estimate 10% processing
	}
	
	return metrics
}

func (h *ConfigurationQueryHandler) buildListQueryWarnings(query queries.ListConfigurationsQuery, resultCount int, totalCount int64) []queries.QueryWarning {
	warnings := make([]queries.QueryWarning, 0)
	
	// Large result set warning
	if totalCount > 10000 {
		warnings = append(warnings, queries.QueryWarning{
			Code:       "large_result_set",
			Message:    fmt.Sprintf("Query returned %d total results. Consider adding more filters", totalCount),
			Severity:   "warning",
			Suggestion: "Add more specific filters to reduce result set size",
		})
	}
	
	// Performance warning for complex projections
	if query.ProjectionLevel == queries.ProjectionLevelComplete && resultCount > 100 {
		warnings = append(warnings, queries.QueryWarning{
			Code:       "performance_concern",
			Message:    "Complete projection level with large result set may impact performance",
			Severity:   "info",
			Suggestion: "Consider using standard projection level for large lists",
		})
	}
	
	return warnings
}

func buildErrorResult[T any](requestID, errorCode string, err error, startTime time.Time) *queries.QueryResult[T] {
	return &queries.QueryResult[T]{
		Success: false,
		Errors: []queries.QueryError{
			{
				Code:      errorCode,
				Message:   err.Error(),
				Retryable: isRetryableError(errorCode),
				Timestamp: time.Now(),
			},
		},
		Performance: buildPerformanceMetrics(startTime, false),
		RequestID:   requestID,
	}
}

// buildPerformanceMetrics creates performance metrics for query results
func buildPerformanceMetrics(startTime time.Time, success bool) queries.PerformanceMetrics {
	duration := time.Since(startTime)
	return queries.PerformanceMetrics{
		ExecutionTime:     duration.Milliseconds(),
		DatabaseTime:      duration.Milliseconds() / 2, // Estimate
		CacheTime:        0,
		SerializationTime: duration.Milliseconds() / 10, // Estimate
		TotalTime:        duration.Milliseconds(),
		MemoryUsage:      0,
	}
}

func (h *ConfigurationQueryHandler) getDirectDependencies(ctx context.Context, config *configuration.Configuration) (DependencyInfo, error) {
	// Implementation for direct dependencies
	// This would extract components and their immediate dependencies
	return DependencyInfo{}, nil
}

func (h *ConfigurationQueryHandler) getTransitiveDependencies(ctx context.Context, config *configuration.Configuration, depth int) (DependencyInfo, error) {
	// Implementation for transitive dependencies
	// This would follow dependency chains up to specified depth
	return DependencyInfo{}, nil
}

func (h *ConfigurationQueryHandler) getAllDependencies(ctx context.Context, config *configuration.Configuration, depth int) (DependencyInfo, error) {
	// Implementation for all dependencies
	// This would combine direct and transitive dependencies
	return DependencyInfo{}, nil
}

func (h *ConfigurationQueryHandler) getReverseDependencies(ctx context.Context, config *configuration.Configuration) (DependencyInfo, error) {
	// Implementation for reverse dependencies
	// This would find configurations that depend on this one
	return DependencyInfo{}, nil
}

func (h *ConfigurationQueryHandler) extractComponentNames(config *configuration.Configuration) []configuration.ComponentName {
	componentsList := config.ComponentsList()
	names := make([]configuration.ComponentName, len(componentsList))
	for i, comp := range componentsList {
		names[i] = comp.Name()
	}
	return names
}

func (h *ConfigurationQueryHandler) hashFilter(filter queries.ConfigurationFilter) string {
	// Simple hash implementation for filter - in practice use a proper hash function
	return fmt.Sprintf("%v", filter)[:10]
}

func isRetryableError(errorCode string) bool {
	retryableErrors := map[string]bool{
		"repository_error":     true,
		"timeout_error":       true,
		"temporary_failure":   true,
		"cache_error":         true,
	}
	return retryableErrors[errorCode]
}

// Supporting types for read models and projections

type ConfigurationReadModel struct {
	ID               string                     `json:"id"`
	Name             string                     `json:"name"`
	Description      string                     `json:"description"`
	Mode             string                     `json:"mode"`
	Version          string                     `json:"version"`
	Status           string                     `json:"status"`
	Labels           map[string]string          `json:"labels"`
	Annotations      map[string]string          `json:"annotations"`
	Components       []*ComponentReadModel      `json:"components,omitempty"`
	EnterpriseConfig *EnterpriseConfigReadModel `json:"enterprise_config,omitempty"`
	Events           []*ConfigurationEventReadModel `json:"events,omitempty"`
	Metrics          *ConfigurationMetricsReadModel `json:"metrics,omitempty"`
	CreatedAt        time.Time                  `json:"created_at"`
	UpdatedAt        time.Time                  `json:"updated_at"`
	Metadata         map[string]interface{}     `json:"metadata,omitempty"`
}

type ConfigurationListItem struct {
	ID              string                `json:"id"`
	Name            string                `json:"name"`
	Mode            string                `json:"mode"`
	Version         string                `json:"version"`
	Status          string                `json:"status"`
	ComponentCount  int                   `json:"component_count"`
	CreatedAt       time.Time             `json:"created_at"`
	UpdatedAt       time.Time             `json:"updated_at"`
	Summary         string                `json:"summary"`
}

type ComponentReadModel struct {
	Name          string                 `json:"name"`
	Version       string                 `json:"version"`
	Enabled       bool                   `json:"enabled"`
	Configuration map[string]interface{} `json:"configuration"`
	Resources     *ResourcesReadModel    `json:"resources"`
	Dependencies  []string               `json:"dependencies"`
}

type ResourcesReadModel struct {
	CPU       string `json:"cpu"`
	Memory    string `json:"memory"`
	Storage   string `json:"storage"`
	Replicas  int    `json:"replicas"`
	Namespace string `json:"namespace"`
}

type EnterpriseConfigReadModel struct {
	ComplianceFramework string            `json:"compliance_framework"`
	SecurityLevel       string            `json:"security_level"`
	AuditEnabled        bool              `json:"audit_enabled"`
	EncryptionRequired  bool              `json:"encryption_required"`
	BackupRequired      bool              `json:"backup_required"`
	PolicyTemplates     []string          `json:"policy_templates"`
	Metadata            map[string]string `json:"metadata"`
}

type ConfigurationEventReadModel struct {
	ID          string                 `json:"id"`
	Type        string                 `json:"type"`
	AggregateID string                 `json:"aggregate_id"`
	OccurredAt  time.Time              `json:"occurred_at"`
	Data        map[string]interface{} `json:"data"`
	Metadata    map[string]interface{} `json:"metadata,omitempty"`
}

type ConfigurationMetricsReadModel struct {
	ConfigurationID string                             `json:"configuration_id"`
	TimeRange       queries.TimeRange                  `json:"time_range"`
	Metrics         map[string]*MetricSeriesReadModel  `json:"metrics"`
	Summary         *MetricsSummaryReadModel           `json:"summary"`
}

type MetricSeriesReadModel struct {
	Type       string                 `json:"type"`
	DataPoints []*MetricDataPoint     `json:"data_points"`
	Metadata   map[string]interface{} `json:"metadata"`
}

type MetricDataPoint struct {
	Timestamp time.Time   `json:"timestamp"`
	Value     float64     `json:"value"`
	Tags      map[string]string `json:"tags,omitempty"`
}

type MetricsSummaryReadModel struct {
	TotalDataPoints int                    `json:"total_data_points"`
	TimeRange       queries.TimeRange      `json:"time_range"`
	Aggregations    map[string]float64     `json:"aggregations"`
}

type ConfigurationDependenciesReadModel struct {
	ConfigurationID   string                          `json:"configuration_id"`
	DependencyType    string                          `json:"dependency_type"`
	DirectDependencies []*DependencyReadModel         `json:"direct_dependencies"`
	TransitiveDependencies []*DependencyReadModel     `json:"transitive_dependencies,omitempty"`
	ReverseDependencies []*DependencyReadModel        `json:"reverse_dependencies,omitempty"`
	Resolution        *DependencyResolutionReadModel  `json:"resolution,omitempty"`
	Conflicts         []*DependencyConflictReadModel  `json:"conflicts,omitempty"`
}

type DependencyReadModel struct {
	ComponentName string `json:"component_name"`
	Version       string `json:"version"`
	Optional      bool   `json:"optional"`
	Depth         int    `json:"depth"`
}

type DependencyResolutionReadModel struct {
	Valid             bool                    `json:"valid"`
	InstallationOrder []string                `json:"installation_order"`
	Warnings          []string                `json:"warnings,omitempty"`
}

type DependencyConflictReadModel struct {
	ComponentName    string `json:"component_name"`
	ConflictingVersions []string `json:"conflicting_versions"`
	Reason           string `json:"reason"`
}

// Supporting types for services

type ConfigurationProjectionOptions struct {
	Level             queries.ProjectionLevel
	IncludeComponents bool
	IncludeEvents     bool
	IncludeMetrics    bool
}

type ConfigurationListProjectionOptions struct {
	Level queries.ProjectionLevel
}

type EventProjectionOptions struct {
	Level queries.ProjectionLevel
}

type MetricsProjectionOptions struct {
	Level queries.ProjectionLevel
}

type DependencyProjectionOptions struct {
	Level             queries.ProjectionLevel
	IncludeResolution bool
	IncludeConflicts  bool
}

type DependencyInfo struct {
	Direct      []*DependencyReadModel
	Transitive  []*DependencyReadModel
	Reverse     []*DependencyReadModel
	Resolution  *services.ResolutionResult
	Conflicts   []*DependencyConflictReadModel
}

type MetricsQuery struct {
	ConfigurationID string
	MetricTypes     []string
	TimeRange       queries.TimeRange
	Aggregation     queries.AggregationOptions
}

type CachedListData struct {
	Items      interface{}
	TotalCount int64
}

// Service interfaces - these would be implemented separately

type ProjectionService struct {
	// Implementation would handle projection from domain models to read models
}

func (ps *ProjectionService) ProjectConfiguration(ctx context.Context, config *configuration.Configuration, options ConfigurationProjectionOptions) (*ConfigurationReadModel, error) {
	// Implementation would convert domain model to read model
	return &ConfigurationReadModel{}, nil
}

func (ps *ProjectionService) ProjectConfigurationListItem(ctx context.Context, config *configuration.Configuration, options ConfigurationListProjectionOptions) (*ConfigurationListItem, error) {
	// Implementation would convert domain model to list item
	return &ConfigurationListItem{}, nil
}

func (ps *ProjectionService) ProjectConfigurationEvent(ctx context.Context, event events.DomainEvent, options EventProjectionOptions) (*ConfigurationEventReadModel, error) {
	// Implementation would convert domain event to read model
	return &ConfigurationEventReadModel{}, nil
}

func (ps *ProjectionService) ProjectConfigurationMetrics(ctx context.Context, metrics interface{}, options MetricsProjectionOptions) (*ConfigurationMetricsReadModel, error) {
	// Implementation would convert metrics to read model
	return &ConfigurationMetricsReadModel{}, nil
}

func (ps *ProjectionService) ProjectConfigurationDependencies(ctx context.Context, deps DependencyInfo, options DependencyProjectionOptions) (*ConfigurationDependenciesReadModel, error) {
	// Implementation would convert dependency info to read model
	return &ConfigurationDependenciesReadModel{}, nil
}

type CacheService struct {
	// Implementation would handle caching operations
}

func (cs *CacheService) Get(ctx context.Context, key string) (interface{}, error) {
	return nil, fmt.Errorf("not implemented")
}

func (cs *CacheService) Set(ctx context.Context, key string, value interface{}, ttl time.Duration) error {
	return nil
}

func (cs *CacheService) GetList(ctx context.Context, key string) (*CachedListData, error) {
	return nil, fmt.Errorf("not implemented")
}

func (cs *CacheService) SetList(ctx context.Context, key string, data CachedListData, ttl time.Duration) error {
	return nil
}

type MetricsService struct {
	// Implementation would handle metrics collection and aggregation
}

func (ms *MetricsService) GetConfigurationMetrics(ctx context.Context, query MetricsQuery) (interface{}, error) {
	return nil, fmt.Errorf("not implemented")
}