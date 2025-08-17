package cache

import (
	"context"
	"encoding/json"
	"fmt"
	"time"

	"github.com/go-redis/redis/v8"
	
	"github.com/hedgehog/cnoc/internal/application/queries"
	"github.com/hedgehog/cnoc/internal/domain/configuration"
	"github.com/hedgehog/cnoc/internal/domain/shared"
)

// RedisCacheAdapter implements caching with anti-corruption layer patterns
// Following hexagonal architecture to prevent domain model contamination
type RedisCacheAdapter struct {
	client           *redis.Client
	defaultTTL       time.Duration
	keyPrefix        string
	serializer       *CacheSerializer
	metricsCollector *CacheMetricsCollector
	compressionLevel int
}

// NewRedisCacheAdapter creates a new Redis cache adapter with MDD compliance
func NewRedisCacheAdapter(
	client *redis.Client,
	defaultTTL time.Duration,
	keyPrefix string,
	metricsCollector *CacheMetricsCollector,
) *RedisCacheAdapter {
	return &RedisCacheAdapter{
		client:           client,
		defaultTTL:       defaultTTL,
		keyPrefix:        keyPrefix,
		serializer:       NewCacheSerializer(),
		metricsCollector: metricsCollector,
		compressionLevel: 6, // Optimal compression level for performance
	}
}

// Configuration caching with domain isolation

// CacheConfiguration stores configuration in cache with proper anti-corruption
func (c *RedisCacheAdapter) CacheConfiguration(
	ctx context.Context,
	config *configuration.Configuration,
	ttl time.Duration,
) error {
	startTime := time.Now()
	defer c.recordMetrics("cache_configuration", startTime, nil)

	if config == nil {
		return fmt.Errorf("configuration cannot be nil")
	}

	// Convert domain model to cache model through anti-corruption layer
	cacheModel, err := c.serializer.ConfigurationToCacheModel(config)
	if err != nil {
		return c.wrapError("domain_serialization_failed", err)
	}

	// Generate cache key with proper namespacing
	key := c.generateKey("config", config.ID().String())

	// Serialize to JSON with compression
	data, err := c.serializer.SerializeCacheModel(cacheModel, c.compressionLevel)
	if err != nil {
		return c.wrapError("cache_serialization_failed", err)
	}

	// Set cache with TTL
	if ttl == 0 {
		ttl = c.defaultTTL
	}

	err = c.client.Set(ctx, key, data, ttl).Err()
	if err != nil {
		return c.wrapError("redis_set_failed", err)
	}

	// Cache metadata for efficient querying
	metadataKey := c.generateKey("config_meta", config.ID().String())
	metadata := ConfigurationCacheMetadata{
		ID:            config.ID().String(),
		Name:          config.Name().String(),
		Mode:          string(config.Mode()),
		Version:       config.Version().String(),
		Status:        string(config.Status()),
		ComponentCount: len(config.Components()),
		CachedAt:      time.Now().Unix(),
		TTL:           int64(ttl.Seconds()),
	}

	metadataJSON, _ := json.Marshal(metadata)
	c.client.Set(ctx, metadataKey, metadataJSON, ttl)

	return nil
}

// GetConfiguration retrieves configuration from cache with domain conversion
func (c *RedisCacheAdapter) GetConfiguration(
	ctx context.Context,
	id configuration.ConfigurationID,
) (*configuration.Configuration, error) {
	startTime := time.Now()
	defer c.recordMetrics("get_configuration", startTime, nil)

	key := c.generateKey("config", id.String())

	// Get from Redis
	data, err := c.client.Get(ctx, key).Result()
	if err != nil {
		if err == redis.Nil {
			c.metricsCollector.RecordCacheMiss("configuration")
			return nil, ErrCacheNotFound
		}
		return nil, c.wrapError("redis_get_failed", err)
	}

	c.metricsCollector.RecordCacheHit("configuration")

	// Deserialize cache model
	cacheModel, err := c.serializer.DeserializeCacheModel([]byte(data))
	if err != nil {
		return nil, c.wrapError("cache_deserialization_failed", err)
	}

	// Convert cache model back to domain model through anti-corruption layer
	domainModel, err := c.serializer.CacheModelToConfiguration(cacheModel)
	if err != nil {
		return nil, c.wrapError("domain_deserialization_failed", err)
	}

	return domainModel, nil
}

