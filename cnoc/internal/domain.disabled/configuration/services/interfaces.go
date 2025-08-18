package services

import (
	"context"

	"github.com/hedgehog/cnoc/internal/domain/configuration"
	"github.com/hedgehog/cnoc/internal/domain/shared"
)

// ComponentRegistry interface defines the contract for component registry access
// This interface follows clean architecture principles by defining domain behavior
// without infrastructure dependencies
type ComponentRegistry interface {
	// Exists checks if a component exists in the registry
	Exists(name configuration.ComponentName) bool
	
	// GetVersion retrieves the version for a component
	GetVersion(name configuration.ComponentName) (shared.Version, error)
	
	// GetDependencies retrieves dependencies for a component
	GetDependencies(name configuration.ComponentName) ([]DependencyRequirement, error)
	
	// GetComponentInfo retrieves detailed component information
	GetComponentInfo(name configuration.ComponentName) (*ComponentInfo, error)
	
	// ListAvailable returns all available components
	ListAvailable() ([]configuration.ComponentName, error)
	
	// ValidateComponent validates component configuration
	ValidateComponent(name configuration.ComponentName, config map[string]interface{}) error
	
	// GetDefaultConfiguration returns default configuration for a component
	GetDefaultConfiguration(name configuration.ComponentName) (map[string]interface{}, error)
}

// ComponentInfo represents detailed information about a component
type ComponentInfo struct {
	Name            configuration.ComponentName
	LatestVersion   shared.Version
	AvailableVersions []shared.Version
	Description     string
	Category        string
	Dependencies    []DependencyRequirement
	OptionalDependencies []DependencyRequirement
	Resources       DefaultResourceRequirements
	Documentation   DocumentationLinks
	Maturity        ComponentMaturity
	SupportedModes  []configuration.ConfigurationMode
}

// DefaultResourceRequirements represents default resource requirements for a component
type DefaultResourceRequirements struct {
	MinCPU    string
	MinMemory string
	MaxCPU    string
	MaxMemory string
	Storage   string
}

// DocumentationLinks contains links to component documentation
type DocumentationLinks struct {
	Homepage      string
	Documentation string
	Repository    string
	Issues        string
	Changelog     string
}

// ComponentMaturity represents the maturity level of a component
type ComponentMaturity string

const (
	MaturityAlpha      ComponentMaturity = "alpha"
	MaturityBeta       ComponentMaturity = "beta"
	MaturityStable     ComponentMaturity = "stable"
	MaturityDeprecated ComponentMaturity = "deprecated"
)

// PolicyEnforcer interface defines enterprise policy enforcement capabilities
type PolicyEnforcer interface {
	// ValidateCompliance validates configuration against enterprise policies
	ValidateCompliance(ctx context.Context, config *configuration.Configuration, framework string) PolicyComplianceResult
	
	// EnforceSecurityPolicies enforces security policies on configuration
	EnforceSecurityPolicies(ctx context.Context, config *configuration.Configuration) error
	
	// ValidateNetworkPolicies validates network security requirements
	ValidateNetworkPolicies(ctx context.Context, networking NetworkConfiguration) error
	
	// GetRequiredPolicies returns policies required for a compliance framework
	GetRequiredPolicies(framework string) ([]PolicyDefinition, error)
	
	// ApplyPolicyTemplate applies a policy template to configuration
	ApplyPolicyTemplate(ctx context.Context, config *configuration.Configuration, template string) error
}

// NetworkConfiguration represents network configuration for policy validation
type NetworkConfiguration struct {
	Isolation     NetworkIsolation
	Encryption    EncryptionRequirements
	AccessControl AccessControlConfiguration
	Monitoring    NetworkMonitoring
}

// NetworkIsolation represents network isolation requirements
type NetworkIsolation struct {
	NamespaceIsolation bool
	PodIsolation      bool
	ServiceMesh       bool
	NetworkPolicies   []NetworkPolicy
}

// NetworkPolicy represents a network policy requirement
type NetworkPolicy struct {
	Name        string
	Type        string
	Rules       []PolicyRule
	Enforcement string
}

// PolicyRule represents a network policy rule
type PolicyRule struct {
	Direction string
	Protocol  string
	Ports     []string
	Sources   []string
	Actions   []string
}

// EncryptionRequirements represents encryption requirements
type EncryptionRequirements struct {
	InTransit  bool
	AtRest     bool
	KeyRotation bool
	Algorithm   string
}

