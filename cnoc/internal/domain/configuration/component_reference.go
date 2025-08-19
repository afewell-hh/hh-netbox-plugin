package configuration

import (
	"errors"
	"fmt"
	"regexp"

	"github.com/hedgehog/cnoc/internal/domain/shared"
)

// ComponentReference represents a reference to a component within a configuration
// This is a value object that encapsulates component identification and configuration
type ComponentReference struct {
	name          ComponentName
	version       shared.Version
	enabled       bool
	configuration ComponentConfiguration
	metadata      ComponentMetadata
}

// ComponentName is a type-safe identifier for components
type ComponentName struct {
	value string
}

// NewComponentName creates a validated component name
func NewComponentName(value string) (ComponentName, error) {
	if value == "" {
		return ComponentName{}, errors.New("component name cannot be empty")
	}
	
	// Kubernetes resource name validation
	if len(value) > 63 {
		return ComponentName{}, errors.New("component name cannot exceed 63 characters")
	}
	
	// Must be lowercase alphanumeric with hyphens
	validName := regexp.MustCompile(`^[a-z0-9]([a-z0-9\-]*[a-z0-9])?$`)
	if !validName.MatchString(value) {
		return ComponentName{}, errors.New("component name must be lowercase alphanumeric with hyphens")
	}
	
	return ComponentName{value: value}, nil
}

// String returns the string representation of the component name
func (name ComponentName) String() string {
	return name.value
}

// Equals checks equality between component names
func (name ComponentName) Equals(other ComponentName) bool {
	return name.value == other.value
}

// ComponentConfiguration holds component-specific configuration parameters
type ComponentConfiguration struct {
	parameters map[string]interface{}
	namespace  string
	replicas   int
	resources  ResourceRequirements
}

// NewComponentConfiguration creates a new component configuration
func NewComponentConfiguration() ComponentConfiguration {
	return ComponentConfiguration{
		parameters: make(map[string]interface{}),
		namespace:  "cnoc", // Default namespace
		replicas:   1,      // Default replica count
		resources:  NewResourceRequirements(),
	}
}

// NewComponentConfigurationWithParams creates a component configuration with parameters
func NewComponentConfigurationWithParams(parameters map[string]interface{}) ComponentConfiguration {
	config := NewComponentConfiguration()
	if parameters != nil {
		config.parameters = parameters
	}
	return config
}

// SetParameter sets a configuration parameter
func (cc *ComponentConfiguration) SetParameter(key string, value interface{}) error {
	if key == "" {
		return errors.New("parameter key cannot be empty")
	}
	cc.parameters[key] = value
	return nil
}

// GetParameter retrieves a configuration parameter
func (cc ComponentConfiguration) GetParameter(key string) (interface{}, bool) {
	value, exists := cc.parameters[key]
	return value, exists
}

// SetNamespace sets the component namespace
func (cc *ComponentConfiguration) SetNamespace(namespace string) error {
	if namespace == "" {
		return errors.New("namespace cannot be empty")
	}
	
	// Kubernetes namespace validation
	validNamespace := regexp.MustCompile(`^[a-z0-9]([a-z0-9\-]*[a-z0-9])?$`)
	if !validNamespace.MatchString(namespace) {
		return errors.New("namespace must be lowercase alphanumeric with hyphens")
	}
	
	cc.namespace = namespace
	return nil
}

// Namespace returns the component namespace
func (cc ComponentConfiguration) Namespace() string {
	return cc.namespace
}

// SetReplicas sets the number of replicas
func (cc *ComponentConfiguration) SetReplicas(replicas int) error {
	if replicas < 0 {
		return errors.New("replicas cannot be negative")
	}
	if replicas > 100 {
		return errors.New("replicas cannot exceed 100")
	}
	cc.replicas = replicas
	return nil
}

// Replicas returns the number of replicas
func (cc ComponentConfiguration) Replicas() int {
	return cc.replicas
}

