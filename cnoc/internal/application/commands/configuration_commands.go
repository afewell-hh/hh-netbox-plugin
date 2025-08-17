package commands

import (
	"context"

	"github.com/hedgehog/cnoc/internal/domain/configuration"
	"github.com/hedgehog/cnoc/internal/domain/shared"
)

// ConfigurationCommand represents the base interface for all configuration commands
// Following CQRS pattern with clean architecture principles
type ConfigurationCommand interface {
	CommandType() string
	AggregateID() string
	Validate() error
}

// CreateConfigurationCommand creates a new configuration
type CreateConfigurationCommand struct {
	ID                string                           `json:"id" validate:"required,uuid"`
	Name              string                           `json:"name" validate:"required,min=1,max=100"`
	Description       string                           `json:"description" validate:"max=500"`
	Mode              string                           `json:"mode" validate:"required,oneof=development staging production enterprise"`
	Version           string                           `json:"version" validate:"required,semver"`
	Labels            map[string]string                `json:"labels" validate:"dive,keys,alphanum,endkeys,alphanum"`
	Annotations       map[string]string                `json:"annotations" validate:"dive,keys,alphanum,endkeys,printascii"`
	Components        []ComponentReference             `json:"components" validate:"dive"`
	EnterpriseConfig  *EnterpriseConfiguration        `json:"enterprise_config,omitempty"`
	Metadata          map[string]interface{}           `json:"metadata,omitempty"`
	ValidationContext ValidationContext                `json:"validation_context"`
}

// ComponentReference represents a component reference in commands
type ComponentReference struct {
	Name          string                 `json:"name" validate:"required,min=1,max=100"`
	Version       string                 `json:"version" validate:"required,semver"`
	Enabled       bool                   `json:"enabled"`
	Configuration map[string]interface{} `json:"configuration" validate:"dive"`
	Resources     ResourceRequirements   `json:"resources"`
	Dependencies  []string               `json:"dependencies" validate:"dive,min=1"`
}

// ResourceRequirements represents resource requirements in commands
type ResourceRequirements struct {
	CPU       string `json:"cpu" validate:"required,cpu_format"`
	Memory    string `json:"memory" validate:"required,memory_format"`
	Storage   string `json:"storage" validate:"storage_format"`
	Replicas  int    `json:"replicas" validate:"min=1,max=100"`
	Namespace string `json:"namespace" validate:"required,dns1123_subdomain"`
}

// EnterpriseConfiguration represents enterprise-specific configuration
type EnterpriseConfiguration struct {
	ComplianceFramework string            `json:"compliance_framework" validate:"oneof=SOC2 HIPAA PCI-DSS ISO27001 FedRAMP"`
	SecurityLevel       string            `json:"security_level" validate:"oneof=basic standard high critical"`
	AuditEnabled        bool              `json:"audit_enabled"`
	EncryptionRequired  bool              `json:"encryption_required"`
	BackupRequired      bool              `json:"backup_required"`
	PolicyTemplates     []string          `json:"policy_templates" validate:"dive,min=1"`
	Metadata            map[string]string `json:"metadata" validate:"dive,keys,alphanum,endkeys,printascii"`
}

// ValidationContext provides context for command validation
type ValidationContext struct {
	UserID            string                 `json:"user_id" validate:"required,uuid"`
	RequestID         string                 `json:"request_id" validate:"required,uuid"`
	Source            string                 `json:"source" validate:"required,oneof=api cli web template"`
	EnforceCompliance bool                   `json:"enforce_compliance"`
	ValidatePolicies  bool                   `json:"validate_policies"`
	DryRun            bool                   `json:"dry_run"`
	Context           map[string]interface{} `json:"context,omitempty"`
}

// CommandType returns the command type
func (c CreateConfigurationCommand) CommandType() string {
	return "CreateConfiguration"
}

// AggregateID returns the aggregate identifier
func (c CreateConfigurationCommand) AggregateID() string {
	return c.ID
}