// AccessControlConfiguration represents access control configuration
type AccessControlConfiguration struct {
	Authentication AuthenticationConfig
	Authorization  AuthorizationConfig
	Audit         AuditConfig
}

// AuthenticationConfig represents authentication configuration
type AuthenticationConfig struct {
	Provider    string
	MFA         bool
	Federation  bool
	TokenExpiry int64
}

// AuthorizationConfig represents authorization configuration
type AuthorizationConfig struct {
	RBAC        bool
	ABAC        bool
	Policies    []string
	DefaultDeny bool
}

// AuditConfig represents audit configuration
type AuditConfig struct {
	Enabled     bool
	Retention   int64
	Events      []string
	Destination string
}

// NetworkMonitoring represents network monitoring requirements
type NetworkMonitoring struct {
	TrafficAnalysis bool
	ThreatDetection bool
	Compliance      bool
	Alerting        AlertingConfig
}

// AlertingConfig represents alerting configuration
type AlertingConfig struct {
	Enabled     bool
	Severity    []string
	Channels    []string
	Escalation  EscalationConfig
}

// EscalationConfig represents alert escalation configuration
type EscalationConfig struct {
	Enabled  bool
	Levels   []EscalationLevel
	Timeout  int64
}

// EscalationLevel represents an escalation level
type EscalationLevel struct {
	Level       int
	Timeout     int64
	Contacts    []string
	Actions     []string
}

// PolicyDefinition represents a policy definition
type PolicyDefinition struct {
	ID           string
	Name         string
	Framework    string
	Category     string
	Description  string
	Requirements []PolicyRequirement
	Validation   ValidationRule
	Remediation  string
}

// PolicyRequirement represents a policy requirement
type PolicyRequirement struct {
	ID          string
	Description string
	Mandatory   bool
	Validation  string
	Parameters  map[string]interface{}
}

// ValidationRule represents a validation rule
type ValidationRule struct {
	Type       string
	Expression string
	Parameters map[string]interface{}
}

// TemplateEngine interface defines configuration template processing capabilities
type TemplateEngine interface {
	// ApplyTemplate applies a template to generate configuration
	ApplyTemplate(ctx context.Context, templateName string, parameters TemplateParameters) (*configuration.Configuration, error)
	
	// ValidateTemplate validates template syntax and structure
	ValidateTemplate(ctx context.Context, templateName string) error
	
	// ListTemplates returns available configuration templates
	ListTemplates() ([]TemplateInfo, error)
	
	// CreateTemplate creates a new configuration template
	CreateTemplate(ctx context.Context, template ConfigurationTemplate) error
	
	// UpdateTemplate updates an existing template
	UpdateTemplate(ctx context.Context, templateName string, template ConfigurationTemplate) error
	
	// DeleteTemplate removes a configuration template
	DeleteTemplate(ctx context.Context, templateName string) error
	
	// RenderPreview renders a template preview without creating configuration
	RenderPreview(ctx context.Context, templateName string, parameters TemplateParameters) (string, error)
}

// TemplateParameters represents parameters for template processing
type TemplateParameters struct {
	Values      map[string]interface{}
	Mode        configuration.ConfigurationMode
	Enterprise  bool
	Environment string
	Overrides   map[string]interface{}
}

// TemplateInfo represents information about a configuration template
type TemplateInfo struct {
	Name         string
	Description  string
	Version      string
	Category     string
	Parameters   []TemplateParameter
	Requirements []TemplateRequirement
	Examples     []TemplateExample
	Metadata     TemplateMetadata
}

// TemplateParameter represents a template parameter
type TemplateParameter struct {
	Name         string
	Type         string
	Description  string
	Required     bool
	DefaultValue interface{}
	Validation   ParameterValidation
}

// ParameterValidation represents parameter validation rules
type ParameterValidation struct {
	Type    string
	Pattern string
	MinValue interface{}
	MaxValue interface{}
	Options []interface{}
}

// TemplateRequirement represents a template requirement
type TemplateRequirement struct {
	Type        string
	Description string
	Optional    bool
}

// TemplateExample represents a template usage example
type TemplateExample struct {
	Name        string
	Description string
	Parameters  map[string]interface{}
	Expected    string
}

// TemplateMetadata represents template metadata
type TemplateMetadata struct {
	Author      string
	Created     int64
	Updated     int64
	Version     string
	Tags        []string
	Maturity    ComponentMaturity
}

