package domain

import (
	"time"
	"database/sql/driver"
	"fmt"
)

// FabricStatus represents the configuration status of a fabric
type FabricStatus string

const (
	FabricStatusPlanned      FabricStatus = "planned"
	FabricStatusActive       FabricStatus = "active"
	FabricStatusMaintenance  FabricStatus = "maintenance"
	FabricStatusRetired      FabricStatus = "retired"
)

// ConnectionStatus represents the connection status to a fabric
type ConnectionStatus string

const (
	ConnectionStatusUnknown     ConnectionStatus = "unknown"
	ConnectionStatusConnected   ConnectionStatus = "connected"
	ConnectionStatusFailed      ConnectionStatus = "failed"
	ConnectionStatusPending     ConnectionStatus = "pending"
)

// SyncStatus represents the synchronization status with Kubernetes
type SyncStatus string

const (
	SyncStatusNeverSynced  SyncStatus = "never_synced"
	SyncStatusInSync       SyncStatus = "in_sync"
	SyncStatusOutOfSync    SyncStatus = "out_of_sync"
	SyncStatusSyncing      SyncStatus = "syncing"
	SyncStatusError        SyncStatus = "error"
)

// Implement driver.Valuer for database serialization
func (fs FabricStatus) Value() (driver.Value, error) {
	return string(fs), nil
}

func (cs ConnectionStatus) Value() (driver.Value, error) {
	return string(cs), nil
}

func (ss SyncStatus) Value() (driver.Value, error) {
	return string(ss), nil
}

// Fabric represents a Hedgehog fabric (Kubernetes cluster) equivalent to HNP HedgehogFabric
// This is the core domain model for fabric management in CNOC
type Fabric struct {
	// Core identification
	ID          string `json:"id" db:"id"`
	Name        string `json:"name" db:"name" validate:"required,max=100"`
	Description string `json:"description" db:"description"`

	// Status tracking (equivalent to HNP status fields)
	Status           FabricStatus     `json:"status" db:"status"`
	ConnectionStatus ConnectionStatus `json:"connection_status" db:"connection_status"`
	SyncStatus       SyncStatus       `json:"sync_status" db:"sync_status"`

	// Kubernetes connection configuration
	KubernetesServer string `json:"kubernetes_server" db:"kubernetes_server" validate:"omitempty,url"`
	KubernetesToken  string `json:"-" db:"kubernetes_token"` // Not exposed in JSON for security

	// GitOps configuration (equivalent to HNP git repository fields)
	GitRepository   string `json:"git_repository" db:"git_repository"`
	GitOpsDirectory string `json:"gitops_directory" db:"gitops_directory"`
	GitCredentials  string `json:"-" db:"git_credentials"` // Encrypted, not exposed

	// Caching and performance (equivalent to HNP cached counts)
	CachedCRDCount    int       `json:"cached_crd_count" db:"cached_crd_count"`
	CachedVPCCount    int       `json:"cached_vpc_count" db:"cached_vpc_count"`
	CachedSwitchCount int       `json:"cached_switch_count" db:"cached_switch_count"`
	LastSyncTime      time.Time `json:"last_sync_time" db:"last_sync_time"`

	// Drift detection (equivalent to HNP drift status)
	DriftStatus    string    `json:"drift_status" db:"drift_status"`
	DriftCount     int       `json:"drift_count" db:"drift_count"`
	LastDriftCheck time.Time `json:"last_drift_check" db:"last_drift_check"`

	// Audit fields
	Created      time.Time `json:"created" db:"created"`
	LastModified time.Time `json:"last_modified" db:"last_modified"`
	CreatedBy    string    `json:"created_by" db:"created_by"`
	ModifiedBy   string    `json:"modified_by" db:"modified_by"`
}

// FabricSummary provides overview statistics equivalent to HNP overview context
type FabricSummary struct {
	TotalFabrics       int               `json:"total_fabrics"`
	FabricsByStatus    map[string]int    `json:"fabrics_by_status"`
	ConnectionSummary  map[string]int    `json:"connection_summary"`
	SyncSummary        map[string]int    `json:"sync_summary"`
	TotalCRDs          int               `json:"total_crds"`
	RecentActivity     []FabricActivity  `json:"recent_activity"`
	GitOpsSummary      GitOpsSummary     `json:"gitops_summary"`
}

// FabricActivity represents recent fabric operations
type FabricActivity struct {
	FabricID    string    `json:"fabric_id"`
	FabricName  string    `json:"fabric_name"`
	Operation   string    `json:"operation"`
	Timestamp   time.Time `json:"timestamp"`
	Status      string    `json:"status"`
	Description string    `json:"description"`
}

// GitOpsSummary provides GitOps statistics equivalent to HNP gitops_stats
type GitOpsSummary struct {
	InSyncCount         int `json:"in_sync_count"`
	DriftDetectedCount  int `json:"drift_detected_count"`
	ErrorCount          int `json:"error_count"`
	NeverSyncedCount    int `json:"never_synced_count"`
}