// InvalidateConfiguration removes configuration from cache
func (c *RedisCacheAdapter) InvalidateConfiguration(
	ctx context.Context,
	id configuration.ConfigurationID,
) error {
	startTime := time.Now()
	defer c.recordMetrics("invalidate_configuration", startTime, nil)

	// Remove both main cache and metadata
	keys := []string{
		c.generateKey("config", id.String()),
		c.generateKey("config_meta", id.String()),
	}

	pipe := c.client.Pipeline()
	for _, key := range keys {
		pipe.Del(ctx, key)
	}

	_, err := pipe.Exec(ctx)
	if err != nil {
		return c.wrapError("cache_invalidation_failed", err)
	}

	return nil
}

// Query result caching with read model optimization

// CacheQueryResult stores query results with sophisticated caching strategies
func (c *RedisCacheAdapter) CacheQueryResult(
	ctx context.Context,
	queryKey string,
	result *queries.QueryResult[*queries.ConfigurationReadModel],
	ttl time.Duration,
) error {
	startTime := time.Now()
	defer c.recordMetrics("cache_query_result", startTime, nil)

	if result == nil {
		return fmt.Errorf("query result cannot be nil")
	}

	// Convert to cache-optimized read model
	cacheResult, err := c.serializer.QueryResultToCacheModel(result)
	if err != nil {
		return c.wrapError("query_serialization_failed", err)
	}

	// Generate cache key with query fingerprint
	key := c.generateKey("query", c.generateQueryHash(queryKey))

	// Serialize with compression for large result sets
	data, err := c.serializer.SerializeCacheModel(cacheResult, c.compressionLevel)
	if err != nil {
		return c.wrapError("query_cache_serialization_failed", err)
	}

	// Cache with shorter TTL for query results (they change more frequently)
	if ttl == 0 {
		ttl = c.defaultTTL / 2 // Query results have shorter TTL
	}

	err = c.client.Set(ctx, key, data, ttl).Err()
	if err != nil {
		return c.wrapError("query_cache_set_failed", err)
	}

	// Cache query metadata for cache management
	c.cacheQueryMetadata(ctx, queryKey, len(result.Data), ttl)

	return nil
}

// GetQueryResult retrieves cached query results
func (c *RedisCacheAdapter) GetQueryResult(
	ctx context.Context,
	queryKey string,
) (*queries.QueryResult[*queries.ConfigurationReadModel], error) {
	startTime := time.Now()
	defer c.recordMetrics("get_query_result", startTime, nil)

	key := c.generateKey("query", c.generateQueryHash(queryKey))

	data, err := c.client.Get(ctx, key).Result()
	if err != nil {
		if err == redis.Nil {
			c.metricsCollector.RecordCacheMiss("query_result")
			return nil, ErrCacheNotFound
		}
		return nil, c.wrapError("query_cache_get_failed", err)
	}

	c.metricsCollector.RecordCacheHit("query_result")

	// Deserialize cache model
	cacheResult, err := c.serializer.DeserializeCacheModel([]byte(data))
	if err != nil {
		return nil, c.wrapError("query_cache_deserialization_failed", err)
	}

	// Convert back to query result
	queryResult, err := c.serializer.CacheModelToQueryResult(cacheResult)
	if err != nil {
		return nil, c.wrapError("query_domain_deserialization_failed", err)
	}

	return queryResult, nil
}

// Bulk operations for performance optimization

// CacheMultipleConfigurations caches multiple configurations efficiently
func (c *RedisCacheAdapter) CacheMultipleConfigurations(
	ctx context.Context,
	configs []*configuration.Configuration,
	ttl time.Duration,
) error {
	if len(configs) == 0 {
		return nil
	}

	startTime := time.Now()
	defer c.recordMetrics("cache_multiple_configurations", startTime, nil)

	pipe := c.client.Pipeline()

	for _, config := range configs {
		// Convert to cache model
		cacheModel, err := c.serializer.ConfigurationToCacheModel(config)
		if err != nil {
			continue // Skip invalid configurations
		}

		// Serialize
		data, err := c.serializer.SerializeCacheModel(cacheModel, c.compressionLevel)
		if err != nil {
			continue
		}

		// Add to pipeline
		key := c.generateKey("config", config.ID().String())
		if ttl == 0 {
			ttl = c.defaultTTL
		}
		pipe.Set(ctx, key, data, ttl)

		// Cache metadata
		metadataKey := c.generateKey("config_meta", config.ID().String())
		metadata := ConfigurationCacheMetadata{
			ID:            config.ID().String(),
			Name:          config.Name().String(),
			Mode:          string(config.Mode()),
			Version:       config.Version().String(),
			Status:        string(config.Status()),
			ComponentCount: len(config.Components()),
			CachedAt:      time.Now().Unix(),
			TTL:           int64(ttl.Seconds()),
		}
		metadataJSON, _ := json.Marshal(metadata)
		pipe.Set(ctx, metadataKey, metadataJSON, ttl)
	}

	_, err := pipe.Exec(ctx)
	if err != nil {
		return c.wrapError("bulk_cache_failed", err)
	}

	return nil
}