// SetResources sets resource requirements
func (cc *ComponentConfiguration) SetResources(resources ResourceRequirements) {
	cc.resources = resources
}

// Resources returns resource requirements
func (cc ComponentConfiguration) Resources() ResourceRequirements {
	return cc.resources
}

// Data returns the configuration parameters as a map
func (cc ComponentConfiguration) Data() map[string]interface{} {
	return cc.parameters
}

// ResourceRequirements represents CPU and memory resource requirements
type ResourceRequirements struct {
	requests ResourceSpec
	limits   ResourceSpec
}

// NewResourceRequirements creates default resource requirements
func NewResourceRequirements() ResourceRequirements {
	return ResourceRequirements{
		requests: ResourceSpec{
			cpu:    "100m",
			memory: "128Mi",
		},
		limits: ResourceSpec{
			cpu:    "500m",
			memory: "512Mi",
		},
	}
}

// NewResourceRequirementsWithParams creates resource requirements with specific parameters
func NewResourceRequirementsWithParams(cpu, memory, storage string, replicas int, namespace string) ResourceRequirements {
	return ResourceRequirements{
		requests: ResourceSpec{
			cpu:    cpu,
			memory: memory,
		},
		limits: ResourceSpec{
			cpu:    cpu,
			memory: memory,
		},
	}
}

// SetRequests sets resource requests
func (rr *ResourceRequirements) SetRequests(cpu, memory string) error {
	if err := validateResourceValue(cpu, "cpu"); err != nil {
		return fmt.Errorf("invalid CPU request: %w", err)
	}
	if err := validateResourceValue(memory, "memory"); err != nil {
		return fmt.Errorf("invalid memory request: %w", err)
	}
	
	rr.requests.cpu = cpu
	rr.requests.memory = memory
	return nil
}

// SetLimits sets resource limits
func (rr *ResourceRequirements) SetLimits(cpu, memory string) error {
	if err := validateResourceValue(cpu, "cpu"); err != nil {
		return fmt.Errorf("invalid CPU limit: %w", err)
	}
	if err := validateResourceValue(memory, "memory"); err != nil {
		return fmt.Errorf("invalid memory limit: %w", err)
	}
	
	rr.limits.cpu = cpu
	rr.limits.memory = memory
	return nil
}

// Requests returns resource requests
func (rr ResourceRequirements) Requests() ResourceSpec {
	return rr.requests
}

// Limits returns resource limits
func (rr ResourceRequirements) Limits() ResourceSpec {
	return rr.limits
}

// CPU returns the CPU request value for compatibility
func (rr ResourceRequirements) CPU() string {
	return rr.requests.cpu
}

// Memory returns the memory request value for compatibility
func (rr ResourceRequirements) Memory() string {
	return rr.requests.memory
}

// Storage returns default storage value for compatibility
func (rr ResourceRequirements) Storage() string {
	return "1Gi" // Default storage value
}

// Replicas returns default replica count for compatibility
func (rr ResourceRequirements) Replicas() int {
	return 1 // Default replica count
}

// Namespace returns default namespace for compatibility
func (rr ResourceRequirements) Namespace() string {
	return "cnoc" // Default namespace
}

// ResourceSpec represents specific resource values
type ResourceSpec struct {
	cpu    string
	memory string
}

// CPU returns the CPU resource value
func (rs ResourceSpec) CPU() string {
	return rs.cpu
}

// Memory returns the memory resource value
func (rs ResourceSpec) Memory() string {
	return rs.memory
}

// ComponentMetadata holds additional component information
type ComponentMetadata struct {
	labels      map[string]string
	annotations map[string]string
	description string
}

// NewComponentMetadata creates new component metadata
func NewComponentMetadata() ComponentMetadata {
	return ComponentMetadata{
		labels:      make(map[string]string),
		annotations: make(map[string]string),
	}
}

