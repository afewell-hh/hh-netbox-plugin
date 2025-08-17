package external

import (
	"fmt"
	"time"

	"k8s.io/apimachinery/pkg/runtime/schema"
)

// Kubernetes adapter types with anti-corruption layer patterns
// Following MDD principles to prevent external service contamination

// Deployment types

// K8sDeploymentOptions configures Kubernetes deployment behavior
type K8sDeploymentOptions struct {
	Namespace          string            `json:"namespace"`
	Labels             map[string]string `json:"labels,omitempty"`
	Annotations        map[string]string `json:"annotations,omitempty"`
	UpdateStrategy     K8sUpdateStrategy `json:"update_strategy"`
	DryRun            bool              `json:"dry_run"`
	OwnerReferences   []K8sOwnerReference `json:"owner_references,omitempty"`
	ResourceQuota     *K8sResourceQuota `json:"resource_quota,omitempty"`
}

// K8sDeploymentResult contains deployment operation results
type K8sDeploymentResult struct {
	ConfigurationID string                  `json:"configuration_id"`
	Namespace       string                  `json:"namespace"`
	Resources       []K8sResourceDeployment `json:"resources"`
	Status          K8sDeploymentStatus     `json:"status"`
	StartTime       time.Time               `json:"start_time"`
	CompletionTime  time.Time               `json:"completion_time,omitempty"`
	Duration        time.Duration           `json:"duration"`
	ErrorMessage    string                  `json:"error_message,omitempty"`
}

// K8sResourceDeployment represents a deployed Kubernetes resource
type K8sResourceDeployment struct {
	Name         string              `json:"name"`
	Namespace    string              `json:"namespace"`
	Kind         string              `json:"kind"`
	APIVersion   string              `json:"api_version"`
	Labels       map[string]string   `json:"labels,omitempty"`
	Annotations  map[string]string   `json:"annotations,omitempty"`
	Status       K8sResourceStatus   `json:"status"`
	CreatedAt    time.Time           `json:"created_at"`
	HealthChecks []K8sHealthCheck    `json:"health_checks,omitempty"`
}

// Update types

// K8sUpdateOptions configures update behavior
type K8sUpdateOptions struct {
	Namespace      string            `json:"namespace"`
	UpdateStrategy K8sUpdateStrategy `json:"update_strategy"`
	DryRun        bool              `json:"dry_run"`
	ForceUpdate   bool              `json:"force_update"`
	BackupEnabled bool              `json:"backup_enabled"`
}

// K8sUpdateResult contains update operation results
type K8sUpdateResult struct {
	ConfigurationID  string              `json:"configuration_id"`
	PreviousStatus   *K8sConfigurationStatus `json:"previous_status"`
	UpdatedResources []K8sResourceUpdate `json:"updated_resources"`
	Status           K8sUpdateStatus     `json:"status"`
	StartTime        time.Time           `json:"start_time"`
	CompletionTime   time.Time           `json:"completion_time,omitempty"`
	Duration         time.Duration       `json:"duration"`
	ErrorMessage     string              `json:"error_message,omitempty"`
}

// K8sResourceUpdate represents an updated Kubernetes resource
type K8sResourceUpdate struct {
	Name         string            `json:"name"`
	Namespace    string            `json:"namespace"`
	Kind         string            `json:"kind"`
	APIVersion   string            `json:"api_version"`
	UpdateType   string            `json:"update_type"`
	PreviousHash string            `json:"previous_hash,omitempty"`
	CurrentHash  string            `json:"current_hash,omitempty"`
	UpdatedAt    time.Time         `json:"updated_at"`
	Changes      []K8sResourceChange `json:"changes,omitempty"`
}

// K8sResourceChange represents a specific resource change
type K8sResourceChange struct {
	Field        string      `json:"field"`
	PreviousValue interface{} `json:"previous_value"`
	NewValue     interface{} `json:"new_value"`
	ChangeType   string      `json:"change_type"`
}

// Delete types