// InvalidateByPattern removes cache entries matching pattern
func (c *RedisCacheAdapter) InvalidateByPattern(
	ctx context.Context,
	pattern string,
) error {
	startTime := time.Now()
	defer c.recordMetrics("invalidate_by_pattern", startTime, nil)

	// Find keys matching pattern
	searchPattern := c.generateKey(pattern, "*")
	keys, err := c.client.Keys(ctx, searchPattern).Result()
	if err != nil {
		return c.wrapError("pattern_search_failed", err)
	}

	if len(keys) == 0 {
		return nil
	}

	// Delete in batches for performance
	batchSize := 100
	for i := 0; i < len(keys); i += batchSize {
		end := i + batchSize
		if end > len(keys) {
			end = len(keys)
		}

		batch := keys[i:end]
		err = c.client.Del(ctx, batch...).Err()
		if err != nil {
			return c.wrapError("batch_deletion_failed", err)
		}
	}

	return nil
}

// Cache management and monitoring

// GetCacheStats returns comprehensive cache statistics
func (c *RedisCacheAdapter) GetCacheStats(ctx context.Context) (*CacheStats, error) {
	info, err := c.client.Info(ctx, "memory", "stats").Result()
	if err != nil {
		return nil, c.wrapError("cache_info_failed", err)
	}

	// Parse Redis info for relevant metrics
	stats := &CacheStats{
		HitRate:        c.metricsCollector.GetHitRate(),
		MissRate:       c.metricsCollector.GetMissRate(),
		EvictionCount:  c.extractRedisMetric(info, "evicted_keys"),
		ConnectionCount: c.extractRedisMetric(info, "connected_clients"),
		MemoryUsage:    c.extractRedisMetric(info, "used_memory"),
		KeyCount:       c.extractRedisMetric(info, "db0:keys"),
		LastUpdated:    time.Now(),
	}

	return stats, nil
}

// FlushCache clears all cache entries with confirmation
func (c *RedisCacheAdapter) FlushCache(ctx context.Context, confirmation string) error {
	if confirmation != "CONFIRM_FLUSH_ALL" {
		return fmt.Errorf("invalid confirmation string")
	}

	startTime := time.Now()
	defer c.recordMetrics("flush_cache", startTime, nil)

	// Only flush keys with our prefix to avoid affecting other applications
	pattern := c.keyPrefix + "*"
	keys, err := c.client.Keys(ctx, pattern).Result()
	if err != nil {
		return c.wrapError("flush_keys_search_failed", err)
	}

	if len(keys) > 0 {
		err = c.client.Del(ctx, keys...).Err()
		if err != nil {
			return c.wrapError("flush_deletion_failed", err)
		}
	}

	c.metricsCollector.RecordCacheFlush(len(keys))
	return nil
}

// Helper methods

func (c *RedisCacheAdapter) generateKey(prefix, identifier string) string {
	return fmt.Sprintf("%s:%s:%s", c.keyPrefix, prefix, identifier)
}

func (c *RedisCacheAdapter) generateQueryHash(queryKey string) string {
	// Simple hash for query key - in production, use proper hashing
	return fmt.Sprintf("hash_%s", queryKey)
}

func (c *RedisCacheAdapter) cacheQueryMetadata(
	ctx context.Context,
	queryKey string,
	resultCount int,
	ttl time.Duration,
) {
	metadata := QueryCacheMetadata{
		QueryKey:    queryKey,
		ResultCount: resultCount,
		CachedAt:    time.Now().Unix(),
		TTL:         int64(ttl.Seconds()),
	}

	metadataJSON, _ := json.Marshal(metadata)
	metadataKey := c.generateKey("query_meta", c.generateQueryHash(queryKey))
	c.client.Set(ctx, metadataKey, metadataJSON, ttl)
}

func (c *RedisCacheAdapter) extractRedisMetric(info string, key string) int64 {
	// Simple extraction - in production, use proper parsing
	return 0 // Placeholder implementation
}

func (c *RedisCacheAdapter) recordMetrics(operation string, startTime time.Time, err error) {
	if c.metricsCollector != nil {
		duration := time.Since(startTime)
		c.metricsCollector.RecordOperation(operation, duration, err)
	}
}

func (c *RedisCacheAdapter) wrapError(operation string, err error) error {
	return fmt.Errorf("Redis cache %s failed: %w", operation, err)
}

// Cache model types with anti-corruption patterns

