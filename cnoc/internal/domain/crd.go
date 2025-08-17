package domain

import (
	"time"
	"encoding/json"
	"fmt"
)

// CRDType represents the type of Kubernetes CRD equivalent to HNP model types
type CRDType string

// CRD types equivalent to HNP models - 12 types total
const (
	// VPC API CRDs (equivalent to vpc_api.py models)
	CRDTypeVPC               CRDType = "vpc"
	CRDTypeExternal          CRDType = "external"
	CRDTypeExternalAttachment CRDType = "external-attachment"
	CRDTypeExternalPeering   CRDType = "external-peering"
	CRDTypeIPv4Namespace     CRDType = "ipv4-namespace"
	CRDTypeVPCAttachment     CRDType = "vpc-attachment"
	CRDTypeVPCPeering        CRDType = "vpc-peering"

	// Wiring API CRDs (equivalent to wiring_api.py models)
	CRDTypeConnection        CRDType = "connection"
	CRDTypeSwitch           CRDType = "switch"
	CRDTypeServer           CRDType = "server"
	CRDTypeSwitchGroup      CRDType = "switch-group"
	CRDTypeVLANNamespace    CRDType = "vlan-namespace"
)

// CRDStatus represents the status of a CRD resource
type CRDStatus string

const (
	CRDStatusActive     CRDStatus = "active"
	CRDStatusPending    CRDStatus = "pending"
	CRDStatusError      CRDStatus = "error"
	CRDStatusDeleting   CRDStatus = "deleting"
	CRDStatusUnknown    CRDStatus = "unknown"
)

// CRDResource represents a generic Kubernetes CRD equivalent to HNP BaseCRD
// This unified model handles all 12 CRD types through a flexible schema
type CRDResource struct {
	// Core identification
	ID        string  `json:"id" db:"id"`
	FabricID  string  `json:"fabric_id" db:"fabric_id"`
	Name      string  `json:"name" db:"name" validate:"required"`
	Kind      string  `json:"kind" db:"kind" validate:"required"`
	Type      CRDType `json:"type" db:"type" validate:"required"`

	// Kubernetes metadata
	APIVersion string            `json:"api_version" db:"api_version"`
	Namespace  string            `json:"namespace" db:"namespace"`
	Labels     map[string]string `json:"labels" db:"labels"`

	// CRD content (equivalent to HNP YAML storage)
	Spec   json.RawMessage `json:"spec" db:"spec"`
	Status json.RawMessage `json:"status" db:"status"`

	// CNOC-specific metadata
	CRDStatus        CRDStatus `json:"crd_status" db:"crd_status"`
	ValidationStatus string    `json:"validation_status" db:"validation_status"`
	ErrorMessage     string    `json:"error_message" db:"error_message"`

	// GitOps tracking (equivalent to HNP git integration)
	GitFilePath    string    `json:"git_file_path" db:"git_file_path"`
	GitCommitHash  string    `json:"git_commit_hash" db:"git_commit_hash"`
	LastSyncedFrom string    `json:"last_synced_from" db:"last_synced_from"` // "git" or "kubernetes"
	LastSyncTime   time.Time `json:"last_sync_time" db:"last_sync_time"`

	// Audit fields
	Created      time.Time `json:"created" db:"created"`
	LastModified time.Time `json:"last_modified" db:"last_modified"`
	CreatedBy    string    `json:"created_by" db:"created_by"`
	ModifiedBy   string    `json:"modified_by" db:"modified_by"`

	// Relationships (equivalent to HNP fabric foreign key)
	Fabric *Fabric `json:"fabric,omitempty" db:"-"`
}

// CRDTypeMetadata defines metadata for each CRD type equivalent to HNP model definitions
type CRDTypeMetadata struct {
	Type         CRDType `json:"type"`
	Kind         string  `json:"kind"`
	APIVersion   string  `json:"api_version"`
	PluralName   string  `json:"plural_name"`
	DisplayName  string  `json:"display_name"`
	Description  string  `json:"description"`
	Category     string  `json:"category"` // "vpc-api" or "wiring-api"
	Icon         string  `json:"icon"`
	HasNamespace bool    `json:"has_namespace"`
}

