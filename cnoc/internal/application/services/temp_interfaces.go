package services

import (
	"context"
	"time"
	"github.com/hedgehog/cnoc/internal/domain/gitops"
)

// Temporary interfaces to satisfy build dependencies
// These were moved from the disabled gitops_repository_application_service.go

// RepositorySyncService defines repository synchronization operations
type RepositorySyncService interface {
	// SyncRepository synchronizes a git repository and parses contents
	SyncRepository(ctx context.Context, repo *gitops.GitRepository, localPath string, encryptionKey []byte) (*RepositorySyncResult, error)
	
	// ParseYAMLFiles parses YAML files from a local repository path
	ParseYAMLFiles(ctx context.Context, localPath string) (*YAMLParseResult, error)
	
	// ValidateYAMLStructure validates YAML file structure and content
	ValidateYAMLStructure(ctx context.Context, yamlContent []byte) (*YAMLValidationResult, error)
	
	// DetectDrift compares local repository state with Kubernetes cluster
	DetectDrift(ctx context.Context, repo *gitops.GitRepository, clusterEndpoint string) (*DriftDetectionResult, error)
}

// RepositorySyncResult represents the result of a repository synchronization
type RepositorySyncResult struct {
	Success       bool                       `json:"success"`
	CommitHash    string                     `json:"commit_hash"`
	FilesChanged  int                        `json:"files_changed"`
	CRDsFound     int                        `json:"crds_found"`
	SyncDuration  time.Duration              `json:"sync_duration"`
	Errors        []string                   `json:"errors,omitempty"`
	Warnings      []string                   `json:"warnings,omitempty"`
	SyncedAt      time.Time                  `json:"synced_at"`
	Details       map[string]interface{}     `json:"details,omitempty"`
}

// YAMLParseResult represents the result of parsing YAML files
type YAMLParseResult struct {
	FilesProcessed int                        `json:"files_processed"`
	CRDsFound      int                        `json:"crds_found"`
	ParseErrors    []string                   `json:"parse_errors,omitempty"`
	ParsedObjects  []map[string]interface{}   `json:"parsed_objects"`
	ProcessingTime time.Duration              `json:"processing_time"`
}

// YAMLValidationResult represents the result of YAML validation
type YAMLValidationResult struct {
	Valid        bool                       `json:"valid"`
	Errors       []ValidationError          `json:"errors,omitempty"`
	Warnings     []ValidationWarning        `json:"warnings,omitempty"`
	Summary      map[string]interface{}     `json:"summary"`
}

// DriftDetectionResult represents the result of drift detection
type DriftDetectionResult struct {
	HasDrift      bool                       `json:"has_drift"`
	DriftItems    []DriftItem                `json:"drift_items,omitempty"`
	ComparedAt    time.Time                  `json:"compared_at"`
	Summary       map[string]interface{}     `json:"summary"`
}

// DriftItem represents a single configuration drift
type DriftItem struct {
	ResourceName string                     `json:"resource_name"`
	ResourceType string                     `json:"resource_type"`
	DriftType    string                     `json:"drift_type"` // "added", "removed", "modified"
	ExpectedValue interface{}               `json:"expected_value,omitempty"`
	ActualValue   interface{}               `json:"actual_value,omitempty"`
	FieldPath     string                     `json:"field_path,omitempty"`
}