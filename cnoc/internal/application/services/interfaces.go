package services

import (
	"context"
	"time"

	"github.com/hedgehog/cnoc/internal/api/rest/dto"
	"github.com/hedgehog/cnoc/internal/domain/configuration"
	"github.com/hedgehog/cnoc/internal/domain"
)

// FORGE Movement 2: Application Service Layer Interfaces
// These interfaces define the contracts that must be implemented for the application service layer
// Following anti-corruption layer patterns to prevent API concerns from leaking into domain

// SimpleConfigurationApplicationService defines the high-level use cases for configuration management
// This is the simplified interface expected by the web layer and tests
type SimpleConfigurationApplicationService interface {
	// CreateConfiguration creates a new configuration with validation
	CreateConfiguration(ctx context.Context, request dto.CreateConfigurationRequestDTO) (*dto.ConfigurationDTO, error)
	
	// GetConfiguration retrieves a configuration by ID
	GetConfiguration(ctx context.Context, id string) (*dto.ConfigurationDTO, error)
	
	// ListConfigurations retrieves configurations with pagination
	ListConfigurations(ctx context.Context, page, pageSize int) (*dto.ConfigurationListDTO, error)
	
	// UpdateConfiguration updates an existing configuration
	UpdateConfiguration(ctx context.Context, id string, request dto.UpdateConfigurationRequestDTO) (*dto.ConfigurationDTO, error)
	
	// DeleteConfiguration removes a configuration
	DeleteConfiguration(ctx context.Context, id string) error
	
	// ValidateConfiguration performs comprehensive validation
	ValidateConfiguration(ctx context.Context, id string) (*dto.ValidationResultDTO, error)
}

// FabricApplicationService defines fabric management use cases
type FabricApplicationService interface {
	// SynchronizeFabric performs GitOps synchronization for a fabric
	SynchronizeFabric(ctx context.Context, command FabricSyncCommand) (*FabricSyncResult, error)
	
	// GetFabricStatus retrieves current fabric synchronization status
	GetFabricStatus(ctx context.Context, fabricID string) (*FabricStatusDTO, error)
	
	// ValidateFabricConfiguration validates fabric configuration
	ValidateFabricConfiguration(ctx context.Context, fabricID string) (*FabricValidationResult, error)
	
	// ListFabrics retrieves all managed fabrics
	ListFabrics(ctx context.Context, page, pageSize int) (*FabricListDTO, error)
}

// GitOpsRepositoryApplicationService defines GitOps repository management use cases
type GitOpsRepositoryApplicationService interface {
	// CreateRepository creates a new GitOps repository with authentication
	CreateRepository(ctx context.Context, request dto.CreateGitOpsRepositoryDTO) (*dto.GitOpsRepositoryDTO, error)
	
	// GetRepository retrieves a repository by ID
	GetRepository(ctx context.Context, id string) (*dto.GitOpsRepositoryDTO, error)
	
	// ListRepositories retrieves repositories with pagination
	ListRepositories(ctx context.Context, page, pageSize int) (*dto.GitOpsRepositoryListDTO, error)
	
	// UpdateRepository updates an existing repository
	UpdateRepository(ctx context.Context, id string, request dto.UpdateGitOpsRepositoryDTO) (*dto.GitOpsRepositoryDTO, error)
	
	// DeleteRepository removes a repository
	DeleteRepository(ctx context.Context, id string) error
	
	// TestConnection tests repository connectivity
	TestConnection(ctx context.Context, id string) (*dto.ConnectionTestResultDTO, error)
	
	// SyncRepository performs repository synchronization
	SyncRepository(ctx context.Context, id string, options map[string]string) (*dto.SyncResult, error)
	
	// ValidateRepository validates repository configuration
	ValidateRepository(ctx context.Context, request dto.ValidationRequestDTO) (*dto.GitOpsValidationResultDTO, error)
	
	// GetRepositoryStatus retrieves current repository status
	GetRepositoryStatus(ctx context.Context, id string) (*dto.GitRepositoryStatusDTO, error)
}

