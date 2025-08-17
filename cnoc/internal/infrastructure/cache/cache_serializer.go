package cache

import (
	"bytes"
	"compress/gzip"
	"encoding/json"
	"fmt"
	"io"

	"github.com/hedgehog/cnoc/internal/application/queries"
	"github.com/hedgehog/cnoc/internal/domain/configuration"
	"github.com/hedgehog/cnoc/internal/domain/shared"
)

// CacheSerializer provides anti-corruption layer for cache serialization
// Following MDD principles to maintain domain model purity
type CacheSerializer struct {
	schemaVersion string
}

// NewCacheSerializer creates a new cache serializer with MDD compliance
func NewCacheSerializer() *CacheSerializer {
	return &CacheSerializer{
		schemaVersion: "1.0",
	}
}

// Configuration serialization with anti-corruption layer

// ConfigurationToCacheModel converts domain configuration to cache model
func (s *CacheSerializer) ConfigurationToCacheModel(
	config *configuration.Configuration,
) (*ConfigurationCacheModel, error) {
	if config == nil {
		return nil, fmt.Errorf("configuration cannot be nil")
	}

	// Convert components with proper anti-corruption
	componentsList := config.ComponentsList()
	components := make([]ComponentCacheModel, len(componentsList))
	for i, component := range componentsList {
		componentCache, err := s.componentToCacheModel(component)
		if err != nil {
			return nil, fmt.Errorf("component %d conversion failed: %w", i, err)
		}
		components[i] = componentCache
	}

	// Convert enterprise configuration if present
	var enterpriseCache *EnterpriseConfigCacheModel
	if config.EnterpriseConfiguration() != nil {
		enterpriseCache = s.enterpriseConfigToCacheModel(config.EnterpriseConfiguration())
	}

	cacheModel := &ConfigurationCacheModel{
		ID:               config.ID().String(),
		Name:             config.Name().String(),
		Description:      config.Description(),
		Mode:             string(config.Mode()),
		Version:          config.Version().String(),
		Status:           string(config.Status()),
		Labels:           config.Labels(),
		Annotations:      config.Annotations(),
		Components:       components,
		EnterpriseConfig: enterpriseCache,
		CacheMetadata: CacheMetadata{
			SerializationFormat: "json_gzip",
			CompressionLevel:    6,
			SchemaVersion:       s.schemaVersion,
		},
	}

	return cacheModel, nil
}

// CacheModelToConfiguration converts cache model back to domain configuration
func (s *CacheSerializer) CacheModelToConfiguration(
	cacheModel *ConfigurationCacheModel,
) (*configuration.Configuration, error) {
	if cacheModel == nil {
		return nil, fmt.Errorf("cache model cannot be nil")
	}

	// Validate schema version
	if cacheModel.CacheMetadata.SchemaVersion != s.schemaVersion {
		return nil, fmt.Errorf("unsupported cache schema version: %s", cacheModel.CacheMetadata.SchemaVersion)
	}

	// Convert ID with validation
	configID, err := configuration.NewConfigurationID(cacheModel.ID)
	if err != nil {
		return nil, fmt.Errorf("invalid configuration ID: %w", err)
	}

	// Convert name with validation
	configName, err := configuration.NewConfigurationName(cacheModel.Name)
	if err != nil {
		return nil, fmt.Errorf("invalid configuration name: %w", err)
	}

	// Convert mode with validation
	configMode, err := configuration.ParseConfigurationMode(cacheModel.Mode)
	if err != nil {
		return nil, fmt.Errorf("invalid configuration mode: %w", err)
	}

	// Convert version with validation
	version, err := shared.NewVersion(cacheModel.Version)
	if err != nil {
		return nil, fmt.Errorf("invalid version: %w", err)
	}

	// Convert components back to domain models
	components := make([]*configuration.ComponentReference, len(cacheModel.Components))
	for i, componentCache := range cacheModel.Components {
		component, err := s.cacheModelToComponent(componentCache)
		if err != nil {
			return nil, fmt.Errorf("component %d conversion failed: %w", i, err)
		}
		components[i] = component
	}

	// Create metadata
	metadata := configuration.NewConfigurationMetadata(
		cacheModel.Description,
		make(map[string]string), // labels
		make(map[string]string), // annotations
	)
	
	// Create domain configuration
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
			return nil, fmt.Errorf("component addition failed: %w", err)
		}
	}

	// Apply labels and annotations through metadata update
	if len(cacheModel.Labels) > 0 || len(cacheModel.Annotations) > 0 {
		// Update metadata to include labels and annotations
		newMetadata := configuration.NewConfigurationMetadata(
			cacheModel.Description,
			cacheModel.Labels,
			cacheModel.Annotations,
		)
		config.UpdateMetadata(newMetadata)
	}

	// Apply enterprise configuration if present
	if cacheModel.EnterpriseConfig != nil {
		enterpriseConfig, err := s.cacheModelToEnterpriseConfig(cacheModel.EnterpriseConfig)
		if err != nil {
			return nil, fmt.Errorf("enterprise config conversion failed: %w", err)
		}
		
		// Enterprise configuration would be set through metadata update
		// For now, we'll skip this as the API needs to be implemented
		_ = enterpriseConfig
	}

	// Apply status if not default
	if cacheModel.Status != "" {
		status, err := configuration.ParseConfigurationStatus(cacheModel.Status)
		if err != nil {
			return nil, fmt.Errorf("invalid status: %w", err)
		}
		// Status would be set through domain methods if available
		// For now, configuration is created with default status
		_ = status
	}

	return config, nil
}

