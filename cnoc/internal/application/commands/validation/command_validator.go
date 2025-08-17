package validation

import (
	"context"
	"fmt"
	"regexp"
	"strings"

	"github.com/hedgehog/cnoc/internal/application/commands"
	"github.com/hedgehog/cnoc/internal/domain/configuration/services"
)

// CommandValidator provides comprehensive command validation
// Following MDD principles with business rule enforcement and policy compliance
type CommandValidator struct {
	policyEnforcer services.PolicyEnforcer
}

// NewCommandValidator creates a new command validator
func NewCommandValidator(policyEnforcer services.PolicyEnforcer) *CommandValidator {
	return &CommandValidator{
		policyEnforcer: policyEnforcer,
	}
}

// ValidationResult represents comprehensive validation results
type ValidationResult struct {
	Valid       bool                    `json:"valid"`
	Violations  []ValidationViolation   `json:"violations,omitempty"`
	Warnings    []ValidationWarning     `json:"warnings,omitempty"`
	Score       float64                 `json:"score"`
	Context     ValidationContext       `json:"context"`
	Metadata    map[string]interface{}  `json:"metadata,omitempty"`
}

// ValidationViolation represents a validation rule violation
type ValidationViolation struct {
	Field       string                 `json:"field"`
	Code        string                 `json:"code"`
	Message     string                 `json:"message"`
	Severity    ValidationSeverity     `json:"severity"`
	Rule        string                 `json:"rule"`
	Value       interface{}            `json:"value,omitempty"`
	Expected    interface{}            `json:"expected,omitempty"`
	Context     map[string]interface{} `json:"context,omitempty"`
}

// ValidationWarning represents a validation warning
type ValidationWarning struct {
	Field       string                 `json:"field"`
	Code        string                 `json:"code"`
	Message     string                 `json:"message"`
	Severity    ValidationSeverity     `json:"severity"`
	Suggestion  string                 `json:"suggestion,omitempty"`
	Context     map[string]interface{} `json:"context,omitempty"`
}

// ValidationSeverity represents validation severity levels
type ValidationSeverity string

const (
	SeverityInfo     ValidationSeverity = "info"
	SeverityWarning  ValidationSeverity = "warning"
	SeverityError    ValidationSeverity = "error"
	SeverityCritical ValidationSeverity = "critical"
)

// ValidationContext provides context for validation
type ValidationContext struct {
	CommandType       string                 `json:"command_type"`
	UserID           string                 `json:"user_id"`
	RequestID        string                 `json:"request_id"`
	Source           string                 `json:"source"`
	EnforceCompliance bool                   `json:"enforce_compliance"`
	ValidationLevel   ValidationLevel        `json:"validation_level"`
	Context          map[string]interface{} `json:"context,omitempty"`
}

// ValidationLevel represents validation strictness levels
type ValidationLevel string

const (
	ValidationLevelBasic    ValidationLevel = "basic"
	ValidationLevelStandard ValidationLevel = "standard"
	ValidationLevelStrict   ValidationLevel = "strict"
)

