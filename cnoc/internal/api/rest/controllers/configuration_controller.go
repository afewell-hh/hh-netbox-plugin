package controllers

import (
	"encoding/json"
	"net/http"
	"strconv"
	"time"

	"github.com/gorilla/mux"
	
	"github.com/hedgehog/cnoc/internal/api/rest/dto"
	"github.com/hedgehog/cnoc/internal/api/rest/middleware"
	"github.com/hedgehog/cnoc/internal/application/commands"
	"github.com/hedgehog/cnoc/internal/application/queries"
	"github.com/hedgehog/cnoc/internal/application/services"
	"github.com/hedgehog/cnoc/internal/domain/configuration/repositories"
)

// ConfigurationController handles HTTP requests for configuration resources
// Following MDD-aligned patterns with Symphony-Level coordination
type ConfigurationController struct {
	appService     *services.ConfigurationApplicationService
	dtoMapper      dto.ConfigurationDTOMapper
	validator      *RequestValidator
	logger         Logger
	metricsCollector *ControllerMetricsCollector
}

// NewConfigurationController creates a new configuration controller
func NewConfigurationController(
	appService *services.ConfigurationApplicationService,
	baseURL string,
	logger Logger,
	metricsCollector *ControllerMetricsCollector,
) *ConfigurationController {
	return &ConfigurationController{
		appService:     appService,
		dtoMapper:      dto.NewConfigurationDTOMapper(baseURL),
		validator:      NewRequestValidator(),
		logger:         logger,
		metricsCollector: metricsCollector,
	}
}

// RegisterRoutes registers all configuration-related HTTP routes
func (c *ConfigurationController) RegisterRoutes(router *mux.Router) {
	// Apply middleware for all routes
	router.Use(middleware.RequestID)
	router.Use(middleware.Logging(c.logger))
	// Note: Metrics middleware would be implemented with proper interface
	// router.Use(middleware.Metrics(c.metricsCollector))
	router.Use(middleware.ErrorRecovery)
	router.Use(middleware.RateLimiting)

	// Configuration CRUD operations
	router.HandleFunc("/api/v1/configurations", c.ListConfigurations).Methods("GET")
	router.HandleFunc("/api/v1/configurations", c.CreateConfiguration).Methods("POST")
	router.HandleFunc("/api/v1/configurations/{id}", c.GetConfiguration).Methods("GET")
	router.HandleFunc("/api/v1/configurations/{id}", c.UpdateConfiguration).Methods("PUT", "PATCH")
	router.HandleFunc("/api/v1/configurations/{id}", c.DeleteConfiguration).Methods("DELETE")

	// Configuration operations
	router.HandleFunc("/api/v1/configurations/{id}/validate", c.ValidateConfiguration).Methods("POST")
	router.HandleFunc("/api/v1/configurations/{id}/deploy", c.DeployConfiguration).Methods("POST")
	router.HandleFunc("/api/v1/configurations/{id}/components", c.GetConfigurationComponents).Methods("GET")
	router.HandleFunc("/api/v1/configurations/{id}/history", c.GetConfigurationHistory).Methods("GET")
	router.HandleFunc("/api/v1/configurations/{id}/status", c.GetConfigurationStatus).Methods("GET")

	// Bulk operations
	router.HandleFunc("/api/v1/configurations/bulk/validate", c.BulkValidateConfigurations).Methods("POST")
	router.HandleFunc("/api/v1/configurations/bulk/deploy", c.BulkDeployConfigurations).Methods("POST")

	// Search and filtering
	router.HandleFunc("/api/v1/configurations/search", c.SearchConfigurations).Methods("POST")
	router.HandleFunc("/api/v1/configurations/export", c.ExportConfigurations).Methods("GET")
	router.HandleFunc("/api/v1/configurations/import", c.ImportConfigurations).Methods("POST")
}

