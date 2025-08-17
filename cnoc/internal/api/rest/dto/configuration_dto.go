package dto

import (
	"time"

	"github.com/hedgehog/cnoc/internal/domain/configuration"
	"github.com/hedgehog/cnoc/internal/domain/shared"
)

// ConfigurationDTO represents the API data transfer object for configurations
// Following anti-corruption layer pattern to prevent API concerns from leaking into domain
type ConfigurationDTO struct {
	ID                   string                  `json:"id" example:"550e8400-e29b-41d4-a716-446655440000"`
	Name                 string                  `json:"name" example:"production-config" validate:"required,min=1,max=100"`
	Description          string                  `json:"description,omitempty" example:"Production environment configuration"`
	Mode                 string                  `json:"mode" example:"production" validate:"required,oneof=development staging production"`
	Version              string                  `json:"version" example:"1.2.3" validate:"required,semver"`
	Status               string                  `json:"status" example:"active" validate:"oneof=draft active deprecated archived"`
	Labels               map[string]string       `json:"labels,omitempty" example:"environment:production,team:platform"`
	Annotations          map[string]string       `json:"annotations,omitempty"`
	Components           []ComponentDTO          `json:"components,omitempty" validate:"dive"`
	EnterpriseConfig     *EnterpriseConfigDTO    `json:"enterprise_config,omitempty"`
	Metadata             ConfigurationMetadataDTO `json:"metadata"`
	Links                ConfigurationLinksDTO    `json:"_links"`
	CreatedAt            time.Time               `json:"created_at" example:"2025-01-17T10:30:00Z"`
	UpdatedAt            time.Time               `json:"updated_at" example:"2025-01-17T10:30:00Z"`
}

// ComponentDTO represents a component in the API layer
type ComponentDTO struct {
	Name          string                   `json:"name" example:"api-gateway" validate:"required,min=1,max=100"`
	Version       string                   `json:"version" example:"2.1.0" validate:"required,semver"`
	Enabled       bool                     `json:"enabled" example:"true"`
	Configuration map[string]interface{}   `json:"configuration,omitempty"`
	Resources     ResourceRequirementsDTO  `json:"resources" validate:"required"`
	Dependencies  []string                 `json:"dependencies,omitempty" example:"database,cache"`
	Metadata      ComponentMetadataDTO     `json:"metadata,omitempty"`
}

// ResourceRequirementsDTO represents resource requirements in the API layer
type ResourceRequirementsDTO struct {
	CPU       string `json:"cpu" example:"500m" validate:"required,k8s_resource"`
	Memory    string `json:"memory" example:"1Gi" validate:"required,k8s_resource"`
	Storage   string `json:"storage,omitempty" example:"10Gi" validate:"k8s_resource"`
	Replicas  int    `json:"replicas" example:"3" validate:"min=1,max=100"`
	Namespace string `json:"namespace,omitempty" example:"default" validate:"dns1123"`
}

// EnterpriseConfigDTO represents enterprise configuration in the API layer
type EnterpriseConfigDTO struct {
	ComplianceFramework string            `json:"compliance_framework" example:"SOC2" validate:"required,oneof=SOC2 HIPAA PCI-DSS ISO27001 GDPR"`
	SecurityLevel       string            `json:"security_level" example:"high" validate:"required,oneof=low medium high critical"`
	AuditEnabled        bool              `json:"audit_enabled" example:"true"`
	EncryptionRequired  bool              `json:"encryption_required" example:"true"`
	BackupRequired      bool              `json:"backup_required" example:"true"`
	PolicyTemplates     []string          `json:"policy_templates,omitempty" example:"security-baseline,network-isolation"`
	Metadata           map[string]string `json:"metadata,omitempty"`
}

// ConfigurationMetadataDTO provides metadata about the configuration
type ConfigurationMetadataDTO struct {
	ComponentCount       int      `json:"component_count" example:"5"`
	EnabledComponentCount int     `json:"enabled_component_count" example:"4"`
	TotalResourceCPU     string   `json:"total_resource_cpu" example:"2500m"`
	TotalResourceMemory  string   `json:"total_resource_memory" example:"8Gi"`
	TotalReplicas        int      `json:"total_replicas" example:"15"`
	Tags                 []string `json:"tags,omitempty" example:"critical,customer-facing"`
	Owner                string   `json:"owner,omitempty" example:"platform-team"`
	LastModifiedBy       string   `json:"last_modified_by,omitempty" example:"john.doe@example.com"`
}