// ValidateCreateConfigurationCommand validates create configuration command
func (v *CommandValidator) ValidateCreateConfigurationCommand(
	ctx context.Context,
	cmd commands.CreateConfigurationCommand,
) ValidationResult {
	result := ValidationResult{
		Valid:      true,
		Violations: make([]ValidationViolation, 0),
		Warnings:   make([]ValidationWarning, 0),
		Context: ValidationContext{
			CommandType:       cmd.CommandType(),
			UserID:           cmd.ValidationContext.UserID,
			RequestID:        cmd.ValidationContext.RequestID,
			Source:           cmd.ValidationContext.Source,
			EnforceCompliance: cmd.ValidationContext.EnforceCompliance,
			ValidationLevel:   ValidationLevelStandard,
		},
		Metadata: make(map[string]interface{}),
	}

	// Basic command validation
	v.validateBasicFields(&result, cmd)
	
	// ID validation
	v.validateConfigurationID(&result, "id", cmd.ID)
	
	// Name validation
	v.validateConfigurationName(&result, "name", cmd.Name)
	
	// Description validation
	v.validateDescription(&result, "description", cmd.Description)
	
	// Mode validation
	v.validateConfigurationMode(&result, "mode", cmd.Mode)
	
	// Version validation
	v.validateVersion(&result, "version", cmd.Version)
	
	// Labels validation
	v.validateLabels(&result, "labels", cmd.Labels)
	
	// Annotations validation
	v.validateAnnotations(&result, "annotations", cmd.Annotations)
	
	// Components validation
	v.validateComponents(&result, "components", cmd.Components)
	
	// Enterprise configuration validation
	if cmd.EnterpriseConfig != nil {
		v.validateEnterpriseConfiguration(&result, "enterprise_config", *cmd.EnterpriseConfig)
	}
	
	// Metadata validation
	v.validateMetadata(&result, "metadata", cmd.Metadata)
	
	// Validation context validation
	v.validateValidationContext(&result, "validation_context", cmd.ValidationContext)
	
	// Business rules validation
	v.validateBusinessRules(&result, cmd)
	
	// Policy compliance validation
	if cmd.ValidationContext.EnforceCompliance && v.policyEnforcer != nil {
		v.validatePolicyCompliance(ctx, &result, cmd)
	}
	
	// Calculate validation score
	result.Score = v.calculateValidationScore(result)
	
	// Set overall validity
	result.Valid = len(result.Violations) == 0
	
	return result
}

// ValidateUpdateConfigurationCommand validates update configuration command
func (v *CommandValidator) ValidateUpdateConfigurationCommand(
	ctx context.Context,
	cmd commands.UpdateConfigurationCommand,
) ValidationResult {
	result := ValidationResult{
		Valid:      true,
		Violations: make([]ValidationViolation, 0),
		Warnings:   make([]ValidationWarning, 0),
		Context: ValidationContext{
			CommandType:       cmd.CommandType(),
			UserID:           cmd.ValidationContext.UserID,
			RequestID:        cmd.ValidationContext.RequestID,
			Source:           cmd.ValidationContext.Source,
			EnforceCompliance: cmd.ValidationContext.EnforceCompliance,
			ValidationLevel:   ValidationLevelStandard,
		},
		Metadata: make(map[string]interface{}),
	}

	// Basic validation
	v.validateConfigurationID(&result, "id", cmd.ID)
	v.validateVersion(&result, "version", cmd.Version)
	
	if cmd.ExpectedVersion < 0 {
		v.addViolation(&result, "expected_version", "invalid_expected_version",
			"Expected version must be non-negative", SeverityError,
			"expected_version_rule", cmd.ExpectedVersion, ">= 0")
	}
	
	// Optional field validation
	if cmd.Name != nil {
		v.validateConfigurationName(&result, "name", *cmd.Name)
	}
	
	if cmd.Description != nil {
		v.validateDescription(&result, "description", *cmd.Description)
	}
	
	// Labels and annotations validation
	v.validateLabels(&result, "labels", cmd.Labels)
	v.validateAnnotations(&result, "annotations", cmd.Annotations)
	
	// Component updates validation
	v.validateComponentUpdates(&result, "component_updates", cmd.ComponentUpdates)
	
	// Enterprise configuration validation
	if cmd.EnterpriseConfig != nil {
		v.validateEnterpriseConfiguration(&result, "enterprise_config", *cmd.EnterpriseConfig)
	}
	
	// Metadata validation
	v.validateMetadata(&result, "metadata", cmd.Metadata)
	
	// Validation context validation
	v.validateValidationContext(&result, "validation_context", cmd.ValidationContext)
	
	// Business rules validation for updates
	v.validateUpdateBusinessRules(&result, cmd)
	
	// Calculate score and validity
	result.Score = v.calculateValidationScore(result)
	result.Valid = len(result.Violations) == 0
	
	return result
}

// Specific field validation methods

