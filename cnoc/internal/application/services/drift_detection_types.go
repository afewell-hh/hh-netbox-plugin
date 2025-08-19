package services

import (
	"time"
)

// DriftDetectionService interface for drift detection operations
type DriftDetectionService interface {
	DetectFabricDrift(ctx interface{}, fabricID string) (*FabricDriftResult, error)
	DetectResourceDrift(ctx interface{}, fabricID, resourceID string) (*ResourceDriftResult, error)
	GetDriftHistory(ctx interface{}, fabricID string, timeRange TimeRange) (*DriftHistory, error)
	AnalyzeDriftSeverity(driftResults []ResourceDriftResult) SeverityLevel
	GenerateDriftReport(ctx interface{}, fabricID string) (*DriftReport, error)
	GetDriftSummary(ctx interface{}, fabricID string) (*DriftSummary, error)
	StartRealtimeMonitoring(ctx interface{}, fabricID string, interval time.Duration) error
	StopRealtimeMonitoring(ctx interface{}, fabricID string) error
}

// FabricDriftResult represents drift detection results for a fabric
type FabricDriftResult struct {
	FabricID        string                   `json:"fabric_id"`
	HasDrift        bool                     `json:"has_drift"`
	DriftCount      int                      `json:"drift_count"`
	TotalResources  int                      `json:"total_resources"`
	DriftSeverity   SeverityLevel            `json:"drift_severity"`
	DriftPercentage float64                  `json:"drift_percentage"`
	DetectionTime   time.Duration            `json:"detection_time"`
	ResourceDrifts  []ResourceDriftResult    `json:"resource_drifts"`
	Summary         string                   `json:"summary"`
	DetectedAt      time.Time                `json:"detected_at"`
	Recommendations []string                 `json:"recommendations"`
}

// ResourceDriftResult represents drift for a specific resource
type ResourceDriftResult struct {
	ResourceID    string                 `json:"resource_id"`
	ResourceType  string                 `json:"resource_type"`
	ResourceName  string                 `json:"resource_name"`
	HasDrift      bool                   `json:"has_drift"`
	DriftType     string                 `json:"drift_type"`
	GitState      map[string]interface{} `json:"git_state"`
	ClusterState  map[string]interface{} `json:"cluster_state"`
	Differences   []string               `json:"differences"`
	Severity      SeverityLevel          `json:"severity"`
	LastModified  time.Time              `json:"last_modified"`
	DetectedAt    time.Time              `json:"detected_at"`
}

// SeverityLevel represents the severity of drift
type SeverityLevel string

const (
	SeverityLow      SeverityLevel = "low"
	SeverityMedium   SeverityLevel = "medium"
	SeverityHigh     SeverityLevel = "high"
	SeverityCritical SeverityLevel = "critical"
)

// TimeRange represents a time range for queries
type TimeRange struct {
	Start time.Time `json:"start"`
	End   time.Time `json:"end"`
}

// DriftHistory represents historical drift data
type DriftHistory struct {
	FabricID     string               `json:"fabric_id"`
	TimeRange    TimeRange            `json:"time_range"`
	HistoryItems []DriftHistoryItem   `json:"history_items"`
	Trends       DriftTrends          `json:"trends"`
}

// DriftHistoryItem represents a single drift detection in history
type DriftHistoryItem struct {
	Timestamp     time.Time         `json:"timestamp"`
	DriftCount    int               `json:"drift_count"`
	DriftSeverity SeverityLevel     `json:"drift_severity"`
	AffectedTypes map[string]int    `json:"affected_types"`
}

// DriftTrends represents drift trends over time
type DriftTrends struct {
	Increasing bool    `json:"increasing"`
	TrendRate  float64 `json:"trend_rate"`
	Prediction string  `json:"prediction"`
}

// DriftReport represents a comprehensive drift report
type DriftReport struct {
	FabricID        string                `json:"fabric_id"`
	GeneratedAt     time.Time             `json:"generated_at"`
	ReportPeriod    TimeRange             `json:"report_period"`
	Summary         DriftSummary          `json:"summary"`
	DetailedResults []ResourceDriftResult `json:"detailed_results"`
	Trends          DriftTrends           `json:"trends"`
	Recommendations []Recommendation      `json:"recommendations"`
	ExportFormat    string                `json:"export_format"`
}