// ComponentMetadataDTO provides metadata about a component
type ComponentMetadataDTO struct {
	Type        string            `json:"type,omitempty" example:"stateless"`
	Category    string            `json:"category,omitempty" example:"infrastructure"`
	Criticality string            `json:"criticality,omitempty" example:"high"`
	SLA         string            `json:"sla,omitempty" example:"99.99%"`
	Tags        []string          `json:"tags,omitempty"`
	Properties  map[string]string `json:"properties,omitempty"`
}

// ConfigurationLinksDTO provides HATEOAS links for the configuration
type ConfigurationLinksDTO struct {
	Self       LinkDTO   `json:"self"`
	Components LinkDTO   `json:"components,omitempty"`
	Validate   LinkDTO   `json:"validate,omitempty"`
	Deploy     LinkDTO   `json:"deploy,omitempty"`
	History    LinkDTO   `json:"history,omitempty"`
	Related    []LinkDTO `json:"related,omitempty"`
}

// LinkDTO represents a HATEOAS link
type LinkDTO struct {
	Href   string `json:"href" example:"/api/v1/configurations/550e8400-e29b-41d4-a716-446655440000"`
	Method string `json:"method,omitempty" example:"GET"`
	Type   string `json:"type,omitempty" example:"application/json"`
	Title  string `json:"title,omitempty" example:"Configuration Details"`
}

// CreateConfigurationRequestDTO represents a request to create a configuration
type CreateConfigurationRequestDTO struct {
	Name             string                 `json:"name" validate:"required,min=1,max=100"`
	Description      string                 `json:"description,omitempty"`
	Mode             string                 `json:"mode" validate:"required,oneof=development staging production"`
	Version          string                 `json:"version" validate:"required,semver"`
	Labels           map[string]string      `json:"labels,omitempty"`
	Annotations      map[string]string      `json:"annotations,omitempty"`
	Components       []ComponentDTO         `json:"components,omitempty" validate:"dive"`
	EnterpriseConfig *EnterpriseConfigDTO   `json:"enterprise_config,omitempty"`
}

// UpdateConfigurationRequestDTO represents a request to update a configuration
type UpdateConfigurationRequestDTO struct {
	Description      *string                `json:"description,omitempty"`
	Mode             *string                `json:"mode,omitempty" validate:"omitempty,oneof=development staging production"`
	Version          *string                `json:"version,omitempty" validate:"omitempty,semver"`
	Status           *string                `json:"status,omitempty" validate:"omitempty,oneof=draft active deprecated archived"`
	Labels           map[string]string      `json:"labels,omitempty"`
	Annotations      map[string]string      `json:"annotations,omitempty"`
	Components       []ComponentDTO         `json:"components,omitempty" validate:"omitempty,dive"`
	EnterpriseConfig *EnterpriseConfigDTO   `json:"enterprise_config,omitempty"`
}

// ConfigurationListDTO represents a list of configurations
type ConfigurationListDTO struct {
	Items      []ConfigurationSummaryDTO `json:"items"`
	TotalCount int64                     `json:"total_count" example:"100"`
	Page       int                       `json:"page" example:"1"`
	PageSize   int                       `json:"page_size" example:"20"`
	HasMore    bool                      `json:"has_more" example:"true"`
	Links      ListLinksDTO              `json:"_links"`
}

// ConfigurationSummaryDTO represents a summarized configuration for list views
type ConfigurationSummaryDTO struct {
	ID             string                `json:"id"`
	Name           string                `json:"name"`
	Mode           string                `json:"mode"`
	Version        string                `json:"version"`
	Status         string                `json:"status"`
	ComponentCount int                   `json:"component_count"`
	CreatedAt      time.Time             `json:"created_at"`
	UpdatedAt      time.Time             `json:"updated_at"`
	Links          ConfigurationLinksDTO `json:"_links"`
}

// ListLinksDTO provides HATEOAS links for list responses
type ListLinksDTO struct {
	Self  LinkDTO  `json:"self"`
	First *LinkDTO `json:"first,omitempty"`
	Prev  *LinkDTO `json:"prev,omitempty"`
	Next  *LinkDTO `json:"next,omitempty"`
	Last  *LinkDTO `json:"last,omitempty"`
}

// ValidationResultDTO represents validation results
type ValidationResultDTO struct {
	Valid      bool                `json:"valid" example:"false"`
	Errors     []ValidationErrorDTO `json:"errors,omitempty"`
	Warnings   []ValidationWarningDTO `json:"warnings,omitempty"`
	ValidatedAt time.Time          `json:"validated_at"`
}