// K8sDeleteOptions configures deletion behavior
type K8sDeleteOptions struct {
	Namespace          string                `json:"namespace"`
	GracePeriodSeconds *int64                `json:"grace_period_seconds,omitempty"`
	DryRun            bool                  `json:"dry_run"`
	Cascade           K8sCascadeDeletePolicy `json:"cascade"`
	BackupEnabled     bool                  `json:"backup_enabled"`
}

// K8sDeleteResult contains deletion operation results
type K8sDeleteResult struct {
	ConfigurationID  string                `json:"configuration_id"`
	DeletedResources []K8sResourceDeletion `json:"deleted_resources"`
	Status           K8sDeleteStatus       `json:"status"`
	StartTime        time.Time             `json:"start_time"`
	CompletionTime   time.Time             `json:"completion_time,omitempty"`
	Duration         time.Duration         `json:"duration"`
	ErrorMessage     string                `json:"error_message,omitempty"`
}

// K8sResourceDeletion represents a deleted Kubernetes resource
type K8sResourceDeletion struct {
	Name        string        `json:"name"`
	Namespace   string        `json:"namespace"`
	Kind        string        `json:"kind"`
	APIVersion  string        `json:"api_version"`
	DeletedAt   time.Time     `json:"deleted_at"`
	Finalizers  []string      `json:"finalizers,omitempty"`
	DeleteType  string        `json:"delete_type"`
}

// Status and health types

// K8sConfigurationStatus represents configuration status in Kubernetes
type K8sConfigurationStatus struct {
	ConfigurationID string              `json:"configuration_id"`
	Namespace       string              `json:"namespace"`
	Resources       []K8sResourceStatus `json:"resources"`
	OverallStatus   K8sStatus           `json:"overall_status"`
	HealthScore     float64             `json:"health_score"`
	LastChecked     time.Time           `json:"last_checked"`
	Events          []K8sEvent          `json:"events,omitempty"`
}

// K8sResourceStatus represents status of a Kubernetes resource
type K8sResourceStatus struct {
	Name           string            `json:"name"`
	Namespace      string            `json:"namespace"`
	Kind           string            `json:"kind"`
	APIVersion     string            `json:"api_version"`
	Status         K8sResourceState  `json:"status"`
	Ready          bool              `json:"ready"`
	Replicas       *K8sReplicaStatus `json:"replicas,omitempty"`
	Conditions     []K8sCondition    `json:"conditions,omitempty"`
	LastTransition time.Time         `json:"last_transition"`
	Message        string            `json:"message,omitempty"`
}

// K8sReplicaStatus represents replica status for deployments
type K8sReplicaStatus struct {
	Desired     int32 `json:"desired"`
	Current     int32 `json:"current"`
	Ready       int32 `json:"ready"`
	Available   int32 `json:"available"`
	Unavailable int32 `json:"unavailable"`
}

// K8sCondition represents a Kubernetes condition
type K8sCondition struct {
	Type               string    `json:"type"`
	Status             string    `json:"status"`
	LastUpdateTime     time.Time `json:"last_update_time"`
	LastTransitionTime time.Time `json:"last_transition_time"`
	Reason             string    `json:"reason,omitempty"`
	Message            string    `json:"message,omitempty"`
}

// K8sEvent represents a Kubernetes event
type K8sEvent struct {
	Type      string    `json:"type"`
	Reason    string    `json:"reason"`
	Message   string    `json:"message"`
	Source    string    `json:"source"`
	Timestamp time.Time `json:"timestamp"`
	Count     int32     `json:"count"`
}

// Component types

// K8sComponentOptions configures component deployment
type K8sComponentOptions struct {
	Namespace      string            `json:"namespace"`
	Labels         map[string]string `json:"labels,omitempty"`
	Annotations    map[string]string `json:"annotations,omitempty"`
	DryRun        bool              `json:"dry_run"`
	ResourceLimits *K8sResourceLimits `json:"resource_limits,omitempty"`
}