// ConfigurationTemplate represents a configuration template definition
type ConfigurationTemplate struct {
	Name        string
	Description string
	Version     string
	Content     string
	Parameters  []TemplateParameter
	Metadata    TemplateMetadata
	Schema      TemplateSchema
}

// TemplateSchema represents the template schema definition
type TemplateSchema struct {
	Type       string
	Properties map[string]PropertySchema
	Required   []string
}

// PropertySchema represents a property schema definition
type PropertySchema struct {
	Type        string
	Description string
	Default     interface{}
	Enum        []interface{}
	Pattern     string
	Minimum     *float64
	Maximum     *float64
}

// InfrastructureProvisioner interface defines infrastructure provisioning capabilities
// This follows Symphony-Level coordination patterns for complex orchestration
type InfrastructureProvisioner interface {
	// ProvisionControlNode provisions a new control node
	ProvisionControlNode(ctx context.Context, spec ControlNodeSpecification) (*ProvisioningResult, error)
	
	// ConfigureNetworking configures networking for a control node
	ConfigureNetworking(ctx context.Context, nodeID string, config NetworkConfiguration) error
	
	// SetupStorage configures storage for a control node
	SetupStorage(ctx context.Context, nodeID string, config StorageConfiguration) error
	
	// InstallComponents installs components on a control node
	InstallComponents(ctx context.Context, nodeID string, components []ComponentInstallation) error
	
	// ValidateInfrastructure validates infrastructure state
	ValidateInfrastructure(ctx context.Context, nodeID string) (*InfrastructureValidation, error)
	
	// GetProvisioningStatus returns the status of provisioning operations
	GetProvisioningStatus(ctx context.Context, nodeID string) (*ProvisioningStatus, error)
}

// ControlNodeSpecification represents control node provisioning specification
type ControlNodeSpecification struct {
	Name         string
	Platform     PlatformType
	Resources    NodeResources
	Networking   NodeNetworking
	Storage      NodeStorage
	Security     NodeSecurity
	Metadata     map[string]string
}

// PlatformType represents the target platform type
type PlatformType string

const (
	PlatformAWS        PlatformType = "aws"
	PlatformGCP        PlatformType = "gcp"
	PlatformAzure      PlatformType = "azure"
	PlatformVMware     PlatformType = "vmware"
	PlatformBareMetal  PlatformType = "baremetal"
	PlatformKubernetes PlatformType = "kubernetes"
)

// NodeResources represents node resource requirements
type NodeResources struct {
	CPU       string
	Memory    string
	Storage   string
	GPU       bool
	Instances int
}

// NodeNetworking represents node networking configuration
type NodeNetworking struct {
	VPC           string
	Subnet        string
	SecurityGroup string
	PublicIP      bool
	LoadBalancer  bool
}

// NodeStorage represents node storage configuration
type NodeStorage struct {
	RootVolume       VolumeConfiguration
	DataVolumes      []VolumeConfiguration
	BackupRetention  int64
	Encryption       bool
}

// VolumeConfiguration represents storage volume configuration
type VolumeConfiguration struct {
	Size       string
	Type       string
	IOPS       int
	Throughput int
	Encrypted  bool
}

// NodeSecurity represents node security configuration
type NodeSecurity struct {
	SSHKeyPair    string
	Firewall      []FirewallRule
	Monitoring    bool
	LoggingAgent  bool
	SecurityAgent bool
}

// FirewallRule represents a firewall rule
type FirewallRule struct {
	Direction string
	Protocol  string
	Port      string
	Source    string
	Action    string
}

// ComponentInstallation represents component installation specification
type ComponentInstallation struct {
	Component     configuration.ComponentName
	Version       shared.Version
	Configuration map[string]interface{}
	Dependencies  []string
	Priority      InstallationPriority
}

// InstallationPriority represents installation priority
type InstallationPriority int

const (
	InstallPriorityLow InstallationPriority = iota
	InstallPriorityNormal
	InstallPriorityHigh
	InstallPriorityCritical
)

// ProvisioningResult represents the result of infrastructure provisioning
type ProvisioningResult struct {
	NodeID       string
	Status       ProvisioningStatus
	Endpoints    []Endpoint
	Credentials  []Credential
	Metadata     map[string]string
	Cost         CostEstimate
}

