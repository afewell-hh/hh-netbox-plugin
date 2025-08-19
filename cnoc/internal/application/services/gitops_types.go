package services

import (
	"context"
	"time"
)

// Additional types needed by GitOps services to resolve build issues

// SyncStatus represents synchronization status (extended for GitOps workflow)
type SyncStatus struct {
	FabricID             string         `json:"fabric_id"`
	CurrentState         SyncState      `json:"current_state"`
	InProgress           bool           `json:"in_progress"`
	SyncProgress         float64        `json:"sync_progress"`
	CurrentOperation     string         `json:"current_operation,omitempty"`
	EstimatedCompletion  *time.Time     `json:"estimated_completion,omitempty"`
	LastSyncAt           *time.Time     `json:"last_sync_at,omitempty"`
	LastSuccessfulSync   *time.Time     `json:"last_successful_sync,omitempty"`
	StatusUpdatedAt      time.Time      `json:"status_updated_at"`
	HealthScore          float64        `json:"health_score"`
	DriftDetected        bool           `json:"drift_detected"`
	DriftCount           int            `json:"drift_count"`
	PeriodicSyncEnabled  bool           `json:"periodic_sync_enabled"`
	SyncInterval         time.Duration  `json:"sync_interval"`
	NextScheduledSync    *time.Time     `json:"next_scheduled_sync,omitempty"`
	
	// Legacy fields for backward compatibility
	Status    string     `json:"status"`
	StartTime time.Time  `json:"start_time"`
	EndTime   *time.Time `json:"end_time,omitempty"`
	Progress  int        `json:"progress"`
	Message   string     `json:"message"`
}

// GitOpsValidationResult represents validation results (for GitOps services)
// Extended to match ValidationResult interface
type GitOpsValidationResult struct {
	Valid               bool              `json:"valid"`
	Errors              []string          `json:"errors,omitempty"`
	Message             string            `json:"message"`
	ConfigurationsCount int               `json:"configurations_count"`
	ValidationErrors    []ValidationError `json:"validation_errors,omitempty"`
}

// SchemaValidationResult represents schema validation results
type SchemaValidationResult struct {
	Valid        bool     `json:"valid"`
	Errors       []string `json:"errors,omitempty"`
	Schema       string   `json:"schema"`
	ErrorCount   int      `json:"error_count"`
	SchemaErrors []string `json:"schema_errors,omitempty"`
}

// DependencyCheckResult represents dependency check results
type DependencyCheckResult struct {
	Valid        bool     `json:"valid"`
	MissingDeps  []string `json:"missing_dependencies,omitempty"`
	CircularDeps []string `json:"circular_dependencies,omitempty"`
}

// PolicyComplianceResult represents policy compliance check results
type PolicyComplianceResult struct {
	Compliant  bool                   `json:"compliant"`
	Violations []PolicyViolation      `json:"violations,omitempty"`
	Score      float64                `json:"score"`
}

// PolicyViolation represents a policy violation
type PolicyViolation struct {
	Policy   string `json:"policy"`
	Severity string `json:"severity"`
	Message  string `json:"message"`
}

// ConnectionResult represents connection test results
type ConnectionResult struct {
	Success      bool          `json:"success"`
	ResponseTime time.Duration `json:"response_time"`
	Error        string        `json:"error,omitempty"`
}

// Simple interfaces to resolve dependencies

// GitRepositoryService provides git repository operations
type GitRepositoryService interface {
	Clone(ctx context.Context, repoURL string) error
	GetStatus(ctx context.Context) (*GitOpsValidationResult, error)
}

// ConfigurationValidator provides configuration validation
type ConfigurationValidator interface {
	Validate(ctx context.Context, config []byte) (*GitOpsValidationResult, error)
}

// Additional missing types for compatibility

// EventWatcher interface for Kubernetes events
type EventWatcher interface {
	Watch(ctx context.Context) error
}

// ConfigValidationParseResult represents configuration parsing results
type ConfigValidationParseResult struct {
	Valid   bool     `json:"valid"`
	Errors  []string `json:"errors,omitempty"`
	Content []byte   `json:"content,omitempty"`
}

// YAMLConfiguration represents a YAML configuration
type YAMLConfiguration struct {
	Content    map[string]interface{} `json:"content"`
	SourceFile string                 `json:"source_file"`
	Namespace  string                 `json:"namespace"`
}

// ConfigValidationResult represents configuration validation results
type ConfigValidationResult struct {
	Valid     bool                   `json:"valid"`
	Errors    []string               `json:"errors,omitempty"`
	Warnings  []string               `json:"warnings,omitempty"`
	Config    *YAMLConfiguration     `json:"config,omitempty"`
}