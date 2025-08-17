package configuration

import (
	"errors"
	"fmt"
	"time"

	"github.com/hedgehog/cnoc/internal/domain/events"
	"github.com/hedgehog/cnoc/internal/domain/shared"
)

// Configuration represents the aggregate root for CNOC system configuration
// following strict Domain-Driven Design principles with rich behavior
type Configuration struct {
	id          ConfigurationID
	name        ConfigurationName
	version     shared.Version
	mode        ConfigurationMode
	components  ComponentCollection
	metadata    ConfigurationMetadata
	status      ConfigurationStatus
	domainEvents []events.DomainEvent
	createdAt   time.Time
	updatedAt   time.Time
}

// ConfigurationID is a type-safe identifier for configurations
type ConfigurationID struct {
	value string
}

// NewConfigurationID creates a new configuration ID with validation
func NewConfigurationID(value string) (ConfigurationID, error) {
	if value == "" {
		return ConfigurationID{}, errors.New("configuration ID cannot be empty")
	}
	if len(value) > 64 {
		return ConfigurationID{}, errors.New("configuration ID cannot exceed 64 characters")
	}
	return ConfigurationID{value: value}, nil
}

// String returns the string representation of the configuration ID
func (id ConfigurationID) String() string {
	return id.value
}

// Equals checks equality between configuration IDs
func (id ConfigurationID) Equals(other ConfigurationID) bool {
	return id.value == other.value
}

// ConfigurationName represents a human-readable configuration name
type ConfigurationName struct {
	value string
}

// NewConfigurationName creates a validated configuration name
func NewConfigurationName(value string) (ConfigurationName, error) {
	if value == "" {
		return ConfigurationName{}, errors.New("configuration name cannot be empty")
	}
	if len(value) > 128 {
		return ConfigurationName{}, errors.New("configuration name cannot exceed 128 characters")
	}
	return ConfigurationName{value: value}, nil
}

// String returns the string representation of the configuration name
func (name ConfigurationName) String() string {
	return name.value
}

// ConfigurationMode represents the operational mode of the configuration
type ConfigurationMode int

const (
	ModeEnterprise ConfigurationMode = iota
	ModeMinimal
	ModeDevelopment
)

// String returns the string representation of the configuration mode
func (mode ConfigurationMode) String() string {
	switch mode {
	case ModeEnterprise:
		return "enterprise"
	case ModeMinimal:
		return "minimal"
	case ModeDevelopment:
		return "development"
	default:
		return "unknown"
	}
}

// ConfigurationStatus represents the current status of the configuration
type ConfigurationStatus int

const (
	StatusDraft ConfigurationStatus = iota
	StatusValidated
	StatusDeployed
	StatusFailed
	StatusArchived
)

// String returns the string representation of the configuration status
func (status ConfigurationStatus) String() string {
	switch status {
	case StatusDraft:
		return "draft"
	case StatusValidated:
		return "validated"
	case StatusDeployed:
		return "deployed"
	case StatusFailed:
		return "failed"
	case StatusArchived:
		return "archived"
	default:
		return "unknown"
	}
}

// ConfigurationMetadata holds additional configuration information
type ConfigurationMetadata struct {
	description      string
	labels          map[string]string
	annotations     map[string]string
	enterpriseConfig *EnterpriseConfiguration
	createdBy       string
	purpose         string
}

// EnterpriseConfiguration represents enterprise-specific configuration settings
type EnterpriseConfiguration struct {
	complianceFramework string
	securityLevel      string
	auditEnabled       bool
	encryptionRequired bool
	backupRequired     bool
	policyTemplates    []string
	metadata          map[string]string
}

// ComplianceFramework returns the compliance framework
func (e *EnterpriseConfiguration) ComplianceFramework() string {
	return e.complianceFramework
}

// SecurityLevel returns the security level
func (e *EnterpriseConfiguration) SecurityLevel() string {
	return e.securityLevel
}

// AuditEnabled returns whether audit is enabled
func (e *EnterpriseConfiguration) AuditEnabled() bool {
	return e.auditEnabled
}

// EncryptionRequired returns whether encryption is required
func (e *EnterpriseConfiguration) EncryptionRequired() bool {
	return e.encryptionRequired
}

// BackupRequired returns whether backup is required
func (e *EnterpriseConfiguration) BackupRequired() bool {
	return e.backupRequired
}

// PolicyTemplates returns the policy templates
func (e *EnterpriseConfiguration) PolicyTemplates() []string {
	return e.policyTemplates
}

// Metadata returns the metadata
func (e *EnterpriseConfiguration) Metadata() map[string]string {
	return e.metadata
}