func (v *CommandValidator) validateBasicFields(result *ValidationResult, cmd commands.CreateConfigurationCommand) {
	if cmd.ID == "" {
		v.addViolation(result, "id", "required_field", "ID is required", SeverityCritical,
			"required_field_rule", "", "non-empty string")
	}
	
	if cmd.Name == "" {
		v.addViolation(result, "name", "required_field", "Name is required", SeverityCritical,
			"required_field_rule", "", "non-empty string")
	}
	
	if cmd.Mode == "" {
		v.addViolation(result, "mode", "required_field", "Mode is required", SeverityCritical,
			"required_field_rule", "", "valid configuration mode")
	}
	
	if cmd.Version == "" {
		v.addViolation(result, "version", "required_field", "Version is required", SeverityCritical,
			"required_field_rule", "", "semantic version")
	}
}

func (v *CommandValidator) validateConfigurationID(result *ValidationResult, field, id string) {
	if id == "" {
		v.addViolation(result, field, "required_field", "Configuration ID is required", SeverityCritical,
			"required_field_rule", "", "non-empty UUID")
		return
	}
	
	// UUID format validation
	uuidRegex := regexp.MustCompile(`^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$`)
	if !uuidRegex.MatchString(id) {
		v.addViolation(result, field, "invalid_uuid_format", "Configuration ID must be a valid UUID", SeverityError,
			"uuid_format_rule", id, "UUID format (8-4-4-4-12)")
	}
}

func (v *CommandValidator) validateConfigurationName(result *ValidationResult, field, name string) {
	if name == "" {
		v.addViolation(result, field, "required_field", "Configuration name is required", SeverityCritical,
			"required_field_rule", "", "non-empty string")
		return
	}
	
	if len(name) < 1 || len(name) > 100 {
		v.addViolation(result, field, "invalid_length", "Configuration name must be 1-100 characters", SeverityError,
			"length_rule", name, "1-100 characters")
	}
	
	// Name format validation (alphanumeric, hyphens, underscores)
	nameRegex := regexp.MustCompile(`^[a-zA-Z0-9][a-zA-Z0-9\-_]*[a-zA-Z0-9]$`)
	if len(name) > 1 && !nameRegex.MatchString(name) {
		v.addViolation(result, field, "invalid_name_format", 
			"Configuration name must contain only alphanumeric characters, hyphens, and underscores", SeverityError,
			"name_format_rule", name, "alphanumeric with hyphens/underscores")
	}
	
	// Reserved names check
	reservedNames := []string{"system", "admin", "root", "default", "config", "cnoc"}
	for _, reserved := range reservedNames {
		if strings.EqualFold(name, reserved) {
			v.addWarning(result, field, "reserved_name", 
				fmt.Sprintf("Configuration name '%s' is reserved", name), SeverityWarning,
				"Consider using a different name")
		}
	}
}

func (v *CommandValidator) validateDescription(result *ValidationResult, field, description string) {
	if len(description) > 500 {
		v.addViolation(result, field, "invalid_length", "Description must not exceed 500 characters", SeverityError,
			"length_rule", description, "<= 500 characters")
	}
	
	// Check for potentially harmful content
	if containsSuspiciousContent(description) {
		v.addWarning(result, field, "suspicious_content", 
			"Description contains potentially suspicious content", SeverityWarning,
			"Review description content")
	}
}

func (v *CommandValidator) validateConfigurationMode(result *ValidationResult, field, mode string) {
	validModes := []string{"development", "staging", "production", "enterprise"}
	isValid := false
	for _, validMode := range validModes {
		if mode == validMode {
			isValid = true
			break
		}
	}
	
	if !isValid {
		v.addViolation(result, field, "invalid_mode", 
			fmt.Sprintf("Configuration mode must be one of: %v", validModes), SeverityError,
			"mode_rule", mode, strings.Join(validModes, ", "))
	}
}

func (v *CommandValidator) validateVersion(result *ValidationResult, field, version string) {
	if version == "" {
		v.addViolation(result, field, "required_field", "Version is required", SeverityCritical,
			"required_field_rule", "", "semantic version")
		return
	}
	
	// Semantic version validation
	semverRegex := regexp.MustCompile(`^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-((?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)(?:\.(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*))?(?:\+([0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*))?$`)
	if !semverRegex.MatchString(version) {
		v.addViolation(result, field, "invalid_semver", "Version must follow semantic versioning format", SeverityError,
			"semver_rule", version, "MAJOR.MINOR.PATCH format")
	}
}

