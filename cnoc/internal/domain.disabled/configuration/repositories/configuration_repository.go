package repositories

import (
	"context"
	"errors"

	"github.com/hedgehog/cnoc/internal/domain/configuration"
	"github.com/hedgehog/cnoc/internal/domain/events"
	"github.com/hedgehog/cnoc/internal/domain/shared"
)

// ConfigurationRepository defines the contract for configuration persistence
// following clean architecture and repository pattern principles
type ConfigurationRepository interface {
	// Save persists a configuration aggregate with its domain events
	Save(ctx context.Context, config *configuration.Configuration) error
	
	// FindByID retrieves a configuration by its unique identifier
	FindByID(ctx context.Context, id configuration.ConfigurationID) (*configuration.Configuration, error)
	
	// FindByName retrieves a configuration by its name
	FindByName(ctx context.Context, name configuration.ConfigurationName) (*configuration.Configuration, error)
	
	// FindAll retrieves all configurations with optional filtering
	FindAll(ctx context.Context, filter ConfigurationFilter) ([]*configuration.Configuration, error)
	
	// Delete removes a configuration from persistence
	Delete(ctx context.Context, id configuration.ConfigurationID) error
	
	// Exists checks if a configuration exists by ID
	Exists(ctx context.Context, id configuration.ConfigurationID) (bool, error)
	
	// Count returns the total number of configurations matching filter
	Count(ctx context.Context, filter ConfigurationFilter) (int64, error)
	
	// FindByVersion retrieves configurations by version criteria
	FindByVersion(ctx context.Context, versionCriteria VersionCriteria) ([]*configuration.Configuration, error)
	
	// FindByMode retrieves configurations by mode
	FindByMode(ctx context.Context, mode configuration.ConfigurationMode) ([]*configuration.Configuration, error)
	
	// FindByStatus retrieves configurations by status
	FindByStatus(ctx context.Context, status configuration.ConfigurationStatus) ([]*configuration.Configuration, error)
	
	// SaveWithTransaction saves configuration within a transaction context
	SaveWithTransaction(ctx context.Context, config *configuration.Configuration, tx Transaction) error
	
	// GetNextID generates the next available configuration ID
	GetNextID(ctx context.Context) (configuration.ConfigurationID, error)
}

// ConfigurationFilter provides filtering criteria for configuration queries
type ConfigurationFilter struct {
	// Basic filters
	IDs     []configuration.ConfigurationID
	Names   []configuration.ConfigurationName
	Modes   []configuration.ConfigurationMode
	Statuses []configuration.ConfigurationStatus
	
	// Version filters
	VersionFrom *shared.Version
	VersionTo   *shared.Version
	
	// Time-based filters
	CreatedAfter  *int64
	CreatedBefore *int64
	UpdatedAfter  *int64
	UpdatedBefore *int64
	
	// Component filters
	HasComponent    *configuration.ComponentName
	ComponentCount  *ComponentCountFilter
	
	// Metadata filters
	Labels      map[string]string
	Annotations map[string]string
	
	// Pagination
	Limit  *int
	Offset *int
	
	// Sorting
	SortBy    ConfigurationSortField
	SortOrder SortOrder
}

// ComponentCountFilter provides component count filtering
type ComponentCountFilter struct {
	Min *int
	Max *int
}

// ConfigurationSortField defines fields for sorting configurations
type ConfigurationSortField string

const (
	SortByName      ConfigurationSortField = "name"
	SortByVersion   ConfigurationSortField = "version"
	SortByCreated   ConfigurationSortField = "created"
	SortByUpdated   ConfigurationSortField = "updated"
	SortByStatus    ConfigurationSortField = "status"
	SortByMode      ConfigurationSortField = "mode"
)

// SortOrder defines sort ordering
type SortOrder string

const (
	SortOrderAsc  SortOrder = "asc"
	SortOrderDesc SortOrder = "desc"
)

// VersionCriteria provides version-based filtering criteria
type VersionCriteria struct {
	ExactVersion    *shared.Version
	MinVersion      *shared.Version
	MaxVersion      *shared.Version
	VersionPattern  string
	IncludePreRelease bool
	OnlyStable      bool
}

// Transaction defines transaction context for repository operations
type Transaction interface {
	// Commit commits the transaction
	Commit() error
	
	// Rollback rolls back the transaction
	Rollback() error
	
	// IsActive returns true if transaction is active
	IsActive() bool
	
	// Context returns the transaction context
	Context() context.Context
}