// ValidationErrorDTO represents a validation error
type ValidationErrorDTO struct {
	Field   string `json:"field" example:"components[0].resources.cpu"`
	Message string `json:"message" example:"CPU resource must be a valid Kubernetes quantity"`
	Code    string `json:"code" example:"INVALID_RESOURCE_FORMAT"`
	Details string `json:"details,omitempty"`
}

// ValidationWarningDTO represents a validation warning
type ValidationWarningDTO struct {
	Field   string `json:"field" example:"components[2].replicas"`
	Message string `json:"message" example:"High replica count may impact resource utilization"`
	Code    string `json:"code" example:"HIGH_REPLICA_COUNT"`
	Details string `json:"details,omitempty"`
}

// ErrorResponseDTO represents an error response
type ErrorResponseDTO struct {
	Error     string                 `json:"error" example:"Bad Request"`
	Message   string                 `json:"message" example:"Invalid configuration data provided"`
	Code      string                 `json:"code" example:"INVALID_REQUEST"`
	Details   map[string]interface{} `json:"details,omitempty"`
	Timestamp time.Time              `json:"timestamp"`
	TraceID   string                 `json:"trace_id,omitempty" example:"550e8400-e29b-41d4-a716-446655440000"`
	Links     ErrorLinksDTO          `json:"_links,omitempty"`
}

// ErrorLinksDTO provides links for error responses
type ErrorLinksDTO struct {
	Documentation LinkDTO `json:"documentation,omitempty"`
	Support       LinkDTO `json:"support,omitempty"`
}

// Mapper interface for DTO conversions with anti-corruption layer
type ConfigurationDTOMapper interface {
	// ToDTO converts domain model to DTO
	ToDTO(config *configuration.Configuration) ConfigurationDTO
	
	// FromCreateRequest converts create request DTO to domain model
	FromCreateRequest(dto CreateConfigurationRequestDTO) (*configuration.Configuration, error)
	
	// FromUpdateRequest converts update request DTO to domain model updates
	FromUpdateRequest(dto UpdateConfigurationRequestDTO, existing *configuration.Configuration) error
	
	// ToSummaryDTO converts domain model to summary DTO
	ToSummaryDTO(config *configuration.Configuration) ConfigurationSummaryDTO
	
	// ToListDTO converts domain models to list DTO
	ToListDTO(configs []*configuration.Configuration, page, pageSize int, totalCount int64) ConfigurationListDTO
}

// ConfigurationDTOMapperImpl implements the DTO mapper with anti-corruption patterns
type ConfigurationDTOMapperImpl struct {
	baseURL string
}

// NewConfigurationDTOMapper creates a new DTO mapper
func NewConfigurationDTOMapper(baseURL string) ConfigurationDTOMapper {
	return &ConfigurationDTOMapperImpl{
		baseURL: baseURL,
	}
}

// ToDTO converts domain configuration to API DTO
func (m *ConfigurationDTOMapperImpl) ToDTO(config *configuration.Configuration) ConfigurationDTO {
	dto := ConfigurationDTO{
		ID:          config.ID().String(),
		Name:        config.Name().String(),
		Description: config.Description(),
		Mode:        string(config.Mode()),
		Version:     config.Version().String(),
		Status:      string(config.Status()),
		Labels:      config.Labels(),
		Annotations: config.Annotations(),
		Components:  m.componentsToDTO(config.ComponentsList()),
		Metadata:    m.metadataToDTO(config),
		Links:       m.generateLinks(config.ID().String()),
		CreatedAt:   config.CreatedAt(),
		UpdatedAt:   config.UpdatedAt(),
	}

	if config.EnterpriseConfiguration() != nil {
		dto.EnterpriseConfig = m.enterpriseConfigToDTO(config.EnterpriseConfiguration())
	}

	return dto
}