// Validate validates the command
func (c CreateConfigurationCommand) Validate() error {
	// Basic validation - detailed validation in handlers
	if c.ID == "" {
		return ErrInvalidCommandData.WithField("id", "required")
	}
	if c.Name == "" {
		return ErrInvalidCommandData.WithField("name", "required")
	}
	if c.Mode == "" {
		return ErrInvalidCommandData.WithField("mode", "required")
	}
	if c.Version == "" {
		return ErrInvalidCommandData.WithField("version", "required")
	}
	if c.ValidationContext.UserID == "" {
		return ErrInvalidCommandData.WithField("validation_context.user_id", "required")
	}
	if c.ValidationContext.RequestID == "" {
		return ErrInvalidCommandData.WithField("validation_context.request_id", "required")
	}
	return nil
}

// UpdateConfigurationCommand updates an existing configuration
type UpdateConfigurationCommand struct {
	ID                string                    `json:"id" validate:"required,uuid"`
	Name              *string                   `json:"name,omitempty" validate:"omitempty,min=1,max=100"`
	Description       *string                   `json:"description,omitempty" validate:"omitempty,max=500"`
	Version           string                    `json:"version" validate:"required,semver"`
	Labels            map[string]string         `json:"labels,omitempty" validate:"dive,keys,alphanum,endkeys,alphanum"`
	Annotations       map[string]string         `json:"annotations,omitempty" validate:"dive,keys,alphanum,endkeys,printascii"`
	ComponentUpdates  []ComponentUpdate         `json:"component_updates,omitempty" validate:"dive"`
	EnterpriseConfig  *EnterpriseConfiguration  `json:"enterprise_config,omitempty"`
	Metadata          map[string]interface{}    `json:"metadata,omitempty"`
	ValidationContext ValidationContext         `json:"validation_context"`
	ExpectedVersion   int                       `json:"expected_version" validate:"min=0"`
}

// ComponentUpdate represents a component update operation
type ComponentUpdate struct {
	Name          string                 `json:"name" validate:"required,min=1,max=100"`
	Operation     string                 `json:"operation" validate:"required,oneof=add update remove enable disable"`
	Version       *string                `json:"version,omitempty" validate:"omitempty,semver"`
	Enabled       *bool                  `json:"enabled,omitempty"`
	Configuration map[string]interface{} `json:"configuration,omitempty" validate:"dive"`
	Resources     *ResourceRequirements  `json:"resources,omitempty"`
	Dependencies  []string               `json:"dependencies,omitempty" validate:"dive,min=1"`
}

// CommandType returns the command type
func (c UpdateConfigurationCommand) CommandType() string {
	return "UpdateConfiguration"
}

// AggregateID returns the aggregate identifier
func (c UpdateConfigurationCommand) AggregateID() string {
	return c.ID
}

// Validate validates the command
func (c UpdateConfigurationCommand) Validate() error {
	if c.ID == "" {
		return ErrInvalidCommandData.WithField("id", "required")
	}
	if c.Version == "" {
		return ErrInvalidCommandData.WithField("version", "required")
	}
	if c.ValidationContext.UserID == "" {
		return ErrInvalidCommandData.WithField("validation_context.user_id", "required")
	}
	if c.ValidationContext.RequestID == "" {
		return ErrInvalidCommandData.WithField("validation_context.request_id", "required")
	}
	if c.ExpectedVersion < 0 {
		return ErrInvalidCommandData.WithField("expected_version", "must be non-negative")
	}
	return nil
}

// ValidateConfigurationCommand validates a configuration without persisting
type ValidateConfigurationCommand struct {
	ID                string                    `json:"id" validate:"required,uuid"`
	Framework         string                    `json:"framework" validate:"required,oneof=SOC2 HIPAA PCI-DSS ISO27001 FedRAMP"`
	ValidationLevel   string                    `json:"validation_level" validate:"required,oneof=basic standard strict"`
	ComponentChecks   bool                      `json:"component_checks"`
	DependencyChecks  bool                      `json:"dependency_checks"`
	PolicyChecks      bool                      `json:"policy_checks"`
	SecurityChecks    bool                      `json:"security_checks"`
	ValidationContext ValidationContext         `json:"validation_context"`
}

// CommandType returns the command type
func (c ValidateConfigurationCommand) CommandType() string {
	return "ValidateConfiguration"
}

// AggregateID returns the aggregate identifier
func (c ValidateConfigurationCommand) AggregateID() string {
	return c.ID
}

