package services

import (
	"time"
)

// KubernetesServiceInterface represents the Kubernetes service interface
type KubernetesServiceInterface interface {
	GetClusterHealth() (*ClusterHealth, error)
	DeployConfiguration(config []byte) (*DeploymentResult, error)
	ApplyManifest(manifest []byte) (*ApplyResult, error)
	DeleteResource(kind, name, namespace string) (*DeletionResult, error)
	GetResourceState(kind, name, namespace string) (*ResourceState, error)
	ValidateManifest(manifest []byte) error
	ListResources(kind, namespace string) ([]map[string]interface{}, error)
	WatchResource(kind, name, namespace string) (<-chan ResourceState, error)
	GetLogs(podName, namespace string) (string, error)
	ScaleDeployment(name, namespace string, replicas int) error
}

// ClusterHealth represents Kubernetes cluster health information
type ClusterHealth struct {
	Healthy     bool              `json:"healthy"`
	Version     string            `json:"version"`
	NodeCount   int               `json:"node_count"`
	PodCount    int               `json:"pod_count"`
	Nodes       []NodeInfo        `json:"nodes"`
	Components  []ComponentStatus `json:"components"`
	CheckedAt   time.Time         `json:"checked_at"`
	Issues      []string          `json:"issues,omitempty"`
}

// NodeInfo represents information about a Kubernetes node
type NodeInfo struct {
	Name      string            `json:"name"`
	Ready     bool              `json:"ready"`
	Version   string            `json:"version"`
	Roles     []string          `json:"roles"`
	Labels    map[string]string `json:"labels"`
	Capacity  ResourceCapacity  `json:"capacity"`
	Usage     ResourceUsage     `json:"usage"`
}

// ComponentStatus represents the status of a Kubernetes component
type ComponentStatus struct {
	Name      string    `json:"name"`
	Healthy   bool      `json:"healthy"`
	Message   string    `json:"message,omitempty"`
	CheckedAt time.Time `json:"checked_at"`
}

// ResourceCapacity represents resource capacity
type ResourceCapacity struct {
	CPU    string `json:"cpu"`
	Memory string `json:"memory"`
	Pods   string `json:"pods"`
}

// ResourceUsage represents resource usage
type ResourceUsage struct {
	CPU    string `json:"cpu"`
	Memory string `json:"memory"`
	Pods   int    `json:"pods"`
}

// DeploymentResult represents the result of a deployment operation
type DeploymentResult struct {
	Success     bool              `json:"success"`
	DeployedAt  time.Time         `json:"deployed_at"`
	Resources   []ResourceInfo    `json:"resources"`
	Duration    time.Duration     `json:"duration"`
	Errors      []string          `json:"errors,omitempty"`
	Warnings    []string          `json:"warnings,omitempty"`
	Rollout     RolloutStatus     `json:"rollout"`
	Metadata    map[string]string `json:"metadata,omitempty"`
}

// ResourceInfo represents information about a deployed resource
type ResourceInfo struct {
	Kind      string            `json:"kind"`
	Name      string            `json:"name"`
	Namespace string            `json:"namespace"`
	Status    string            `json:"status"`
	Labels    map[string]string `json:"labels,omitempty"`
	CreatedAt time.Time         `json:"created_at"`
}

// RolloutStatus represents deployment rollout status
type RolloutStatus struct {
	Phase             string    `json:"phase"`
	Replicas          int       `json:"replicas"`
	UpdatedReplicas   int       `json:"updated_replicas"`
	ReadyReplicas     int       `json:"ready_replicas"`
	AvailableReplicas int       `json:"available_replicas"`
	Conditions        []string  `json:"conditions"`
	StartedAt         time.Time `json:"started_at"`
	CompletedAt       *time.Time `json:"completed_at,omitempty"`
}

// ApplyResult represents the result of applying a manifest
type ApplyResult struct {
	Success     bool              `json:"success"`
	AppliedAt   time.Time         `json:"applied_at"`
	Operation   string            `json:"operation"` // created, updated, unchanged
	Resource    ResourceInfo      `json:"resource"`
	Duration    time.Duration     `json:"duration"`
	Errors      []string          `json:"errors,omitempty"`
	Warnings    []string          `json:"warnings,omitempty"`
	DryRun      bool              `json:"dry_run"`
	Diff        *ResourceDiff     `json:"diff,omitempty"`
}

// ResourceDiff represents differences between desired and current state
type ResourceDiff struct {
	Added    map[string]interface{} `json:"added,omitempty"`
	Modified map[string]interface{} `json:"modified,omitempty"`
	Removed  map[string]interface{} `json:"removed,omitempty"`
}

// DeletionResult represents the result of a resource deletion
type DeletionResult struct {
	Success     bool          `json:"success"`
	DeletedAt   time.Time     `json:"deleted_at"`
	Resource    ResourceInfo  `json:"resource"`
	Duration    time.Duration `json:"duration"`
	Errors      []string      `json:"errors,omitempty"`
	Warnings    []string      `json:"warnings,omitempty"`
	FinalCleanup bool         `json:"final_cleanup"`
	Cascade     string        `json:"cascade"`
}

// ResourceState represents the current state of a Kubernetes resource
type ResourceState struct {
	Resource     ResourceInfo           `json:"resource"`
	Phase        string                 `json:"phase"`
	Ready        bool                   `json:"ready"`
	Conditions   []ResourceCondition    `json:"conditions"`
	Spec         map[string]interface{} `json:"spec"`
	Status       map[string]interface{} `json:"status"`
	Events       []ResourceEvent        `json:"events,omitempty"`
	LastUpdated  time.Time              `json:"last_updated"`
	Generation   int64                  `json:"generation"`
	Annotations  map[string]string      `json:"annotations,omitempty"`
}

// ResourceCondition represents a condition of a Kubernetes resource
type ResourceCondition struct {
	Type               string    `json:"type"`
	Status             string    `json:"status"`
	Reason             string    `json:"reason,omitempty"`
	Message            string    `json:"message,omitempty"`
	LastTransitionTime time.Time `json:"last_transition_time"`
	LastProbeTime      time.Time `json:"last_probe_time,omitempty"`
}

// ResourceEvent represents an event related to a Kubernetes resource
type ResourceEvent struct {
	Type      string    `json:"type"`
	Reason    string    `json:"reason"`
	Message   string    `json:"message"`
	Source    string    `json:"source"`
	Count     int       `json:"count"`
	FirstTime time.Time `json:"first_time"`
	LastTime  time.Time `json:"last_time"`
}