// NewEnterpriseConfiguration creates a new enterprise configuration
func NewEnterpriseConfiguration(
	framework, securityLevel string,
	auditEnabled, encryptionRequired, backupRequired bool,
	policyTemplates []string,
	metadata map[string]string,
) (*EnterpriseConfiguration, error) {
	return &EnterpriseConfiguration{
		complianceFramework: framework,
		securityLevel:      securityLevel,
		auditEnabled:       auditEnabled,
		encryptionRequired: encryptionRequired,
		backupRequired:     backupRequired,
		policyTemplates:    policyTemplates,
		metadata:          metadata,
	}, nil
}

// ComponentCollection manages a collection of component references
type ComponentCollection struct {
	components map[ComponentName]*ComponentReference
}

// NewComponentCollection creates a new component collection
func NewComponentCollection() *ComponentCollection {
	return &ComponentCollection{
		components: make(map[ComponentName]*ComponentReference),
	}
}

// Add adds a component reference to the collection
func (cc *ComponentCollection) Add(ref *ComponentReference) error {
	if ref == nil {
		return errors.New("component reference cannot be nil")
	}
	
	// Check for conflicts
	if existing, exists := cc.components[ref.Name()]; exists {
		return fmt.Errorf("component '%s' already exists with version %s", 
			ref.Name().String(), existing.Version().String())
	}
	
	cc.components[ref.Name()] = ref
	return nil
}

// Remove removes a component reference from the collection
func (cc *ComponentCollection) Remove(name ComponentName) error {
	if _, exists := cc.components[name]; !exists {
		return fmt.Errorf("component '%s' not found", name.String())
	}
	
	delete(cc.components, name)
	return nil
}

// Get retrieves a component reference by name
func (cc *ComponentCollection) Get(name ComponentName) (*ComponentReference, bool) {
	ref, exists := cc.components[name]
	return ref, exists
}

// List returns all component references
func (cc *ComponentCollection) List() []*ComponentReference {
	refs := make([]*ComponentReference, 0, len(cc.components))
	for _, ref := range cc.components {
		refs = append(refs, ref)
	}
	return refs
}

// Size returns the number of components in the collection
func (cc *ComponentCollection) Size() int {
	return len(cc.components)
}

// ValidationResult represents the result of configuration validation
type ValidationResult struct {
	Valid    bool
	Errors   []ValidationError
	Warnings []ValidationWarning
}

// ValidationError represents a validation error
type ValidationError struct {
	Field   string
	Message string
	Code    string
}

// ValidationWarning represents a validation warning
type ValidationWarning struct {
	Field   string
	Message string
}

// NewConfiguration creates a new configuration aggregate
func NewConfiguration(
	id ConfigurationID,
	name ConfigurationName,
	version shared.Version,
	mode ConfigurationMode,
	metadata ConfigurationMetadata,
) *Configuration {
	config := &Configuration{
		id:           id,
		name:         name,
		version:      version,
		mode:         mode,
		components:   *NewComponentCollection(),
		metadata:     metadata,
		status:       StatusDraft,
		domainEvents: make([]events.DomainEvent, 0),
		createdAt:    time.Now(),
		updatedAt:    time.Now(),
	}
	
	// Raise domain event
	config.addDomainEvent(events.NewConfigurationCreated(id.String(), name.String(), mode.String()))
	
	return config
}

// ID returns the configuration ID
func (c *Configuration) ID() ConfigurationID {
	return c.id
}

// Name returns the configuration name
func (c *Configuration) Name() ConfigurationName {
	return c.name
}

// Version returns the configuration version
func (c *Configuration) Version() shared.Version {
	return c.version
}

// Mode returns the configuration mode
func (c *Configuration) Mode() ConfigurationMode {
	return c.mode
}

// Status returns the current configuration status
func (c *Configuration) Status() ConfigurationStatus {
	return c.status
}

// Components returns the component collection
func (c *Configuration) Components() *ComponentCollection {
	return &c.components
}

// Metadata returns the configuration metadata
func (c *Configuration) Metadata() ConfigurationMetadata {
	return c.metadata
}

// AddComponent adds a component to the configuration with business rule validation
func (c *Configuration) AddComponent(ref *ComponentReference) error {
	if c.status == StatusArchived {
		return errors.New("cannot modify archived configuration")
	}
	
	// Validate component compatibility with current mode
	if err := c.validateComponentCompatibility(ref); err != nil {
		return fmt.Errorf("component compatibility validation failed: %w", err)
	}
	
	// Add to collection
	if err := c.components.Add(ref); err != nil {
		return fmt.Errorf("failed to add component: %w", err)
	}
	
	// Update timestamps and status
	c.updatedAt = time.Now()
	if c.status == StatusValidated {
		c.status = StatusDraft // Requires re-validation after changes
	}
	
	// Raise domain event
	c.addDomainEvent(events.NewComponentAdded(c.id.String(), ref.Name().String(), ref.Version().String()))
	
	return nil
}