// ListConfigurations handles GET /api/v1/configurations
func (c *ConfigurationController) ListConfigurations(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()
	startTime := time.Now()
	defer c.recordMetrics("list_configurations", startTime, nil)

	// Parse query parameters
	page, _ := strconv.Atoi(r.URL.Query().Get("page"))
	if page < 1 {
		page = 1
	}
	
	pageSize, _ := strconv.Atoi(r.URL.Query().Get("page_size"))
	if pageSize < 1 || pageSize > 100 {
		pageSize = 20
	}

	mode := r.URL.Query().Get("mode")
	status := r.URL.Query().Get("status")
	sortBy := r.URL.Query().Get("sort_by")
	sortOrder := r.URL.Query().Get("sort_order")

	// Build request for application service
	request := services.ListConfigurationsRequest{
		UserID:    middleware.GetUserID(r.Context()),
		RequestID: middleware.GetRequestID(r.Context()),
		Source:    "api",
		Filter: queries.ConfigurationFilter{
			Modes:    []string{mode},
			Statuses: []string{status},
		},
		Pagination: queries.PaginationOptions{
			Offset: (page - 1) * pageSize,
			Limit:  pageSize,
		},
		Sorting: queries.SortingOptions{
			SortBy: []queries.SortField{
				{
					Field:     sortBy,
					Direction: queries.SortOrder(sortOrder),
				},
			},
			SortOrder: queries.SortOrder(sortOrder),
		},
		ProjectionLevel: queries.ProjectionLevelStandard,
		CacheStrategy:   queries.CacheStrategyStandard,
	}

	// Execute query through application service
	result, err := c.appService.ListConfigurationsWithFiltering(ctx, request)
	if err != nil {
		c.handleError(w, r, err)
		return
	}

	// Convert to DTO and respond  
	// Note: This would be implemented by the DTO mapper in complete system
	listDTO := map[string]interface{}{
		"configurations": result.Configurations,
		"pagination":     result.Pagination,
		"total_count":    result.Pagination.TotalCount,
	}
	c.respondJSON(w, http.StatusOK, listDTO)
}

// CreateConfiguration handles POST /api/v1/configurations
func (c *ConfigurationController) CreateConfiguration(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()
	startTime := time.Now()
	defer c.recordMetrics("create_configuration", startTime, nil)

	// Parse request body
	var createDTO dto.CreateConfigurationRequestDTO
	if err := json.NewDecoder(r.Body).Decode(&createDTO); err != nil {
		c.handleValidationError(w, r, "Invalid request body", err)
		return
	}

	// Validate request
	if err := c.validator.ValidateCreateRequest(createDTO); err != nil {
		c.handleValidationError(w, r, "Validation failed", err)
		return
	}

	// Convert DTO to command through anti-corruption layer  
	// Note: This would be implemented by the DTO mapper in complete system
	cmd := commands.CreateConfigurationCommand{
		Name:        createDTO.Name,
		Description: createDTO.Description,
		Mode:        createDTO.Mode,
		Version:     createDTO.Version,
		// Additional fields would be mapped here
	}

	// Create workflow request
	workflowRequest := services.CreateConfigurationWorkflowRequest{
		WorkflowID:        "workflow-" + createDTO.Name + "-" + time.Now().Format("20060102150405"),
		UserID:           middleware.GetUserID(r.Context()),
		RequestID:        middleware.GetRequestID(r.Context()),
		Source:           "api",
		ConfigurationData: cmd,
		AutoDeploy:       false,
		EnforceCompliance: false,
		Metadata:         c.createRequestContext(r),
	}

	// Execute creation workflow through application service
	result, err := c.appService.CreateConfigurationWorkflow(ctx, workflowRequest)
	if err != nil {
		c.handleError(w, r, err)
		return
	}

	// Convert to DTO and respond - workflow result contains steps and success status
	responseDTO := map[string]interface{}{
		"success":     result.Success,
		"workflow_id": result.WorkflowID,
		"request_id":  result.RequestID,
		"duration":    result.Duration,
		"completed_at": result.CompletedAt,
	}
	c.respondJSON(w, http.StatusCreated, responseDTO)
}