// SetLabel sets a label
func (cm *ComponentMetadata) SetLabel(key, value string) error {
	if err := validateLabelKey(key); err != nil {
		return fmt.Errorf("invalid label key: %w", err)
	}
	if err := validateLabelValue(value); err != nil {
		return fmt.Errorf("invalid label value: %w", err)
	}
	cm.labels[key] = value
	return nil
}

// GetLabel retrieves a label
func (cm ComponentMetadata) GetLabel(key string) (string, bool) {
	value, exists := cm.labels[key]
	return value, exists
}

// SetAnnotation sets an annotation
func (cm *ComponentMetadata) SetAnnotation(key, value string) error {
	if err := validateLabelKey(key); err != nil {
		return fmt.Errorf("invalid annotation key: %w", err)
	}
	cm.annotations[key] = value
	return nil
}

// GetAnnotation retrieves an annotation
func (cm ComponentMetadata) GetAnnotation(key string) (string, bool) {
	value, exists := cm.annotations[key]
	return value, exists
}

// SetDescription sets the component description
func (cm *ComponentMetadata) SetDescription(description string) {
	cm.description = description
}

// Description returns the component description
func (cm ComponentMetadata) Description() string {
	return cm.description
}

// Labels returns all labels
func (cm ComponentMetadata) Labels() map[string]string {
	// Return copy to prevent external modification
	labels := make(map[string]string)
	for k, v := range cm.labels {
		labels[k] = v
	}
	return labels
}

// Annotations returns all annotations
func (cm ComponentMetadata) Annotations() map[string]string {
	// Return copy to prevent external modification
	annotations := make(map[string]string)
	for k, v := range cm.annotations {
		annotations[k] = v
	}
	return annotations
}

// NewComponentReference creates a new component reference
func NewComponentReference(
	name ComponentName,
	version shared.Version,
	enabled bool,
) *ComponentReference {
	return &ComponentReference{
		name:          name,
		version:       version,
		enabled:       enabled,
		configuration: NewComponentConfiguration(),
		metadata:      NewComponentMetadata(),
	}
}

// Name returns the component name
func (cr *ComponentReference) Name() ComponentName {
	return cr.name
}

// Version returns the component version
func (cr *ComponentReference) Version() shared.Version {
	return cr.version
}

// IsEnabled returns whether the component is enabled
func (cr *ComponentReference) IsEnabled() bool {
	return cr.enabled
}

// Enabled returns whether the component is enabled (alias for IsEnabled for API compatibility)
func (cr *ComponentReference) Enabled() bool {
	return cr.enabled
}

// Configuration returns the component configuration by value
func (cr *ComponentReference) Configuration() ComponentConfiguration {
	return cr.configuration
}

// ConfigurationPtr returns a pointer to the component configuration for modification
func (cr *ComponentReference) ConfigurationPtr() *ComponentConfiguration {
	return &cr.configuration
}

// Resources returns the resource requirements for the component
func (cr *ComponentReference) Resources() ResourceRequirements {
	return cr.configuration.resources
}

// Enable enables the component
func (cr *ComponentReference) Enable() {
	cr.enabled = true
}

// Disable disables the component
func (cr *ComponentReference) Disable() {
	cr.enabled = false
}

// Metadata returns the component metadata
func (cr *ComponentReference) Metadata() *ComponentMetadata {
	return &cr.metadata
}

// UpdateVersion updates the component version
func (cr *ComponentReference) UpdateVersion(version shared.Version) error {
	// Version compatibility validation would go here
	// For now, accept any valid version
	cr.version = version
	return nil
}