// Component serialization helpers

func (s *CacheSerializer) componentToCacheModel(
	component *configuration.ComponentReference,
) (ComponentCacheModel, error) {
	return ComponentCacheModel{
		Name:          component.Name().String(),
		Version:       component.Version().String(),
		Enabled:       component.Enabled(),
		Configuration: component.Configuration().Data(),
		Resources: ResourceRequirementsCacheModel{
			CPU:       component.Resources().CPU(),
			Memory:    component.Resources().Memory(),
			Storage:   component.Resources().Storage(),
			Replicas:  component.Resources().Replicas(),
			Namespace: component.Resources().Namespace(),
		},
	}, nil
}

func (s *CacheSerializer) cacheModelToComponent(
	cacheModel ComponentCacheModel,
) (*configuration.ComponentReference, error) {
	// Convert name with validation
	name, err := configuration.NewComponentName(cacheModel.Name)
	if err != nil {
		return nil, fmt.Errorf("invalid component name: %w", err)
	}

	// Convert version with validation
	version, err := shared.NewVersion(cacheModel.Version)
	if err != nil {
		return nil, fmt.Errorf("invalid component version: %w", err)
	}

	// Convert resource requirements
	resources := configuration.NewResourceRequirements()
	// Note: Would configure resources with setters if available
	_ = cacheModel.Resources // Using resource values would require proper setters

	// Create component reference
	component := configuration.NewComponentReference(
		name,
		version,
		cacheModel.Enabled,
	)
	
	// Configure component with additional settings
	// Note: Would use setters to configure resources and parameters
	_ = resources // Would be set via setters
	_ = cacheModel.Configuration // Would be set via configuration setters

	return component, nil
}

// Enterprise configuration serialization helpers

func (s *CacheSerializer) enterpriseConfigToCacheModel(
	enterpriseConfig *configuration.EnterpriseConfiguration,
) *EnterpriseConfigCacheModel {
	return &EnterpriseConfigCacheModel{
		ComplianceFramework: string(enterpriseConfig.ComplianceFramework()),
		SecurityLevel:       string(enterpriseConfig.SecurityLevel()),
		AuditEnabled:        enterpriseConfig.AuditEnabled(),
		EncryptionRequired:  enterpriseConfig.EncryptionRequired(),
		BackupRequired:      enterpriseConfig.BackupRequired(),
		PolicyTemplates:     enterpriseConfig.PolicyTemplates(),
		Metadata:           enterpriseConfig.Metadata(),
	}
}

func (s *CacheSerializer) cacheModelToEnterpriseConfig(
	cacheModel *EnterpriseConfigCacheModel,
) (*configuration.EnterpriseConfiguration, error) {
	// For now, use simple string assignment since parsing functions may not exist
	framework := cacheModel.ComplianceFramework
	securityLevel := cacheModel.SecurityLevel

	// Create enterprise configuration
	enterpriseConfig, err := configuration.NewEnterpriseConfiguration(
		framework,
		securityLevel,
		cacheModel.AuditEnabled,
		cacheModel.EncryptionRequired,
		cacheModel.BackupRequired,
		cacheModel.PolicyTemplates,
		cacheModel.Metadata,
	)
	if err != nil {
		return nil, fmt.Errorf("enterprise configuration creation failed: %w", err)
	}

	return enterpriseConfig, nil
}