// ConfigurationQueryResult provides rich query results with metadata
type ConfigurationQueryResult struct {
	Configurations []*configuration.Configuration
	TotalCount     int64
	HasMore        bool
	NextOffset     *int
	Metadata       QueryMetadata
}

// QueryMetadata provides additional information about query execution
type QueryMetadata struct {
	ExecutionTimeMs int64
	IndexesUsed     []string
	CacheHit        bool
	QueryPlan       string
}

// ConfigurationTemplateRepository defines template persistence contract
type ConfigurationTemplateRepository interface {
	// SaveTemplate persists a configuration template
	SaveTemplate(ctx context.Context, template *ConfigurationTemplate) error
	
	// FindTemplateByName retrieves a template by name
	FindTemplateByName(ctx context.Context, name string) (*ConfigurationTemplate, error)
	
	// ListTemplates returns available templates with filtering
	ListTemplates(ctx context.Context, filter TemplateFilter) ([]*ConfigurationTemplate, error)
	
	// DeleteTemplate removes a template
	DeleteTemplate(ctx context.Context, name string) error
	
	// UpdateTemplate updates an existing template
	UpdateTemplate(ctx context.Context, template *ConfigurationTemplate) error
	
	// TemplateExists checks if a template exists
	TemplateExists(ctx context.Context, name string) (bool, error)
}

// ConfigurationTemplate represents a configuration template entity
type ConfigurationTemplate struct {
	Name        string
	Description string
	Version     string
	Content     []byte
	Parameters  []TemplateParameter
	Metadata    TemplateMetadata
	Schema      []byte
	CreatedAt   int64
	UpdatedAt   int64
}

// TemplateParameter represents a template parameter
type TemplateParameter struct {
	Name         string
	Type         ParameterType
	Description  string
	Required     bool
	DefaultValue interface{}
	Validation   ParameterValidation
}

// ParameterType defines template parameter types
type ParameterType string

const (
	ParameterTypeString  ParameterType = "string"
	ParameterTypeNumber  ParameterType = "number"
	ParameterTypeBoolean ParameterType = "boolean"
	ParameterTypeArray   ParameterType = "array"
	ParameterTypeObject  ParameterType = "object"
)

// ParameterValidation defines parameter validation rules
type ParameterValidation struct {
	Pattern     string
	MinLength   *int
	MaxLength   *int
	MinValue    *float64
	MaxValue    *float64
	Enum        []interface{}
	Format      string
}

// TemplateMetadata holds template metadata
type TemplateMetadata struct {
	Author      string
	Category    string
	Tags        []string
	Maturity    TemplateMaturity
	SupportedModes []configuration.ConfigurationMode
}

// TemplateMaturity defines template maturity levels
type TemplateMaturity string

const (
	TemplateMaturityExperimental TemplateMaturity = "experimental"
	TemplateMaturityBeta         TemplateMaturity = "beta"
	TemplateMaturityStable       TemplateMaturity = "stable"
	TemplateMaturityDeprecated   TemplateMaturity = "deprecated"
)

// TemplateFilter provides filtering for template queries
type TemplateFilter struct {
	Names      []string
	Categories []string
	Tags       []string
	Maturity   []TemplateMaturity
	Author     string
	
	// Version filters
	VersionFrom string
	VersionTo   string
	
	// Mode compatibility
	SupportedMode *configuration.ConfigurationMode
	
	// Pagination
	Limit  *int
	Offset *int
	
	// Sorting
	SortBy    TemplateSortField
	SortOrder SortOrder
}

// TemplateSortField defines fields for sorting templates
type TemplateSortField string

const (
	TemplateSortByName     TemplateSortField = "name"
	TemplateSortByVersion  TemplateSortField = "version"
	TemplateSortByCreated  TemplateSortField = "created"
	TemplateSortByCategory TemplateSortField = "category"
	TemplateSortByMaturity TemplateSortField = "maturity"
)

