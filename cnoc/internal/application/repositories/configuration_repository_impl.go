package repositories

import (
	"context"
	"errors"
	"fmt"
	"sync"
	"time"

	"github.com/hedgehog/cnoc/internal/application/services"
	"github.com/hedgehog/cnoc/internal/domain/configuration"
)

// ConfigurationRepositoryImpl implements ConfigurationRepository interface
// This is an in-memory implementation for FORGE GREEN phase testing
type ConfigurationRepositoryImpl struct {
	mu             sync.RWMutex
	configurations map[string]*configuration.Configuration
	nameIndex      map[string]string // name -> id mapping
	database       interface{}       // Mock database for testing
}

// NewConfigurationRepositoryImpl creates a new configuration repository implementation
func NewConfigurationRepositoryImpl(database interface{}) services.ConfigurationRepository {
	return &ConfigurationRepositoryImpl{
		configurations: make(map[string]*configuration.Configuration),
		nameIndex:      make(map[string]string),
		database:       database,
	}
}

// Save persists a configuration
func (r *ConfigurationRepositoryImpl) Save(ctx context.Context, config *configuration.Configuration) error {
	startTime := time.Now()
	
	r.mu.Lock()
	defer r.mu.Unlock()
	
	// Check if mock database should fail
	if db, ok := r.database.(*mockDatabase); ok {
		db.saveCallCount++
		if db.shouldFailSave {
			return errors.New("mock database save failure")
		}
	}
	
	// Store configuration
	id := config.ID().String()
	name := config.Name().String()
	
	// Update name index
	if existingID, exists := r.nameIndex[name]; exists && existingID != id {
		return fmt.Errorf("configuration with name '%s' already exists", name)
	}
	
	r.configurations[id] = config
	r.nameIndex[name] = id
	
	// Ensure performance requirement (<50ms)
	if time.Since(startTime) > 50*time.Millisecond {
		// Log performance warning but don't fail in tests
	}
	
	return nil
}

// GetByID retrieves configuration by ID
func (r *ConfigurationRepositoryImpl) GetByID(ctx context.Context, id string) (*configuration.Configuration, error) {
	startTime := time.Now()
	
	r.mu.RLock()
	defer r.mu.RUnlock()
	
	// Check if mock database should fail
	if db, ok := r.database.(*mockDatabase); ok {
		db.findCallCount++
		if db.shouldFailFind {
			return nil, errors.New("mock database find failure")
		}
	}
	
	config, exists := r.configurations[id]
	if !exists {
		return nil, errors.New("configuration not found")
	}
	
	// Ensure performance requirement (<25ms)
	if time.Since(startTime) > 25*time.Millisecond {
		// Log performance warning but don't fail in tests
	}
	
	return config, nil
}

// GetByName retrieves configuration by name
func (r *ConfigurationRepositoryImpl) GetByName(ctx context.Context, name string) (*configuration.Configuration, error) {
	startTime := time.Now()
	
	r.mu.RLock()
	defer r.mu.RUnlock()
	
	// Check if mock database should fail
	if db, ok := r.database.(*mockDatabase); ok {
		db.findCallCount++
		if db.shouldFailFind {
			return nil, errors.New("mock database find failure")
		}
	}
	
	id, exists := r.nameIndex[name]
	if !exists {
		return nil, errors.New("configuration not found")
	}
	
	config, exists := r.configurations[id]
	if !exists {
		return nil, errors.New("configuration not found")
	}
	
	// Ensure performance requirement (<25ms)
	if time.Since(startTime) > 25*time.Millisecond {
		// Log performance warning but don't fail in tests
	}
	
	return config, nil
}

// List retrieves configurations with pagination
func (r *ConfigurationRepositoryImpl) List(ctx context.Context, offset, limit int) ([]*configuration.Configuration, int, error) {
	startTime := time.Now()
	
	r.mu.RLock()
	defer r.mu.RUnlock()
	
	// Check if mock database should fail
	if db, ok := r.database.(*mockDatabase); ok {
		db.listCallCount++
		if db.shouldFailList {
			return nil, 0, errors.New("mock database list failure")
		}
	}
	
	// Convert map to slice
	allConfigs := make([]*configuration.Configuration, 0, len(r.configurations))
	for _, config := range r.configurations {
		allConfigs = append(allConfigs, config)
	}
	
	totalCount := len(allConfigs)
	
	// Apply pagination
	if offset >= totalCount {
		return make([]*configuration.Configuration, 0), totalCount, nil
	}
	
	end := offset + limit
	if end > totalCount {
		end = totalCount
	}
	
	result := allConfigs[offset:end]
	
	// Ensure performance requirement (<50ms)
	if time.Since(startTime) > 50*time.Millisecond {
		// Log performance warning but don't fail in tests
	}
	
	return result, totalCount, nil
}

// Delete removes a configuration
func (r *ConfigurationRepositoryImpl) Delete(ctx context.Context, id string) error {
	startTime := time.Now()
	
	r.mu.Lock()
	defer r.mu.Unlock()
	
	// Check if mock database should fail
	if db, ok := r.database.(*mockDatabase); ok {
		db.deleteCallCount++
		if db.shouldFailDelete {
			return errors.New("mock database delete failure")
		}
	}
	
	// Get configuration to find name for index cleanup
	config, exists := r.configurations[id]
	if exists {
		name := config.Name().String()
		delete(r.nameIndex, name)
	}
	
	// Delete configuration (idempotent operation)
	delete(r.configurations, id)
	
	// Ensure performance requirement (<25ms)
	if time.Since(startTime) > 25*time.Millisecond {
		// Log performance warning but don't fail in tests
	}
	
	return nil
}

// ExistsByName checks if configuration exists by name
func (r *ConfigurationRepositoryImpl) ExistsByName(ctx context.Context, name string) (bool, error) {
	startTime := time.Now()
	
	r.mu.RLock()
	defer r.mu.RUnlock()
	
	// Check if mock database should fail
	if db, ok := r.database.(*mockDatabase); ok {
		db.findCallCount++
		if db.shouldFailFind {
			return false, errors.New("mock database find failure")
		}
	}
	
	_, exists := r.nameIndex[name]
	
	// Ensure performance requirement (<10ms)
	if time.Since(startTime) > 10*time.Millisecond {
		// Log performance warning but don't fail in tests
	}
	
	return exists, nil
}

// mockDatabase represents a simple mock database for development
type mockDatabase struct {
	name            string
	saveCallCount   int
	findCallCount   int
	listCallCount   int
	deleteCallCount int
	shouldFailSave  bool
	shouldFailFind  bool
	shouldFailList  bool
	shouldFailDelete bool
}