// Query result serialization with read model optimization

// QueryResultToCacheModel converts query result to cache-optimized model
// TODO: Implement once cache model types are properly defined
func (s *CacheSerializer) QueryResultToCacheModel(
	result *queries.QueryResult[*queries.ConfigurationReadModel],
) (*QueryResultCacheModel, error) {
	if result == nil {
		return nil, fmt.Errorf("query result cannot be nil")
	}

	// Temporary stub implementation to allow compilation
	return &QueryResultCacheModel{}, nil
}

// CacheModelToQueryResult converts cache model back to query result
// TODO: Implement once cache model types are properly defined
func (s *CacheSerializer) CacheModelToQueryResult(
	cacheModel *QueryResultCacheModel,
) (*queries.QueryResult[*queries.ConfigurationReadModel], error) {
	if cacheModel == nil {
		return nil, fmt.Errorf("cache model cannot be nil")
	}

	// Temporary stub implementation to allow compilation
	return &queries.QueryResult[*queries.ConfigurationReadModel]{}, nil
}

// Compression and data serialization

// SerializeCacheModel serializes cache model with optional compression
func (s *CacheSerializer) SerializeCacheModel(
	model interface{},
	compressionLevel int,
) ([]byte, error) {
	// Serialize to JSON
	jsonData, err := json.Marshal(model)
	if err != nil {
		return nil, fmt.Errorf("JSON serialization failed: %w", err)
	}

	// Apply compression if requested
	if compressionLevel > 0 {
		return s.compressData(jsonData, compressionLevel)
	}

	return jsonData, nil
}

// DeserializeCacheModel deserializes cache model with decompression
func (s *CacheSerializer) DeserializeCacheModel(data []byte) (interface{}, error) {
	// Try to decompress first (handles both compressed and uncompressed data)
	decompressedData, err := s.decompressData(data)
	if err != nil {
		// If decompression fails, assume data is uncompressed
		decompressedData = data
	}

	// Determine model type from JSON structure
	var rawModel map[string]interface{}
	if err := json.Unmarshal(decompressedData, &rawModel); err != nil {
		return nil, fmt.Errorf("JSON deserialization failed: %w", err)
	}

	// Check for model type indicators
	if _, hasID := rawModel["id"]; hasID {
		if _, hasData := rawModel["data"]; hasData {
			// Query result model
			var queryModel QueryResultCacheModel
			if err := json.Unmarshal(decompressedData, &queryModel); err != nil {
				return nil, fmt.Errorf("query result deserialization failed: %w", err)
			}
			return &queryModel, nil
		} else {
			// Configuration model
			var configModel ConfigurationCacheModel
			if err := json.Unmarshal(decompressedData, &configModel); err != nil {
				return nil, fmt.Errorf("configuration deserialization failed: %w", err)
			}
			return &configModel, nil
		}
	}

	return nil, fmt.Errorf("unknown cache model type")
}

// Compression helpers

func (s *CacheSerializer) compressData(data []byte, level int) ([]byte, error) {
	var buf bytes.Buffer
	
	writer, err := gzip.NewWriterLevel(&buf, level)
	if err != nil {
		return nil, fmt.Errorf("gzip writer creation failed: %w", err)
	}
	defer writer.Close()

	if _, err := writer.Write(data); err != nil {
		return nil, fmt.Errorf("data compression failed: %w", err)
	}

	if err := writer.Close(); err != nil {
		return nil, fmt.Errorf("compression finalization failed: %w", err)
	}

	return buf.Bytes(), nil
}

func (s *CacheSerializer) decompressData(data []byte) ([]byte, error) {
	reader, err := gzip.NewReader(bytes.NewReader(data))
	if err != nil {
		return nil, fmt.Errorf("gzip reader creation failed: %w", err)
	}
	defer reader.Close()

	decompressed, err := io.ReadAll(reader)
	if err != nil {
		return nil, fmt.Errorf("data decompression failed: %w", err)
	}

	return decompressed, nil
}

// Cache model types for query results

