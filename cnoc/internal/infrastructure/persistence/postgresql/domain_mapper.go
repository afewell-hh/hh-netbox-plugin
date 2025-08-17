package postgresql

import (
	"encoding/json"
	"fmt"
	"time"

	"github.com/hedgehog/cnoc/internal/domain/configuration"
	"github.com/hedgehog/cnoc/internal/domain/shared"
)

// ConfigurationDomainMapper provides anti-corruption layer between domain and persistence models
// Following hexagonal architecture principles to prevent domain model contamination
type ConfigurationDomainMapper struct {
	componentMapper    *ComponentDomainMapper
	enterpriseMapper   *EnterpriseConfigDomainMapper
	metadataMapper     *MetadataMapper
}

// NewConfigurationDomainMapper creates a new configuration domain mapper
func NewConfigurationDomainMapper() *ConfigurationDomainMapper {
	return &ConfigurationDomainMapper{
		componentMapper:  NewComponentDomainMapper(),
		enterpriseMapper: NewEnterpriseConfigDomainMapper(),
		metadataMapper:   NewMetadataMapper(),
	}
}

// ToDomainModel converts persistence model to domain model with strict anti-corruption
func (m *ConfigurationDomainMapper) ToDomainModel(
	persistenceModel ConfigurationPersistenceModel,
) (*configuration.Configuration, error) {
	// Convert basic fields with domain validation
	configID, err := configuration.NewConfigurationID(persistenceModel.ID)
	if err != nil {
		return nil, m.wrapMappingError("id_conversion", err)
	}

	configName, err := configuration.NewConfigurationName(persistenceModel.Name)
	if err != nil {
		return nil, m.wrapMappingError("name_conversion", err)
	}

	configMode, err := configuration.ParseConfigurationMode(persistenceModel.Mode)
	if err != nil {
		return nil, m.wrapMappingError("mode_conversion", err)
	}

	version, err := shared.NewVersion(persistenceModel.Version)
	if err != nil {
		return nil, m.wrapMappingError("version_conversion", err)
	}

	// Convert components through anti-corruption layer
	components := make([]*configuration.ComponentReference, len(persistenceModel.Components))
	for i, componentModel := range persistenceModel.Components {
		component, err := m.componentMapper.ToDomainModel(componentModel)
		if err != nil {
			return nil, m.wrapMappingError(fmt.Sprintf("component_%d_conversion", i), err)
		}
		components[i] = component
	}

	// Create domain configuration
	config, err := configuration.NewConfiguration(
		configID,
		configName,
		configMode,
		version,
		persistenceModel.Description,
		components,
	)
	if err != nil {
		return nil, m.wrapMappingError("configuration_creation", err)
	}

	// Apply labels
	labels, err := m.metadataMapper.ParseLabels(persistenceModel.Labels)
	if err != nil {
		return nil, m.wrapMappingError("labels_parsing", err)
	}
	for key, value := range labels {
		if err := config.AddLabel(key, value); err != nil {
			return nil, m.wrapMappingError("label_application", err)
		}
	}

	// Apply annotations
	annotations, err := m.metadataMapper.ParseAnnotations(persistenceModel.Annotations)
	if err != nil {
		return nil, m.wrapMappingError("annotations_parsing", err)
	}
	for key, value := range annotations {
		if err := config.AddAnnotation(key, value); err != nil {
			return nil, m.wrapMappingError("annotation_application", err)
		}
	}

	// Apply enterprise configuration if present
	if persistenceModel.EnterpriseConfig != nil {
		enterpriseConfig, err := m.enterpriseMapper.ToDomainModel(*persistenceModel.EnterpriseConfig)
		if err != nil {
			return nil, m.wrapMappingError("enterprise_config_conversion", err)
		}
		
		if err := config.SetEnterpriseConfiguration(enterpriseConfig); err != nil {
			return nil, m.wrapMappingError("enterprise_config_application", err)
		}
	}

	// Apply status if not default
	if persistenceModel.Status != "" {
		status, err := configuration.ParseConfigurationStatus(persistenceModel.Status)
		if err != nil {
			return nil, m.wrapMappingError("status_conversion", err)
		}
		config.SetStatus(status)
	}

	return config, nil
}

