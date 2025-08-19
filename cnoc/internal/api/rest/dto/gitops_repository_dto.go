package dto

import "time"

// GitOps Repository DTOs for REST API layer
// Defines data transfer objects for GitOps repository management

// GitOpsRepositoryDTO represents a GitOps repository in API responses
type GitOpsRepositoryDTO struct {
	ID                  string            `json:"id"`
	Name                string            `json:"name"`
	URL                 string            `json:"url"`
	Description         string            `json:"description,omitempty"`
	AuthenticationType  string            `json:"authentication_type"`
	ConnectionStatus    string            `json:"connection_status"`
	LastValidated       *time.Time        `json:"last_validated,omitempty"`
	Labels              map[string]string `json:"labels,omitempty"`
	Metadata            map[string]string `json:"metadata,omitempty"`
	CreatedAt           time.Time         `json:"created_at"`
	UpdatedAt           time.Time         `json:"updated_at"`
}

// CreateGitOpsRepositoryDTO represents the request to create a new GitOps repository
type CreateGitOpsRepositoryDTO struct {
	Name               string                    `json:"name" validate:"required,min=3,max=100"`
	URL                string                    `json:"url" validate:"required,url"`
	Description        string                    `json:"description,omitempty"`
	AuthenticationType string                    `json:"authentication_type" validate:"required,oneof=token ssh_key oauth"`
	Credentials        GitCredentialsDTO         `json:"credentials" validate:"required"`
	Labels             map[string]string         `json:"labels,omitempty"`
	Metadata           map[string]string         `json:"metadata,omitempty"`
}

// UpdateGitOpsRepositoryDTO represents the request to update a GitOps repository
type UpdateGitOpsRepositoryDTO struct {
	Name               *string                   `json:"name,omitempty" validate:"omitempty,min=3,max=100"`
	URL                *string                   `json:"url,omitempty" validate:"omitempty,url"`
	Description        *string                   `json:"description,omitempty"`
	AuthenticationType *string                   `json:"authentication_type,omitempty" validate:"omitempty,oneof=token ssh_key oauth"`
	Credentials        *GitCredentialsDTO        `json:"credentials,omitempty"`
	Labels             map[string]string         `json:"labels,omitempty"`
	Metadata           map[string]string         `json:"metadata,omitempty"`
}

// GitCredentialsDTO represents Git authentication credentials
type GitCredentialsDTO struct {
	Type        string            `json:"type" validate:"required,oneof=token ssh_key oauth"`
	Token       *string           `json:"token,omitempty"`
	SSHKey      *SSHKeyDTO        `json:"ssh_key,omitempty"`
	OAuth       *OAuthConfigDTO   `json:"oauth,omitempty"`
	Metadata    map[string]string `json:"metadata,omitempty"`
}

// SSHKeyDTO represents SSH key authentication
type SSHKeyDTO struct {
	PrivateKey string `json:"private_key" validate:"required"`
	PublicKey  string `json:"public_key,omitempty"`
	Passphrase string `json:"passphrase,omitempty"`
}

// OAuthConfigDTO represents OAuth authentication configuration
type OAuthConfigDTO struct {
	ClientID     string `json:"client_id" validate:"required"`
	ClientSecret string `json:"client_secret" validate:"required"`
	RedirectURL  string `json:"redirect_url,omitempty"`
	Scope        string `json:"scope,omitempty"`
}

// GitOpsRepositoryListDTO represents a paginated list of GitOps repositories
type GitOpsRepositoryListDTO struct {
	Items      []GitOpsRepositoryDTO `json:"items"`
	TotalCount int                   `json:"total_count"`
	Page       int                   `json:"page"`
	PageSize   int                   `json:"page_size"`
	TotalPages int                   `json:"total_pages"`
}