// K8sComponentDeployment represents a deployed component
type K8sComponentDeployment struct {
	ComponentName string                  `json:"component_name"`
	Version       string                  `json:"version"`
	Namespace     string                  `json:"namespace"`
	Resources     []K8sResourceDeployment `json:"resources"`
	Status        K8sComponentStatus      `json:"status"`
	DeployedAt    time.Time               `json:"deployed_at"`
	HealthChecks  []K8sHealthCheck        `json:"health_checks,omitempty"`
}

// Health and monitoring types

// K8sClusterHealth represents overall cluster health
type K8sClusterHealth struct {
	CheckedAt     time.Time         `json:"checked_at"`
	Namespace     string            `json:"namespace"`
	OverallStatus K8sHealthStatus   `json:"overall_status"`
	HealthScore   float64           `json:"health_score"`
	NodeHealth    []K8sNodeHealth   `json:"node_health"`
	PodHealth     []K8sPodHealth    `json:"pod_health"`
	SystemHealth  K8sSystemHealth   `json:"system_health"`
}

// K8sNodeHealth represents node health status
type K8sNodeHealth struct {
	NodeName      string            `json:"node_name"`
	Status        K8sHealthStatus   `json:"status"`
	Ready         bool              `json:"ready"`
	Schedulable   bool              `json:"schedulable"`
	Conditions    []K8sCondition    `json:"conditions"`
	Capacity      K8sNodeCapacity   `json:"capacity"`
	Allocatable   K8sNodeCapacity   `json:"allocatable"`
	Usage         K8sNodeUsage      `json:"usage"`
	LastHeartbeat time.Time         `json:"last_heartbeat"`
}

// K8sNodeCapacity represents node resource capacity
type K8sNodeCapacity struct {
	CPU           string `json:"cpu"`
	Memory        string `json:"memory"`
	Storage       string `json:"storage"`
	Pods          int32  `json:"pods"`
	EphemeralStorage string `json:"ephemeral_storage"`
}

// K8sNodeUsage represents current node resource usage
type K8sNodeUsage struct {
	CPUPercent     float64 `json:"cpu_percent"`
	MemoryPercent  float64 `json:"memory_percent"`
	StoragePercent float64 `json:"storage_percent"`
	PodCount       int32   `json:"pod_count"`
}

// K8sPodHealth represents pod health status
type K8sPodHealth struct {
	PodName       string             `json:"pod_name"`
	Namespace     string             `json:"namespace"`
	Status        K8sHealthStatus    `json:"status"`
	Phase         string             `json:"phase"`
	Ready         bool               `json:"ready"`
	Containers    []K8sContainerHealth `json:"containers"`
	Conditions    []K8sCondition     `json:"conditions"`
	RestartCount  int32              `json:"restart_count"`
	LastRestart   *time.Time         `json:"last_restart,omitempty"`
}

// K8sContainerHealth represents container health within a pod
type K8sContainerHealth struct {
	Name         string          `json:"name"`
	Ready        bool            `json:"ready"`
	RestartCount int32           `json:"restart_count"`
	Status       K8sHealthStatus `json:"status"`
	LastState    string          `json:"last_state,omitempty"`
	CurrentState string          `json:"current_state"`
}

// K8sSystemHealth represents system-level health metrics
type K8sSystemHealth struct {
	APIServerHealth     K8sHealthStatus `json:"api_server_health"`
	ControllerHealth    K8sHealthStatus `json:"controller_health"`
	SchedulerHealth     K8sHealthStatus `json:"scheduler_health"`
	EtcdHealth          K8sHealthStatus `json:"etcd_health"`
	DNSHealth           K8sHealthStatus `json:"dns_health"`
	NetworkingHealth    K8sHealthStatus `json:"networking_health"`
}

// Resource and metrics types

// K8sResourceMetrics represents resource utilization metrics
type K8sResourceMetrics struct {
	ConfigurationID  string              `json:"configuration_id"`
	Namespace        string              `json:"namespace"`
	PodMetrics       []K8sPodMetrics     `json:"pod_metrics"`
	AggregateMetrics K8sAggregateMetrics `json:"aggregate_metrics"`
	CollectedAt      time.Time           `json:"collected_at"`
}