// FromCreateRequest converts create request DTO to domain configuration
func (m *ConfigurationDTOMapperImpl) FromCreateRequest(dto CreateConfigurationRequestDTO) (*configuration.Configuration, error) {
	// Convert DTOs to domain value objects through anti-corruption layer
	configID := configuration.GenerateConfigurationID()

	configName, err := configuration.NewConfigurationName(dto.Name)
	if err != nil {
		return nil, err
	}

	configMode, err := configuration.ParseConfigurationMode(dto.Mode)
	if err != nil {
		return nil, err
	}

	version, err := shared.NewVersion(dto.Version)
	if err != nil {
		return nil, err
	}

	// Convert components
	components, err := m.componentsFromDTO(dto.Components)
	if err != nil {
		return nil, err
	}

	// Create configuration metadata
	metadata := configuration.NewConfigurationMetadata(
		dto.Description,
		dto.Labels,
		dto.Annotations,
	)
	
	// Create configuration
	config := configuration.NewConfiguration(
		configID,
		configName,
		version,
		configMode,
		metadata,
	)
	
	// Add components to configuration
	for _, component := range components {
		if err := config.AddComponent(component); err != nil {
			return nil, err
		}
	}

	// Apply enterprise configuration if provided
	if dto.EnterpriseConfig != nil {
		enterpriseConfig, err := m.enterpriseConfigFromDTO(dto.EnterpriseConfig)
		if err != nil {
			return nil, err
		}
		// Enterprise configuration would be set through metadata
		// For now, we'll skip this and implement it properly later
		_ = enterpriseConfig
	}

	return config, nil
}

// FromUpdateRequest converts update request DTO to domain model updates
func (m *ConfigurationDTOMapperImpl) FromUpdateRequest(dto UpdateConfigurationRequestDTO, existing *configuration.Configuration) error {
	// For now, implement a simplified update strategy
	// Updates would be handled through the UpdateMetadata method
	
	// Create new metadata with updates
	currentMeta := existing.Metadata()
	description := existing.Description()
	labels := existing.Labels()
	annotations := existing.Annotations()
	
	// Apply updates if provided
	if dto.Description != nil {
		description = *dto.Description
	}
	
	if dto.Labels != nil {
		for k, v := range dto.Labels {
			labels[k] = v
		}
	}
	
	if dto.Annotations != nil {
		for k, v := range dto.Annotations {
			annotations[k] = v
		}
	}
	
	// Update metadata
	newMetadata := configuration.NewConfigurationMetadata(description, labels, annotations)
	existing.UpdateMetadata(newMetadata)
	
	// Handle component updates
	for _, compUpdate := range dto.ComponentUpdates {
		switch compUpdate.Operation {
		case "add":
			// Add new component
			name, _ := configuration.NewComponentName(compUpdate.Name)
			version, _ := shared.NewVersion(*compUpdate.Version)
			comp := configuration.NewComponentReference(name, version, *compUpdate.Enabled)
			existing.AddComponent(comp)
		case "remove":
			// Remove component
			name, _ := configuration.NewComponentName(compUpdate.Name)
			existing.RemoveComponent(name)
		case "update":
			// Update existing component
			// Implementation would update component configuration
		}
	}
	
	return nil
}

// ToSummaryDTO converts domain model to summary DTO
func (m *ConfigurationDTOMapperImpl) ToSummaryDTO(config *configuration.Configuration) ConfigurationSummaryDTO {
	return ConfigurationSummaryDTO{
		ID:                    config.ID().String(),
		Name:                  config.Name().String(),
		Description:           config.Description(),
		Mode:                  config.Mode().String(),
		Version:               config.Version().String(),
		Status:                config.Status().String(),
		ComponentCount:        config.Components().Size(),
		EnabledComponentCount: m.countEnabledComponents(config),
		CreatedAt:             config.CreatedAt(),
		UpdatedAt:             config.UpdatedAt(),
		Links:                 m.generateLinks(config.ID().String()),
	}
}

// ToListDTO converts domain models to list DTO
func (m *ConfigurationDTOMapperImpl) ToListDTO(configs []*configuration.Configuration, page, pageSize int, totalCount int64) ConfigurationListDTO {
	summaries := make([]ConfigurationSummaryDTO, len(configs))
	for i, config := range configs {
		summaries[i] = m.ToSummaryDTO(config)
	}
	
	return ConfigurationListDTO{
		Configurations: summaries,
		Pagination: PaginationDTO{
			Page:       page,
			PageSize:   pageSize,
			TotalCount: totalCount,
			TotalPages: int((totalCount + int64(pageSize) - 1) / int64(pageSize)),
		},
	}
}

// Helper methods for DTO conversion

func (m *ConfigurationDTOMapperImpl) countEnabledComponents(config *configuration.Configuration) int {
	count := 0
	for _, comp := range config.ComponentsList() {
		if comp.Enabled() {
			count++
		}
	}
	return count
}