// ComponentRepository defines component persistence contract
type ComponentRepository interface {
	// SaveComponent persists a component reference
	SaveComponent(ctx context.Context, component *configuration.ComponentReference) error
	
	// FindComponentByName retrieves a component by name
	FindComponentByName(ctx context.Context, name configuration.ComponentName) (*configuration.ComponentReference, error)
	
	// ListComponents returns components with filtering
	ListComponents(ctx context.Context, filter ComponentFilter) ([]*configuration.ComponentReference, error)
	
	// DeleteComponent removes a component
	DeleteComponent(ctx context.Context, name configuration.ComponentName) error
	
	// UpdateComponent updates component configuration
	UpdateComponent(ctx context.Context, component *configuration.ComponentReference) error
	
	// ComponentExists checks if a component exists
	ComponentExists(ctx context.Context, name configuration.ComponentName) (bool, error)
	
	// FindComponentsByVersion retrieves components by version criteria
	FindComponentsByVersion(ctx context.Context, versionCriteria VersionCriteria) ([]*configuration.ComponentReference, error)
	
	// GetComponentHistory returns component version history
	GetComponentHistory(ctx context.Context, name configuration.ComponentName) ([]ComponentHistoryEntry, error)
}

// ComponentFilter provides filtering for component queries
type ComponentFilter struct {
	Names    []configuration.ComponentName
	Enabled  *bool
	Versions []shared.Version
	
	// Configuration filters
	Namespaces []string
	MinReplicas *int
	MaxReplicas *int
	
	// Resource filters
	MinCPU    string
	MaxCPU    string
	MinMemory string
	MaxMemory string
	
	// Metadata filters
	Labels      map[string]string
	Annotations map[string]string
	
	// Pagination and sorting
	Limit     *int
	Offset    *int
	SortBy    ComponentSortField
	SortOrder SortOrder
}

// ComponentSortField defines fields for sorting components
type ComponentSortField string

const (
	ComponentSortByName      ComponentSortField = "name"
	ComponentSortByVersion   ComponentSortField = "version"
	ComponentSortByEnabled   ComponentSortField = "enabled"
	ComponentSortByNamespace ComponentSortField = "namespace"
	ComponentSortByReplicas  ComponentSortField = "replicas"
)

// ComponentHistoryEntry represents a component history entry
type ComponentHistoryEntry struct {
	Version     shared.Version
	Enabled     bool
	ChangedAt   int64
	ChangedBy   string
	ChangeType  ComponentChangeType
	Description string
}

// ComponentChangeType defines types of component changes
type ComponentChangeType string

const (
	ComponentChangeTypeCreated  ComponentChangeType = "created"
	ComponentChangeTypeUpdated  ComponentChangeType = "updated"
	ComponentChangeTypeEnabled  ComponentChangeType = "enabled"
	ComponentChangeTypeDisabled ComponentChangeType = "disabled"
	ComponentChangeTypeDeleted  ComponentChangeType = "deleted"
)

// EventRepository defines event store contract for event sourcing
type EventRepository interface {
	// SaveEvents persists domain events for an aggregate
	SaveEvents(ctx context.Context, aggregateID string, events []events.DomainEvent, expectedVersion int) error
	
	// GetEvents retrieves all events for an aggregate
	GetEvents(ctx context.Context, aggregateID string) ([]events.DomainEvent, error)
	
	// GetEventsAfter retrieves events after a specific version
	GetEventsAfter(ctx context.Context, aggregateID string, version int) ([]events.DomainEvent, error)
	
	// GetEventsByType retrieves events by type
	GetEventsByType(ctx context.Context, eventType string, filter EventFilter) ([]events.DomainEvent, error)
	
	// GetEventsStream creates an event stream for real-time processing
	GetEventsStream(ctx context.Context, filter EventStreamFilter) (<-chan events.DomainEvent, error)
	
	// GetSnapshotVersion returns the latest snapshot version for an aggregate
	GetSnapshotVersion(ctx context.Context, aggregateID string) (int, error)
	
	// SaveSnapshot saves an aggregate snapshot
	SaveSnapshot(ctx context.Context, snapshot AggregateSnapshot) error
	
	// GetSnapshot retrieves the latest snapshot for an aggregate
	GetSnapshot(ctx context.Context, aggregateID string) (*AggregateSnapshot, error)
}

// EventFilter provides filtering for event queries
type EventFilter struct {
	AggregateIDs []string
	EventTypes   []string
	OccurredAfter  *int64
	OccurredBefore *int64
	
	// Metadata filters
	CorrelationID string
	CausationID   string
	UserID        string
	Source        string
	
	// Pagination
	Limit  *int
	Offset *int
	
	// Sorting
	SortOrder SortOrder
}

// EventStreamFilter provides filtering for event streams
type EventStreamFilter struct {
	AggregateIDs   []string
	EventTypes     []string
	StartFromVersion *int
	StartFromTime    *int64
	BufferSize     int
}