// K8sPodMetrics represents metrics for a single pod
type K8sPodMetrics struct {
	PodName           string              `json:"pod_name"`
	Namespace         string              `json:"namespace"`
	CPURequests       string              `json:"cpu_requests"`
	CPULimits         string              `json:"cpu_limits"`
	MemoryRequests    string              `json:"memory_requests"`
	MemoryLimits      string              `json:"memory_limits"`
	ContainerMetrics  []K8sContainerMetrics `json:"container_metrics"`
	NetworkMetrics    K8sNetworkMetrics   `json:"network_metrics"`
	StorageMetrics    K8sStorageMetrics   `json:"storage_metrics"`
}

// K8sContainerMetrics represents metrics for a container
type K8sContainerMetrics struct {
	ContainerName string  `json:"container_name"`
	CPUUsage      string  `json:"cpu_usage"`
	MemoryUsage   string  `json:"memory_usage"`
	CPUPercent    float64 `json:"cpu_percent"`
	MemoryPercent float64 `json:"memory_percent"`
}

// K8sNetworkMetrics represents network metrics
type K8sNetworkMetrics struct {
	RxBytes   int64 `json:"rx_bytes"`
	TxBytes   int64 `json:"tx_bytes"`
	RxPackets int64 `json:"rx_packets"`
	TxPackets int64 `json:"tx_packets"`
	RxErrors  int64 `json:"rx_errors"`
	TxErrors  int64 `json:"tx_errors"`
}

// K8sStorageMetrics represents storage metrics
type K8sStorageMetrics struct {
	UsedBytes      int64   `json:"used_bytes"`
	AvailableBytes int64   `json:"available_bytes"`
	CapacityBytes  int64   `json:"capacity_bytes"`
	UsagePercent   float64 `json:"usage_percent"`
}

// K8sAggregateMetrics represents aggregated metrics
type K8sAggregateMetrics struct {
	PodCount            int    `json:"pod_count"`
	TotalCPURequests    string `json:"total_cpu_requests"`
	TotalMemoryRequests string `json:"total_memory_requests"`
	TotalCPULimits      string `json:"total_cpu_limits"`
	TotalMemoryLimits   string `json:"total_memory_limits"`
	AverageCPUUsage     float64 `json:"average_cpu_usage"`
	AverageMemoryUsage  float64 `json:"average_memory_usage"`
}

// Manifest and resource types

// K8sManifest represents a Kubernetes manifest
type K8sManifest struct {
	GVR     schema.GroupVersionResource `json:"gvr"`
	Content map[string]interface{}      `json:"content"`
	Hash    string                      `json:"hash"`
}

// K8sResourceLimits defines resource limits for components
type K8sResourceLimits struct {
	CPU           string `json:"cpu,omitempty"`
	Memory        string `json:"memory,omitempty"`
	Storage       string `json:"storage,omitempty"`
	EphemeralStorage string `json:"ephemeral_storage,omitempty"`
}

// K8sResourceQuota defines namespace resource quotas
type K8sResourceQuota struct {
	Hard     map[string]string `json:"hard"`
	Used     map[string]string `json:"used,omitempty"`
	Enforced bool              `json:"enforced"`
}

// K8sOwnerReference represents owner reference for resources
type K8sOwnerReference struct {
	APIVersion         string `json:"api_version"`
	Kind               string `json:"kind"`
	Name               string `json:"name"`
	UID                string `json:"uid"`
	Controller         *bool  `json:"controller,omitempty"`
	BlockOwnerDeletion *bool  `json:"block_owner_deletion,omitempty"`
}

