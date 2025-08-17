package services

import (
	"context"
	"fmt"

	"github.com/hedgehog/cnoc/internal/domain/configuration"
	"github.com/hedgehog/cnoc/internal/domain/events"
)

// ConfigurationValidator is a domain service that provides comprehensive
// configuration validation following business rules and domain constraints
type ConfigurationValidator struct {
	dependencyResolver DependencyResolver
	policyEnforcer     PolicyEnforcer
	componentRegistry  ComponentRegistry
	eventBus          events.EventBus
}

// NewConfigurationValidator creates a new configuration validator
func NewConfigurationValidator(
	dependencyResolver DependencyResolver,
	policyEnforcer PolicyEnforcer,
	componentRegistry ComponentRegistry,
	eventBus events.EventBus,
) *ConfigurationValidator {
	return &ConfigurationValidator{
		dependencyResolver: dependencyResolver,
		policyEnforcer:     policyEnforcer,
		componentRegistry:  componentRegistry,
		eventBus:          eventBus,
	}
}

// ValidationContext provides context for validation operations
type ValidationContext struct {
	Context           context.Context
	ConfigurationMode configuration.ConfigurationMode
	EnterpriseMode    bool
	StrictValidation  bool
	PolicyFramework   string
}

// ExtendedValidationResult provides comprehensive validation results
type ExtendedValidationResult struct {
	Valid             bool
	Errors           []ValidationError
	Warnings         []ValidationWarning
	Suggestions      []ValidationSuggestion
	Dependencies     DependencyValidationResult
	PolicyCompliance PolicyComplianceResult
	Metadata         ValidationMetadata
}

// ValidationError represents a validation error with context
type ValidationError struct {
	Field       string
	Message     string
	Code        string
	Severity    ValidationSeverity
	Context     map[string]interface{}
	Suggestion  string
}

// ValidationWarning represents a validation warning
type ValidationWarning struct {
	Field   string
	Message string
	Code    string
	Impact  string
}

// ValidationSuggestion represents an improvement suggestion
type ValidationSuggestion struct {
	Category    string
	Message     string
	Action      string
	Priority    SuggestionPriority
	Command     string
}

// ValidationSeverity represents the severity of validation issues
type ValidationSeverity int

const (
	SeverityLow ValidationSeverity = iota
	SeverityMedium
	SeverityHigh
	SeverityCritical
)

// SuggestionPriority represents the priority of suggestions
type SuggestionPriority int

const (
	PriorityLow SuggestionPriority = iota
	PriorityMedium
	PriorityHigh
	PriorityCritical
)

// ValidationMetadata provides additional validation context
type ValidationMetadata struct {
	ValidatedLayers    []string
	ValidationDuration int64
	ComponentCount     int
	DependencyCount    int
	PolicyCount        int
}

// DependencyValidationResult contains dependency validation results
type DependencyValidationResult struct {
	Valid              bool
	MissingDependencies []MissingDependency
	CircularDependencies []CircularDependency
	VersionConflicts    []VersionConflict
	InstallationOrder   []string
}

// MissingDependency represents a missing component dependency
type MissingDependency struct {
	RequiredBy    string
	ComponentName string
	RequiredVersion string
	Severity      ValidationSeverity
}

// CircularDependency represents a circular dependency
type CircularDependency struct {
	Components []string
	Cycle      []string
}

// VersionConflict represents a version compatibility conflict
type VersionConflict struct {
	ComponentName    string
	RequestedVersion string
	ConflictingWith  string
	ConflictVersion  string
	Resolution       string
}

// PolicyComplianceResult contains policy compliance validation results
type PolicyComplianceResult struct {
	Compliant        bool
	Framework        string
	ViolatedPolicies []PolicyViolation
	RequiredActions  []PolicyAction
}

// PolicyViolation represents a policy compliance violation
type PolicyViolation struct {
	Policy      string
	Violation   string
	Severity    ValidationSeverity
	Remediation string
}

// PolicyAction represents a required policy action
type PolicyAction struct {
	Action      string
	Component   string
	Description string
	Required    bool
}

