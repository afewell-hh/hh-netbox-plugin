package rest

import (
	"time"
)

// APIResponse represents standard API response structure
type APIResponse struct {
	Success   bool        `json:"success"`
	Data      interface{} `json:"data,omitempty"`
	Error     string      `json:"error,omitempty"`
	Message   string      `json:"message,omitempty"`
	Timestamp time.Time   `json:"timestamp"`
	RequestID string      `json:"request_id,omitempty"`
	Duration  string      `json:"duration,omitempty"`
	Metadata  interface{} `json:"metadata,omitempty"`
}

// ValidationError represents field validation errors
type ValidationError struct {
	Field   string `json:"field"`
	Message string `json:"message"`
	Code    string `json:"code"`
}

// PaginatedResponse represents paginated API response
type PaginatedResponse struct {
	Items      interface{} `json:"items"`
	TotalCount int         `json:"total_count"`
	Page       int         `json:"page"`
	PageSize   int         `json:"page_size"`
	HasMore    bool        `json:"has_more"`
}

// Fabric represents a fabric configuration for API responses
type Fabric struct {
	ID                string            `json:"id"`
	Name              string            `json:"name"`
	Description       string            `json:"description"`
	KubernetesServer  string            `json:"kubernetes_server"`
	GitRepository     string            `json:"git_repository"`
	GitOpsDirectory   string            `json:"gitops_directory"`
	Status            string            `json:"status"`
	CreatedAt         time.Time         `json:"created_at"`
	UpdatedAt         time.Time         `json:"updated_at"`
	CRDCount          int               `json:"crd_count"`
	DriftStatus       string            `json:"drift_status"`
	LastSyncTime      time.Time         `json:"last_sync_time"`
	Metadata          map[string]interface{} `json:"metadata,omitempty"`
}

// FabricSyncRequest represents a sync operation request
type FabricSyncRequest struct {
	FabricID         string   `json:"fabric_id"`
	Force            bool     `json:"force"`
	DryRun           bool     `json:"dry_run"`
	GitBranch        string   `json:"git_branch,omitempty"`
	IncludePatterns  []string `json:"include_patterns,omitempty"`
	ExcludePatterns  []string `json:"exclude_patterns,omitempty"`
}

// FabricConnectionTestRequest represents connection test request
type FabricConnectionTestRequest struct {
	FabricID          string `json:"fabric_id"`
	TestKubernetes    bool   `json:"test_kubernetes"`
	TestGitRepository bool   `json:"test_git_repository"`
	Timeout           int    `json:"timeout_seconds"`
}

// CRDResource type is defined in crd_controller.go to avoid duplication

// CreateAPIResponse creates a successful API response
func CreateAPIResponse(data interface{}) APIResponse {
	return APIResponse{
		Success:   true,
		Data:      data,
		Timestamp: time.Now(),
	}
}

// CreateErrorResponse creates an error API response
func CreateErrorResponse(err error, message string) APIResponse {
	return APIResponse{
		Success:   false,
		Error:     err.Error(),
		Message:   message,
		Timestamp: time.Now(),
	}
}

// CreateValidationErrorResponse creates a validation error response
func CreateValidationErrorResponse(errors []ValidationError) APIResponse {
	return APIResponse{
		Success:   false,
		Error:     "Validation failed",
		Data:      errors,
		Timestamp: time.Now(),
	}
}