// CRDApplicationService defines Custom Resource Definition management use cases
type CRDApplicationService interface {
	// CreateCRD creates a new CRD in the cluster
	CreateCRD(ctx context.Context, command CRDCreateCommand) (*CRDCreateResult, error)
	
	// GetCRD retrieves a CRD by name and namespace
	GetCRD(ctx context.Context, name, namespace string) (*CRDDetailDTO, error)
	
	// ListCRDs retrieves CRDs with filtering
	ListCRDs(ctx context.Context, filter CRDFilter) (*CRDListDTO, error)
	
	// UpdateCRD updates an existing CRD
	UpdateCRD(ctx context.Context, command CRDUpdateCommand) (*CRDUpdateResult, error)
	
	// DeleteCRD removes a CRD from the cluster
	DeleteCRD(ctx context.Context, name, namespace string) error
	
	// ValidateCRD validates CRD compliance and health
	ValidateCRD(ctx context.Context, name, namespace string) (*CRDValidationResult, error)
}

// Domain service interfaces that application services depend on

// ConfigurationDomainService provides domain-level configuration services
type ConfigurationDomainService interface {
	// ValidateConfiguration validates configuration against domain rules
	ValidateConfiguration(config *configuration.Configuration) error
	
	// ValidateBusinessRules validates business-specific rules
	ValidateBusinessRules(config *configuration.Configuration) error
	
	// ResolveDependencies resolves component dependencies
	ResolveDependencies(config *configuration.Configuration) error
	
	// ApplyPolicies applies enterprise policies to configuration
	ApplyPolicies(config *configuration.Configuration) error
}

// Repository interfaces for persistence

// ConfigurationRepository provides configuration persistence operations
type ConfigurationRepository interface {
	// Save persists a configuration
	Save(ctx context.Context, config *configuration.Configuration) error
	
	// GetByID retrieves configuration by ID
	GetByID(ctx context.Context, id string) (*configuration.Configuration, error)
	
	// GetByName retrieves configuration by name
	GetByName(ctx context.Context, name string) (*configuration.Configuration, error)
	
	// List retrieves configurations with pagination
	List(ctx context.Context, offset, limit int) ([]*configuration.Configuration, int, error)
	
	// Delete removes a configuration
	Delete(ctx context.Context, id string) error
	
	// ExistsByName checks if configuration exists by name
	ExistsByName(ctx context.Context, name string) (bool, error)
}

// FabricRepository provides fabric persistence operations
type FabricRepository interface {
	// Save persists a fabric
	Save(ctx context.Context, fabric *domain.Fabric) error
	
	// GetByID retrieves fabric by ID
	GetByID(ctx context.Context, id string) (*domain.Fabric, error)
	
	// GetByName retrieves fabric by name
	GetByName(ctx context.Context, name string) (*domain.Fabric, error)
	
	// List retrieves fabrics with pagination
	List(ctx context.Context, page, pageSize int) ([]*domain.Fabric, int, error)
	
	// Delete removes a fabric
	Delete(ctx context.Context, id string) error
	
	// ExistsByName checks if fabric exists by name
	ExistsByName(ctx context.Context, name string) (bool, error)
}

// CRDRepository provides CRD persistence operations
type CRDRepository interface {
	// Save persists a CRD
	Save(ctx context.Context, crd *domain.CRD) error
	
	// GetByName retrieves CRD by name and namespace
	GetByName(ctx context.Context, name, namespace string) (*domain.CRD, error)
	
	// List retrieves CRDs with filtering
	List(ctx context.Context, filter CRDFilter) ([]*domain.CRD, int, error)
	
	// Delete removes a CRD
	Delete(ctx context.Context, name, namespace string) error
}

// Anti-corruption layer interfaces for external systems

// KubernetesService provides anti-corruption layer for Kubernetes operations
type KubernetesService interface {
	// ApplyManifest applies a Kubernetes manifest
	ApplyManifest(ctx context.Context, manifest []byte) error
	
	// GetResource retrieves a Kubernetes resource
	GetResource(ctx context.Context, kind, name, namespace string) ([]byte, error)
	
	// DeleteResource deletes a Kubernetes resource
	DeleteResource(ctx context.Context, kind, name, namespace string) error
	
	// ValidateManifest validates a Kubernetes manifest
	ValidateManifest(ctx context.Context, manifest []byte) error
	
	// GetClusterHealth checks cluster health
	GetClusterHealth(ctx context.Context) (*ClusterHealthStatus, error)
}