// ToDatabaseModel converts domain model to persistence model with data integrity protection
func (m *ConfigurationDomainMapper) ToDatabaseModel(
	domainModel *configuration.Configuration,
) (ConfigurationPersistenceModel, error) {
	// Convert basic fields
	persistenceModel := ConfigurationPersistenceModel{
		ID:                   domainModel.ID().String(),
		Name:                 domainModel.Name().String(),
		Description:          domainModel.Description(),
		Mode:                 string(domainModel.Mode()),
		Version:              domainModel.Version().String(),
		Status:               string(domainModel.Status()),
		CachedComponentCount: len(domainModel.Components()),
		CreatedAt:            time.Now(),
		UpdatedAt:            time.Now(),
	}

	// Serialize labels
	labelsJSON, err := m.metadataMapper.SerializeLabels(domainModel.Labels())
	if err != nil {
		return persistenceModel, m.wrapMappingError("labels_serialization", err)
	}
	persistenceModel.Labels = labelsJSON

	// Serialize annotations
	annotationsJSON, err := m.metadataMapper.SerializeAnnotations(domainModel.Annotations())
	if err != nil {
		return persistenceModel, m.wrapMappingError("annotations_serialization", err)
	}
	persistenceModel.Annotations = annotationsJSON

	// Convert components
	components := make([]ComponentPersistenceModel, len(domainModel.Components()))
	for i, component := range domainModel.Components() {
		componentModel, err := m.componentMapper.ToDatabaseModel(component, persistenceModel.ID)
		if err != nil {
			return persistenceModel, m.wrapMappingError(fmt.Sprintf("component_%d_conversion", i), err)
		}
		components[i] = componentModel
	}
	persistenceModel.Components = components

	// Convert enterprise configuration if present
	if domainModel.EnterpriseConfiguration() != nil {
		enterpriseModel, err := m.enterpriseMapper.ToDatabaseModel(domainModel.EnterpriseConfiguration())
		if err != nil {
			return persistenceModel, m.wrapMappingError("enterprise_config_conversion", err)
		}
		persistenceModel.EnterpriseConfig = &enterpriseModel
	}

	// Serialize metadata
	metadata, err := m.metadataMapper.SerializeMetadata(map[string]interface{}{
		"cached_component_count": persistenceModel.CachedComponentCount,
		"last_modified_by":      "system", // This would come from context
		"schema_version":        "1.0",
	})
	if err != nil {
		return persistenceModel, m.wrapMappingError("metadata_serialization", err)
	}
	persistenceModel.Metadata = metadata

	return persistenceModel, nil
}

func (m *ConfigurationDomainMapper) wrapMappingError(operation string, err error) error {
	return fmt.Errorf("configuration mapping %s failed: %w", operation, err)
}

// ComponentDomainMapper handles component mapping with anti-corruption patterns
type ComponentDomainMapper struct {
	resourceMapper *ResourceRequirementsMapper
}

// NewComponentDomainMapper creates a new component domain mapper
func NewComponentDomainMapper() *ComponentDomainMapper {
	return &ComponentDomainMapper{
		resourceMapper: NewResourceRequirementsMapper(),
	}
}