// GetConfiguration handles GET /api/v1/configurations/{id}
func (c *ConfigurationController) GetConfiguration(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()
	startTime := time.Now()
	defer c.recordMetrics("get_configuration", startTime, nil)

	// Extract configuration ID from path
	vars := mux.Vars(r)
	configID := vars["id"]

	if configID == "" {
		c.handleValidationError(w, r, "Configuration ID is required", nil)
		return
	}

	// Parse query parameters
	includeComponents := r.URL.Query().Get("include_components") == "true"
	includeHistory := r.URL.Query().Get("include_history") == "true"

	// Build request for application service
	request := services.GetConfigurationRequest{
		ConfigurationID:     configID,
		UserID:             middleware.GetUserID(r.Context()),
		RequestID:          middleware.GetRequestID(r.Context()),
		Source:             "api",
		ProjectionLevel:    queries.ProjectionLevelComplete,
		IncludeComponents:  includeComponents,
		IncludeHistory:     includeHistory,
		IncludeEvents:      false,
		IncludeMetrics:     false,
		IncludeDependencies: false,
		IncludeCompliance:  false,
		CacheStrategy:      queries.CacheStrategyStandard,
	}

	// Execute query through application service
	result, err := c.appService.GetConfigurationWithRelatedData(ctx, request)
	if err != nil {
		if err == repositories.ErrConfigurationNotFound {
			c.handleNotFound(w, r, "Configuration not found")
			return
		}
		c.handleError(w, r, err)
		return
	}

	// Convert to DTO and respond
	// Note: This would be implemented by the DTO mapper in complete system
	configDTO := map[string]interface{}{
		"configuration": result.Configuration,
		"metadata":      result.QueryMetadata,
		"performance":   result.Performance,
	}
	c.respondJSON(w, http.StatusOK, configDTO)
}

// UpdateConfiguration handles PUT/PATCH /api/v1/configurations/{id}
func (c *ConfigurationController) UpdateConfiguration(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()
	startTime := time.Now()
	defer c.recordMetrics("update_configuration", startTime, nil)

	// Extract configuration ID from path
	vars := mux.Vars(r)
	configID := vars["id"]

	if configID == "" {
		c.handleValidationError(w, r, "Configuration ID is required", nil)
		return
	}

	// Parse request body
	var updateDTO dto.UpdateConfigurationRequestDTO
	if err := json.NewDecoder(r.Body).Decode(&updateDTO); err != nil {
		c.handleValidationError(w, r, "Invalid request body", err)
		return
	}

	// Validate request
	if err := c.validator.ValidateUpdateRequest(updateDTO); err != nil {
		c.handleValidationError(w, r, "Validation failed", err)
		return
	}

	// Build update command
	updateCommand := c.buildUpdateCommand(configID, updateDTO)

	// Execute update through application service
	workflowRequest := services.UpdateConfigurationWorkflowRequest{
		WorkflowID:         "workflow-update-" + configID + "-" + time.Now().Format("20060102150405"),
		UserID:            middleware.GetUserID(r.Context()),
		RequestID:         middleware.GetRequestID(r.Context()),
		Source:            "api",
		ConfigurationData: updateCommand,
		CreateBackup:      true,
		AutoDeploy:        false,
		DeploymentStrategy: "rolling",
		Metadata:          c.createRequestContext(r),
	}

	result, err := c.appService.UpdateConfigurationWorkflow(ctx, workflowRequest)
	if err != nil {
		if err == repositories.ErrConfigurationNotFound {
			c.handleNotFound(w, r, "Configuration not found")
			return
		}
		c.handleError(w, r, err)
		return
	}

	// Convert to DTO and respond
	// Note: This would be implemented by the DTO mapper in complete system
	responseDTO := map[string]interface{}{
		"success":     result.Success,
		"workflow_id": result.WorkflowID,
		"request_id":  result.RequestID,
		"duration":    result.Duration,
		"completed_at": result.CompletedAt,
	}
	c.respondJSON(w, http.StatusOK, responseDTO)
}

// DeleteConfiguration handles DELETE /api/v1/configurations/{id}
func (c *ConfigurationController) DeleteConfiguration(w http.ResponseWriter, r *http.Request) {
	// Note: Delete functionality would be implemented with proper command and service methods
	c.respondJSON(w, http.StatusNotImplemented, map[string]string{
		"message": "Delete functionality not yet implemented",
	})
}