// GitOpsService provides anti-corruption layer for GitOps operations
type GitOpsService interface {
	// SyncRepository synchronizes from git repository
	SyncRepository(ctx context.Context, repoURL, path string) (*GitSyncResult, error)
	
	// ValidateRepository validates git repository access
	ValidateRepository(ctx context.Context, repoURL string) error
	
	// GetRepositoryStatus gets repository synchronization status
	GetRepositoryStatus(ctx context.Context, repoURL string) (*GitRepositoryStatus, error)
	
	// CommitChanges commits changes to repository
	CommitChanges(ctx context.Context, repoURL, path string, changes []byte, message string) error
}

// MonitoringService provides anti-corruption layer for monitoring operations
type MonitoringService interface {
	// RecordMetric records a performance metric
	RecordMetric(ctx context.Context, name string, value float64, labels map[string]string) error
	
	// StartTrace starts a distributed trace
	StartTrace(ctx context.Context, operationName string) (TraceContext, error)
	
	// FinishTrace finishes a distributed trace
	FinishTrace(ctx context.Context, trace TraceContext, success bool, metadata map[string]interface{}) error
	
	// GetHealthMetrics retrieves system health metrics
	GetHealthMetrics(ctx context.Context) (*HealthMetrics, error)
}

// GitAuthenticationService provides git authentication and credential management
type GitAuthenticationService interface {
	// EncryptCredentials encrypts git credentials using AES-256-GCM
	EncryptCredentials(ctx context.Context, authType string, credentials map[string]interface{}) (string, error)
	
	// DecryptCredentials decrypts git credentials using AES-256-GCM
	DecryptCredentials(ctx context.Context, encryptedData string) (map[string]interface{}, error)
	
	// ValidateCredentials tests git repository connection with credentials
	ValidateCredentials(ctx context.Context, repoURL string, credentials map[string]interface{}) error
	
	// RefreshToken refreshes OAuth tokens if supported
	RefreshToken(ctx context.Context, repoURL string, refreshToken string) (*TokenResult, error)
}

// TokenResult represents the result of token refresh operations
type TokenResult struct {
	AccessToken  string    `json:"access_token"`
	RefreshToken string    `json:"refresh_token,omitempty"`
	ExpiresAt    time.Time `json:"expires_at"`
	TokenType    string    `json:"token_type"`
	Scope        string    `json:"scope,omitempty"`
}

// GitCredentialStorage defines the interface for git credential storage operations
type GitCredentialStorage interface {
	// Credential storage operations
	StoreCredentials(ctx context.Context, repoID string, authType string, credentials map[string]interface{}) error
	RetrieveCredentials(ctx context.Context, repoID string) (*GitCredentials, error)
	DeleteCredentials(ctx context.Context, repoID string) error
	
	// Connection testing and validation
	TestConnection(ctx context.Context, repoID string, repoURL string) (*GitCredentialConnectionTestResult, error)
	ValidateCredentials(ctx context.Context, repoID string, repoURL string) error
	
	// Credential lifecycle management
	RefreshCredentials(ctx context.Context, repoID string) error
	RotateCredentials(ctx context.Context, repoID string, newCredentials map[string]interface{}) error
	
	// Health monitoring and management
	ListCredentialHealth(ctx context.Context) ([]*CredentialHealthStatus, error)
	GetCredentialHealth(ctx context.Context, repoID string) (*CredentialHealthStatus, error)
	RefreshExpiredCredentials(ctx context.Context) ([]string, error)
	
	// Bulk operations
	BulkValidateCredentials(ctx context.Context, repoIDs []string) (map[string]*GitCredentialConnectionTestResult, error)
	BulkDeleteCredentials(ctx context.Context, repoIDs []string) error
	
	// Format validation and metadata
	ValidateCredentialsFormat(ctx context.Context, authType string, credentials map[string]interface{}) error
	GetCredentialMetadata(ctx context.Context, repoID string) (*CredentialMetadata, error)
	UpdateCredentialMetadata(ctx context.Context, repoID string, metadata *CredentialMetadata) error
}

