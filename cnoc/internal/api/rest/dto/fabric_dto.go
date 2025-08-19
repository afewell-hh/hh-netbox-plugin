package dto

import (
	"time"

	"github.com/hedgehog/cnoc/internal/domain"
)

// FabricDTO represents fabric information for API responses
type FabricDTO struct {
	ID          string    `json:"id"`
	Name        string    `json:"name"`
	Description string    `json:"description"`
	Status      string    `json:"status"`
	
	// Connection information
	ConnectionStatus string `json:"connection_status"`
	KubernetesServer string `json:"kubernetes_server,omitempty"`
	
	// GitOps configuration
	GitRepositoryID *string `json:"git_repository_id,omitempty"`
	GitOpsDirectory string  `json:"gitops_directory,omitempty"`
	GitOpsBranch    string  `json:"gitops_branch,omitempty"`
	
	// Synchronization status
	SyncStatus      string     `json:"sync_status"`
	GitSyncStatus   string     `json:"git_sync_status"`
	LastSyncTime    *time.Time `json:"last_sync_time,omitempty"`
	LastGitSync     *time.Time `json:"last_git_sync,omitempty"`
	
	// Resource counts
	CachedCRDCount    int `json:"cached_crd_count"`
	CachedVPCCount    int `json:"cached_vpc_count"`
	CachedSwitchCount int `json:"cached_switch_count"`
	
	// Drift detection
	DriftStatus    string    `json:"drift_status"`
	DriftCount     int       `json:"drift_count"`
	LastDriftCheck time.Time `json:"last_drift_check"`
	
	// Audit information
	CreatedAt    time.Time `json:"created_at"`
	LastModified time.Time `json:"last_modified"`
	CreatedBy    string    `json:"created_by"`
	ModifiedBy   string    `json:"modified_by"`
}

// CreateFabricRequestDTO represents a request to create a new fabric
type CreateFabricRequestDTO struct {
	Name        string `json:"name" validate:"required,max=100"`
	Description string `json:"description" validate:"max=500"`
	
	// Kubernetes connection
	KubernetesServer string `json:"kubernetes_server" validate:"omitempty,url"`
	KubernetesToken  string `json:"kubernetes_token,omitempty"`
	
	// GitOps configuration
	GitRepositoryID string `json:"git_repository_id" validate:"required"`
	GitOpsDirectory string `json:"gitops_directory" validate:"required"`
	GitOpsBranch    string `json:"gitops_branch"`
	
	// Metadata
	CreatedBy string `json:"created_by"`
}

// UpdateFabricRequestDTO represents a request to update an existing fabric
type UpdateFabricRequestDTO struct {
	Name        *string `json:"name,omitempty" validate:"omitempty,max=100"`
	Description *string `json:"description,omitempty" validate:"omitempty,max=500"`
	
	// Status update
	Status           *string `json:"status,omitempty"`
	ConnectionStatus *string `json:"connection_status,omitempty"`
	
	// Kubernetes connection
	KubernetesServer *string `json:"kubernetes_server,omitempty" validate:"omitempty,url"`
	KubernetesToken  *string `json:"kubernetes_token,omitempty"`
	
	// GitOps configuration
	GitRepositoryID *string `json:"git_repository_id,omitempty"`
	GitOpsDirectory *string `json:"gitops_directory,omitempty"`
	GitOpsBranch    *string `json:"gitops_branch,omitempty"`
	
	// Metadata
	ModifiedBy string `json:"modified_by"`
}

// FabricListResponseDTO represents a paginated list of fabrics
type FabricListResponseDTO struct {
	Items      []FabricDTO `json:"items"`
	TotalCount int         `json:"total_count"`
	Page       int         `json:"page"`
	PageSize   int         `json:"page_size"`
	HasMore    bool        `json:"has_more"`
}

// FabricSyncRequestDTO represents a request to synchronize a fabric
type FabricSyncRequestDTO struct {
	ForceSync bool              `json:"force_sync"`
	DryRun    bool              `json:"dry_run"`
	Source    string            `json:"source"`
	Metadata  map[string]string `json:"metadata,omitempty"`
}