// ValidateConfiguration handles POST /api/v1/configurations/{id}/validate
func (c *ConfigurationController) ValidateConfiguration(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()
	startTime := time.Now()
	defer c.recordMetrics("validate_configuration", startTime, nil)

	// Extract configuration ID from path
	vars := mux.Vars(r)
	configID := vars["id"]

	if configID == "" {
		c.handleValidationError(w, r, "Configuration ID is required", nil)
		return
	}

	// Note: validateCommand is built but not used directly in workflow pattern

	// Build validation workflow request
	validationRequest := services.ValidateConfigurationWorkflowRequest{
		ConfigurationID:   configID,
		UserID:           middleware.GetUserID(r.Context()),
		RequestID:        middleware.GetRequestID(r.Context()),
		Source:           "api",
		Framework:        "default",
		ValidationLevel:  "standard",
		ComponentChecks:  r.URL.Query().Get("component_checks") == "true",
		DependencyChecks: r.URL.Query().Get("dependency_checks") == "true",
		PolicyChecks:     r.URL.Query().Get("policy_checks") == "true",
		SecurityChecks:   r.URL.Query().Get("security_checks") == "true",
		EnforceCompliance: false,
	}

	// Execute validation through application service
	result, err := c.appService.ValidateConfigurationWorkflow(ctx, validationRequest)
	if err != nil {
		if err == repositories.ErrConfigurationNotFound {
			c.handleNotFound(w, r, "Configuration not found")
			return
		}
		c.handleError(w, r, err)
		return
	}

	// Convert to validation result DTO
	validationDTO := map[string]interface{}{
		"success":          result.Success,
		"configuration_id": result.ConfigurationID,
		"validation_level": result.ValidationLevel,
		"framework":        result.Framework,
		"duration":         result.Duration,
	}
	c.respondJSON(w, http.StatusOK, validationDTO)
}

// DeployConfiguration handles POST /api/v1/configurations/{id}/deploy
func (c *ConfigurationController) DeployConfiguration(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()
	startTime := time.Now()
	defer c.recordMetrics("deploy_configuration", startTime, nil)

	// Extract configuration ID from path
	vars := mux.Vars(r)
	configID := vars["id"]

	if configID == "" {
		c.handleValidationError(w, r, "Configuration ID is required", nil)
		return
	}

	// Parse deployment options
	var deployOptions DeploymentOptionsDTO
	if r.ContentLength > 0 {
		if err := json.NewDecoder(r.Body).Decode(&deployOptions); err != nil {
			c.handleValidationError(w, r, "Invalid deployment options", err)
			return
		}
	}

	// Build deployment workflow request
	deployRequest := services.DeployConfigurationWorkflowRequest{
		WorkflowID:         "workflow-deploy-" + configID + "-" + time.Now().Format("20060102150405"),
		UserID:            middleware.GetUserID(r.Context()),
		RequestID:         middleware.GetRequestID(r.Context()),
		Source:            "api",
		ConfigurationID:   configID,
		Environment:       deployOptions.Environment,
		DeploymentStrategy: deployOptions.Strategy,
		ValidationRequired: true,
		BackupRequired:    true,
		RollbackEnabled:   true,
		Metadata:          c.createRequestContext(r),
	}

	// Execute deployment through application service
	result, err := c.appService.DeployConfigurationWorkflow(ctx, deployRequest)
	if err != nil {
		if err == repositories.ErrConfigurationNotFound {
			c.handleNotFound(w, r, "Configuration not found")
			return
		}
		c.handleError(w, r, err)
		return
	}

	// Convert to deployment result DTO
	deploymentDTO := map[string]interface{}{
		"success":     result.Success,
		"workflow_id": result.WorkflowID,
		"request_id":  result.RequestID,
		"duration":    result.Duration,
		"completed_at": result.CompletedAt,
	}
	c.respondJSON(w, http.StatusAccepted, deploymentDTO)
}

// Helper methods

func (c *ConfigurationController) createQueryContext(r *http.Request) queries.QueryContext {
	return queries.QueryContext{
		UserID:          middleware.GetUserID(r.Context()),
		RequestID:       middleware.GetRequestID(r.Context()),
		Source:          "api",
		CacheStrategy:   queries.CacheStrategyStandard,
		Timeout:         30000, // 30 seconds
		IncludeDebug:    false,
		Context: map[string]interface{}{
			"tenant_id":   middleware.GetTenantID(r.Context()),
			"source_ip":   r.RemoteAddr,
			"user_agent":  r.UserAgent(),
			"method":      r.Method,
			"path":        r.URL.Path,
		},
	}
}