// ConfigurationCacheModel represents configuration in cache format
type ConfigurationCacheModel struct {
	ID                   string                     `json:"id"`
	Name                 string                     `json:"name"`
	Description          string                     `json:"description"`
	Mode                 string                     `json:"mode"`
	Version              string                     `json:"version"`
	Status               string                     `json:"status"`
	Labels               map[string]string          `json:"labels"`
	Annotations          map[string]string          `json:"annotations"`
	Components           []ComponentCacheModel      `json:"components"`
	EnterpriseConfig     *EnterpriseConfigCacheModel `json:"enterprise_config,omitempty"`
	CacheMetadata        CacheMetadata              `json:"cache_metadata"`
}

// ComponentCacheModel represents component in cache format
type ComponentCacheModel struct {
	Name                string                          `json:"name"`
	Version             string                          `json:"version"`
	Enabled             bool                           `json:"enabled"`
	Configuration       map[string]interface{}         `json:"configuration"`
	Resources           ResourceRequirementsCacheModel `json:"resources"`
}

// ResourceRequirementsCacheModel represents resource requirements in cache
type ResourceRequirementsCacheModel struct {
	CPU       string `json:"cpu"`
	Memory    string `json:"memory"`
	Storage   string `json:"storage"`
	Replicas  int    `json:"replicas"`
	Namespace string `json:"namespace"`
}

// EnterpriseConfigCacheModel represents enterprise config in cache
type EnterpriseConfigCacheModel struct {
	ComplianceFramework string            `json:"compliance_framework"`
	SecurityLevel       string            `json:"security_level"`
	AuditEnabled        bool              `json:"audit_enabled"`
	EncryptionRequired  bool              `json:"encryption_required"`
	BackupRequired      bool              `json:"backup_required"`
	PolicyTemplates     []string          `json:"policy_templates"`
	Metadata           map[string]string `json:"metadata"`
}

// CacheMetadata holds cache-specific metadata
type CacheMetadata struct {
	SerializationFormat string    `json:"serialization_format"`
	CompressionLevel    int       `json:"compression_level"`
	CachedAt           time.Time `json:"cached_at"`
	TTL                time.Duration `json:"ttl"`
	SchemaVersion      string    `json:"schema_version"`
}

// Metadata types for cache management

// ConfigurationCacheMetadata holds configuration cache metadata
type ConfigurationCacheMetadata struct {
	ID             string `json:"id"`
	Name           string `json:"name"`
	Mode           string `json:"mode"`
	Version        string `json:"version"`
	Status         string `json:"status"`
	ComponentCount int    `json:"component_count"`
	CachedAt       int64  `json:"cached_at"`
	TTL            int64  `json:"ttl"`
}

// QueryCacheMetadata holds query cache metadata
type QueryCacheMetadata struct {
	QueryKey    string `json:"query_key"`
	ResultCount int    `json:"result_count"`
	CachedAt    int64  `json:"cached_at"`
	TTL         int64  `json:"ttl"`
}

// CacheStats provides comprehensive cache statistics
type CacheStats struct {
	HitRate         float64   `json:"hit_rate"`
	MissRate        float64   `json:"miss_rate"`
	EvictionCount   int64     `json:"eviction_count"`
	ConnectionCount int64     `json:"connection_count"`
	MemoryUsage     int64     `json:"memory_usage"`
	KeyCount        int64     `json:"key_count"`
	LastUpdated     time.Time `json:"last_updated"`
}

// Cache error types
var (
	ErrCacheNotFound = fmt.Errorf("cache entry not found")
	ErrCacheInvalid  = fmt.Errorf("cache entry is invalid")
	ErrCacheExpired  = fmt.Errorf("cache entry has expired")
)

// CacheMetricsCollector collects cache operation metrics
type CacheMetricsCollector struct {
	// Implementation would collect comprehensive cache metrics
}

func (cmc *CacheMetricsCollector) RecordOperation(operation string, duration time.Duration, err error) {
	// Implementation would record cache operation metrics
}

func (cmc *CacheMetricsCollector) RecordCacheHit(cacheType string) {
	// Implementation would record cache hit metrics
}

func (cmc *CacheMetricsCollector) RecordCacheMiss(cacheType string) {
	// Implementation would record cache miss metrics
}

func (cmc *CacheMetricsCollector) GetHitRate() float64 {
	// Implementation would calculate hit rate
	return 0.0
}

func (cmc *CacheMetricsCollector) GetMissRate() float64 {
	// Implementation would calculate miss rate
	return 0.0
}

func (cmc *CacheMetricsCollector) RecordCacheFlush(keyCount int) {
	// Implementation would record cache flush metrics
}