// DriftSummary represents a summary of drift status
type DriftSummary struct {
	FabricID         string        `json:"fabric_id"`
	HasDrift         bool          `json:"has_drift"`
	DriftCount       int           `json:"drift_count"`
	TotalResources   int           `json:"total_resources"`
	OverallSeverity  SeverityLevel `json:"overall_severity"`
	LastCheckTime    time.Time     `json:"last_check_time"`
	DriftCategories  map[string]int `json:"drift_categories"`
	HealthScore      float64       `json:"health_score"`
}

// Recommendation represents a drift remediation recommendation
type Recommendation struct {
	Type        string    `json:"type"`
	Priority    string    `json:"priority"`
	Description string    `json:"description"`
	Action      string    `json:"action"`
	Impact      string    `json:"impact"`
	CreatedAt   time.Time `json:"created_at"`
}

// SchemaDefinition represents a schema definition (for configuration validator)
type SchemaDefinition struct {
	Name        string                 `json:"name"`
	Version     string                 `json:"version"`
	Schema      map[string]interface{} `json:"schema"`
	Required    []string               `json:"required"`
	Properties  map[string]Property    `json:"properties"`
	Description string                 `json:"description"`
}

// Property represents a schema property
type Property struct {
	Type        string      `json:"type"`
	Description string      `json:"description"`
	Default     interface{} `json:"default,omitempty"`
	Required    bool        `json:"required"`
	Format      string      `json:"format,omitempty"`
	Pattern     string      `json:"pattern,omitempty"`
}

// PerformanceMetrics represents drift detection performance metrics
type PerformanceMetrics struct {
	DetectionTime    time.Duration `json:"detection_time"`
	ResourcesScanned int           `json:"resources_scanned"`
	Accuracy         float64       `json:"accuracy"`
	MemoryUsage      int64         `json:"memory_usage"`
	CPUUsage         float64       `json:"cpu_usage"`
}

// FieldDifference represents a field-level difference
type FieldDifference struct {
	FieldName string      `json:"field_name"`
	GitValue  interface{} `json:"git_value"`
	K8sValue  interface{} `json:"k8s_value"`
	DiffType  string      `json:"diff_type"`
}

// ConfigurationDrift represents configuration-level drift
type ConfigurationDrift struct {
	ConfigType   string            `json:"config_type"`
	ConfigName   string            `json:"config_name"`
	Differences  []FieldDifference `json:"differences"`
	Severity     SeverityLevel     `json:"severity"`
	DetectedAt   time.Time         `json:"detected_at"`
}

// StateDrift represents state-level drift
type StateDrift struct {
	StateType   string        `json:"state_type"`
	Expected    interface{}   `json:"expected"`
	Actual      interface{}   `json:"actual"`
	Severity    SeverityLevel `json:"severity"`
	DetectedAt  time.Time     `json:"detected_at"`
}

// ComplianceDrift represents compliance policy drift
type ComplianceDrift struct {
	PolicyName  string        `json:"policy_name"`
	Violations  []string      `json:"violations"`
	Severity    SeverityLevel `json:"severity"`
	DetectedAt  time.Time     `json:"detected_at"`
}

// PerformanceDrift represents performance-related drift
type PerformanceDrift struct {
	MetricName   string        `json:"metric_name"`
	Expected     float64       `json:"expected"`
	Actual       float64       `json:"actual"`
	Threshold    float64       `json:"threshold"`
	Severity     SeverityLevel `json:"severity"`
	DetectedAt   time.Time     `json:"detected_at"`
}

// TypeDriftSummary represents drift summary by type
type TypeDriftSummary struct {
	ResourceType string `json:"resource_type"`
	Count        int    `json:"count"`
	Percentage   float64 `json:"percentage"`
	Severity     SeverityLevel `json:"severity"`
}

// RemediationRecommendation represents a remediation recommendation
type RemediationRecommendation struct {
	ID          string    `json:"id"`
	Type        string    `json:"type"`
	Description string    `json:"description"`
	Action      string    `json:"action"`
	Priority    string    `json:"priority"`
	Effort      string    `json:"effort"`
	Impact      string    `json:"impact"`
	CreatedAt   time.Time `json:"created_at"`
}

// DriftDataPoint represents a single drift measurement
type DriftDataPoint struct {
	Timestamp   time.Time     `json:"timestamp"`
	FabricID    string        `json:"fabric_id"`
	DriftCount  int           `json:"drift_count"`
	Severity    SeverityLevel `json:"severity"`
	ResourceType string       `json:"resource_type"`
	Value       float64       `json:"value"`
}

// TrendAnalysis represents drift trend analysis
type TrendAnalysis struct {
	Direction    string    `json:"direction"`
	Rate         float64   `json:"rate"`
	Prediction   string    `json:"prediction"`
	Confidence   float64   `json:"confidence"`
	DataPoints   []DriftDataPoint `json:"data_points"`
	AnalyzedAt   time.Time `json:"analyzed_at"`
}

