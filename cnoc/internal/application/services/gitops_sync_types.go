package services

import (
	"context"
	"time"
)

// FORGE Movement 3: GitOps Sync Workflow Types and Interfaces
// These types support the GitOpsSyncWorkflowService implementation
// Mock types for testing until real domain types are fully integrated

// MockGitSyncResult represents the result of Git synchronization operations
type MockGitSyncResult struct {
	Success         bool                   `json:"success"`
	FilesChanged    []string               `json:"files_changed"`
	CommitHash      string                 `json:"commit_hash"`
	ConfigsUpdated  int                    `json:"configs_updated"`
	ErrorsCount     int                    `json:"errors_count"`
	SyncDirection   string                 `json:"sync_direction"` // "from_git" or "to_git"
	Timestamp       time.Time              `json:"timestamp"`
	Details         map[string]interface{} `json:"details"`
}

// MockKubernetesDiscoveryResult represents the result of Kubernetes discovery operations
type MockKubernetesDiscoveryResult struct {
	Success           bool                   `json:"success"`
	ResourcesFound    int                    `json:"resources_found"`
	CRDsDiscovered    []string               `json:"crds_discovered"`
	Namespaces        []string               `json:"namespaces"`
	ClusterVersion    string                 `json:"cluster_version"`
	ErrorsCount       int                    `json:"errors_count"`
	DiscoveryDuration time.Duration          `json:"discovery_duration"`
	Details           map[string]interface{} `json:"details"`
}

// MockDriftDetectionResult represents the result of drift detection operations
type MockDriftDetectionResult struct {
	HasDrift          bool                   `json:"has_drift"`
	DriftCount        int                    `json:"drift_count"`
	GitOnlyResources  []string               `json:"git_only_resources"`
	K8sOnlyResources  []string               `json:"k8s_only_resources"`
	MismatchedConfigs []string               `json:"mismatched_configs"`
	Severity          string                 `json:"severity"` // "low", "medium", "high", "critical"
	DetectionTime     time.Duration          `json:"detection_time"`
	Details           map[string]interface{} `json:"details"`
}

// MockFullSyncResult represents the result of a complete synchronization workflow
type MockFullSyncResult struct {
	GitSyncResult        *MockGitSyncResult             `json:"git_sync_result"`
	KubernetesDiscovery  *MockKubernetesDiscoveryResult `json:"kubernetes_discovery"`
	DriftDetection       *MockDriftDetectionResult      `json:"drift_detection"`
	OverallSuccess       bool                           `json:"overall_success"`
	TotalDuration        time.Duration                  `json:"total_duration"`
	OperationID          string                         `json:"operation_id"`
	FabricID             string                         `json:"fabric_id"`
	CompletedSteps       []string                       `json:"completed_steps"`
	FailedSteps          []string                       `json:"failed_steps"`
	RecommendedActions   []string                       `json:"recommended_actions"`
}

// MockConfigurationChange represents a configuration change to be applied
type MockConfigurationChange struct {
	Type         string                 `json:"type"`         // "create", "update", "delete"
	ResourceKind string                 `json:"resource_kind"` // "VPC", "Switch", "Connection"
	ResourceName string                 `json:"resource_name"`
	OldConfig    map[string]interface{} `json:"old_config,omitempty"`
	NewConfig    map[string]interface{} `json:"new_config,omitempty"`
	GitPath      string                 `json:"git_path"`
	Timestamp    time.Time              `json:"timestamp"`
}

// MockConfiguration represents a configuration resource
type MockConfiguration struct {
	ID           string                 `json:"id"`
	Kind         string                 `json:"kind"`         // "VPC", "Switch", "Connection"
	Name         string                 `json:"name"`
	Namespace    string                 `json:"namespace"`
	Labels       map[string]string      `json:"labels,omitempty"`
	Annotations  map[string]string      `json:"annotations,omitempty"`
	Spec         map[string]interface{} `json:"spec"`
	Status       map[string]interface{} `json:"status,omitempty"`
	GitPath      string                 `json:"git_path"`
	LastModified time.Time              `json:"last_modified"`
}

// GitOpsSyncWorkflowService defines the interface for GitOps synchronization workflows
// This orchestrates bidirectional Git sync and read-only Kubernetes discovery
type GitOpsSyncWorkflowService interface {
	// Bidirectional Git sync operations
	SyncFromGit(ctx context.Context, fabricID string) (*MockGitSyncResult, error)
	SyncToGit(ctx context.Context, fabricID string, changes []*MockConfigurationChange) (*MockGitSyncResult, error)
	
	// Unidirectional Kubernetes discovery (READ-ONLY)
	DiscoverFromKubernetes(ctx context.Context, fabricID string) (*MockKubernetesDiscoveryResult, error)
	
	// Drift detection comparing Git vs Kubernetes
	DetectConfigurationDrift(ctx context.Context, fabricID string) (*MockDriftDetectionResult, error)
	
	// Complete synchronization orchestration
	PerformFullSync(ctx context.Context, fabricID string) (*MockFullSyncResult, error)
	
	// Configuration management
	CreateConfiguration(ctx context.Context, fabricID string, config *MockConfiguration) error
	UpdateConfiguration(ctx context.Context, fabricID string, configID string, config *MockConfiguration) error
	DeleteConfiguration(ctx context.Context, fabricID string, configID string) error
}