// AggregateSnapshot represents an aggregate state snapshot
type AggregateSnapshot struct {
	AggregateID   string
	AggregateType string
	Version       int
	Data          []byte
	Metadata      SnapshotMetadata
	CreatedAt     int64
}

// SnapshotMetadata holds snapshot metadata
type SnapshotMetadata struct {
	Compression string
	Checksum    string
	Size        int64
	EventCount  int
}

// UnitOfWork defines unit of work pattern for transaction coordination
type UnitOfWork interface {
	// Begin starts a new unit of work
	Begin(ctx context.Context) error
	
	// RegisterNew registers a new aggregate for persistence
	RegisterNew(aggregate DomainAggregate) error
	
	// RegisterDirty registers a modified aggregate for persistence
	RegisterDirty(aggregate DomainAggregate) error
	
	// RegisterDeleted registers an aggregate for deletion
	RegisterDeleted(aggregate DomainAggregate) error
	
	// Commit commits all registered changes
	Commit() error
	
	// Rollback rolls back all registered changes
	Rollback() error
	
	// IsActive returns true if unit of work is active
	IsActive() bool
}

// DomainAggregate represents a domain aggregate for unit of work
type DomainAggregate interface {
	// GetID returns the aggregate ID
	GetID() string
	
	// GetType returns the aggregate type
	GetType() string
	
	// GetVersion returns the aggregate version
	GetVersion() int
	
	// GetDomainEvents returns uncommitted domain events
	GetDomainEvents() []events.DomainEvent
	
	// MarkEventsAsCommitted marks events as committed
	MarkEventsAsCommitted()
}

// RepositoryError defines repository-specific errors
type RepositoryError struct {
	Type    RepositoryErrorType
	Message string
	Cause   error
	Context map[string]interface{}
}

// Error implements the error interface
func (e *RepositoryError) Error() string {
	return e.Message
}

// Unwrap returns the underlying error
func (e *RepositoryError) Unwrap() error {
	return e.Cause
}

// RepositoryErrorType defines types of repository errors
type RepositoryErrorType string

const (
	ErrorTypeNotFound         RepositoryErrorType = "not_found"
	ErrorTypeDuplicateKey     RepositoryErrorType = "duplicate_key"
	ErrorTypeVersionConflict  RepositoryErrorType = "version_conflict"
	ErrorTypeConstraintViolation RepositoryErrorType = "constraint_violation"
	ErrorTypeConnectionFailed RepositoryErrorType = "connection_failed"
	ErrorTypeTimeout          RepositoryErrorType = "timeout"
	ErrorTypeValidation       RepositoryErrorType = "validation"
	ErrorTypeUnknown          RepositoryErrorType = "unknown"
)

// Common repository errors
var (
	ErrConfigurationNotFound = &RepositoryError{
		Type:    ErrorTypeNotFound,
		Message: "configuration not found",
	}
	
	ErrTemplateNotFound = &RepositoryError{
		Type:    ErrorTypeNotFound,
		Message: "template not found",
	}
	
	ErrComponentNotFound = &RepositoryError{
		Type:    ErrorTypeNotFound,
		Message: "component not found",
	}
	
	ErrVersionConflict = &RepositoryError{
		Type:    ErrorTypeVersionConflict,
		Message: "version conflict detected",
	}
	
	ErrDuplicateConfiguration = &RepositoryError{
		Type:    ErrorTypeDuplicateKey,
		Message: "configuration already exists",
	}
)

// NewRepositoryError creates a new repository error
func NewRepositoryError(errorType RepositoryErrorType, message string, cause error) *RepositoryError {
	return &RepositoryError{
		Type:    errorType,
		Message: message,
		Cause:   cause,
		Context: make(map[string]interface{}),
	}
}

// WithContext adds context to the repository error
func (e *RepositoryError) WithContext(key string, value interface{}) *RepositoryError {
	e.Context[key] = value
	return e
}

// IsNotFound checks if the error is a not found error
func IsNotFound(err error) bool {
	var repoErr *RepositoryError
	return errors.As(err, &repoErr) && repoErr.Type == ErrorTypeNotFound
}

// IsVersionConflict checks if the error is a version conflict error
func IsVersionConflict(err error) bool {
	var repoErr *RepositoryError
	return errors.As(err, &repoErr) && repoErr.Type == ErrorTypeVersionConflict
}

// IsDuplicateKey checks if the error is a duplicate key error
func IsDuplicateKey(err error) bool {
	var repoErr *RepositoryError
	return errors.As(err, &repoErr) && repoErr.Type == ErrorTypeDuplicateKey
}