func (c *ConfigurationController) createRequestContext(r *http.Request) map[string]interface{} {
	return map[string]interface{}{
		"request_id":  middleware.GetRequestID(r.Context()),
		"user_id":     middleware.GetUserID(r.Context()),
		"tenant_id":   middleware.GetTenantID(r.Context()),
		"source_ip":   r.RemoteAddr,
		"user_agent":  r.UserAgent(),
		"method":      r.Method,
		"path":        r.URL.Path,
	}
}

func (c *ConfigurationController) buildUpdateCommand(configID string, dto dto.UpdateConfigurationRequestDTO) commands.UpdateConfigurationCommand {
	cmd := commands.UpdateConfigurationCommand{
		ID: configID,
	}

	if dto.Description != nil {
		cmd.Description = dto.Description
	}
	if dto.Version != nil {
		cmd.Version = *dto.Version  // Dereference pointer
	}
	if dto.Labels != nil {
		cmd.Labels = dto.Labels
	}
	if dto.Annotations != nil {
		cmd.Annotations = dto.Annotations
	}

	// Convert components and enterprise config
	// Implementation would be here

	return cmd
}

func (c *ConfigurationController) convertValidationResult(result *ValidationResult) dto.ValidationResultDTO {
	validationDTO := dto.ValidationResultDTO{
		Valid:       result.IsValid,
		ValidatedAt: time.Now(),
	}

	// Convert errors
	for _, err := range result.Errors {
		validationDTO.Errors = append(validationDTO.Errors, dto.ValidationErrorDTO{
			Field:   err.Field,
			Message: err.Message,
			Code:    err.Code,
			Details: "", // Convert details to string representation if needed
		})
	}

	// Convert warnings
	for _, warning := range result.Warnings {
		validationDTO.Warnings = append(validationDTO.Warnings, dto.ValidationWarningDTO{
			Field:   warning.Field,
			Message: warning.Message,
			Code:    warning.Code,
			Details: "", // Convert details to string representation if needed
		})
	}

	return validationDTO
}

func (c *ConfigurationController) convertDeploymentResult(result *DeploymentResult) DeploymentResultDTO {
	return DeploymentResultDTO{
		DeploymentID:    result.DeploymentID,
		ConfigurationID: result.ConfigurationID,
		Status:         result.Status,
		Environment:    result.Environment,
		StartedAt:      result.StartedAt,
		CompletedAt:    result.CompletedAt,
		Details:        result.Details,
	}
}

func (c *ConfigurationController) respondJSON(w http.ResponseWriter, statusCode int, data interface{}) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(statusCode)
	
	if err := json.NewEncoder(w).Encode(data); err != nil {
		c.logger.Error("Failed to encode response", "error", err)
	}
}

func (c *ConfigurationController) handleError(w http.ResponseWriter, r *http.Request, err error) {
	c.logger.Error("Request failed", "error", err, "path", r.URL.Path)
	
	errorResponse := dto.ErrorResponseDTO{
		Error:     "Internal Server Error",
		Message:   "An unexpected error occurred",
		Code:      "INTERNAL_ERROR",
		Timestamp: time.Now(),
		TraceID:   middleware.GetRequestID(r.Context()),
	}

	c.respondJSON(w, http.StatusInternalServerError, errorResponse)
}

func (c *ConfigurationController) handleValidationError(w http.ResponseWriter, r *http.Request, message string, err error) {
	c.logger.Warn("Validation failed", "error", err, "path", r.URL.Path)
	
	errorResponse := dto.ErrorResponseDTO{
		Error:     "Bad Request",
		Message:   message,
		Code:      "VALIDATION_ERROR",
		Timestamp: time.Now(),
		TraceID:   middleware.GetRequestID(r.Context()),
	}

	if err != nil {
		errorResponse.Details = map[string]interface{}{
			"validation_error": err.Error(),
		}
	}

	c.respondJSON(w, http.StatusBadRequest, errorResponse)
}

func (c *ConfigurationController) handleNotFound(w http.ResponseWriter, r *http.Request, message string) {
	errorResponse := dto.ErrorResponseDTO{
		Error:     "Not Found",
		Message:   message,
		Code:      "RESOURCE_NOT_FOUND",
		Timestamp: time.Now(),
		TraceID:   middleware.GetRequestID(r.Context()),
	}

	c.respondJSON(w, http.StatusNotFound, errorResponse)
}