// GitCredentials represents decrypted credential information (never persisted)
type GitCredentials struct {
	Type                string            `json:"type"`
	Token               string            `json:"token,omitempty"`
	Username            string            `json:"username,omitempty"`
	Password            string            `json:"password,omitempty"`
	SSHKey              string            `json:"ssh_key,omitempty"`
	SSHKeyPassphrase    string            `json:"ssh_key_passphrase,omitempty"`
	RefreshToken        string            `json:"refresh_token,omitempty"`
	Scope               string            `json:"scope,omitempty"`
	ExpiresAt           *time.Time        `json:"expires_at,omitempty"`
	AdditionalMetadata  map[string]string `json:"additional_metadata,omitempty"`
}

// GitCredentialConnectionTestResult represents the result of testing a git repository connection
type GitCredentialConnectionTestResult struct {
	Success       bool          `json:"success"`
	ResponseTime  int64         `json:"response_time_ms"`
	Error         string        `json:"error,omitempty"`
	DefaultBranch string        `json:"default_branch,omitempty"`
	RefsCount     int           `json:"refs_count,omitempty"`
	TestedAt      time.Time     `json:"tested_at"`
	Provider      string        `json:"provider,omitempty"`     // github, gitlab, azure_devops
	RateLimit     *RateLimit    `json:"rate_limit,omitempty"`
	Details       interface{}   `json:"details,omitempty"`
}

// RateLimit provides information about API rate limiting
type RateLimit struct {
	Limit     int       `json:"limit"`
	Remaining int       `json:"remaining"`
	ResetAt   time.Time `json:"reset_at"`
}

// CredentialHealthStatus represents the health status of stored credentials
type CredentialHealthStatus struct {
	RepositoryID       string            `json:"repository_id"`
	RepositoryURL      string            `json:"repository_url"`
	AuthType           string            `json:"auth_type"`
	IsValid            bool              `json:"is_valid"`
	LastChecked        time.Time         `json:"last_checked"`
	ExpiresAt          *time.Time        `json:"expires_at,omitempty"`
	ExpiresInDays      *int              `json:"expires_in_days,omitempty"`
	HealthStatus       string            `json:"health_status"` // healthy, warning, critical, expired
	ValidationError    string            `json:"validation_error,omitempty"`
	Provider           string            `json:"provider,omitempty"`
	LastSuccessfulTest *time.Time        `json:"last_successful_test,omitempty"`
	RefreshSupported   bool              `json:"refresh_supported"`
}

// CredentialMetadata represents metadata about stored credentials
type CredentialMetadata struct {
	RepositoryID     string     `json:"repository_id"`
	AuthType         string     `json:"auth_type"`
	HasCredentials   bool       `json:"has_credentials"`
	KeyVersion       int        `json:"key_version"`
	LastModified     time.Time  `json:"last_modified"`
	LastValidated    time.Time  `json:"last_validated"`
	ConnectionStatus string     `json:"connection_status"`
	ExpiresAt        *time.Time `json:"expires_at,omitempty"`
}

// DTOs for application service operations

// FabricSyncCommand represents a fabric synchronization command
type FabricSyncCommand struct {
	FabricID     string            `json:"fabric_id" validate:"required"`
	ForceSync    bool              `json:"force_sync"`
	DryRun       bool              `json:"dry_run"`
	Source       string            `json:"source"`
	RequestID    string            `json:"request_id"`
	UserID       string            `json:"user_id"`
	Metadata     map[string]string `json:"metadata,omitempty"`
}

// FabricSyncResult represents the result of a fabric synchronization
type FabricSyncResult struct {
	Success         bool                   `json:"success"`
	FabricID        string                 `json:"fabric_id"`
	SyncedResources int                    `json:"synced_resources"`
	Errors          []FabricSyncError      `json:"errors,omitempty"`
	Warnings        []FabricSyncWarning    `json:"warnings,omitempty"`
	DriftDetected   bool                   `json:"drift_detected"`
	DriftSummary    *FabricDriftSummary    `json:"drift_summary,omitempty"`
	Performance     *SyncPerformanceMetrics `json:"performance"`
	SyncedAt        time.Time              `json:"synced_at"`
	RequestID       string                 `json:"request_id"`
}