// Validate validates the command
func (c ValidateConfigurationCommand) Validate() error {
	if c.ID == "" {
		return ErrInvalidCommandData.WithField("id", "required")
	}
	if c.Framework == "" {
		return ErrInvalidCommandData.WithField("framework", "required")
	}
	if c.ValidationLevel == "" {
		return ErrInvalidCommandData.WithField("validation_level", "required")
	}
	if c.ValidationContext.UserID == "" {
		return ErrInvalidCommandData.WithField("validation_context.user_id", "required")
	}
	return nil
}

// DeployConfigurationCommand initiates configuration deployment
type DeployConfigurationCommand struct {
	ID                string            `json:"id" validate:"required,uuid"`
	TargetEnvironment string            `json:"target_environment" validate:"required,oneof=development staging production"`
	DeploymentMode    string            `json:"deployment_mode" validate:"required,oneof=rolling blue_green canary"`
	ValidationRequired bool             `json:"validation_required"`
	BackupRequired    bool             `json:"backup_required"`
	RollbackEnabled   bool             `json:"rollback_enabled"`
	DeploymentConfig  DeploymentConfig  `json:"deployment_config"`
	ValidationContext ValidationContext `json:"validation_context"`
}

// DeploymentConfig represents deployment-specific configuration
type DeploymentConfig struct {
	Timeout           int64             `json:"timeout" validate:"min=60,max=3600"`
	MaxRetries        int               `json:"max_retries" validate:"min=0,max=5"`
	HealthCheckURL    string            `json:"health_check_url,omitempty" validate:"omitempty,url"`
	NotificationURL   string            `json:"notification_url,omitempty" validate:"omitempty,url"`
	PreDeploymentHooks []DeploymentHook `json:"pre_deployment_hooks,omitempty" validate:"dive"`
	PostDeploymentHooks []DeploymentHook `json:"post_deployment_hooks,omitempty" validate:"dive"`
	RollbackConfig    *RollbackConfig   `json:"rollback_config,omitempty"`
}

// DeploymentHook represents a deployment hook
type DeploymentHook struct {
	Name        string            `json:"name" validate:"required,min=1,max=100"`
	Type        string            `json:"type" validate:"required,oneof=webhook script command"`
	Target      string            `json:"target" validate:"required"`
	Timeout     int64             `json:"timeout" validate:"min=1,max=300"`
	RetryCount  int               `json:"retry_count" validate:"min=0,max=3"`
	FailureMode string            `json:"failure_mode" validate:"required,oneof=abort warn continue"`
	Parameters  map[string]string `json:"parameters,omitempty" validate:"dive,keys,alphanum,endkeys,printascii"`
}

// RollbackConfig represents rollback configuration
type RollbackConfig struct {
	Enabled         bool   `json:"enabled"`
	AutoRollback    bool   `json:"auto_rollback"`
	HealthThreshold int    `json:"health_threshold" validate:"min=1,max=100"`
	RollbackTimeout int64  `json:"rollback_timeout" validate:"min=60,max=1800"`
	PreviousVersion string `json:"previous_version,omitempty" validate:"omitempty,semver"`
}

// CommandType returns the command type
func (c DeployConfigurationCommand) CommandType() string {
	return "DeployConfiguration"
}

// AggregateID returns the aggregate identifier
func (c DeployConfigurationCommand) AggregateID() string {
	return c.ID
}

// Validate validates the command
func (c DeployConfigurationCommand) Validate() error {
	if c.ID == "" {
		return ErrInvalidCommandData.WithField("id", "required")
	}
	if c.TargetEnvironment == "" {
		return ErrInvalidCommandData.WithField("target_environment", "required")
	}
	if c.DeploymentMode == "" {
		return ErrInvalidCommandData.WithField("deployment_mode", "required")
	}
	if c.ValidationContext.UserID == "" {
		return ErrInvalidCommandData.WithField("validation_context.user_id", "required")
	}
	if c.DeploymentConfig.Timeout <= 0 {
		return ErrInvalidCommandData.WithField("deployment_config.timeout", "must be positive")
	}
	return nil
}

// ArchiveConfigurationCommand archives a configuration
type ArchiveConfigurationCommand struct {
	ID                string            `json:"id" validate:"required,uuid"`
	Reason            string            `json:"reason" validate:"required,min=1,max=500"`
	RetentionDays     int               `json:"retention_days" validate:"min=30,max=2555"`
	BackupRequired    bool              `json:"backup_required"`
	ValidationContext ValidationContext `json:"validation_context"`
}