func (v *CommandValidator) validateLabels(result *ValidationResult, field string, labels map[string]string) {
	if len(labels) > 50 {
		v.addViolation(result, field, "too_many_labels", "Maximum 50 labels allowed", SeverityError,
			"label_count_rule", len(labels), "<= 50")
	}
	
	for key, value := range labels {
		if !isValidLabelKey(key) {
			v.addViolation(result, fmt.Sprintf("%s.%s", field, key), "invalid_label_key", 
				"Label key contains invalid characters", SeverityError,
				"label_key_rule", key, "alphanumeric with hyphens/underscores")
		}
		
		if len(value) > 200 {
			v.addViolation(result, fmt.Sprintf("%s.%s", field, key), "invalid_label_value", 
				"Label value too long", SeverityError,
				"label_value_rule", len(value), "<= 200 characters")
		}
	}
}

func (v *CommandValidator) validateAnnotations(result *ValidationResult, field string, annotations map[string]string) {
	if len(annotations) > 100 {
		v.addViolation(result, field, "too_many_annotations", "Maximum 100 annotations allowed", SeverityError,
			"annotation_count_rule", len(annotations), "<= 100")
	}
	
	for key, value := range annotations {
		if !isValidAnnotationKey(key) {
			v.addViolation(result, fmt.Sprintf("%s.%s", field, key), "invalid_annotation_key", 
				"Annotation key contains invalid characters", SeverityError,
				"annotation_key_rule", key, "valid annotation key format")
		}
		
		if len(value) > 1000 {
			v.addViolation(result, fmt.Sprintf("%s.%s", field, key), "invalid_annotation_value", 
				"Annotation value too long", SeverityError,
				"annotation_value_rule", len(value), "<= 1000 characters")
		}
	}
}

func (v *CommandValidator) validateComponents(result *ValidationResult, field string, components []commands.ComponentReference) {
	if len(components) == 0 {
		v.addWarning(result, field, "no_components", "Configuration has no components", SeverityWarning,
			"Consider adding at least one component")
	}
	
	if len(components) > 100 {
		v.addViolation(result, field, "too_many_components", "Maximum 100 components allowed", SeverityError,
			"component_count_rule", len(components), "<= 100")
	}
	
	componentNames := make(map[string]bool)
	for i, component := range components {
		componentField := fmt.Sprintf("%s[%d]", field, i)
		
		// Check for duplicate names
		if componentNames[component.Name] {
			v.addViolation(result, componentField, "duplicate_component", 
				fmt.Sprintf("Duplicate component name: %s", component.Name), SeverityError,
				"unique_component_rule", component.Name, "unique component names")
		}
		componentNames[component.Name] = true
		
		// Validate individual component
		v.validateComponentReference(result, componentField, component)
	}
}

func (v *CommandValidator) validateComponentReference(result *ValidationResult, field string, component commands.ComponentReference) {
	// Name validation
	if component.Name == "" {
		v.addViolation(result, fmt.Sprintf("%s.name", field), "required_field", 
			"Component name is required", SeverityCritical,
			"required_field_rule", "", "non-empty string")
	} else {
		v.validateConfigurationName(result, fmt.Sprintf("%s.name", field), component.Name)
	}
	
	// Version validation
	v.validateVersion(result, fmt.Sprintf("%s.version", field), component.Version)
	
	// Resource requirements validation
	v.validateResourceRequirements(result, fmt.Sprintf("%s.resources", field), component.Resources)
	
	// Dependencies validation
	v.validateDependencies(result, fmt.Sprintf("%s.dependencies", field), component.Dependencies)
	
	// Configuration validation
	if len(component.Configuration) > 50 {
		v.addWarning(result, fmt.Sprintf("%s.configuration", field), "complex_configuration", 
			"Component has many configuration options", SeverityWarning,
			"Consider simplifying component configuration")
	}
}