// GetCRDTypeMetadata returns metadata for all supported CRD types
func GetCRDTypeMetadata() map[CRDType]CRDTypeMetadata {
	return map[CRDType]CRDTypeMetadata{
		// VPC API CRDs
		CRDTypeVPC: {
			Type:         CRDTypeVPC,
			Kind:         "VPC",
			APIVersion:   "vpc.githedgehog.com/v1beta1",
			PluralName:   "vpcs",
			DisplayName:  "VPCs",
			Description:  "Virtual Private Clouds",
			Category:     "vpc-api",
			Icon:         "cloud",
			HasNamespace: true,
		},
		CRDTypeExternal: {
			Type:         CRDTypeExternal,
			Kind:         "External",
			APIVersion:   "vpc.githedgehog.com/v1beta1",
			PluralName:   "externals",
			DisplayName:  "External Systems",
			Description:  "External systems connected to fabric",
			Category:     "vpc-api",
			Icon:         "external-link",
			HasNamespace: true,
		},
		CRDTypeExternalAttachment: {
			Type:         CRDTypeExternalAttachment,
			Kind:         "ExternalAttachment",
			APIVersion:   "vpc.githedgehog.com/v1beta1",
			PluralName:   "external-attachments",
			DisplayName:  "External Attachments",
			Description:  "External system attachments",
			Category:     "vpc-api",
			Icon:         "link",
			HasNamespace: true,
		},
		CRDTypeExternalPeering: {
			Type:         CRDTypeExternalPeering,
			Kind:         "ExternalPeering",
			APIVersion:   "vpc.githedgehog.com/v1beta1",
			PluralName:   "external-peerings",
			DisplayName:  "External Peerings",
			Description:  "External peering configurations",
			Category:     "vpc-api",
			Icon:         "share",
			HasNamespace: true,
		},
		CRDTypeIPv4Namespace: {
			Type:         CRDTypeIPv4Namespace,
			Kind:         "IPv4Namespace",
			APIVersion:   "vpc.githedgehog.com/v1beta1",
			PluralName:   "ipv4-namespaces",
			DisplayName:  "IPv4 Namespaces",
			Description:  "IPv4 namespace management",
			Category:     "vpc-api",
			Icon:         "network",
			HasNamespace: true,
		},
		CRDTypeVPCAttachment: {
			Type:         CRDTypeVPCAttachment,
			Kind:         "VPCAttachment",
			APIVersion:   "vpc.githedgehog.com/v1beta1",
			PluralName:   "vpc-attachments",
			DisplayName:  "VPC Attachments",
			Description:  "VPC attachment configurations",
			Category:     "vpc-api",
			Icon:         "paperclip",
			HasNamespace: true,
		},
		CRDTypeVPCPeering: {
			Type:         CRDTypeVPCPeering,
			Kind:         "VPCPeering",
			APIVersion:   "vpc.githedgehog.com/v1beta1",
			PluralName:   "vpc-peerings",
			DisplayName:  "VPC Peerings",
			Description:  "VPC peering configurations",
			Category:     "vpc-api",
			Icon:         "shuffle",
			HasNamespace: true,
		},

		// Wiring API CRDs
		CRDTypeConnection: {
			Type:         CRDTypeConnection,
			Kind:         "Connection",
			APIVersion:   "wiring.githedgehog.com/v1beta1",
			PluralName:   "connections",
			DisplayName:  "Connections",
			Description:  "Network connections",
			Category:     "wiring-api",
			Icon:         "zap",
			HasNamespace: true,
		},
		CRDTypeSwitch: {
			Type:         CRDTypeSwitch,
			Kind:         "Switch",
			APIVersion:   "wiring.githedgehog.com/v1beta1",
			PluralName:   "switches",
			DisplayName:  "Switches",
			Description:  "Network switches",
			Category:     "wiring-api",
			Icon:         "box",
			HasNamespace: true,
		},
		CRDTypeServer: {
			Type:         CRDTypeServer,
			Kind:         "Server",
			APIVersion:   "wiring.githedgehog.com/v1beta1",
			PluralName:   "servers",
			DisplayName:  "Servers",
			Description:  "Server configurations",
			Category:     "wiring-api",
			Icon:         "server",
			HasNamespace: true,
		},
		CRDTypeSwitchGroup: {
			Type:         CRDTypeSwitchGroup,
			Kind:         "SwitchGroup",
			APIVersion:   "wiring.githedgehog.com/v1beta1",
			PluralName:   "switch-groups",
			DisplayName:  "Switch Groups",
			Description:  "Switch group configurations",
			Category:     "wiring-api",
			Icon:         "layers",
			HasNamespace: true,
		},
		CRDTypeVLANNamespace: {
			Type:         CRDTypeVLANNamespace,
			Kind:         "VLANNamespace",
			APIVersion:   "wiring.githedgehog.com/v1beta1",
			PluralName:   "vlan-namespaces",
			DisplayName:  "VLAN Namespaces",
			Description:  "VLAN namespace management",
			Category:     "wiring-api",
			Icon:         "layers",
			HasNamespace: true,
		},
	}
}

// CRDSummary provides overview statistics equivalent to HNP overview context
type CRDSummary struct {
	TotalCRDs         int                    `json:"total_crds"`
	CRDsByType        map[CRDType]int        `json:"crds_by_type"`
	CRDsByStatus      map[CRDStatus]int      `json:"crds_by_status"`
	CRDsByFabric      map[string]int         `json:"crds_by_fabric"`
	RecentActivity    []CRDActivity          `json:"recent_activity"`
	ValidationSummary ValidationSummary      `json:"validation_summary"`
}

// CRDActivity represents recent CRD operations equivalent to HNP activity tracking
type CRDActivity struct {
	CRDID       string    `json:"crd_id"`
	CRDName     string    `json:"crd_name"`
	CRDType     CRDType   `json:"crd_type"`
	FabricID    string    `json:"fabric_id"`
	FabricName  string    `json:"fabric_name"`
	Operation   string    `json:"operation"` // "created", "updated", "synced", "deleted"
	Timestamp   time.Time `json:"timestamp"`
	Status      string    `json:"status"`
	Description string    `json:"description"`
}

