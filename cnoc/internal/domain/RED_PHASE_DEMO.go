package domain

import (
	"context"
	"time"
)

// FORGE RED PHASE DEMONSTRATION
// This demonstrates the RED phase principle: tests that define interfaces and MUST fail before implementation

// KubernetesClusterService - Interface defined by tests in RED phase
// This interface DOES NOT HAVE AN IMPLEMENTATION YET - that's the RED phase requirement
type KubernetesClusterService interface {
	// Cluster connection with performance requirement: < 2 seconds
	ConnectToCluster(ctx context.Context, kubeconfig []byte) (*ClusterConnectionResult, error)
	
	// Resource deployment with performance requirement: < 3 seconds  
	DeployResource(ctx context.Context, resourceYAML []byte) (*ResourceDeploymentResult, error)
	
	// Resource querying with performance requirement: < 1 second
	QueryResourceState(ctx context.Context, resourceType, namespace, name string) (*KubernetesResourceState, error)
	
	// Configuration application with GitOps integration
	ApplyConfiguration(ctx context.Context, yamlContent []byte) (*ConfigurationApplyResult, error)
}

// Data structures defined by tests - no implementation yet
type ClusterConnectionResult struct {
	Success         bool          `json:"success"`
	ClusterName     string        `json:"cluster_name"`
	ServerVersion   string        `json:"server_version"`
	ConnectedAt     time.Time     `json:"connected_at"`
	ConnectionTime  time.Duration `json:"connection_time"`
	Error           string        `json:"error,omitempty"`
}

type ResourceDeploymentResult struct {
	Success       bool          `json:"success"`
	ResourceName  string        `json:"resource_name"`
	ResourceType  string        `json:"resource_type"`
	Namespace     string        `json:"namespace"`
	Action        string        `json:"action"` // "created", "updated", "unchanged"
	DeployTime    time.Duration `json:"deploy_time"`
	Error         string        `json:"error,omitempty"`
}

type KubernetesResourceState struct {
	Name         string                 `json:"name"`
	Namespace    string                 `json:"namespace"`
	ResourceType string                 `json:"resource_type"`
	Spec         map[string]interface{} `json:"spec"`
	Status       map[string]interface{} `json:"status"`
	IsReady      bool                   `json:"is_ready"`
	HealthStatus string                 `json:"health_status"`
}

type ConfigurationApplyResult struct {
	Success         bool                           `json:"success"`
	AppliedResources int                          `json:"applied_resources"`
	Results         []*ResourceDeploymentResult   `json:"results"`
	TotalTime       time.Duration                 `json:"total_time"`
	Errors          []string                      `json:"errors,omitempty"`
}