// ProvisioningStatus represents provisioning status
type ProvisioningStatus struct {
	Phase       ProvisioningPhase
	Progress    int
	Message     string
	StartTime   int64
	EndTime     int64
	LastUpdate  int64
	Errors      []ProvisioningError
}

// ProvisioningPhase represents the current provisioning phase
type ProvisioningPhase string

const (
	PhaseInitializing ProvisioningPhase = "initializing"
	PhaseProvisioning ProvisioningPhase = "provisioning"
	PhaseConfiguring  ProvisioningPhase = "configuring"
	PhaseInstalling   ProvisioningPhase = "installing"
	PhaseValidating   ProvisioningPhase = "validating"
	PhaseCompleted    ProvisioningPhase = "completed"
	PhaseFailed       ProvisioningPhase = "failed"
)

// ProvisioningError represents a provisioning error
type ProvisioningError struct {
	Phase       ProvisioningPhase
	Code        string
	Message     string
	Timestamp   int64
	Recoverable bool
	Suggestion  string
}

// Endpoint represents a service endpoint
type Endpoint struct {
	Name     string
	URL      string
	Protocol string
	Port     int
	Internal bool
}

// Credential represents access credentials
type Credential struct {
	Type     string
	Username string
	Password string
	KeyFile  string
	Token    string
	Metadata map[string]string
}

// CostEstimate represents infrastructure cost estimation
type CostEstimate struct {
	HourlyCost  float64
	MonthlyCost float64
	Currency    string
	Breakdown   []CostBreakdown
}

// CostBreakdown represents cost breakdown by resource type
type CostBreakdown struct {
	Resource string
	Cost     float64
	Unit     string
}

// InfrastructureValidation represents infrastructure validation results
type InfrastructureValidation struct {
	Valid       bool
	Checks      []ValidationCheck
	Performance PerformanceMetrics
	Security    SecurityValidation
	Compliance  ComplianceValidation
}

// ValidationCheck represents an individual validation check
type ValidationCheck struct {
	Name        string
	Status      CheckStatus
	Message     string
	Severity    CheckSeverity
	Timestamp   int64
	Duration    int64
	Metadata    map[string]interface{}
}

// CheckStatus represents the status of a validation check
type CheckStatus string

const (
	CheckStatusPassed  CheckStatus = "passed"
	CheckStatusFailed  CheckStatus = "failed"
	CheckStatusWarning CheckStatus = "warning"
	CheckStatusSkipped CheckStatus = "skipped"
)

// CheckSeverity represents the severity of a validation check
type CheckSeverity string

const (
	CheckSeverityInfo     CheckSeverity = "info"
	CheckSeverityWarning  CheckSeverity = "warning"
	CheckSeverityError    CheckSeverity = "error"
	CheckSeverityCritical CheckSeverity = "critical"
)

// PerformanceMetrics represents performance validation metrics
type PerformanceMetrics struct {
	CPU       ResourceMetrics
	Memory    ResourceMetrics
	Storage   ResourceMetrics
	Network   NetworkMetrics
	Latency   LatencyMetrics
}

// ResourceMetrics represents resource utilization metrics
type ResourceMetrics struct {
	Current     float64
	Average     float64
	Peak        float64
	Unit        string
	Threshold   float64
	Status      MetricStatus
}

// NetworkMetrics represents network performance metrics
type NetworkMetrics struct {
	Bandwidth   float64
	Throughput  float64
	PacketLoss  float64
	Latency     float64
	Jitter      float64
	Status      MetricStatus
}

// LatencyMetrics represents latency performance metrics
type LatencyMetrics struct {
	Average     float64
	P50         float64
	P95         float64
	P99         float64
	Unit        string
	Threshold   float64
	Status      MetricStatus
}

// MetricStatus represents the status of a performance metric
type MetricStatus string

const (
	MetricStatusHealthy  MetricStatus = "healthy"
	MetricStatusWarning  MetricStatus = "warning"
	MetricStatusCritical MetricStatus = "critical"
	MetricStatusUnknown  MetricStatus = "unknown"
)

// SecurityValidation represents security validation results
type SecurityValidation struct {
	Compliant       bool
	Vulnerabilities []SecurityVulnerability
	Configurations  []SecurityConfiguration
	Certificates    []CertificateValidation
}

// SecurityVulnerability represents a security vulnerability
type SecurityVulnerability struct {
	ID          string
	Severity    VulnerabilitySeverity
	Component   string
	Description string
	CVSS        float64
	Remediation string
	Status      VulnerabilityStatus
}