func (c *ConfigurationController) recordMetrics(operation string, startTime time.Time, err error) {
	if c.metricsCollector != nil {
		duration := time.Since(startTime)
		c.metricsCollector.RecordRequest(operation, duration, err)
	}
}

// Additional handler methods for other endpoints...

func (c *ConfigurationController) GetConfigurationComponents(w http.ResponseWriter, r *http.Request) {
	// Implementation
}

func (c *ConfigurationController) GetConfigurationHistory(w http.ResponseWriter, r *http.Request) {
	// Implementation
}

func (c *ConfigurationController) GetConfigurationStatus(w http.ResponseWriter, r *http.Request) {
	// Implementation
}

func (c *ConfigurationController) BulkValidateConfigurations(w http.ResponseWriter, r *http.Request) {
	// Implementation
}

func (c *ConfigurationController) BulkDeployConfigurations(w http.ResponseWriter, r *http.Request) {
	// Implementation
}

func (c *ConfigurationController) SearchConfigurations(w http.ResponseWriter, r *http.Request) {
	// Implementation
}

func (c *ConfigurationController) ExportConfigurations(w http.ResponseWriter, r *http.Request) {
	// Implementation
}

func (c *ConfigurationController) ImportConfigurations(w http.ResponseWriter, r *http.Request) {
	// Implementation
}

// ValidationResult represents the result of configuration validation
type ValidationResult struct {
	IsValid  bool                    `json:"is_valid"`
	Errors   []ValidationError       `json:"errors,omitempty"`
	Warnings []ValidationWarning     `json:"warnings,omitempty"`
}

// ValidationError represents a validation error
type ValidationError struct {
	Field   string                 `json:"field"`
	Message string                 `json:"message"`
	Code    string                 `json:"code"`
	Details map[string]interface{} `json:"details,omitempty"`
}

// ValidationWarning represents a validation warning
type ValidationWarning struct {
	Field   string                 `json:"field"`
	Message string                 `json:"message"`
	Code    string                 `json:"code"`
	Details map[string]interface{} `json:"details,omitempty"`
}

// DeploymentResult represents the result of configuration deployment
type DeploymentResult struct {
	DeploymentID    string                 `json:"deployment_id"`
	ConfigurationID string                 `json:"configuration_id"`
	Status         string                 `json:"status"`
	Environment    string                 `json:"environment"`
	StartedAt      time.Time              `json:"started_at"`
	CompletedAt    *time.Time             `json:"completed_at,omitempty"`
	Details        map[string]interface{} `json:"details,omitempty"`
}

// Supporting types

// RequestValidator validates incoming requests
type RequestValidator struct {
	// Validation implementation
}

func NewRequestValidator() *RequestValidator {
	return &RequestValidator{}
}

func (v *RequestValidator) ValidateCreateRequest(dto dto.CreateConfigurationRequestDTO) error {
	// Validation logic
	return nil
}

func (v *RequestValidator) ValidateUpdateRequest(dto dto.UpdateConfigurationRequestDTO) error {
	// Validation logic
	return nil
}

// Logger interface for logging abstraction
type Logger interface {
	Debug(msg string, args ...interface{})
	Info(msg string, args ...interface{})
	Warn(msg string, args ...interface{})
	Error(msg string, args ...interface{})
}

// ControllerMetricsCollector collects controller metrics
type ControllerMetricsCollector struct {
	// Metrics implementation
}

func (m *ControllerMetricsCollector) RecordRequest(operation string, duration time.Duration, err error) {
	// Record metrics
}

// DeploymentOptionsDTO represents deployment options
type DeploymentOptionsDTO struct {
	Environment string `json:"environment"`
	DryRun     bool   `json:"dry_run"`
	Strategy   string `json:"strategy"`
}

// DeploymentResultDTO represents deployment result
type DeploymentResultDTO struct {
	DeploymentID    string                 `json:"deployment_id"`
	ConfigurationID string                 `json:"configuration_id"`
	Status         string                 `json:"status"`
	Environment    string                 `json:"environment"`
	StartedAt      time.Time              `json:"started_at"`
	CompletedAt    *time.Time             `json:"completed_at,omitempty"`
	Details        map[string]interface{} `json:"details,omitempty"`
}