func (m *ConfigurationDTOMapperImpl) componentsToDTO(components []*configuration.ComponentReference) []ComponentDTO {
	dtos := make([]ComponentDTO, len(components))
	for i, component := range components {
		dtos[i] = ComponentDTO{
			Name:          component.Name().String(),
			Version:       component.Version().String(),
			Enabled:       component.Enabled(),
			Configuration: component.Configuration().Data(),
			Resources: ResourceRequirementsDTO{
				CPU:       component.Resources().CPU(),
				Memory:    component.Resources().Memory(),
				Storage:   component.Resources().Storage(),
				Replicas:  component.Resources().Replicas(),
				Namespace: component.Resources().Namespace(),
			},
		}
	}
	return dtos
}

func (m *ConfigurationDTOMapperImpl) componentsFromDTO(dtos []ComponentDTO) ([]*configuration.ComponentReference, error) {
	components := make([]*configuration.ComponentReference, len(dtos))
	for i, dto := range dtos {
		name, err := configuration.NewComponentName(dto.Name)
		if err != nil {
			return nil, err
		}

		version, err := shared.NewVersion(dto.Version)
		if err != nil {
			return nil, err
		}

		resources, err := configuration.NewResourceRequirements(
			dto.Resources.CPU,
			dto.Resources.Memory,
			dto.Resources.Storage,
			dto.Resources.Replicas,
			dto.Resources.Namespace,
		)
		if err != nil {
			return nil, err
		}

		component, err := configuration.NewComponentReference(
			name,
			version,
			dto.Enabled,
			configuration.NewComponentConfiguration(dto.Configuration),
			resources,
		)
		if err != nil {
			return nil, err
		}

		components[i] = component
	}
	return components, nil
}

func (m *ConfigurationDTOMapperImpl) enterpriseConfigToDTO(config *configuration.EnterpriseConfiguration) *EnterpriseConfigDTO {
	return &EnterpriseConfigDTO{
		ComplianceFramework: string(config.ComplianceFramework()),
		SecurityLevel:       string(config.SecurityLevel()),
		AuditEnabled:        config.AuditEnabled(),
		EncryptionRequired:  config.EncryptionRequired(),
		BackupRequired:      config.BackupRequired(),
		PolicyTemplates:     config.PolicyTemplates(),
		Metadata:           config.Metadata(),
	}
}

func (m *ConfigurationDTOMapperImpl) enterpriseConfigFromDTO(dto *EnterpriseConfigDTO) (*configuration.EnterpriseConfiguration, error) {
	framework, err := configuration.ParseComplianceFramework(dto.ComplianceFramework)
	if err != nil {
		return nil, err
	}

	securityLevel, err := configuration.ParseSecurityLevel(dto.SecurityLevel)
	if err != nil {
		return nil, err
	}

	return configuration.NewEnterpriseConfiguration(
		framework,
		securityLevel,
		dto.AuditEnabled,
		dto.EncryptionRequired,
		dto.BackupRequired,
		dto.PolicyTemplates,
		dto.Metadata,
	)
}

func (m *ConfigurationDTOMapperImpl) metadataToDTO(config *configuration.Configuration) ConfigurationMetadataDTO {
	enabledCount := 0
	totalCPU := 0
	totalMemory := 0
	totalReplicas := 0

	for _, component := range config.Components() {
		if component.Enabled() {
			enabledCount++
		}
		totalReplicas += component.Resources().Replicas()
		// In production, parse and sum actual resource values
	}

	return ConfigurationMetadataDTO{
		ComponentCount:        len(config.Components()),
		EnabledComponentCount: enabledCount,
		TotalResourceCPU:      "calculated", // Would calculate actual sum
		TotalResourceMemory:   "calculated", // Would calculate actual sum
		TotalReplicas:         totalReplicas,
	}
}

func (m *ConfigurationDTOMapperImpl) generateLinks(configID string) ConfigurationLinksDTO {
	return ConfigurationLinksDTO{
		Self: LinkDTO{
			Href:   m.baseURL + "/api/v1/configurations/" + configID,
			Method: "GET",
			Type:   "application/json",
		},
		Components: LinkDTO{
			Href:   m.baseURL + "/api/v1/configurations/" + configID + "/components",
			Method: "GET",
			Type:   "application/json",
		},
		Validate: LinkDTO{
			Href:   m.baseURL + "/api/v1/configurations/" + configID + "/validate",
			Method: "POST",
			Type:   "application/json",
		},
		Deploy: LinkDTO{
			Href:   m.baseURL + "/api/v1/configurations/" + configID + "/deploy",
			Method: "POST",
			Type:   "application/json",
		},
		History: LinkDTO{
			Href:   m.baseURL + "/api/v1/configurations/" + configID + "/history",
			Method: "GET",
			Type:   "application/json",
		},
	}
}

// Additional helper methods would be implemented here...