// Clone creates a deep copy of the component reference
func (cr *ComponentReference) Clone() *ComponentReference {
	clone := &ComponentReference{
		name:    cr.name,
		version: cr.version,
		enabled: cr.enabled,
	}
	
	// Deep copy configuration
	clone.configuration = ComponentConfiguration{
		parameters: make(map[string]interface{}),
		namespace:  cr.configuration.namespace,
		replicas:   cr.configuration.replicas,
		resources:  cr.configuration.resources,
	}
	
	for k, v := range cr.configuration.parameters {
		clone.configuration.parameters[k] = v
	}
	
	// Deep copy metadata
	clone.metadata = ComponentMetadata{
		labels:      make(map[string]string),
		annotations: make(map[string]string),
		description: cr.metadata.description,
	}
	
	for k, v := range cr.metadata.labels {
		clone.metadata.labels[k] = v
	}
	
	for k, v := range cr.metadata.annotations {
		clone.metadata.annotations[k] = v
	}
	
	return clone
}

// Validation helper functions

func validateResourceValue(value, resourceType string) error {
	if value == "" {
		return errors.New("resource value cannot be empty")
	}
	
	switch resourceType {
	case "cpu":
		// Validate CPU format (e.g., "100m", "0.1", "1")
		validCPU := regexp.MustCompile(`^(\d+(\.\d+)?|\d+m)$`)
		if !validCPU.MatchString(value) {
			return errors.New("CPU must be in format like '100m', '0.1', or '1'")
		}
	case "memory":
		// Validate memory format (e.g., "128Mi", "1Gi", "500M")
		validMemory := regexp.MustCompile(`^(\d+(\.\d+)?)(Mi|Gi|M|G|Ki|K)?$`)
		if !validMemory.MatchString(value) {
			return errors.New("memory must be in format like '128Mi', '1Gi', or '500M'")
		}
	}
	
	return nil
}

func validateLabelKey(key string) error {
	if key == "" {
		return errors.New("label key cannot be empty")
	}
	
	// Kubernetes label key validation
	if len(key) > 63 {
		return errors.New("label key cannot exceed 63 characters")
	}
	
	validKey := regexp.MustCompile(`^[a-z0-9A-Z]([a-z0-9A-Z\-_.]*[a-z0-9A-Z])?$`)
	if !validKey.MatchString(key) {
		return errors.New("label key must be alphanumeric with hyphens, underscores, or dots")
	}
	
	return nil
}

func validateLabelValue(value string) error {
	// Kubernetes label value validation
	if len(value) > 63 {
		return errors.New("label value cannot exceed 63 characters")
	}
	
	if value != "" {
		validValue := regexp.MustCompile(`^[a-z0-9A-Z]([a-z0-9A-Z\-_.]*[a-z0-9A-Z])?$`)
		if !validValue.MatchString(value) {
			return errors.New("label value must be alphanumeric with hyphens, underscores, or dots")
		}
	}
	
	return nil
}

// Security validation methods

// ValidateSecurityRequirements validates security requirements for the component
func (cr *ComponentReference) ValidateSecurityRequirements() ComponentValidationResult {
	result := ComponentValidationResult{
		Valid:    true,
		Errors:   make([]ComponentValidationError, 0),
		Warnings: make([]ComponentValidationWarning, 0),
	}

	// Component-specific security requirements
	switch cr.name.String() {
	case "cert-manager":
		// cert-manager always requires encryption
		if !cr.IsEncryptionRequired() {
			result.Warnings = append(result.Warnings, ComponentValidationWarning{
				Field:   "encryption",
				Message: "cert-manager should have encryption enabled",
			})
		}
	case "prometheus":
		// Prometheus should have resource limits for security
		if !cr.RequiresResourceLimits() {
			result.Warnings = append(result.Warnings, ComponentValidationWarning{
				Field:   "resources",
				Message: "prometheus should have resource limits configured",
			})
		}
	case "argocd":
		// ArgoCD requires network policies and security context
		if !cr.RequiresNetworkPolicies() {
			result.Errors = append(result.Errors, ComponentValidationError{
				Field:   "networkPolicies",
				Message: "argocd requires network policies for security",
				Code:    "NETWORK_POLICIES_REQUIRED",
			})
			result.Valid = false
		}
		if !cr.RequiresSecurityContext() {
			result.Errors = append(result.Errors, ComponentValidationError{
				Field:   "securityContext",
				Message: "argocd requires security context configuration",
				Code:    "SECURITY_CONTEXT_REQUIRED",
			})
			result.Valid = false
		}
	}

	return result
}