// ValidationSummary provides validation statistics
type ValidationSummary struct {
	ValidCRDs     int `json:"valid_crds"`
	InvalidCRDs   int `json:"invalid_crds"`
	PendingCRDs   int `json:"pending_crds"`
	ErrorRate     float64 `json:"error_rate"`
}

// Domain validation methods

// Validate performs domain validation equivalent to HNP model validation
func (c *CRDResource) Validate() error {
	if c.Name == "" {
		return fmt.Errorf("CRD name is required")
	}
	if c.Kind == "" {
		return fmt.Errorf("CRD kind is required")
	}
	if c.Type == "" {
		return fmt.Errorf("CRD type is required")
	}
	if c.FabricID == "" {
		return fmt.Errorf("fabric ID is required")
	}

	// Validate that type matches kind
	metadata := GetCRDTypeMetadata()
	if meta, exists := metadata[c.Type]; exists {
		if c.Kind != meta.Kind {
			return fmt.Errorf("kind '%s' does not match type '%s' (expected '%s')", c.Kind, c.Type, meta.Kind)
		}
		if c.APIVersion == "" {
			c.APIVersion = meta.APIVersion
		}
	} else {
		return fmt.Errorf("unsupported CRD type: %s", c.Type)
	}

	return nil
}

// GetTypeMetadata returns metadata for this CRD's type
func (c *CRDResource) GetTypeMetadata() (CRDTypeMetadata, error) {
	metadata := GetCRDTypeMetadata()
	if meta, exists := metadata[c.Type]; exists {
		return meta, nil
	}
	return CRDTypeMetadata{}, fmt.Errorf("unsupported CRD type: %s", c.Type)
}

// IsValid returns true if the CRD passes validation
func (c *CRDResource) IsValid() bool {
	return c.ValidationStatus == "valid" && c.ErrorMessage == ""
}

// IsActive returns true if the CRD is in active status
func (c *CRDResource) IsActive() bool {
	return c.CRDStatus == CRDStatusActive
}

// HasError returns true if the CRD has validation errors
func (c *CRDResource) HasError() bool {
	return c.CRDStatus == CRDStatusError || c.ErrorMessage != ""
}

// IsSyncedFromGit returns true if the CRD was last synced from git
func (c *CRDResource) IsSyncedFromGit() bool {
	return c.LastSyncedFrom == "git"
}

// GetStatusBadgeClass returns CSS class for status display equivalent to HNP template logic
func (c *CRDResource) GetStatusBadgeClass() string {
	switch c.CRDStatus {
	case CRDStatusActive:
		return "badge-success"
	case CRDStatusPending:
		return "badge-warning"
	case CRDStatusError:
		return "badge-danger"
	case CRDStatusDeleting:
		return "badge-secondary"
	default:
		return "badge-light"
	}
}

// GetCategoryBadgeClass returns CSS class for category display
func (c *CRDResource) GetCategoryBadgeClass() string {
	meta, err := c.GetTypeMetadata()
	if err != nil {
		return "badge-secondary"
	}
	switch meta.Category {
	case "vpc-api":
		return "badge-primary"
	case "wiring-api":
		return "badge-info"
	default:
		return "badge-secondary"
	}
}

// CRDService defines the interface for CRD domain operations
// This interface ensures clean separation between domain logic and infrastructure
type CRDService interface {
	// CRUD operations equivalent to HNP Django ORM operations
	CreateCRD(crd *CRDResource) error
	GetCRD(id string) (*CRDResource, error)
	GetCRDByName(fabricID, name string, crdType CRDType) (*CRDResource, error)
	UpdateCRD(crd *CRDResource) error
	DeleteCRD(id string) error
	ListCRDs(fabricID string, crdType CRDType, offset, limit int) ([]*CRDResource, int, error)
	ListAllCRDs(offset, limit int) ([]*CRDResource, int, error)

	// Type-specific operations equivalent to HNP model managers
	ListCRDsByType(crdType CRDType, offset, limit int) ([]*CRDResource, int, error)
	GetCRDsByFabric(fabricID string) ([]*CRDResource, error)
	CountCRDsByType(fabricID string) (map[CRDType]int, error)

	// Validation operations equivalent to HNP validation logic
	ValidateCRD(crd *CRDResource) error
	ValidateSpec(crdType CRDType, spec json.RawMessage) error
	GetValidationErrors(fabricID string) ([]CRDResource, error)

	// Statistics and monitoring equivalent to HNP overview context
	GetCRDSummary() (*CRDSummary, error)
	GetRecentActivity(limit int) ([]CRDActivity, error)
	GetValidationSummary(fabricID string) (*ValidationSummary, error)

	// GitOps integration equivalent to HNP git operations
	SyncCRDsFromGit(fabricID string, gitDirectory string) error
	SyncCRDsToKubernetes(fabricID string) error
	GetCRDsFromGitFile(filePath string) ([]*CRDResource, error)
}