// VulnerabilitySeverity represents vulnerability severity
type VulnerabilitySeverity string

const (
	VulnerabilityLow      VulnerabilitySeverity = "low"
	VulnerabilityMedium   VulnerabilitySeverity = "medium"
	VulnerabilityHigh     VulnerabilitySeverity = "high"
	VulnerabilityCritical VulnerabilitySeverity = "critical"
)

// VulnerabilityStatus represents vulnerability status
type VulnerabilityStatus string

const (
	VulnerabilityStatusOpen      VulnerabilityStatus = "open"
	VulnerabilityStatusFixed     VulnerabilityStatus = "fixed"
	VulnerabilityStatusAccepted  VulnerabilityStatus = "accepted"
	VulnerabilityStatusIgnored   VulnerabilityStatus = "ignored"
)

// SecurityConfiguration represents security configuration validation
type SecurityConfiguration struct {
	Name        string
	Status      ConfigurationStatus
	Expected    string
	Actual      string
	Compliant   bool
	Remediation string
}

// ConfigurationStatus represents configuration validation status
type ConfigurationStatus string

const (
	ConfigurationStatusValid   ConfigurationStatus = "valid"
	ConfigurationStatusInvalid ConfigurationStatus = "invalid"
	ConfigurationStatusMissing ConfigurationStatus = "missing"
	ConfigurationStatusUnknown ConfigurationStatus = "unknown"
)

// CertificateValidation represents certificate validation results
type CertificateValidation struct {
	Name        string
	Subject     string
	Issuer      string
	NotBefore   int64
	NotAfter    int64
	Valid       bool
	SelfSigned  bool
	Expired     bool
	Algorithm   string
	KeySize     int
	Issues      []CertificateIssue
}

// CertificateIssue represents a certificate issue
type CertificateIssue struct {
	Type        string
	Severity    CheckSeverity
	Description string
	Suggestion  string
}

// ComplianceValidation represents compliance validation results
type ComplianceValidation struct {
	Framework   string
	Compliant   bool
	Score       float64
	Controls    []ComplianceControl
	Gaps        []ComplianceGap
	Remediation []ComplianceRemediation
}

// ComplianceControl represents a compliance control
type ComplianceControl struct {
	ID          string
	Name        string
	Description string
	Status      ControlStatus
	Evidence    []string
	Notes       string
}

// ControlStatus represents compliance control status
type ControlStatus string

const (
	ControlStatusCompliant     ControlStatus = "compliant"
	ControlStatusNonCompliant  ControlStatus = "non_compliant"
	ControlStatusPartial       ControlStatus = "partial"
	ControlStatusNotApplicable ControlStatus = "not_applicable"
)

// ComplianceGap represents a compliance gap
type ComplianceGap struct {
	Control     string
	Gap         string
	Risk        string
	Priority    CompliancePriority
	Remediation string
}

// CompliancePriority represents compliance priority
type CompliancePriority string

const (
	CompliancePriorityLow      CompliancePriority = "low"
	CompliancePriorityMedium   CompliancePriority = "medium"
	CompliancePriorityHigh     CompliancePriority = "high"
	CompliancePriorityCritical CompliancePriority = "critical"
)

// ComplianceRemediation represents compliance remediation steps
type ComplianceRemediation struct {
	Control     string
	Steps       []RemediationStep
	Timeline    int64
	Responsible string
	Cost        float64
}

// RemediationStep represents a single remediation step
type RemediationStep struct {
	Order       int
	Description string
	Action      string
	Validation  string
	Automated   bool
	Duration    int64
}

// StorageConfiguration represents storage configuration
type StorageConfiguration struct {
	Type        StorageType
	Size        string
	IOPS        int
	Throughput  int
	Encryption  bool
	Backup      BackupConfiguration
	Retention   RetentionPolicy
}

// StorageType represents storage type
type StorageType string

const (
	StorageTypeBlock  StorageType = "block"
	StorageTypeFile   StorageType = "file"
	StorageTypeObject StorageType = "object"
)

// BackupConfiguration represents backup configuration
type BackupConfiguration struct {
	Enabled   bool
	Schedule  string
	Retention int64
	Location  string
	Encrypted bool
}

// RetentionPolicy represents data retention policy
type RetentionPolicy struct {
	Days        int64
	Archives    int64
	Compliance  string
	Automated   bool
}