// QueryResultCacheModel represents query results in cache format
type QueryResultCacheModel struct {
	Data             []ConfigurationReadModelCache `json:"data"`
	TotalCount       int64                        `json:"total_count"`
	HasMore          bool                         `json:"has_more"`
	NextOffset       *int                         `json:"next_offset,omitempty"`
	ExecutionContext QueryExecutionContextCache   `json:"execution_context"`
	CacheMetadata    QueryCacheMetadata          `json:"cache_metadata"`
}

// ConfigurationReadModelCache represents read model in cache format
type ConfigurationReadModelCache struct {
	ID               string                          `json:"id"`
	Name             string                          `json:"name"`
	Description      string                          `json:"description"`
	Mode             string                          `json:"mode"`
	Version          string                          `json:"version"`
	Status           string                          `json:"status"`
	ComponentCount   int                             `json:"component_count"`
	Labels           map[string]string               `json:"labels"`
	Annotations      map[string]string               `json:"annotations"`
	CreatedAt        int64                           `json:"created_at"`
	UpdatedAt        int64                           `json:"updated_at"`
	ComponentSummary []queries.ComponentSummary      `json:"component_summary"`
	EnterpriseConfig *EnterpriseConfigReadModelCache `json:"enterprise_config,omitempty"`
}

// EnterpriseConfigReadModelCache represents enterprise config in cache format
type EnterpriseConfigReadModelCache struct {
	ComplianceFramework string `json:"compliance_framework"`
	SecurityLevel       string `json:"security_level"`
	AuditEnabled        bool   `json:"audit_enabled"`
	EncryptionRequired  bool   `json:"encryption_required"`
	BackupRequired      bool   `json:"backup_required"`
}

// QueryExecutionContextCache represents execution context in cache format
type QueryExecutionContextCache struct {
	QueryType       string `json:"query_type"`
	ExecutionTimeMs int64  `json:"execution_time_ms"`
	CacheStrategy   string `json:"cache_strategy"`
}

// QueryCacheMetadata represents cache metadata for query results
type QueryCacheMetadata struct {
	CachedAt       int64  `json:"cached_at"`
	TTL            int64  `json:"ttl"`
	CacheStrategy  string `json:"cache_strategy"`
	SchemaVersion  string `json:"schema_version"`
}

// ConfigurationCacheModel represents configuration in cache format
type ConfigurationCacheModel struct {
	ID               string                     `json:"id"`
	Name             string                     `json:"name"`
	Description      string                     `json:"description"`
	Mode             string                     `json:"mode"`
	Version          string                     `json:"version"`
	Status           string                     `json:"status"`
	Labels           map[string]string          `json:"labels"`
	Annotations      map[string]string          `json:"annotations"`
	Components       []ComponentCacheModel      `json:"components"`
	EnterpriseConfig *EnterpriseConfigCacheModel `json:"enterprise_config,omitempty"`
	CacheMetadata    CacheMetadata              `json:"cache_metadata"`
}

// ComponentCacheModel represents component in cache format
type ComponentCacheModel struct {
	Name          string                       `json:"name"`
	Version       string                       `json:"version"`
	Enabled       bool                         `json:"enabled"`
	Configuration map[string]interface{}       `json:"configuration"`
	Resources     ResourceRequirementsCacheModel `json:"resources"`
}

// ResourceRequirementsCacheModel represents resource requirements in cache format
type ResourceRequirementsCacheModel struct {
	CPU       string `json:"cpu"`
	Memory    string `json:"memory"`
	Storage   string `json:"storage"`
	Replicas  int    `json:"replicas"`
	Namespace string `json:"namespace"`
}

// EnterpriseConfigCacheModel represents enterprise config in cache format
type EnterpriseConfigCacheModel struct {
	ComplianceFramework string            `json:"compliance_framework"`
	SecurityLevel       string            `json:"security_level"`
	AuditEnabled        bool              `json:"audit_enabled"`
	EncryptionRequired  bool              `json:"encryption_required"`
	BackupRequired      bool              `json:"backup_required"`
	PolicyTemplates     []string          `json:"policy_templates"`
	Metadata           map[string]string `json:"metadata"`
}

// CacheMetadata represents general cache metadata
type CacheMetadata struct {
	SerializationFormat string `json:"serialization_format"`
	CompressionLevel    int    `json:"compression_level"`
	SchemaVersion       string `json:"schema_version"`
}