// FabricStatusDTO represents fabric status information
type FabricStatusDTO struct {
	FabricID        string            `json:"fabric_id"`
	Name            string            `json:"name"`
	Status          string            `json:"status"`
	LastSyncAt      *time.Time        `json:"last_sync_at"`
	ResourceCount   int               `json:"resource_count"`
	DriftStatus     string            `json:"drift_status"`
	HealthScore     float64           `json:"health_score"`
	Metadata        map[string]string `json:"metadata,omitempty"`
}

// FabricValidationResult represents fabric validation results
type FabricValidationResult struct {
	Valid           bool                      `json:"valid"`
	FabricID        string                    `json:"fabric_id"`
	ValidationLevel string                    `json:"validation_level"`
	Errors          []FabricValidationError   `json:"errors,omitempty"`
	Warnings        []FabricValidationWarning `json:"warnings,omitempty"`
	ValidatedAt     time.Time                 `json:"validated_at"`
	RequestID       string                    `json:"request_id"`
}

// FabricListDTO represents a list of fabrics
type FabricListDTO struct {
	Items      []FabricStatusDTO `json:"items"`
	TotalCount int               `json:"total_count"`
	Page       int               `json:"page"`
	PageSize   int               `json:"page_size"`
	HasMore    bool              `json:"has_more"`
}

// CRD-related DTOs

// CRDCreateCommand represents a CRD creation command
type CRDCreateCommand struct {
	Name         string                 `json:"name" validate:"required"`
	Namespace    string                 `json:"namespace" validate:"required"`
	Kind         string                 `json:"kind" validate:"required"`
	APIVersion   string                 `json:"api_version" validate:"required"`
	Manifest     map[string]interface{} `json:"manifest" validate:"required"`
	Source       string                 `json:"source"`
	RequestID    string                 `json:"request_id"`
	UserID       string                 `json:"user_id"`
	Metadata     map[string]string      `json:"metadata,omitempty"`
}

// CRDCreateResult represents the result of CRD creation
type CRDCreateResult struct {
	Success     bool                `json:"success"`
	CRDID       string              `json:"crd_id"`
	Name        string              `json:"name"`
	Namespace   string              `json:"namespace"`
	Kind        string              `json:"kind"`
	Errors      []CRDOperationError `json:"errors,omitempty"`
	Warnings    []CRDOperationWarning `json:"warnings,omitempty"`
	CreatedAt   time.Time           `json:"created_at"`
	RequestID   string              `json:"request_id"`
}

// CRDUpdateCommand represents a CRD update command
type CRDUpdateCommand struct {
	Name         string                 `json:"name" validate:"required"`
	Namespace    string                 `json:"namespace" validate:"required"`
	Manifest     map[string]interface{} `json:"manifest" validate:"required"`
	Source       string                 `json:"source"`
	RequestID    string                 `json:"request_id"`
	UserID       string                 `json:"user_id"`
	Metadata     map[string]string      `json:"metadata,omitempty"`
}

// CRDUpdateResult represents the result of CRD update
type CRDUpdateResult struct {
	Success     bool                  `json:"success"`
	Name        string                `json:"name"`
	Namespace   string                `json:"namespace"`
	Errors      []CRDOperationError   `json:"errors,omitempty"`
	Warnings    []CRDOperationWarning `json:"warnings,omitempty"`
	UpdatedAt   time.Time             `json:"updated_at"`
	RequestID   string                `json:"request_id"`
}

// CRDDetailDTO represents detailed CRD information
type CRDDetailDTO struct {
	Name        string                 `json:"name"`
	Namespace   string                 `json:"namespace"`
	Kind        string                 `json:"kind"`
	APIVersion  string                 `json:"api_version"`
	Status      string                 `json:"status"`
	Manifest    map[string]interface{} `json:"manifest"`
	CreatedAt   time.Time              `json:"created_at"`
	UpdatedAt   time.Time              `json:"updated_at"`
	Metadata    map[string]string      `json:"metadata,omitempty"`
}