func (v *CommandValidator) validateResourceRequirements(result *ValidationResult, field string, resources commands.ResourceRequirements) {
	// CPU validation
	if !isValidResourceQuantity(resources.CPU) {
		v.addViolation(result, fmt.Sprintf("%s.cpu", field), "invalid_cpu_format", 
			"Invalid CPU resource format", SeverityError,
			"cpu_format_rule", resources.CPU, "e.g., '100m', '1', '2.5'")
	}
	
	// Memory validation
	if !isValidMemoryQuantity(resources.Memory) {
		v.addViolation(result, fmt.Sprintf("%s.memory", field), "invalid_memory_format", 
			"Invalid memory resource format", SeverityError,
			"memory_format_rule", resources.Memory, "e.g., '128Mi', '1Gi', '2G'")
	}
	
	// Storage validation
	if resources.Storage != "" && !isValidStorageQuantity(resources.Storage) {
		v.addViolation(result, fmt.Sprintf("%s.storage", field), "invalid_storage_format", 
			"Invalid storage resource format", SeverityError,
			"storage_format_rule", resources.Storage, "e.g., '1Gi', '10G', '100GB'")
	}
	
	// Replicas validation
	if resources.Replicas < 1 || resources.Replicas > 100 {
		v.addViolation(result, fmt.Sprintf("%s.replicas", field), "invalid_replicas", 
			"Replicas must be between 1 and 100", SeverityError,
			"replicas_rule", resources.Replicas, "1-100")
	}
	
	// Namespace validation
	if !isValidNamespace(resources.Namespace) {
		v.addViolation(result, fmt.Sprintf("%s.namespace", field), "invalid_namespace", 
			"Invalid namespace format", SeverityError,
			"namespace_rule", resources.Namespace, "DNS-1123 subdomain format")
	}
}

func (v *CommandValidator) validateDependencies(result *ValidationResult, field string, dependencies []string) {
	if len(dependencies) > 20 {
		v.addViolation(result, field, "too_many_dependencies", "Maximum 20 dependencies allowed", SeverityError,
			"dependency_count_rule", len(dependencies), "<= 20")
	}
	
	dependencyMap := make(map[string]bool)
	for i, dep := range dependencies {
		if dep == "" {
			v.addViolation(result, fmt.Sprintf("%s[%d]", field, i), "empty_dependency", 
				"Dependency name cannot be empty", SeverityError,
				"dependency_name_rule", "", "non-empty string")
		}
		
		if dependencyMap[dep] {
			v.addViolation(result, fmt.Sprintf("%s[%d]", field, i), "duplicate_dependency", 
				fmt.Sprintf("Duplicate dependency: %s", dep), SeverityError,
				"unique_dependency_rule", dep, "unique dependency names")
		}
		dependencyMap[dep] = true
	}
}

func (v *CommandValidator) validateEnterpriseConfiguration(result *ValidationResult, field string, enterprise commands.EnterpriseConfiguration) {
	// Compliance framework validation
	validFrameworks := []string{"SOC2", "HIPAA", "PCI-DSS", "ISO27001", "FedRAMP"}
	isValidFramework := false
	for _, framework := range validFrameworks {
		if enterprise.ComplianceFramework == framework {
			isValidFramework = true
			break
		}
	}
	
	if !isValidFramework {
		v.addViolation(result, fmt.Sprintf("%s.compliance_framework", field), "invalid_compliance_framework", 
			fmt.Sprintf("Compliance framework must be one of: %v", validFrameworks), SeverityError,
			"compliance_framework_rule", enterprise.ComplianceFramework, strings.Join(validFrameworks, ", "))
	}
	
	// Security level validation
	validSecurityLevels := []string{"basic", "standard", "high", "critical"}
	isValidLevel := false
	for _, level := range validSecurityLevels {
		if enterprise.SecurityLevel == level {
			isValidLevel = true
			break
		}
	}
	
	if !isValidLevel {
		v.addViolation(result, fmt.Sprintf("%s.security_level", field), "invalid_security_level", 
			fmt.Sprintf("Security level must be one of: %v", validSecurityLevels), SeverityError,
			"security_level_rule", enterprise.SecurityLevel, strings.Join(validSecurityLevels, ", "))
	}
	
	// Policy templates validation
	if len(enterprise.PolicyTemplates) > 20 {
		v.addViolation(result, fmt.Sprintf("%s.policy_templates", field), "too_many_policy_templates", 
			"Maximum 20 policy templates allowed", SeverityError,
			"policy_template_count_rule", len(enterprise.PolicyTemplates), "<= 20")
	}
}