// ValidateConfiguration performs comprehensive configuration validation
func (cv *ConfigurationValidator) ValidateConfiguration(
	ctx context.Context,
	config *configuration.Configuration,
	validationCtx ValidationContext,
) ExtendedValidationResult {
	result := ExtendedValidationResult{
		Valid:        true,
		Errors:       make([]ValidationError, 0),
		Warnings:     make([]ValidationWarning, 0),
		Suggestions:  make([]ValidationSuggestion, 0),
		Dependencies: DependencyValidationResult{Valid: true},
		PolicyCompliance: PolicyComplianceResult{Compliant: true},
	}

	// Basic configuration validation
	cv.validateBasicConfiguration(config, &result)
	
	// Component validation
	cv.validateComponents(ctx, config, &result)
	
	// Dependency validation using dependency resolver domain service
	cv.validateDependencies(ctx, config, &result)
	
	// Mode-specific validation
	cv.validateModeConstraints(config, validationCtx, &result)
	
	// Enterprise policy validation if applicable
	if validationCtx.EnterpriseMode {
		cv.validatePolicyCompliance(ctx, config, validationCtx, &result)
	}
	
	// Performance and resource validation
	cv.validateResourceRequirements(config, &result)
	
	// Generate suggestions for optimization
	cv.generateOptimizationSuggestions(config, &result)
	
	// Update metadata
	cv.updateValidationMetadata(config, &result)
	
	// Determine overall validity
	result.Valid = len(result.Errors) == 0 && result.Dependencies.Valid && result.PolicyCompliance.Compliant
	
	// Publish validation event
	cv.publishValidationEvent(config, result)
	
	return result
}

// ValidateUpgrade validates configuration upgrade compatibility
func (cv *ConfigurationValidator) ValidateUpgrade(
	ctx context.Context,
	fromConfig *configuration.Configuration,
	toConfig *configuration.Configuration,
	validationCtx ValidationContext,
) UpgradeValidationResult {
	result := UpgradeValidationResult{
		Compatible:      true,
		BreakingChanges: make([]BreakingChange, 0),
		Warnings:       make([]UpgradeWarning, 0),
		MigrationSteps: make([]MigrationStep, 0),
	}
	
	// Validate version compatibility
	cv.validateVersionUpgrade(fromConfig, toConfig, &result)
	
	// Validate component changes
	cv.validateComponentChanges(fromConfig, toConfig, &result)
	
	// Check for breaking changes
	cv.detectBreakingChanges(fromConfig, toConfig, &result)
	
	// Generate migration steps
	cv.generateMigrationSteps(fromConfig, toConfig, &result)
	
	return result
}

// UpgradeValidationResult contains upgrade validation results
type UpgradeValidationResult struct {
	Compatible      bool
	BreakingChanges []BreakingChange
	Warnings        []UpgradeWarning
	MigrationSteps  []MigrationStep
	RollbackPlan    RollbackPlan
}

// BreakingChange represents a breaking change in upgrade
type BreakingChange struct {
	Type        string
	Component   string
	Description string
	Impact      string
	Mitigation  string
}

// UpgradeWarning represents an upgrade warning
type UpgradeWarning struct {
	Component   string
	Message     string
	Recommendation string
}

// MigrationStep represents a step in configuration migration
type MigrationStep struct {
	Order       int
	Description string
	Component   string
	Action      string
	Reversible  bool
}

// RollbackPlan contains rollback information
type RollbackPlan struct {
	Supported bool
	Steps     []RollbackStep
	Duration  int64
}

// RollbackStep represents a rollback step
type RollbackStep struct {
	Order       int
	Description string
	Command     string
	Validation  string
}

// Private validation methods

func (cv *ConfigurationValidator) validateBasicConfiguration(
	config *configuration.Configuration,
	result *ExtendedValidationResult,
) {
	// Validate configuration name
	if config.Name().String() == "" {
		result.Errors = append(result.Errors, ValidationError{
			Field:    "name",
			Message:  "configuration name cannot be empty",
			Code:     "EMPTY_NAME",
			Severity: SeverityCritical,
		})
	}
	
	// Validate component count
	if config.Components().Size() == 0 {
		result.Errors = append(result.Errors, ValidationError{
			Field:    "components",
			Message:  "configuration must contain at least one component",
			Code:     "EMPTY_COMPONENTS",
			Severity: SeverityCritical,
		})
	}
	
	// Validate version format
	if config.Version().String() == "" {
		result.Errors = append(result.Errors, ValidationError{
			Field:    "version",
			Message:  "configuration version cannot be empty",
			Code:     "EMPTY_VERSION",
			Severity: SeverityHigh,
		})
	}
}