// CRDFilter represents filtering options for CRD listing
type CRDFilter struct {
	Namespace  string            `json:"namespace,omitempty"`
	Kind       string            `json:"kind,omitempty"`
	APIVersion string            `json:"api_version,omitempty"`
	Status     string            `json:"status,omitempty"`
	Labels     map[string]string `json:"labels,omitempty"`
	Page       int               `json:"page"`
	PageSize   int               `json:"page_size"`
}

// CRDListDTO represents a list of CRDs
type CRDListDTO struct {
	Items      []CRDDetailDTO `json:"items"`
	TotalCount int            `json:"total_count"`
	Page       int            `json:"page"`
	PageSize   int            `json:"page_size"`
	HasMore    bool           `json:"has_more"`
}

// CRDValidationResult represents CRD validation results
type CRDValidationResult struct {
	Valid       bool                    `json:"valid"`
	Name        string                  `json:"name"`
	Namespace   string                  `json:"namespace"`
	Errors      []CRDValidationError    `json:"errors,omitempty"`
	Warnings    []CRDValidationWarning  `json:"warnings,omitempty"`
	ValidatedAt time.Time               `json:"validated_at"`
	RequestID   string                  `json:"request_id"`
}

// Supporting DTOs for error handling and metadata

// FabricSyncError represents a fabric synchronization error
type FabricSyncError struct {
	Code        string `json:"code"`
	Message     string `json:"message"`
	Resource    string `json:"resource,omitempty"`
	Severity    string `json:"severity"`
	Recoverable bool   `json:"recoverable"`
}

// FabricSyncWarning represents a fabric synchronization warning
type FabricSyncWarning struct {
	Code       string `json:"code"`
	Message    string `json:"message"`
	Resource   string `json:"resource,omitempty"`
	Suggestion string `json:"suggestion,omitempty"`
}

// FabricDriftSummary represents drift detection summary
type FabricDriftSummary struct {
	DriftedResources  int                    `json:"drifted_resources"`
	TotalResources    int                    `json:"total_resources"`
	DriftPercentage   float64                `json:"drift_percentage"`
	DriftDetails      []FabricDriftDetail    `json:"drift_details,omitempty"`
	LastDriftCheck    time.Time              `json:"last_drift_check"`
}

// FabricDriftDetail represents individual drift details
type FabricDriftDetail struct {
	ResourceName string                 `json:"resource_name"`
	ResourceType string                 `json:"resource_type"`
	DriftType    string                 `json:"drift_type"`
	Expected     map[string]interface{} `json:"expected"`
	Actual       map[string]interface{} `json:"actual"`
	Severity     string                 `json:"severity"`
}

// SyncPerformanceMetrics represents sync performance data
type SyncPerformanceMetrics struct {
	Duration         time.Duration `json:"duration_ms"`
	ResourcesPerSec  float64       `json:"resources_per_second"`
	NetworkLatency   time.Duration `json:"network_latency_ms"`
	ProcessingTime   time.Duration `json:"processing_time_ms"`
	ValidationTime   time.Duration `json:"validation_time_ms"`
}

// FabricValidationError represents fabric validation errors
type FabricValidationError struct {
	Code        string `json:"code"`
	Message     string `json:"message"`
	Resource    string `json:"resource,omitempty"`
	Field       string `json:"field,omitempty"`
	Severity    string `json:"severity"`
	Recoverable bool   `json:"recoverable"`
}

// FabricValidationWarning represents fabric validation warnings
type FabricValidationWarning struct {
	Code       string `json:"code"`
	Message    string `json:"message"`
	Resource   string `json:"resource,omitempty"`
	Field      string `json:"field,omitempty"`
	Suggestion string `json:"suggestion,omitempty"`
}

// CRDOperationError represents CRD operation errors
type CRDOperationError struct {
	Code        string `json:"code"`
	Message     string `json:"message"`
	Field       string `json:"field,omitempty"`
	Severity    string `json:"severity"`
	Recoverable bool   `json:"recoverable"`
}

// CRDOperationWarning represents CRD operation warnings
type CRDOperationWarning struct {
	Code       string `json:"code"`
	Message    string `json:"message"`
	Field      string `json:"field,omitempty"`
	Suggestion string `json:"suggestion,omitempty"`
}