// ToDomainModel converts component persistence model to domain model
func (m *ComponentDomainMapper) ToDomainModel(
	persistenceModel ComponentPersistenceModel,
) (*configuration.ComponentReference, error) {
	// Convert name with domain validation
	name, err := configuration.NewComponentName(persistenceModel.Name)
	if err != nil {
		return nil, fmt.Errorf("component name conversion failed: %w", err)
	}

	// Convert version
	version, err := shared.NewVersion(persistenceModel.Version)
	if err != nil {
		return nil, fmt.Errorf("component version conversion failed: %w", err)
	}

	// Parse configuration data
	var configData map[string]interface{}
	if persistenceModel.ConfigurationData != "" {
		if err := json.Unmarshal([]byte(persistenceModel.ConfigurationData), &configData); err != nil {
			return nil, fmt.Errorf("component configuration parsing failed: %w", err)
		}
	}

	// Convert resource requirements
	resources, err := m.resourceMapper.ToDomainModel(ResourceRequirementsPersistenceModel{
		CPU:     persistenceModel.CPURequirement,
		Memory:  persistenceModel.MemoryRequirement,
		Storage: persistenceModel.StorageRequirement,
		Replicas: persistenceModel.Replicas,
		Namespace: persistenceModel.Namespace,
	})
	if err != nil {
		return nil, fmt.Errorf("resource requirements conversion failed: %w", err)
	}

	// Create component reference
	component, err := configuration.NewComponentReference(
		name,
		version,
		persistenceModel.Enabled,
		configuration.NewComponentConfiguration(configData),
		resources,
	)
	if err != nil {
		return nil, fmt.Errorf("component reference creation failed: %w", err)
	}

	return component, nil
}

// ToDatabaseModel converts domain component to persistence model
func (m *ComponentDomainMapper) ToDatabaseModel(
	domainModel *configuration.ComponentReference,
	configurationID string,
) (ComponentPersistenceModel, error) {
	// Serialize configuration data
	configData, err := json.Marshal(domainModel.Configuration().Data())
	if err != nil {
		return ComponentPersistenceModel{}, fmt.Errorf("configuration serialization failed: %w", err)
	}

	// Convert resource requirements
	resourceModel, err := m.resourceMapper.ToDatabaseModel(domainModel.Resources())
	if err != nil {
		return ComponentPersistenceModel{}, fmt.Errorf("resource requirements conversion failed: %w", err)
	}

	return ComponentPersistenceModel{
		ID:                   generateComponentID(configurationID, domainModel.Name().String()),
		Name:                 domainModel.Name().String(),
		Version:              domainModel.Version().String(),
		Enabled:              domainModel.Enabled(),
		ConfigurationData:    string(configData),
		CPURequirement:       resourceModel.CPU,
		MemoryRequirement:    resourceModel.Memory,
		StorageRequirement:   resourceModel.Storage,
		Replicas:             resourceModel.Replicas,
		Namespace:            resourceModel.Namespace,
		Dependencies:         []string{}, // This would come from component configuration
		CreatedAt:            time.Now(),
	}, nil
}

// EnterpriseConfigDomainMapper handles enterprise configuration mapping
type EnterpriseConfigDomainMapper struct {
	metadataMapper *MetadataMapper
}

// NewEnterpriseConfigDomainMapper creates a new enterprise config domain mapper
func NewEnterpriseConfigDomainMapper() *EnterpriseConfigDomainMapper {
	return &EnterpriseConfigDomainMapper{
		metadataMapper: NewMetadataMapper(),
	}
}

// ToDomainModel converts enterprise config persistence model to domain model
func (m *EnterpriseConfigDomainMapper) ToDomainModel(
	persistenceModel EnterpriseConfigPersistenceModel,
) (*configuration.EnterpriseConfiguration, error) {
	// Convert compliance framework
	framework, err := configuration.ParseComplianceFramework(persistenceModel.ComplianceFramework)
	if err != nil {
		return nil, fmt.Errorf("compliance framework conversion failed: %w", err)
	}

	// Convert security level
	securityLevel, err := configuration.ParseSecurityLevel(persistenceModel.SecurityLevel)
	if err != nil {
		return nil, fmt.Errorf("security level conversion failed: %w", err)
	}

	// Parse metadata
	metadata, err := m.metadataMapper.ParseMetadata(persistenceModel.Metadata)
	if err != nil {
		return nil, fmt.Errorf("enterprise metadata parsing failed: %w", err)
	}

	// Create enterprise configuration
	enterpriseConfig, err := configuration.NewEnterpriseConfiguration(
		framework,
		securityLevel,
		persistenceModel.AuditEnabled,
		persistenceModel.EncryptionRequired,
		persistenceModel.BackupRequired,
		persistenceModel.PolicyTemplates,
		metadata,
	)
	if err != nil {
		return nil, fmt.Errorf("enterprise configuration creation failed: %w", err)
	}

	return enterpriseConfig, nil
}