// FabricSyncResponseDTO represents the result of a fabric synchronization
type FabricSyncResponseDTO struct {
	Success         bool                     `json:"success"`
	FabricID        string                   `json:"fabric_id"`
	SyncedResources int                      `json:"synced_resources"`
	Errors          []FabricSyncErrorDTO     `json:"errors,omitempty"`
	Warnings        []FabricSyncWarningDTO   `json:"warnings,omitempty"`
	DriftDetected   bool                     `json:"drift_detected"`
	DriftSummary    *FabricDriftSummaryDTO   `json:"drift_summary,omitempty"`
	Performance     *SyncPerformanceDTO      `json:"performance"`
	SyncedAt        time.Time                `json:"synced_at"`
	RequestID       string                   `json:"request_id"`
}

// FabricSyncErrorDTO represents a fabric synchronization error
type FabricSyncErrorDTO struct {
	Code        string `json:"code"`
	Message     string `json:"message"`
	Resource    string `json:"resource,omitempty"`
	Severity    string `json:"severity"`
	Recoverable bool   `json:"recoverable"`
}

// FabricSyncWarningDTO represents a fabric synchronization warning
type FabricSyncWarningDTO struct {
	Code       string `json:"code"`
	Message    string `json:"message"`
	Resource   string `json:"resource,omitempty"`
	Suggestion string `json:"suggestion,omitempty"`
}

// FabricDriftSummaryDTO represents drift detection summary
type FabricDriftSummaryDTO struct {
	DriftedResources int                      `json:"drifted_resources"`
	TotalResources   int                      `json:"total_resources"`
	DriftPercentage  float64                  `json:"drift_percentage"`
	DriftDetails     []FabricDriftDetailDTO   `json:"drift_details,omitempty"`
	LastDriftCheck   time.Time                `json:"last_drift_check"`
}

// FabricDriftDetailDTO represents individual drift details
type FabricDriftDetailDTO struct {
	ResourceName string                 `json:"resource_name"`
	ResourceType string                 `json:"resource_type"`
	DriftType    string                 `json:"drift_type"`
	Expected     map[string]interface{} `json:"expected"`
	Actual       map[string]interface{} `json:"actual"`
	Severity     string                 `json:"severity"`
}

// SyncPerformanceDTO represents sync performance data
type SyncPerformanceDTO struct {
	DurationMs       int64 `json:"duration_ms"`
	ResourcesPerSec  float64 `json:"resources_per_second"`
	NetworkLatencyMs int64 `json:"network_latency_ms"`
	ProcessingTimeMs int64 `json:"processing_time_ms"`
	ValidationTimeMs int64 `json:"validation_time_ms"`
}

// FabricValidationResponseDTO represents fabric validation results
type FabricValidationResponseDTO struct {
	Valid           bool                         `json:"valid"`
	FabricID        string                       `json:"fabric_id"`
	ValidationLevel string                       `json:"validation_level"`
	Errors          []FabricValidationErrorDTO   `json:"errors,omitempty"`
	Warnings        []FabricValidationWarningDTO `json:"warnings,omitempty"`
	ValidatedAt     time.Time                    `json:"validated_at"`
	RequestID       string                       `json:"request_id"`
}

// FabricValidationErrorDTO represents fabric validation errors
type FabricValidationErrorDTO struct {
	Code        string `json:"code"`
	Message     string `json:"message"`
	Resource    string `json:"resource,omitempty"`
	Field       string `json:"field,omitempty"`
	Severity    string `json:"severity"`
	Recoverable bool   `json:"recoverable"`
}

// FabricValidationWarningDTO represents fabric validation warnings
type FabricValidationWarningDTO struct {
	Code       string `json:"code"`
	Message    string `json:"message"`
	Resource   string `json:"resource,omitempty"`
	Field      string `json:"field,omitempty"`
	Suggestion string `json:"suggestion,omitempty"`
}