// CRDValidationError represents CRD validation errors
type CRDValidationError struct {
	Code        string `json:"code"`
	Message     string `json:"message"`
	Field       string `json:"field,omitempty"`
	Severity    string `json:"severity"`
	Recoverable bool   `json:"recoverable"`
}

// CRDValidationWarning represents CRD validation warnings
type CRDValidationWarning struct {
	Code       string `json:"code"`
	Message    string `json:"message"`
	Field      string `json:"field,omitempty"`
	Suggestion string `json:"suggestion,omitempty"`
}

// Infrastructure service DTOs

// ClusterHealthStatus represents Kubernetes cluster health
type ClusterHealthStatus struct {
	Healthy     bool              `json:"healthy"`
	Version     string            `json:"version"`
	NodeCount   int               `json:"node_count"`
	PodCount    int               `json:"pod_count"`
	Errors      []string          `json:"errors,omitempty"`
	Warnings    []string          `json:"warnings,omitempty"`
	Metrics     map[string]float64 `json:"metrics,omitempty"`
	CheckedAt   time.Time         `json:"checked_at"`
}

// GitSyncResult represents git synchronization results
type GitSyncResult struct {
	Success       bool              `json:"success"`
	CommitHash    string            `json:"commit_hash"`
	FilesChanged  int               `json:"files_changed"`
	Errors        []string          `json:"errors,omitempty"`
	Warnings      []string          `json:"warnings,omitempty"`
	SyncDuration  time.Duration     `json:"sync_duration_ms"`
	SyncedAt      time.Time         `json:"synced_at"`
}

// GitRepositoryStatus represents git repository status
type GitRepositoryStatus struct {
	URL           string    `json:"url"`
	Connected     bool      `json:"connected"`
	LastSync      *time.Time `json:"last_sync"`
	CurrentCommit string    `json:"current_commit"`
	BranchName    string    `json:"branch_name"`
	Errors        []string  `json:"errors,omitempty"`
}

// TraceContext represents distributed tracing context
type TraceContext struct {
	TraceID  string            `json:"trace_id"`
	SpanID   string            `json:"span_id"`
	Tags     map[string]string `json:"tags,omitempty"`
	StartTime time.Time        `json:"start_time"`
}

// HealthMetrics represents system health metrics
type HealthMetrics struct {
	CPUUsage       float64           `json:"cpu_usage_percent"`
	MemoryUsage    float64           `json:"memory_usage_percent"`
	DiskUsage      float64           `json:"disk_usage_percent"`
	ActiveRequests int               `json:"active_requests"`
	ResponseTimes  map[string]float64 `json:"response_times_ms"`
	ErrorRates     map[string]float64 `json:"error_rates_percent"`
	Uptime         time.Duration     `json:"uptime_seconds"`
	CollectedAt    time.Time         `json:"collected_at"`
}

// FORGE Movement 2 Interface Requirements Summary:
//
// 1. APPLICATION SERVICE LAYER:
//    - ConfigurationApplicationService: High-level configuration management
//    - FabricApplicationService: GitOps fabric synchronization
//    - CRDApplicationService: Kubernetes Custom Resource management
//
// 2. DOMAIN SERVICE INTERFACES:
//    - ConfigurationDomainService: Domain-level validation and business rules
//    - Integration with existing domain models and validation services
//
// 3. REPOSITORY INTERFACES:
//    - ConfigurationRepository: Configuration persistence operations
//    - FabricRepository: Fabric data management
//    - CRDRepository: CRD state management
//
// 4. ANTI-CORRUPTION LAYER:
//    - KubernetesService: K8s cluster interaction abstraction
//    - GitOpsService: Git repository synchronization abstraction
//    - MonitoringService: Observability and metrics abstraction
//
// 5. COMPREHENSIVE DTO LAYER:
//    - Request/Response DTOs for all operations
//    - Error and warning structures with detailed information
//    - Performance and health monitoring DTOs
//
// 6. ENTERPRISE FEATURES:
//    - Drift detection and management
//    - Performance monitoring and metrics
//    - Comprehensive error handling and recovery
//    - Distributed tracing support