// RemoveComponent removes a component from the configuration
func (c *Configuration) RemoveComponent(name ComponentName) error {
	if c.status == StatusArchived {
		return errors.New("cannot modify archived configuration")
	}
	
	// Check if component exists
	ref, exists := c.components.Get(name)
	if !exists {
		return fmt.Errorf("component '%s' not found", name.String())
	}
	
	// Validate removal doesn't break dependencies
	if err := c.validateComponentRemoval(name); err != nil {
		return fmt.Errorf("component removal validation failed: %w", err)
	}
	
	// Remove from collection
	if err := c.components.Remove(name); err != nil {
		return fmt.Errorf("failed to remove component: %w", err)
	}
	
	// Update timestamps and status
	c.updatedAt = time.Now()
	if c.status == StatusValidated {
		c.status = StatusDraft // Requires re-validation after changes
	}
	
	// Raise domain event
	c.addDomainEvent(events.NewComponentRemoved(c.id.String(), name.String(), ref.Version().String()))
	
	return nil
}

// ValidateIntegrity performs comprehensive configuration validation
func (c *Configuration) ValidateIntegrity() ValidationResult {
	result := ValidationResult{
		Valid:    true,
		Errors:   make([]ValidationError, 0),
		Warnings: make([]ValidationWarning, 0),
	}
	
	// Basic validation rules
	if c.components.Size() == 0 {
		result.Errors = append(result.Errors, ValidationError{
			Field:   "components",
			Message: "configuration must contain at least one component",
			Code:    "EMPTY_COMPONENTS",
		})
		result.Valid = false
	}
	
	// Mode-specific validation
	if err := c.validateModeConstraints(); err != nil {
		result.Errors = append(result.Errors, ValidationError{
			Field:   "mode",
			Message: err.Error(),
			Code:    "MODE_CONSTRAINT_VIOLATION",
		})
		result.Valid = false
	}
	
	// Component dependency validation
	if err := c.validateComponentDependencies(); err != nil {
		result.Errors = append(result.Errors, ValidationError{
			Field:   "dependencies",
			Message: err.Error(),
			Code:    "DEPENDENCY_VIOLATION",
		})
		result.Valid = false
	}
	
	// Version compatibility validation
	if warnings := c.validateVersionCompatibility(); len(warnings) > 0 {
		result.Warnings = append(result.Warnings, warnings...)
	}
	
	// Update status based on validation result
	if result.Valid {
		c.status = StatusValidated
		c.addDomainEvent(events.NewConfigurationValidated(c.id.String()))
	}
	
	return result
}

// Deploy initiates configuration deployment
func (c *Configuration) Deploy() error {
	if c.status != StatusValidated {
		return errors.New("configuration must be validated before deployment")
	}
	
	c.status = StatusDeployed
	c.updatedAt = time.Now()
	
	// Raise domain event
	c.addDomainEvent(events.NewConfigurationDeployed(c.id.String()))
	
	return nil
}

// MarkFailed marks the configuration as failed
func (c *Configuration) MarkFailed(reason string) {
	c.status = StatusFailed
	c.updatedAt = time.Now()
	
	// Raise domain event
	c.addDomainEvent(events.NewConfigurationFailed(c.id.String(), reason))
}

// Archive archives the configuration
func (c *Configuration) Archive() error {
	if c.status == StatusDeployed {
		return errors.New("cannot archive deployed configuration")
	}
	
	c.status = StatusArchived
	c.updatedAt = time.Now()
	
	// Raise domain event
	c.addDomainEvent(events.NewConfigurationArchived(c.id.String()))
	
	return nil
}

// UpdateMetadata updates configuration metadata
func (c *Configuration) UpdateMetadata(metadata ConfigurationMetadata) {
	c.metadata = metadata
	c.updatedAt = time.Now()
	
	// Raise domain event
	c.addDomainEvent(events.NewConfigurationUpdated(c.id.String()))
}

// DomainEvents returns all uncommitted domain events
func (c *Configuration) DomainEvents() []events.DomainEvent {
	return c.domainEvents
}

// MarkEventsAsCommitted clears domain events after they've been published
func (c *Configuration) MarkEventsAsCommitted() {
	c.domainEvents = make([]events.DomainEvent, 0)
}

// Private helper methods