func (cv *ConfigurationValidator) validateComponents(
	ctx context.Context,
	config *configuration.Configuration,
	result *ExtendedValidationResult,
) {
	for _, comp := range config.Components().List() {
		// Validate component exists in registry
		if !cv.componentRegistry.Exists(comp.Name()) {
			result.Errors = append(result.Errors, ValidationError{
				Field:    "components",
				Message:  fmt.Sprintf("component '%s' not found in registry", comp.Name().String()),
				Code:     "COMPONENT_NOT_FOUND",
				Severity: SeverityHigh,
				Context: map[string]interface{}{
					"component": comp.Name().String(),
				},
			})
			continue
		}
		
		// Validate component version
		if err := cv.validateComponentVersion(comp); err != nil {
			result.Errors = append(result.Errors, ValidationError{
				Field:    "components",
				Message:  err.Error(),
				Code:     "INVALID_COMPONENT_VERSION",
				Severity: SeverityMedium,
				Context: map[string]interface{}{
					"component": comp.Name().String(),
					"version":   comp.Version().String(),
				},
			})
		}
		
		// Validate component configuration
		if err := cv.validateComponentConfiguration(comp); err != nil {
			result.Warnings = append(result.Warnings, ValidationWarning{
				Field:   "components",
				Message: err.Error(),
				Code:    "COMPONENT_CONFIG_WARNING",
				Impact:  "Performance or reliability may be affected",
			})
		}
	}
}

func (cv *ConfigurationValidator) validateDependencies(
	ctx context.Context,
	config *configuration.Configuration,
	result *ExtendedValidationResult,
) {
	components := make([]configuration.ComponentName, 0, config.Components().Size())
	for _, comp := range config.Components().List() {
		components = append(components, comp.Name())
	}
	
	// Use dependency resolver domain service
	depResult := cv.dependencyResolver.ValidateDependencies(ctx, components)
	result.Dependencies = depResult
	
	// Convert dependency errors to validation errors
	for _, missing := range depResult.MissingDependencies {
		result.Errors = append(result.Errors, ValidationError{
			Field:    "dependencies",
			Message:  fmt.Sprintf("component '%s' requires '%s' but it's not present", missing.RequiredBy, missing.ComponentName),
			Code:     "MISSING_DEPENDENCY",
			Severity: missing.Severity,
			Context: map[string]interface{}{
				"requiredBy":      missing.RequiredBy,
				"missingComponent": missing.ComponentName,
				"requiredVersion": missing.RequiredVersion,
			},
			Suggestion: fmt.Sprintf("Add component '%s' to configuration", missing.ComponentName),
		})
	}
	
	// Handle circular dependencies
	for _, circular := range depResult.CircularDependencies {
		result.Errors = append(result.Errors, ValidationError{
			Field:    "dependencies",
			Message:  fmt.Sprintf("circular dependency detected: %v", circular.Cycle),
			Code:     "CIRCULAR_DEPENDENCY",
			Severity: SeverityCritical,
			Context: map[string]interface{}{
				"components": circular.Components,
				"cycle":      circular.Cycle,
			},
		})
	}
}

func (cv *ConfigurationValidator) validateModeConstraints(
	config *configuration.Configuration,
	validationCtx ValidationContext,
	result *ExtendedValidationResult,
) {
	switch config.Mode() {
	case configuration.ModeEnterprise:
		cv.validateEnterpriseMode(config, result)
	case configuration.ModeMinimal:
		cv.validateMinimalMode(config, result)
	case configuration.ModeDevelopment:
		cv.validateDevelopmentMode(config, result)
	}
}

func (cv *ConfigurationValidator) validateEnterpriseMode(
	config *configuration.Configuration,
	result *ExtendedValidationResult,
) {
	requiredComponents := []string{"cert-manager", "argocd"}
	for _, required := range requiredComponents {
		name, _ := configuration.NewComponentName(required)
		if _, exists := config.Components().Get(name); !exists {
			result.Errors = append(result.Errors, ValidationError{
				Field:    "mode",
				Message:  fmt.Sprintf("enterprise mode requires component '%s'", required),
				Code:     "ENTERPRISE_COMPONENT_REQUIRED",
				Severity: SeverityHigh,
				Suggestion: fmt.Sprintf("Add '%s' component to configuration", required),
			})
		}
	}
	
	// Enterprise mode should have security components
	securityComponents := []string{"cert-manager"}
	for _, security := range securityComponents {
		name, _ := configuration.NewComponentName(security)
		if _, exists := config.Components().Get(name); !exists {
			result.Warnings = append(result.Warnings, ValidationWarning{
				Field:   "security",
				Message: fmt.Sprintf("enterprise mode should include security component '%s'", security),
				Code:    "SECURITY_COMPONENT_RECOMMENDED",
				Impact:  "Security posture may be compromised",
			})
		}
	}
}

func (cv *ConfigurationValidator) validateMinimalMode(
	config *configuration.Configuration,
	result *ExtendedValidationResult,
) {
	maxComponents := 3
	if config.Components().Size() > maxComponents {
		result.Errors = append(result.Errors, ValidationError{
			Field:    "mode",
			Message:  fmt.Sprintf("minimal mode cannot have more than %d components", maxComponents),
			Code:     "MINIMAL_COMPONENT_LIMIT",
			Severity: SeverityMedium,
			Context: map[string]interface{}{
				"currentCount": config.Components().Size(),
				"maxAllowed":   maxComponents,
			},
		})
	}
}