// SyncResult represents the result of a GitOps synchronization operation
type SyncResult struct {
	Success           bool                  `json:"success"`
	SyncedResources   int                   `json:"synced_resources"`
	FailedResources   int                   `json:"failed_resources"`
	CommitHash        string                `json:"commit_hash,omitempty"`
	Branch            string                `json:"branch,omitempty"`
	Performance       SyncPerformanceMetrics `json:"performance"`
	Errors            []SyncError           `json:"errors,omitempty"`
	Warnings          []SyncWarning         `json:"warnings,omitempty"`
	SyncedAt          time.Time             `json:"synced_at"`
}

// SyncPerformanceMetrics tracks synchronization performance
type SyncPerformanceMetrics struct {
	Duration        time.Duration `json:"duration"`
	FilesProcessed  int           `json:"files_processed"`
	BytesProcessed  int64         `json:"bytes_processed"`
	NetworkLatency  time.Duration `json:"network_latency,omitempty"`
}

// SyncError represents an error during synchronization
type SyncError struct {
	Type        string `json:"type"`
	Message     string `json:"message"`
	Resource    string `json:"resource,omitempty"`
	FilePath    string `json:"file_path,omitempty"`
	LineNumber  int    `json:"line_number,omitempty"`
}

// SyncWarning represents a warning during synchronization
type SyncWarning struct {
	Type     string `json:"type"`
	Message  string `json:"message"`
	Resource string `json:"resource,omitempty"`
	FilePath string `json:"file_path,omitempty"`
}

// ConnectionTestResultDTO represents the result of testing a Git repository connection
type ConnectionTestResultDTO struct {
	Success     bool      `json:"success"`
	StatusCode  int       `json:"status_code,omitempty"`
	Message     string    `json:"message"`
	Latency     int64     `json:"latency_ms"`
	TestedAt    time.Time `json:"tested_at"`
	Error       string    `json:"error,omitempty"`
}

// GitRepositoryStatusDTO represents the current status of a Git repository
type GitRepositoryStatusDTO struct {
	ConnectionStatus    string    `json:"connection_status"`
	LastValidated       time.Time `json:"last_validated"`
	CurrentCommit       string    `json:"current_commit"`
	BranchName          string    `json:"branch_name"`
	LastSyncAt          *time.Time `json:"last_sync_at,omitempty"`
	NextSyncScheduled   *time.Time `json:"next_sync_scheduled,omitempty"`
	SyncStatus          string    `json:"sync_status"`
}

// ValidationRequestDTO represents a request to validate a GitOps repository
type ValidationRequestDTO struct {
	RepositoryID    string            `json:"repository_id" validate:"required"`
	ValidationType  string            `json:"validation_type" validate:"required,oneof=connectivity configuration full"`
	Options         map[string]string `json:"options,omitempty"`
}

// GitOpsValidationResultDTO represents the result of repository validation
type GitOpsValidationResultDTO struct {
	Valid           bool              `json:"valid"`
	ValidationID    string            `json:"validation_id"`
	RepositoryID    string            `json:"repository_id"`
	ValidationType  string            `json:"validation_type"`
	Issues          []ValidationIssue `json:"issues,omitempty"`
	Performance     ValidationMetrics `json:"performance"`
	ValidatedAt     time.Time         `json:"validated_at"`
}

// ValidationIssue represents a validation issue
type ValidationIssue struct {
	Severity    string `json:"severity" validate:"required,oneof=error warning info"`
	Type        string `json:"type"`
	Message     string `json:"message"`
	Resource    string `json:"resource,omitempty"`
	FilePath    string `json:"file_path,omitempty"`
	LineNumber  int    `json:"line_number,omitempty"`
	Suggestion  string `json:"suggestion,omitempty"`
}

// ValidationMetrics tracks validation performance
type ValidationMetrics struct {
	Duration       time.Duration `json:"duration"`
	FilesChecked   int           `json:"files_checked"`
	RulesApplied   int           `json:"rules_applied"`
	CacheHitRate   float64       `json:"cache_hit_rate"`
}