// K8sHealthCheck represents a health check configuration
type K8sHealthCheck struct {
	Type            K8sHealthCheckType `json:"type"`
	Path            string             `json:"path,omitempty"`
	Port            int32              `json:"port,omitempty"`
	IntervalSeconds int32              `json:"interval_seconds"`
	TimeoutSeconds  int32              `json:"timeout_seconds"`
	SuccessThreshold int32             `json:"success_threshold"`
	FailureThreshold int32             `json:"failure_threshold"`
	Status          K8sHealthStatus    `json:"status"`
	LastChecked     time.Time          `json:"last_checked"`
}

// Enum types with proper validation

// K8sDeploymentStatus represents deployment status
type K8sDeploymentStatus string

const (
	K8sDeploymentStatusPending    K8sDeploymentStatus = "pending"
	K8sDeploymentStatusInProgress K8sDeploymentStatus = "in_progress"
	K8sDeploymentStatusSuccess    K8sDeploymentStatus = "success"
	K8sDeploymentStatusFailed     K8sDeploymentStatus = "failed"
	K8sDeploymentStatusRolledBack K8sDeploymentStatus = "rolled_back"
)

// K8sUpdateStatus represents update status
type K8sUpdateStatus string

const (
	K8sUpdateStatusPending    K8sUpdateStatus = "pending"
	K8sUpdateStatusInProgress K8sUpdateStatus = "in_progress"
	K8sUpdateStatusSuccess    K8sUpdateStatus = "success"
	K8sUpdateStatusFailed     K8sUpdateStatus = "failed"
	K8sUpdateStatusRolledBack K8sUpdateStatus = "rolled_back"
)

// K8sDeleteStatus represents deletion status
type K8sDeleteStatus string

const (
	K8sDeleteStatusPending        K8sDeleteStatus = "pending"
	K8sDeleteStatusInProgress     K8sDeleteStatus = "in_progress"
	K8sDeleteStatusSuccess        K8sDeleteStatus = "success"
	K8sDeleteStatusFailed         K8sDeleteStatus = "failed"
	K8sDeleteStatusPartialFailure K8sDeleteStatus = "partial_failure"
)

// K8sUpdateStrategy represents update strategy
type K8sUpdateStrategy string

const (
	K8sUpdateStrategyRollingUpdate K8sUpdateStrategy = "rolling_update"
	K8sUpdateStrategyRecreate      K8sUpdateStrategy = "recreate"
	K8sUpdateStrategyBlueGreen     K8sUpdateStrategy = "blue_green"
	K8sUpdateStrategyCanary        K8sUpdateStrategy = "canary"
)

// K8sCascadeDeletePolicy represents cascade delete policy
type K8sCascadeDeletePolicy string

const (
	K8sCascadeDeletePolicyForeground K8sCascadeDeletePolicy = "foreground"
	K8sCascadeDeletePolicyBackground K8sCascadeDeletePolicy = "background"
	K8sCascadeDeletePolicyOrphan     K8sCascadeDeletePolicy = "orphan"
)

// K8sStatus represents resource status
type K8sStatus string

const (
	K8sStatusUnknown   K8sStatus = "unknown"
	K8sStatusHealthy   K8sStatus = "healthy"
	K8sStatusDegraded  K8sStatus = "degraded"
	K8sStatusUnhealthy K8sStatus = "unhealthy"
	K8sStatusFailed    K8sStatus = "failed"
)

// K8sResourceState represents resource state
type K8sResourceState string

const (
	K8sResourceStatePending   K8sResourceState = "pending"
	K8sResourceStateRunning   K8sResourceState = "running"
	K8sResourceStateSucceeded K8sResourceState = "succeeded"
	K8sResourceStateFailed    K8sResourceState = "failed"
	K8sResourceStateUnknown   K8sResourceState = "unknown"
)

// K8sOperationStatus represents resource deployment operation status
type K8sOperationStatus string

const (
	K8sOperationStatusCreated  K8sOperationStatus = "created"
	K8sOperationStatusUpdated  K8sOperationStatus = "updated"
	K8sOperationStatusDeleted  K8sOperationStatus = "deleted"
	K8sOperationStatusError    K8sOperationStatus = "error"
)

// K8sComponentStatus represents component status
type K8sComponentStatus string