func (cv *ConfigurationValidator) validateDevelopmentMode(
	config *configuration.Configuration,
	result *ExtendedValidationResult,
) {
	// Development mode should include monitoring for debugging
	monitoringComponents := []string{"prometheus", "grafana"}
	missingMonitoring := 0
	
	for _, monitoring := range monitoringComponents {
		name, _ := configuration.NewComponentName(monitoring)
		if _, exists := config.Components().Get(name); !exists {
			missingMonitoring++
		}
	}
	
	if missingMonitoring == len(monitoringComponents) {
		result.Suggestions = append(result.Suggestions, ValidationSuggestion{
			Category: "monitoring",
			Message:  "development mode benefits from monitoring components",
			Action:   "Consider adding prometheus and grafana for better debugging",
			Priority: PriorityMedium,
		})
	}
}

func (cv *ConfigurationValidator) validatePolicyCompliance(
	ctx context.Context,
	config *configuration.Configuration,
	validationCtx ValidationContext,
	result *ExtendedValidationResult,
) {
	// Use policy enforcer domain service
	complianceResult := cv.policyEnforcer.ValidateCompliance(ctx, config, validationCtx.PolicyFramework)
	result.PolicyCompliance = complianceResult
	
	// Convert policy violations to validation errors
	for _, violation := range complianceResult.ViolatedPolicies {
		result.Errors = append(result.Errors, ValidationError{
			Field:    "policy",
			Message:  violation.Violation,
			Code:     "POLICY_VIOLATION",
			Severity: violation.Severity,
			Context: map[string]interface{}{
				"policy":      violation.Policy,
				"framework":   complianceResult.Framework,
			},
			Suggestion: violation.Remediation,
		})
	}
}

func (cv *ConfigurationValidator) validateResourceRequirements(
	config *configuration.Configuration,
	result *ExtendedValidationResult,
) {
	totalCPU := 0.0
	
	for _, comp := range config.Components().List() {
		// Parse CPU and memory requirements (simplified)
		// In real implementation, this would use proper resource parsing
		cpuReq := comp.Configuration().Resources().Requests().CPU()
		memReq := comp.Configuration().Resources().Requests().Memory()
		
		// Validate resource format
		if cpuReq == "" || memReq == "" {
			result.Warnings = append(result.Warnings, ValidationWarning{
				Field:   "resources",
				Message: fmt.Sprintf("component '%s' has no resource requirements specified", comp.Name().String()),
				Code:    "MISSING_RESOURCES",
				Impact:  "Resource planning may be inaccurate",
			})
		}
	}
	
	// Check if total resource requirements are reasonable
	if totalCPU > 10.0 { // Example threshold
		result.Warnings = append(result.Warnings, ValidationWarning{
			Field:   "resources",
			Message: "total CPU requirements may be excessive",
			Code:    "HIGH_CPU_USAGE",
			Impact:  "May require significant cluster resources",
		})
	}
}

func (cv *ConfigurationValidator) generateOptimizationSuggestions(
	config *configuration.Configuration,
	result *ExtendedValidationResult,
) {
	// Suggest monitoring if not present
	hasMonitoring := false
	monitoringComponents := []string{"prometheus", "grafana"}
	
	for _, monitoring := range monitoringComponents {
		name, _ := configuration.NewComponentName(monitoring)
		if _, exists := config.Components().Get(name); exists {
			hasMonitoring = true
			break
		}
	}
	
	if !hasMonitoring {
		result.Suggestions = append(result.Suggestions, ValidationSuggestion{
			Category: "observability",
			Message:  "consider adding monitoring components",
			Action:   "Add prometheus and grafana for better system visibility",
			Priority: PriorityMedium,
			Command:  "cnocfab components add prometheus grafana",
		})
	}
	
	// Suggest security improvements
	hasSecurityManager := false
	name, _ := configuration.NewComponentName("cert-manager")
	if _, exists := config.Components().Get(name); exists {
		hasSecurityManager = true
	}
	
	if !hasSecurityManager && config.Mode() != configuration.ModeMinimal {
		result.Suggestions = append(result.Suggestions, ValidationSuggestion{
			Category: "security",
			Message:  "consider adding certificate management",
			Action:   "Add cert-manager for TLS certificate automation",
			Priority: PriorityHigh,
			Command:  "cnocfab components add cert-manager",
		})
	}
}