func (v *CommandValidator) validateComponentUpdates(result *ValidationResult, field string, updates []commands.ComponentUpdate) {
	if len(updates) > 50 {
		v.addViolation(result, field, "too_many_updates", "Maximum 50 component updates allowed", SeverityError,
			"update_count_rule", len(updates), "<= 50")
	}
	
	for i, update := range updates {
		updateField := fmt.Sprintf("%s[%d]", field, i)
		
		// Operation validation
		validOperations := []string{"add", "update", "remove", "enable", "disable"}
		isValidOperation := false
		for _, op := range validOperations {
			if update.Operation == op {
				isValidOperation = true
				break
			}
		}
		
		if !isValidOperation {
			v.addViolation(result, fmt.Sprintf("%s.operation", updateField), "invalid_operation", 
				fmt.Sprintf("Operation must be one of: %v", validOperations), SeverityError,
				"operation_rule", update.Operation, strings.Join(validOperations, ", "))
		}
		
		// Name validation
		v.validateConfigurationName(result, fmt.Sprintf("%s.name", updateField), update.Name)
		
		// Version validation for add/update operations
		if (update.Operation == "add" || update.Operation == "update") && update.Version != nil {
			v.validateVersion(result, fmt.Sprintf("%s.version", updateField), *update.Version)
		}
		
		// Resources validation for add/update operations
		if (update.Operation == "add" || update.Operation == "update") && update.Resources != nil {
			v.validateResourceRequirements(result, fmt.Sprintf("%s.resources", updateField), *update.Resources)
		}
	}
}

func (v *CommandValidator) validateMetadata(result *ValidationResult, field string, metadata map[string]interface{}) {
	if len(metadata) > 20 {
		v.addViolation(result, field, "too_much_metadata", "Maximum 20 metadata entries allowed", SeverityError,
			"metadata_count_rule", len(metadata), "<= 20")
	}
	
	for key := range metadata {
		if !isValidMetadataKey(key) {
			v.addViolation(result, fmt.Sprintf("%s.%s", field, key), "invalid_metadata_key", 
				"Metadata key contains invalid characters", SeverityError,
				"metadata_key_rule", key, "alphanumeric with underscores")
		}
	}
}

func (v *CommandValidator) validateValidationContext(result *ValidationResult, field string, context commands.ValidationContext) {
	if context.UserID == "" {
		v.addViolation(result, fmt.Sprintf("%s.user_id", field), "required_field", 
			"User ID is required", SeverityCritical,
			"required_field_rule", "", "non-empty UUID")
	} else {
		v.validateConfigurationID(result, fmt.Sprintf("%s.user_id", field), context.UserID)
	}
	
	if context.RequestID == "" {
		v.addViolation(result, fmt.Sprintf("%s.request_id", field), "required_field", 
			"Request ID is required", SeverityCritical,
			"required_field_rule", "", "non-empty UUID")
	} else {
		v.validateConfigurationID(result, fmt.Sprintf("%s.request_id", field), context.RequestID)
	}
	
	validSources := []string{"api", "cli", "web", "template"}
	isValidSource := false
	for _, source := range validSources {
		if context.Source == source {
			isValidSource = true
			break
		}
	}
	
	if !isValidSource {
		v.addViolation(result, fmt.Sprintf("%s.source", field), "invalid_source", 
			fmt.Sprintf("Source must be one of: %v", validSources), SeverityError,
			"source_rule", context.Source, strings.Join(validSources, ", "))
	}
}