const (
	K8sComponentStatusPending   K8sComponentStatus = "pending"
	K8sComponentStatusDeployed  K8sComponentStatus = "deployed"
	K8sComponentStatusRunning   K8sComponentStatus = "running"
	K8sComponentStatusFailed    K8sComponentStatus = "failed"
	K8sComponentStatusStopped   K8sComponentStatus = "stopped"
)

// K8sHealthStatus represents health status
type K8sHealthStatus string

const (
	K8sHealthStatusUnknown    K8sHealthStatus = "unknown"
	K8sHealthStatusHealthy    K8sHealthStatus = "healthy"
	K8sHealthStatusDegraded   K8sHealthStatus = "degraded"
	K8sHealthStatusUnhealthy  K8sHealthStatus = "unhealthy"
	K8sHealthStatusCritical   K8sHealthStatus = "critical"
)

// K8sHealthCheckType represents health check type
type K8sHealthCheckType string

const (
	K8sHealthCheckTypeHTTP K8sHealthCheckType = "http"
	K8sHealthCheckTypeTCP  K8sHealthCheckType = "tcp"
	K8sHealthCheckTypeExec K8sHealthCheckType = "exec"
	K8sHealthCheckTypeGRPC K8sHealthCheckType = "grpc"
)

// Validation methods for enum types

// IsValid validates K8sDeploymentStatus
func (s K8sDeploymentStatus) IsValid() bool {
	switch s {
	case K8sDeploymentStatusPending, K8sDeploymentStatusInProgress,
		 K8sDeploymentStatusSuccess, K8sDeploymentStatusFailed, K8sDeploymentStatusRolledBack:
		return true
	}
	return false
}

// IsValid validates K8sUpdateStrategy
func (s K8sUpdateStrategy) IsValid() bool {
	switch s {
	case K8sUpdateStrategyRollingUpdate, K8sUpdateStrategyRecreate,
		 K8sUpdateStrategyBlueGreen, K8sUpdateStrategyCanary:
		return true
	}
	return false
}

// IsValid validates K8sHealthStatus
func (s K8sHealthStatus) IsValid() bool {
	switch s {
	case K8sHealthStatusUnknown, K8sHealthStatusHealthy, K8sHealthStatusDegraded,
		 K8sHealthStatusUnhealthy, K8sHealthStatusCritical:
		return true
	}
	return false
}

// Helper methods for resource management

// GetResourceIdentifier returns a unique identifier for a Kubernetes resource
func (r K8sResourceDeployment) GetResourceIdentifier() string {
	return fmt.Sprintf("%s/%s/%s/%s", r.APIVersion, r.Kind, r.Namespace, r.Name)
}

// IsReady checks if the resource is ready
func (r K8sResourceStatus) IsReady() bool {
	return r.Ready && r.Status == K8sResourceStateRunning
}

// GetHealthPercentage calculates health percentage from health score
func (h K8sClusterHealth) GetHealthPercentage() float64 {
	return h.HealthScore
}

// IsHealthy checks if the cluster is healthy
func (h K8sClusterHealth) IsHealthy() bool {
	return h.OverallStatus == K8sHealthStatusHealthy || h.OverallStatus == K8sHealthStatusDegraded
}

// GetTotalPods returns total number of pods in health check
func (h K8sClusterHealth) GetTotalPods() int {
	return len(h.PodHealth)
}

// GetHealthyPods returns number of healthy pods
func (h K8sClusterHealth) GetHealthyPods() int {
	count := 0
	for _, pod := range h.PodHealth {
		if pod.Status == K8sHealthStatusHealthy {
			count++
		}
	}
	return count
}

// GetTotalNodes returns total number of nodes in health check
func (h K8sClusterHealth) GetTotalNodes() int {
	return len(h.NodeHealth)
}

// GetReadyNodes returns number of ready nodes
func (h K8sClusterHealth) GetReadyNodes() int {
	count := 0
	for _, node := range h.NodeHealth {
		if node.Ready {
			count++
		}
	}
	return count
}