func (cv *ConfigurationValidator) updateValidationMetadata(
	config *configuration.Configuration,
	result *ExtendedValidationResult,
) {
	result.Metadata = ValidationMetadata{
		ValidatedLayers: []string{"basic", "components", "dependencies", "mode", "resources"},
		ComponentCount:  config.Components().Size(),
		DependencyCount: len(result.Dependencies.MissingDependencies) + len(result.Dependencies.CircularDependencies),
		PolicyCount:     len(result.PolicyCompliance.ViolatedPolicies),
	}
	
	if result.PolicyCompliance.Framework != "" {
		result.Metadata.ValidatedLayers = append(result.Metadata.ValidatedLayers, "policy")
	}
}

func (cv *ConfigurationValidator) publishValidationEvent(
	config *configuration.Configuration,
	result ExtendedValidationResult,
) {
	var event events.DomainEvent
	
	if result.Valid {
		event = events.NewConfigurationValidated(config.ID().String())
	} else {
		errorCount := len(result.Errors)
		event = events.NewConfigurationFailed(config.ID().String(), 
			fmt.Sprintf("validation failed with %d errors", errorCount))
	}
	
	if cv.eventBus != nil {
		cv.eventBus.Publish(event)
	}
}

// Helper validation methods

func (cv *ConfigurationValidator) validateComponentVersion(
	comp *configuration.ComponentReference,
) error {
	if comp.Version().IsPreRelease() {
		return fmt.Errorf("component '%s' uses pre-release version %s", 
			comp.Name().String(), comp.Version().String())
	}
	return nil
}

func (cv *ConfigurationValidator) validateComponentConfiguration(
	comp *configuration.ComponentReference,
) error {
	// Validate replica count
	if comp.Configuration().Replicas() == 0 {
		return fmt.Errorf("component '%s' has zero replicas configured", comp.Name().String())
	}
	
	// Validate namespace
	if comp.Configuration().Namespace() == "" {
		return fmt.Errorf("component '%s' has no namespace configured", comp.Name().String())
	}
	
	return nil
}

func (cv *ConfigurationValidator) validateVersionUpgrade(
	fromConfig *configuration.Configuration,
	toConfig *configuration.Configuration,
	result *UpgradeValidationResult,
) {
	if fromConfig.Version().IsGreaterThan(toConfig.Version()) {
		result.BreakingChanges = append(result.BreakingChanges, BreakingChange{
			Type:        "version_downgrade",
			Description: "configuration version downgrade detected",
			Impact:      "may cause compatibility issues",
			Mitigation:  "ensure compatibility before proceeding",
		})
		result.Compatible = false
	}
}

func (cv *ConfigurationValidator) validateComponentChanges(
	fromConfig *configuration.Configuration,
	toConfig *configuration.Configuration,
	result *UpgradeValidationResult,
) {
	// Check for removed components
	for _, comp := range fromConfig.Components().List() {
		if _, exists := toConfig.Components().Get(comp.Name()); !exists {
			result.BreakingChanges = append(result.BreakingChanges, BreakingChange{
				Type:        "component_removal",
				Component:   comp.Name().String(),
				Description: fmt.Sprintf("component '%s' removed", comp.Name().String()),
				Impact:      "functionality may be lost",
				Mitigation:  "ensure component is no longer needed",
			})
		}
	}
}

func (cv *ConfigurationValidator) detectBreakingChanges(
	fromConfig *configuration.Configuration,
	toConfig *configuration.Configuration,
	result *UpgradeValidationResult,
) {
	// Check for mode changes
	if fromConfig.Mode() != toConfig.Mode() {
		result.BreakingChanges = append(result.BreakingChanges, BreakingChange{
			Type:        "mode_change",
			Description: fmt.Sprintf("mode changed from %s to %s", fromConfig.Mode().String(), toConfig.Mode().String()),
			Impact:      "configuration constraints may change",
			Mitigation:  "validate new mode requirements",
		})
	}
}

func (cv *ConfigurationValidator) generateMigrationSteps(
	fromConfig *configuration.Configuration,
	toConfig *configuration.Configuration,
	result *UpgradeValidationResult,
) {
	step := 1
	
	// Add migration steps for new components
	for _, comp := range toConfig.Components().List() {
		if _, exists := fromConfig.Components().Get(comp.Name()); !exists {
			result.MigrationSteps = append(result.MigrationSteps, MigrationStep{
				Order:       step,
				Description: fmt.Sprintf("install component '%s'", comp.Name().String()),
				Component:   comp.Name().String(),
				Action:      "install",
				Reversible:  true,
			})
			step++
		}
	}
}