// ToDatabaseModel converts domain enterprise config to persistence model
func (m *EnterpriseConfigDomainMapper) ToDatabaseModel(
	domainModel *configuration.EnterpriseConfiguration,
) (EnterpriseConfigPersistenceModel, error) {
	// Serialize metadata
	metadataJSON, err := m.metadataMapper.SerializeMetadata(domainModel.Metadata())
	if err != nil {
		return EnterpriseConfigPersistenceModel{}, fmt.Errorf("metadata serialization failed: %w", err)
	}

	return EnterpriseConfigPersistenceModel{
		ComplianceFramework: string(domainModel.ComplianceFramework()),
		SecurityLevel:       string(domainModel.SecurityLevel()),
		AuditEnabled:        domainModel.AuditEnabled(),
		EncryptionRequired:  domainModel.EncryptionRequired(),
		BackupRequired:      domainModel.BackupRequired(),
		PolicyTemplates:     domainModel.PolicyTemplates(),
		Metadata:            metadataJSON,
		CreatedAt:           time.Now(),
		UpdatedAt:           time.Now(),
	}, nil
}

// ResourceRequirementsMapper handles resource requirements mapping
type ResourceRequirementsMapper struct{}

// NewResourceRequirementsMapper creates a new resource requirements mapper
func NewResourceRequirementsMapper() *ResourceRequirementsMapper {
	return &ResourceRequirementsMapper{}
}

// ResourceRequirementsPersistenceModel represents resource requirements in persistence
type ResourceRequirementsPersistenceModel struct {
	CPU       string `json:"cpu"`
	Memory    string `json:"memory"`
	Storage   string `json:"storage"`
	Replicas  int    `json:"replicas"`
	Namespace string `json:"namespace"`
}

// ToDomainModel converts resource requirements persistence model to domain model
func (m *ResourceRequirementsMapper) ToDomainModel(
	persistenceModel ResourceRequirementsPersistenceModel,
) (*configuration.ResourceRequirements, error) {
	return configuration.NewResourceRequirements(
		persistenceModel.CPU,
		persistenceModel.Memory,
		persistenceModel.Storage,
		persistenceModel.Replicas,
		persistenceModel.Namespace,
	)
}

// ToDatabaseModel converts domain resource requirements to persistence model
func (m *ResourceRequirementsMapper) ToDatabaseModel(
	domainModel *configuration.ResourceRequirements,
) (ResourceRequirementsPersistenceModel, error) {
	return ResourceRequirementsPersistenceModel{
		CPU:       domainModel.CPU(),
		Memory:    domainModel.Memory(),
		Storage:   domainModel.Storage(),
		Replicas:  domainModel.Replicas(),
		Namespace: domainModel.Namespace(),
	}, nil
}

// MetadataMapper handles metadata serialization/deserialization
type MetadataMapper struct{}

// NewMetadataMapper creates a new metadata mapper
func NewMetadataMapper() *MetadataMapper {
	return &MetadataMapper{}
}

// ParseLabels parses labels from JSON string
func (m *MetadataMapper) ParseLabels(labelsJSON string) (map[string]string, error) {
	if labelsJSON == "" {
		return make(map[string]string), nil
	}

	var labels map[string]string
	if err := json.Unmarshal([]byte(labelsJSON), &labels); err != nil {
		return nil, fmt.Errorf("labels parsing failed: %w", err)
	}

	return labels, nil
}