func (v *CommandValidator) validateBusinessRules(result *ValidationResult, cmd commands.CreateConfigurationCommand) {
	// Production mode business rules
	if cmd.Mode == "production" {
		if cmd.EnterpriseConfig == nil {
			v.addViolation(result, "enterprise_config", "missing_enterprise_config", 
				"Enterprise configuration is required for production mode", SeverityError,
				"production_enterprise_rule", nil, "enterprise configuration")
		}
		
		if len(cmd.Components) == 0 {
			v.addViolation(result, "components", "missing_components", 
				"At least one component is required for production mode", SeverityError,
				"production_components_rule", 0, ">= 1 component")
		}
	}
	
	// Enterprise mode business rules
	if cmd.Mode == "enterprise" {
		if cmd.EnterpriseConfig == nil {
			v.addViolation(result, "enterprise_config", "missing_enterprise_config", 
				"Enterprise configuration is required for enterprise mode", SeverityCritical,
				"enterprise_mode_rule", nil, "enterprise configuration")
		} else {
			if !cmd.EnterpriseConfig.AuditEnabled {
				v.addWarning(result, "enterprise_config.audit_enabled", "audit_recommended", 
					"Audit logging is recommended for enterprise mode", SeverityWarning,
					"Enable audit logging for compliance")
			}
			
			if !cmd.EnterpriseConfig.EncryptionRequired {
				v.addWarning(result, "enterprise_config.encryption_required", "encryption_recommended", 
					"Encryption is recommended for enterprise mode", SeverityWarning,
					"Enable encryption for security")
			}
		}
	}
	
	// Component dependency business rules
	for i, component := range cmd.Components {
		if component.Enabled && len(component.Dependencies) == 0 {
			v.addWarning(result, fmt.Sprintf("components[%d].dependencies", i), "no_dependencies", 
				fmt.Sprintf("Component %s has no dependencies", component.Name), SeverityWarning,
				"Verify component independence")
		}
	}
}

func (v *CommandValidator) validateUpdateBusinessRules(result *ValidationResult, cmd commands.UpdateConfigurationCommand) {
	// Version increment validation
	// This would require fetching the current configuration to compare versions
	// For now, we'll add a warning about version management
	v.addWarning(result, "version", "version_management", 
		"Ensure version follows semantic versioning increment rules", SeverityWarning,
		"Follow semantic versioning guidelines")
	
	// Component update business rules
	addOperations := 0
	removeOperations := 0
	
	for _, update := range cmd.ComponentUpdates {
		switch update.Operation {
		case "add":
			addOperations++
		case "remove":
			removeOperations++
		}
	}
	
	if removeOperations > addOperations*2 {
		v.addWarning(result, "component_updates", "many_removals", 
			"Removing many components may affect system stability", SeverityWarning,
			"Review component removal impact")
	}
}

func (v *CommandValidator) validatePolicyCompliance(ctx context.Context, result *ValidationResult, cmd commands.CreateConfigurationCommand) {
	// This would integrate with the policy enforcer service
	// For now, we'll add basic compliance checks
	
	if cmd.EnterpriseConfig != nil {
		framework := cmd.EnterpriseConfig.ComplianceFramework
		
		// Framework-specific validation
		switch framework {
		case "SOC2":
			if !cmd.EnterpriseConfig.AuditEnabled {
				v.addViolation(result, "enterprise_config.audit_enabled", "soc2_audit_required", 
					"SOC2 compliance requires audit logging", SeverityCritical,
					"soc2_compliance_rule", false, true)
			}
			
		case "HIPAA":
			if !cmd.EnterpriseConfig.EncryptionRequired {
				v.addViolation(result, "enterprise_config.encryption_required", "hipaa_encryption_required", 
					"HIPAA compliance requires encryption", SeverityCritical,
					"hipaa_compliance_rule", false, true)
			}
			
		case "PCI-DSS":
			if !cmd.EnterpriseConfig.EncryptionRequired || !cmd.EnterpriseConfig.AuditEnabled {
				v.addViolation(result, "enterprise_config", "pci_dss_requirements", 
					"PCI-DSS compliance requires encryption and audit logging", SeverityCritical,
					"pci_dss_compliance_rule", nil, "encryption and audit enabled")
			}
		}
	}
}