// FabricConnectionTest represents connection test results equivalent to HNP test connection
type FabricConnectionTest struct {
	FabricID            string    `json:"fabric_id"`
	Success             bool      `json:"success"`
	ResponseTime        int       `json:"response_time_ms"`
	KubernetesVersion   string    `json:"kubernetes_version"`
	NodeCount           int       `json:"node_count"`
	NamespaceCount      int       `json:"namespace_count"`
	ErrorMessage        string    `json:"error_message,omitempty"`
	TestTimestamp       time.Time `json:"test_timestamp"`
	ConnectionDetails   map[string]interface{} `json:"connection_details"`
}

// FabricSyncOperation represents sync operation status equivalent to HNP sync operations
type FabricSyncOperation struct {
	FabricID        string                 `json:"fabric_id"`
	OperationID     string                 `json:"operation_id"`
	Status          SyncStatus             `json:"status"`
	StartTime       time.Time              `json:"start_time"`
	EndTime         *time.Time             `json:"end_time,omitempty"`
	Progress        int                    `json:"progress"` // 0-100
	CRDsProcessed   int                    `json:"crds_processed"`
	CRDsTotal       int                    `json:"crds_total"`
	ErrorsCount     int                    `json:"errors_count"`
	Errors          []string               `json:"errors,omitempty"`
	Results         map[string]interface{} `json:"results"`
	GitCommitHash   string                 `json:"git_commit_hash"`
	GitDirectory    string                 `json:"git_directory"`
}

// Domain validation methods

// Validate performs domain validation equivalent to HNP model validation
func (f *Fabric) Validate() error {
	if f.Name == "" {
		return fmt.Errorf("fabric name is required")
	}
	if len(f.Name) > 100 {
		return fmt.Errorf("fabric name must be 100 characters or less")
	}
	if f.KubernetesServer != "" {
		// Basic URL validation - could be enhanced with proper URL parsing
		if len(f.KubernetesServer) < 8 { // Minimum for "https://"
			return fmt.Errorf("invalid kubernetes server URL")
		}
	}
	return nil
}

// IsConnected returns true if the fabric has a successful connection
func (f *Fabric) IsConnected() bool {
	return f.ConnectionStatus == ConnectionStatusConnected
}

// IsSynced returns true if the fabric is in sync with its git repository
func (f *Fabric) IsSynced() bool {
	return f.SyncStatus == SyncStatusInSync
}

// HasDrift returns true if configuration drift has been detected
func (f *Fabric) HasDrift() bool {
	return f.DriftCount > 0 || f.DriftStatus == "drift_detected"
}

// CanSync returns true if the fabric can perform sync operations
func (f *Fabric) CanSync() bool {
	return f.IsConnected() && f.GitRepository != "" && f.GitOpsDirectory != ""
}

// GetStatusBadgeClass returns CSS class for status display equivalent to HNP template logic
func (f *Fabric) GetStatusBadgeClass() string {
	switch f.Status {
	case FabricStatusActive:
		return "badge-success"
	case FabricStatusPlanned:
		return "badge-info"
	case FabricStatusMaintenance:
		return "badge-warning"
	case FabricStatusRetired:
		return "badge-secondary"
	default:
		return "badge-secondary"
	}
}

// GetConnectionBadgeClass returns CSS class for connection status display
func (f *Fabric) GetConnectionBadgeClass() string {
	switch f.ConnectionStatus {
	case ConnectionStatusConnected:
		return "badge-success"
	case ConnectionStatusFailed:
		return "badge-danger"
	case ConnectionStatusPending:
		return "badge-warning"
	default:
		return "badge-secondary"
	}
}

// GetSyncBadgeClass returns CSS class for sync status display
func (f *Fabric) GetSyncBadgeClass() string {
	switch f.SyncStatus {
	case SyncStatusInSync:
		return "badge-success"
	case SyncStatusOutOfSync:
		return "badge-warning"
	case SyncStatusError:
		return "badge-danger"
	case SyncStatusSyncing:
		return "badge-info"
	default:
		return "badge-secondary"
	}
}

// FabricService defines the interface for fabric domain operations
// This interface ensures clean separation between domain logic and infrastructure
type FabricService interface {
	// CRUD operations equivalent to HNP Django ORM operations
	CreateFabric(fabric *Fabric) error
	GetFabric(id string) (*Fabric, error)
	GetFabricByName(name string) (*Fabric, error)
	UpdateFabric(fabric *Fabric) error
	DeleteFabric(id string) error
	ListFabrics(offset, limit int) ([]*Fabric, int, error)

	// Connection and sync operations equivalent to HNP view operations
	TestConnection(fabricID string) (*FabricConnectionTest, error)
	StartSync(fabricID string) (*FabricSyncOperation, error)
	GetSyncStatus(fabricID string, operationID string) (*FabricSyncOperation, error)
	
	// Statistics and monitoring equivalent to HNP overview context
	GetFabricSummary() (*FabricSummary, error)
	GetRecentActivity(limit int) ([]FabricActivity, error)
	
	// Drift detection equivalent to HNP drift functionality
	DetectDrift(fabricID string) error
	GetDriftReport(fabricID string) (map[string]interface{}, error)
}