// SerializeLabels serializes labels to JSON string
func (m *MetadataMapper) SerializeLabels(labels map[string]string) (string, error) {
	if len(labels) == 0 {
		return "{}", nil
	}

	labelsJSON, err := json.Marshal(labels)
	if err != nil {
		return "", fmt.Errorf("labels serialization failed: %w", err)
	}

	return string(labelsJSON), nil
}

// ParseAnnotations parses annotations from JSON string
func (m *MetadataMapper) ParseAnnotations(annotationsJSON string) (map[string]string, error) {
	if annotationsJSON == "" {
		return make(map[string]string), nil
	}

	var annotations map[string]string
	if err := json.Unmarshal([]byte(annotationsJSON), &annotations); err != nil {
		return nil, fmt.Errorf("annotations parsing failed: %w", err)
	}

	return annotations, nil
}

// SerializeAnnotations serializes annotations to JSON string
func (m *MetadataMapper) SerializeAnnotations(annotations map[string]string) (string, error) {
	if len(annotations) == 0 {
		return "{}", nil
	}

	annotationsJSON, err := json.Marshal(annotations)
	if err != nil {
		return "", fmt.Errorf("annotations serialization failed: %w", err)
	}

	return string(annotationsJSON), nil
}

// ParseMetadata parses metadata from JSON string
func (m *MetadataMapper) ParseMetadata(metadataJSON string) (map[string]string, error) {
	if metadataJSON == "" {
		return make(map[string]string), nil
	}

	var metadata map[string]string
	if err := json.Unmarshal([]byte(metadataJSON), &metadata); err != nil {
		return nil, fmt.Errorf("metadata parsing failed: %w", err)
	}

	return metadata, nil
}

// SerializeMetadata serializes metadata to JSON string
func (m *MetadataMapper) SerializeMetadata(metadata map[string]interface{}) (string, error) {
	if len(metadata) == 0 {
		return "{}", nil
	}

	metadataJSON, err := json.Marshal(metadata)
	if err != nil {
		return "", fmt.Errorf("metadata serialization failed: %w", err)
	}

	return string(metadataJSON), nil
}

// Helper functions

func generateComponentID(configurationID, componentName string) string {
	return fmt.Sprintf("%s_%s", configurationID, componentName)
}

// Validation helpers for anti-corruption layer

func validatePersistenceModel(model ConfigurationPersistenceModel) error {
	if model.ID == "" {
		return fmt.Errorf("configuration ID cannot be empty")
	}
	if model.Name == "" {
		return fmt.Errorf("configuration name cannot be empty")
	}
	if model.Mode == "" {
		return fmt.Errorf("configuration mode cannot be empty")
	}
	if model.Version == "" {
		return fmt.Errorf("configuration version cannot be empty")
	}
	return nil
}

func validateDomainModel(model *configuration.Configuration) error {
	if model == nil {
		return fmt.Errorf("configuration cannot be nil")
	}
	if model.ID().String() == "" {
		return fmt.Errorf("configuration ID cannot be empty")
	}
	if model.Name().String() == "" {
		return fmt.Errorf("configuration name cannot be empty")
	}
	return nil
}

// Anti-corruption layer error types

type MappingError struct {
	Operation string
	Cause     error
	Context   map[string]interface{}
}

func (e *MappingError) Error() string {
	return fmt.Sprintf("mapping error in %s: %v", e.Operation, e.Cause)
}

func (e *MappingError) Unwrap() error {
	return e.Cause
}

func NewMappingError(operation string, cause error) *MappingError {
	return &MappingError{
		Operation: operation,
		Cause:     cause,
		Context:   make(map[string]interface{}),
	}
}

func (e *MappingError) WithContext(key string, value interface{}) *MappingError {
	e.Context[key] = value
	return e
}