// HistoryAggregates represents aggregated drift history
type HistoryAggregates struct {
	TotalDrifts     int       `json:"total_drifts"`
	AverageDrifts   float64   `json:"average_drifts"`
	MaxDrifts       int       `json:"max_drifts"`
	MinDrifts       int       `json:"min_drifts"`
	TrendAnalysis   TrendAnalysis `json:"trend_analysis"`
	PeriodStart     time.Time `json:"period_start"`
	PeriodEnd       time.Time `json:"period_end"`
}

// ExecutiveSummary represents an executive summary of drift
type ExecutiveSummary struct {
	OverallHealth   string    `json:"overall_health"`
	KeyFindings     []string  `json:"key_findings"`
	TopRisks        []string  `json:"top_risks"`
	Recommendations []string  `json:"recommendations"`
	NextSteps       []string  `json:"next_steps"`
	GeneratedAt     time.Time `json:"generated_at"`
}

// DetailedFinding represents a detailed drift finding
type DetailedFinding struct {
	ID          string    `json:"id"`
	Title       string    `json:"title"`
	Description string    `json:"description"`
	Evidence    []string  `json:"evidence"`
	Impact      string    `json:"impact"`
	Severity    SeverityLevel `json:"severity"`
	Timestamp   time.Time `json:"timestamp"`
}

// RemediationStep represents a step in remediation
type RemediationStep struct {
	StepNumber  int       `json:"step_number"`
	Description string    `json:"description"`
	Command     string    `json:"command,omitempty"`
	Expected    string    `json:"expected"`
	Duration    time.Duration `json:"duration"`
}

// ComplianceStatus represents compliance status
type ComplianceStatus struct {
	PolicyName     string    `json:"policy_name"`
	Compliant      bool      `json:"compliant"`
	Score          float64   `json:"score"`
	Violations     []string  `json:"violations"`
	LastChecked    time.Time `json:"last_checked"`
}

// RecommendationWithPriority represents a prioritized recommendation
type RecommendationWithPriority struct {
	Recommendation RemediationRecommendation `json:"recommendation"`
	Priority       int                       `json:"priority"`
	UrgencyScore   float64                   `json:"urgency_score"`
	ImpactScore    float64                   `json:"impact_score"`
	EffortScore    float64                   `json:"effort_score"`
}

// GitCredentialsPayload represents Git credentials
type GitCredentialsPayload struct {
	AuthType     string            `json:"auth_type"`
	Username     string            `json:"username,omitempty"`
	Password     string            `json:"password,omitempty"`
	Token        string            `json:"token,omitempty"`
	SSHKey       string            `json:"ssh_key,omitempty"`
	SSHKeyPath   string            `json:"ssh_key_path,omitempty"`
	Passphrase   string            `json:"passphrase,omitempty"`
	Metadata     map[string]string `json:"metadata,omitempty"`
}

// CloneResult represents the result of a git clone operation
type CloneResult struct {
	Success      bool          `json:"success"`
	ClonePath    string        `json:"clone_path"`
	CommitHash   string        `json:"commit_hash"`
	Branch       string        `json:"branch"`
	FilesCount   int           `json:"files_count"`
	CloneTime    time.Duration `json:"clone_time"`
	ErrorMessage string        `json:"error_message,omitempty"`
	Metadata     map[string]interface{} `json:"metadata,omitempty"`
}

// SyncResult represents the result of a synchronization operation
type SyncResult struct {
	FabricID          string        `json:"fabric_id"`
	RepositoryID      string        `json:"repository_id"`
	RequestID         string        `json:"request_id"`
	Success           bool          `json:"success"`
	SyncedAt          time.Time     `json:"synced_at"`
	SyncDuration      time.Duration `json:"sync_duration"`
	NetworkLatency    time.Duration `json:"network_latency"`
	ParsingTime       time.Duration `json:"parsing_time"`
	ValidationTime    time.Duration `json:"validation_time"`
	ApplyTime         time.Duration `json:"apply_time"`
	YAMLFilesCount    int           `json:"yaml_files_count"`
	ResourcesFound    int           `json:"resources_found"`
	ResourcesSynced   int           `json:"resources_synced"`
	ResourcesFailed   int           `json:"resources_failed"`
	ConfigCount       int           `json:"config_count"`
	CRDsCreated       int           `json:"crds_created"`
	CRDsUpdated       int           `json:"crds_updated"`
	CRDsDeleted       int           `json:"crds_deleted"`
	GitCommitHash     string        `json:"git_commit_hash"`
	GitDirectory      string        `json:"git_directory"`
	ErrorDetails      []SyncError   `json:"error_details,omitempty"`
	WarningDetails    []SyncWarning `json:"warning_details,omitempty"`
}