// IsEncryptionRequired returns true if the component requires encryption
func (cr *ComponentReference) IsEncryptionRequired() bool {
	encryptionRequired := map[string]bool{
		"cert-manager": true,
		"argocd":       true,
		"prometheus":   false,
		"grafana":      false,
	}
	
	if required, exists := encryptionRequired[cr.name.String()]; exists {
		return required
	}
	
	return false // Default to not required
}

// RequiresNetworkPolicies returns true if the component requires network policies
func (cr *ComponentReference) RequiresNetworkPolicies() bool {
	networkPolicyRequired := map[string]bool{
		"argocd":     true,
		"prometheus": true,
		"grafana":    false,
	}
	
	if required, exists := networkPolicyRequired[cr.name.String()]; exists {
		return required
	}
	
	return false // Default to not required
}

// RequiresResourceLimits returns true if the component requires resource limits
func (cr *ComponentReference) RequiresResourceLimits() bool {
	resourceLimitsRequired := map[string]bool{
		"prometheus": true,
		"grafana":    true,
		"argocd":     true,
		"cert-manager": true,
	}
	
	if required, exists := resourceLimitsRequired[cr.name.String()]; exists {
		return required
	}
	
	return false // Default to not required
}

// RequiresSecurityContext returns true if the component requires security context
func (cr *ComponentReference) RequiresSecurityContext() bool {
	securityContextRequired := map[string]bool{
		"argocd":       true,
		"prometheus":   true,
		"cert-manager": true,
	}
	
	if required, exists := securityContextRequired[cr.name.String()]; exists {
		return required
	}
	
	return false // Default to not required
}

// ComponentValidationResult represents validation results for component security
type ComponentValidationResult struct {
	Valid    bool
	Errors   []ComponentValidationError
	Warnings []ComponentValidationWarning
}

// ComponentValidationError represents a component validation error
type ComponentValidationError struct {
	Field   string
	Message string
	Code    string
}

// ComponentValidationWarning represents a component validation warning
type ComponentValidationWarning struct {
	Field   string
	Message string
}

// Dependency management methods

// AddDependency adds a dependency to the component
func (cr *ComponentReference) AddDependency(dependency string) error {
	if dependency == "" {
		return fmt.Errorf("dependency cannot be empty")
	}
	
	// Initialize dependencies if not already done
	if cr.configuration.parameters["dependencies"] == nil {
		cr.configuration.parameters["dependencies"] = make([]string, 0)
	}
	
	dependencies := cr.configuration.parameters["dependencies"].([]string)
	
	// Check if dependency already exists
	for _, dep := range dependencies {
		if dep == dependency {
			return fmt.Errorf("dependency '%s' already exists", dependency)
		}
	}
	
	// Add the dependency
	dependencies = append(dependencies, dependency)
	cr.configuration.parameters["dependencies"] = dependencies
	
	return nil
}

// GetDependencies returns the list of dependencies for the component
func (cr *ComponentReference) GetDependencies() []string {
	dependencies, exists := cr.configuration.parameters["dependencies"]
	if !exists {
		return make([]string, 0)
	}
	
	depSlice, ok := dependencies.([]string)
	if !ok {
		return make([]string, 0)
	}
	
	return depSlice
}

// HasDependency checks if the component has a specific dependency
func (cr *ComponentReference) HasDependency(dependency string) bool {
	dependencies := cr.GetDependencies()
	for _, dep := range dependencies {
		if dep == dependency {
			return true
		}
	}
	return false
}