func (c *Configuration) addDomainEvent(event events.DomainEvent) {
	c.domainEvents = append(c.domainEvents, event)
}

func (c *Configuration) validateComponentCompatibility(ref *ComponentReference) error {
	// Mode-specific component validation
	switch c.mode {
	case ModeMinimal:
		// Minimal mode only allows essential components
		essentialComponents := map[string]bool{
			"argocd":      true,
			"prometheus":  false, // Optional in minimal mode
			"grafana":     false, // Optional in minimal mode
		}
		
		if required, exists := essentialComponents[ref.Name().String()]; exists && !required {
			return fmt.Errorf("component '%s' not allowed in minimal mode", ref.Name().String())
		}
		
	case ModeEnterprise:
		// Enterprise mode requires certain components
		if ref.Name().String() == "development-tools" {
			return fmt.Errorf("development tools not allowed in enterprise mode")
		}
	}
	
	return nil
}

// Public accessor methods for anti-corruption layer compliance
func (c *Configuration) Description() string {
	return c.metadata.description
}

func (c *Configuration) Labels() map[string]string {
	return c.metadata.labels
}

func (c *Configuration) Annotations() map[string]string {
	return c.metadata.annotations
}

func (c *Configuration) CreatedAt() time.Time {
	return c.createdAt
}

func (c *Configuration) UpdatedAt() time.Time {
	return c.updatedAt
}

func (c *Configuration) EnterpriseConfiguration() *EnterpriseConfiguration {
	return c.metadata.enterpriseConfig
}

func (c *Configuration) validateComponentRemoval(name ComponentName) error {
	// Find the component reference being removed
	var componentToRemove *ComponentReference
	for _, ref := range c.components.List() {
		if ref.Name().Equals(name) {
			componentToRemove = ref
			break
		}
	}
	
	if componentToRemove == nil {
		return fmt.Errorf("component '%s' not found", name.String())
	}
	
	// Check if other components depend on this one
	for _, ref := range c.components.List() {
		if ref.Name().Equals(name) {
			continue // Skip self
		}
		
		// Check dependencies (this would typically use a dependency resolver service)
		if c.isComponentRequired(componentToRemove, ref) {
			return fmt.Errorf("cannot remove component '%s' as it's required by '%s'", 
				name.String(), ref.Name().String())
		}
	}
	
	return nil
}

func (c *Configuration) isComponentRequired(dependency, dependent *ComponentReference) bool {
	// Simplified dependency checking - in real implementation this would use
	// the DependencyResolver domain service
	dependencyMap := map[string][]string{
		"prometheus": {"grafana"},
		"cert-manager": {"argocd", "grafana"},
	}
	
	if deps, exists := dependencyMap[dependency.Name().String()]; exists {
		for _, dep := range deps {
			if dep == dependent.Name().String() {
				return true
			}
		}
	}
	
	return false
}

func (c *Configuration) validateModeConstraints() error {
	switch c.mode {
	case ModeEnterprise:
		// Enterprise mode must have certain components
		requiredComponents := []string{"cert-manager", "argocd"}
		for _, required := range requiredComponents {
			name, _ := NewComponentName(required)
			if _, exists := c.components.Get(name); !exists {
				return fmt.Errorf("enterprise mode requires component '%s'", required)
			}
		}
		
	case ModeMinimal:
		// Minimal mode has component count limits
		if c.components.Size() > 3 {
			return fmt.Errorf("minimal mode cannot have more than 3 components")
		}
	}
	
	return nil
}

func (c *Configuration) validateComponentDependencies() error {
	// This would typically delegate to a DependencyResolver domain service
	// Simplified implementation for demonstration
	
	dependencies := map[string][]string{
		"grafana": {"prometheus"},
		"argocd":  {"cert-manager"},
	}
	
	for _, ref := range c.components.List() {
		if deps, exists := dependencies[ref.Name().String()]; exists {
			for _, dep := range deps {
				depName, _ := NewComponentName(dep)
				if _, exists := c.components.Get(depName); !exists {
					return fmt.Errorf("component '%s' requires '%s' but it's not present", 
						ref.Name().String(), dep)
				}
			}
		}
	}
	
	return nil
}

func (c *Configuration) validateVersionCompatibility() []ValidationWarning {
	warnings := make([]ValidationWarning, 0)
	
	// Check for version compatibility issues
	for _, ref := range c.components.List() {
		if ref.Version().IsPreRelease() {
			warnings = append(warnings, ValidationWarning{
				Field:   "version",
				Message: fmt.Sprintf("component '%s' uses pre-release version %s", 
					ref.Name().String(), ref.Version().String()),
			})
		}
	}
	
	return warnings
}