// CommandType returns the command type
func (c ArchiveConfigurationCommand) CommandType() string {
	return "ArchiveConfiguration"
}

// AggregateID returns the aggregate identifier
func (c ArchiveConfigurationCommand) AggregateID() string {
	return c.ID
}

// Validate validates the command
func (c ArchiveConfigurationCommand) Validate() error {
	if c.ID == "" {
		return ErrInvalidCommandData.WithField("id", "required")
	}
	if c.Reason == "" {
		return ErrInvalidCommandData.WithField("reason", "required")
	}
	if c.RetentionDays < 30 || c.RetentionDays > 2555 {
		return ErrInvalidCommandData.WithField("retention_days", "must be between 30 and 2555")
	}
	if c.ValidationContext.UserID == "" {
		return ErrInvalidCommandData.WithField("validation_context.user_id", "required")
	}
	return nil
}

// CommandResult represents the result of command execution
type CommandResult struct {
	Success      bool                   `json:"success"`
	AggregateID  string                 `json:"aggregate_id"`
	Version      int                    `json:"version"`
	Events       []string               `json:"events"`
	Warnings     []CommandWarning       `json:"warnings,omitempty"`
	Errors       []CommandError         `json:"errors,omitempty"`
	Metadata     map[string]interface{} `json:"metadata,omitempty"`
	Duration     int64                  `json:"duration_ms"`
	RequestID    string                 `json:"request_id"`
}

// CommandWarning represents a warning from command execution
type CommandWarning struct {
	Code        string `json:"code"`
	Message     string `json:"message"`
	Field       string `json:"field,omitempty"`
	Severity    string `json:"severity"`
	Suggestion  string `json:"suggestion,omitempty"`
}

// CommandError represents an error from command execution
type CommandError struct {
	Code        string                 `json:"code"`
	Message     string                 `json:"message"`
	Field       string                 `json:"field,omitempty"`
	Details     map[string]interface{} `json:"details,omitempty"`
	Recoverable bool                   `json:"recoverable"`
}

// Command validation errors
var (
	ErrInvalidCommandData = &CommandValidationError{
		Type:    "invalid_command_data",
		Message: "command data validation failed",
		Fields:  make(map[string]string),
	}
	
	ErrCommandTimeout = &CommandValidationError{
		Type:    "command_timeout",
		Message: "command execution timeout",
	}
	
	ErrInsufficientPermissions = &CommandValidationError{
		Type:    "insufficient_permissions",
		Message: "insufficient permissions to execute command",
	}
	
	ErrConcurrencyConflict = &CommandValidationError{
		Type:    "concurrency_conflict",
		Message: "concurrency conflict detected",
	}
)

// CommandValidationError represents command validation errors
type CommandValidationError struct {
	Type    string            `json:"type"`
	Message string            `json:"message"`
	Fields  map[string]string `json:"fields,omitempty"`
	Cause   error             `json:"-"`
}

// Error implements the error interface
func (e *CommandValidationError) Error() string {
	return e.Message
}

// WithField adds field-specific error information
func (e *CommandValidationError) WithField(field, message string) *CommandValidationError {
	newErr := &CommandValidationError{
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
func (e *CommandValidationError) WithCause(cause error) *CommandValidationError {
	return &CommandValidationError{
		Type:    e.Type,
		Message: e.Message,
		Fields:  e.Fields,
		Cause:   cause,
	}
}

// Unwrap returns the underlying error
func (e *CommandValidationError) Unwrap() error {
	return e.Cause
}

// IsValidationError checks if error is a validation error
func IsValidationError(err error) bool {
	var validationErr *CommandValidationError
	return errors.As(err, &validationErr)
}

// IsTimeoutError checks if error is a timeout error
func IsTimeoutError(err error) bool {
	var validationErr *CommandValidationError
	return errors.As(err, &validationErr) && validationErr.Type == "command_timeout"
}

// IsConcurrencyError checks if error is a concurrency error
func IsConcurrencyError(err error) bool {
	var validationErr *CommandValidationError
	return errors.As(err, &validationErr) && validationErr.Type == "concurrency_conflict"
}