// SyncError represents an error during synchronization
type SyncError struct {
	Code        string    `json:"code"`
	Message     string    `json:"message"`
	Resource    string    `json:"resource,omitempty"`
	Severity    string    `json:"severity"`
	Recoverable bool      `json:"recoverable"`
	Timestamp   time.Time `json:"timestamp"`
}

// SyncWarning represents a warning during synchronization
type SyncWarning struct {
	Code       string    `json:"code"`
	Message    string    `json:"message"`
	Suggestion string    `json:"suggestion,omitempty"`
	Timestamp  time.Time `json:"timestamp"`
}

// ValidationResult represents YAML validation results
type ValidationResult struct {
	RequestID            string                 `json:"request_id"`
	ValidatedAt          time.Time              `json:"validated_at"`
	ValidationDuration   time.Duration          `json:"validation_duration"`
	Valid                bool                   `json:"valid"`
	ConfigurationsCount  int                    `json:"configurations_count"`
	ErrorCount           int                    `json:"error_count"`
	WarningCount         int                    `json:"warning_count"`
	ValidationErrors     []ValidationError      `json:"validation_errors,omitempty"`
	ValidationWarnings   []ValidationWarning    `json:"validation_warnings,omitempty"`
	BusinessRuleResults  []BusinessRuleResult   `json:"business_rule_results,omitempty"`
	SchemaValidation     *SchemaValidationResult `json:"schema_validation,omitempty"`
	DependencyCheck      *DependencyCheckResult  `json:"dependency_check,omitempty"`
	PolicyCompliance     *PolicyComplianceResult `json:"policy_compliance,omitempty"`
}

// Use ValidationError and ValidationWarning from configuration_application_service.go

// BusinessRuleResult represents a business rule validation result
type BusinessRuleResult struct {
	RuleName string `json:"rule_name"`
	Passed   bool   `json:"passed"`
	Message  string `json:"message"`
	Severity string `json:"severity"`
}

// RollbackResult represents the result of a rollback operation
type RollbackResult struct {
	FabricID           string            `json:"fabric_id"`
	RequestID          string            `json:"request_id"`
	Success            bool              `json:"success"`
	RolledBackAt       time.Time         `json:"rolled_back_at"`
	RollbackDuration   time.Duration     `json:"rollback_duration"`
	RolledBackToCommit string            `json:"rolled_back_to_commit"`
	ConfigsReverted    int               `json:"configs_reverted"`
	CRDsReverted       int               `json:"crds_reverted"`
	ErrorDetails       []RollbackError   `json:"error_details,omitempty"`
}

// RollbackError represents an error during rollback
type RollbackError struct {
	Code      string    `json:"code"`
	Message   string    `json:"message"`
	Severity  string    `json:"severity"`
	Timestamp time.Time `json:"timestamp"`
}

// Sync status types and states
type SyncState string

const (
	SyncStateIdle         SyncState = "idle"
	SyncStateInProgress   SyncState = "in_progress"
	SyncStateCompleted    SyncState = "completed"
	SyncStateFailed       SyncState = "failed"
	SyncStateRollingBack  SyncState = "rolling_back"
)

// Extended SyncStatus for workflow orchestrator
type WorkflowSyncStatus struct {
	FabricID             string         `json:"fabric_id"`
	CurrentState         SyncState      `json:"current_state"`
	InProgress           bool           `json:"in_progress"`
	SyncProgress         float64        `json:"sync_progress"`
	CurrentOperation     string         `json:"current_operation,omitempty"`
	EstimatedCompletion  *time.Time     `json:"estimated_completion,omitempty"`
	LastSyncAt           *time.Time     `json:"last_sync_at,omitempty"`
	LastSuccessfulSync   *time.Time     `json:"last_successful_sync,omitempty"`
	StatusUpdatedAt      time.Time      `json:"status_updated_at"`
	HealthScore          float64        `json:"health_score"`
	DriftDetected        bool           `json:"drift_detected"`
	DriftCount           int            `json:"drift_count"`
	PeriodicSyncEnabled  bool           `json:"periodic_sync_enabled"`
	SyncInterval         time.Duration  `json:"sync_interval"`
	NextScheduledSync    *time.Time     `json:"next_scheduled_sync,omitempty"`
}