// DTO Mapping Functions

// ToFabricDTO converts a domain Fabric to FabricDTO
func ToFabricDTO(fabric *domain.Fabric) *FabricDTO {
	if fabric == nil {
		return nil
	}

	var lastSyncTime *time.Time
	if !fabric.LastSyncTime.IsZero() {
		lastSyncTime = &fabric.LastSyncTime
	}

	return &FabricDTO{
		ID:               fabric.ID,
		Name:             fabric.Name,
		Description:      fabric.Description,
		Status:           string(fabric.Status),
		ConnectionStatus: string(fabric.ConnectionStatus),
		KubernetesServer: fabric.KubernetesServer,
		GitRepositoryID:  fabric.GitRepositoryID,
		GitOpsDirectory:  fabric.GitOpsDirectory,
		GitOpsBranch:     fabric.GitOpsBranch,
		SyncStatus:       string(fabric.SyncStatus),
		GitSyncStatus:    string(fabric.GitSyncStatus),
		LastSyncTime:     lastSyncTime,
		LastGitSync:      fabric.LastGitSync,
		CachedCRDCount:   fabric.CachedCRDCount,
		CachedVPCCount:   fabric.CachedVPCCount,
		CachedSwitchCount: fabric.CachedSwitchCount,
		DriftStatus:      fabric.DriftStatus,
		DriftCount:       fabric.DriftCount,
		LastDriftCheck:   fabric.LastDriftCheck,
		CreatedAt:        fabric.Created,
		LastModified:     fabric.LastModified,
		CreatedBy:        fabric.CreatedBy,
		ModifiedBy:       fabric.ModifiedBy,
	}
}

// ToFabricDomain converts a CreateFabricRequestDTO to domain Fabric
func (dto *CreateFabricRequestDTO) ToFabricDomain() *domain.Fabric {
	fabric := &domain.Fabric{
		Name:        dto.Name,
		Description: dto.Description,
		Status:      domain.FabricStatusPlanned,
		
		KubernetesServer: dto.KubernetesServer,
		KubernetesToken:  dto.KubernetesToken,
		
		GitRepositoryID: &dto.GitRepositoryID,
		GitOpsDirectory: dto.GitOpsDirectory,
		GitOpsBranch:    dto.GitOpsBranch,
		
		ConnectionStatus: domain.ConnectionStatusUnknown,
		SyncStatus:       domain.SyncStatusNeverSynced,
		GitSyncStatus:    domain.GitSyncStatusNeverSynced,
		
		CreatedBy: dto.CreatedBy,
	}

	// Set default branch if not provided
	if fabric.GitOpsBranch == "" {
		fabric.GitOpsBranch = "main"
	}

	return fabric
}

// ApplyUpdateToFabric applies UpdateFabricRequestDTO to a domain Fabric
func (dto *UpdateFabricRequestDTO) ApplyUpdateToFabric(fabric *domain.Fabric) {
	if dto.Name != nil {
		fabric.Name = *dto.Name
	}
	if dto.Description != nil {
		fabric.Description = *dto.Description
	}
	if dto.Status != nil {
		fabric.Status = domain.FabricStatus(*dto.Status)
	}
	if dto.ConnectionStatus != nil {
		fabric.ConnectionStatus = domain.ConnectionStatus(*dto.ConnectionStatus)
	}
	if dto.KubernetesServer != nil {
		fabric.KubernetesServer = *dto.KubernetesServer
	}
	if dto.KubernetesToken != nil {
		fabric.KubernetesToken = *dto.KubernetesToken
	}
	if dto.GitRepositoryID != nil {
		fabric.GitRepositoryID = dto.GitRepositoryID
	}
	if dto.GitOpsDirectory != nil {
		fabric.GitOpsDirectory = *dto.GitOpsDirectory
	}
	if dto.GitOpsBranch != nil {
		fabric.GitOpsBranch = *dto.GitOpsBranch
	}
	
	fabric.ModifiedBy = dto.ModifiedBy
	fabric.LastModified = time.Now()
}