// Helper methods

func (v *CommandValidator) addViolation(result *ValidationResult, field, code, message string, severity ValidationSeverity, rule string, value, expected interface{}) {
	result.Violations = append(result.Violations, ValidationViolation{
		Field:    field,
		Code:     code,
		Message:  message,
		Severity: severity,
		Rule:     rule,
		Value:    value,
		Expected: expected,
	})
}

func (v *CommandValidator) addWarning(result *ValidationResult, field, code, message string, severity ValidationSeverity, suggestion string) {
	result.Warnings = append(result.Warnings, ValidationWarning{
		Field:      field,
		Code:       code,
		Message:    message,
		Severity:   severity,
		Suggestion: suggestion,
	})
}

func (v *CommandValidator) calculateValidationScore(result ValidationResult) float64 {
	if len(result.Violations) == 0 && len(result.Warnings) == 0 {
		return 100.0
	}
	
	score := 100.0
	
	// Deduct points for violations based on severity
	for _, violation := range result.Violations {
		switch violation.Severity {
		case SeverityCritical:
			score -= 25.0
		case SeverityError:
			score -= 10.0
		case SeverityWarning:
			score -= 5.0
		case SeverityInfo:
			score -= 1.0
		}
	}
	
	// Deduct points for warnings
	for _, warning := range result.Warnings {
		switch warning.Severity {
		case SeverityWarning:
			score -= 2.0
		case SeverityInfo:
			score -= 0.5
		}
	}
	
	if score < 0 {
		score = 0
	}
	
	return score
}

// Utility validation functions

func isValidLabelKey(key string) bool {
	labelKeyRegex := regexp.MustCompile(`^[a-zA-Z0-9]([a-zA-Z0-9\-_]*[a-zA-Z0-9])?$`)
	return len(key) <= 100 && labelKeyRegex.MatchString(key)
}

func isValidAnnotationKey(key string) bool {
	// More permissive than label keys, can contain dots and slashes
	annotationKeyRegex := regexp.MustCompile(`^[a-zA-Z0-9]([a-zA-Z0-9\-_\.\/]*[a-zA-Z0-9])?$`)
	return len(key) <= 200 && annotationKeyRegex.MatchString(key)
}

func isValidResourceQuantity(quantity string) bool {
	resourceRegex := regexp.MustCompile(`^(\d+(\.\d+)?)(m||\w+i?)$`)
	return resourceRegex.MatchString(quantity)
}

func isValidMemoryQuantity(quantity string) bool {
	memoryRegex := regexp.MustCompile(`^(\d+(\.\d+)?)(Ei|Pi|Ti|Gi|Mi|Ki|E|P|T|G|M|K)?$`)
	return memoryRegex.MatchString(quantity)
}

func isValidStorageQuantity(quantity string) bool {
	storageRegex := regexp.MustCompile(`^(\d+(\.\d+)?)(Ei|Pi|Ti|Gi|Mi|Ki|E|P|T|G|M|K|EB|PB|TB|GB|MB|KB)?$`)
	return storageRegex.MatchString(quantity)
}

func isValidNamespace(namespace string) bool {
	namespaceRegex := regexp.MustCompile(`^[a-z0-9]([-a-z0-9]*[a-z0-9])?$`)
	return len(namespace) <= 63 && namespaceRegex.MatchString(namespace)
}

func isValidMetadataKey(key string) bool {
	metadataKeyRegex := regexp.MustCompile(`^[a-zA-Z][a-zA-Z0-9_]*$`)
	return len(key) <= 100 && metadataKeyRegex.MatchString(key)
}

func containsSuspiciousContent(content string) bool {
	suspiciousPatterns := []string{
		"<script", "javascript:", "vbscript:", "data:text/html", 
		"eval(", "document.cookie", "window.location",
		"DROP TABLE", "DELETE FROM", "INSERT INTO", "UPDATE SET",
	}
	
	lowerContent := strings.ToLower(content)
	for _, pattern := range suspiciousPatterns {
		if strings.Contains(lowerContent, strings.ToLower(pattern)) {
			return true
		}
	}
	
	return false
}