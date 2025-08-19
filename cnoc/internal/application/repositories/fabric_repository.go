package repositories

import (
	"context"
	"fmt"
	"sync"
	"time"

	"github.com/hedgehog/cnoc/internal/domain"
)

// MemoryFabricRepository implements FabricRepository interface using in-memory storage
// This follows the same pattern as ConfigurationRepositoryImpl for consistency
type MemoryFabricRepository struct {
	mu      sync.RWMutex
	fabrics map[string]*domain.Fabric
	nextID  int
}

// NewMemoryFabricRepository creates a new in-memory fabric repository
func NewMemoryFabricRepository() *MemoryFabricRepository {
	return &MemoryFabricRepository{
		fabrics: make(map[string]*domain.Fabric),
		nextID:  1,
	}
}

// Save persists a fabric to the repository
func (r *MemoryFabricRepository) Save(ctx context.Context, fabric *domain.Fabric) error {
	r.mu.Lock()
	defer r.mu.Unlock()

	// Validate the fabric before saving
	if err := fabric.Validate(); err != nil {
		return fmt.Errorf("fabric validation failed: %w", err)
	}

	// Set audit fields
	now := time.Now()
	if fabric.ID == "" {
		fabric.ID = fmt.Sprintf("fabric-%d", r.nextID)
		r.nextID++
		fabric.Created = now
	}
	fabric.LastModified = now

	// Set default values if not set
	if fabric.Status == "" {
		fabric.Status = domain.FabricStatusPlanned
	}
	if fabric.ConnectionStatus == "" {
		fabric.ConnectionStatus = domain.ConnectionStatusUnknown
	}
	if fabric.SyncStatus == "" {
		fabric.SyncStatus = domain.SyncStatusNeverSynced
	}
	if fabric.GitSyncStatus == "" {
		fabric.GitSyncStatus = domain.GitSyncStatusNeverSynced
	}
	if fabric.GitOpsBranch == "" {
		fabric.GitOpsBranch = "main"
	}

	r.fabrics[fabric.ID] = fabric
	return nil
}

// GetByID retrieves a fabric by its ID
func (r *MemoryFabricRepository) GetByID(ctx context.Context, id string) (*domain.Fabric, error) {
	r.mu.RLock()
	defer r.mu.RUnlock()

	fabric, exists := r.fabrics[id]
	if !exists {
		return nil, fmt.Errorf("fabric with ID %s not found", id)
	}

	// Return a copy to prevent external modification
	fabricCopy := *fabric
	return &fabricCopy, nil
}

// GetByName retrieves a fabric by its name
func (r *MemoryFabricRepository) GetByName(ctx context.Context, name string) (*domain.Fabric, error) {
	r.mu.RLock()
	defer r.mu.RUnlock()

	for _, fabric := range r.fabrics {
		if fabric.Name == name {
			// Return a copy to prevent external modification
			fabricCopy := *fabric
			return &fabricCopy, nil
		}
	}

	return nil, fmt.Errorf("fabric with name %s not found", name)
}

// List retrieves fabrics with pagination
func (r *MemoryFabricRepository) List(ctx context.Context, page, pageSize int) ([]*domain.Fabric, int, error) {
	r.mu.RLock()
	defer r.mu.RUnlock()

	// Convert map to slice for pagination
	var allFabrics []*domain.Fabric
	for _, fabric := range r.fabrics {
		// Add a copy to prevent external modification
		fabricCopy := *fabric
		allFabrics = append(allFabrics, &fabricCopy)
	}

	totalCount := len(allFabrics)

	// Calculate pagination (page is 1-based)
	if page < 1 {
		page = 1
	}
	if pageSize < 1 {
		pageSize = 10
	}
	
	offset := (page - 1) * pageSize
	if offset >= totalCount {
		return []*domain.Fabric{}, totalCount, nil
	}

	end := offset + pageSize
	if end > totalCount {
		end = totalCount
	}

	return allFabrics[offset:end], totalCount, nil
}

// Delete removes a fabric from the repository
func (r *MemoryFabricRepository) Delete(ctx context.Context, id string) error {
	r.mu.Lock()
	defer r.mu.Unlock()

	if _, exists := r.fabrics[id]; !exists {
		return fmt.Errorf("fabric with ID %s not found", id)
	}

	delete(r.fabrics, id)
	return nil
}

// ExistsByName checks if a fabric with the given name exists
func (r *MemoryFabricRepository) ExistsByName(ctx context.Context, name string) (bool, error) {
	r.mu.RLock()
	defer r.mu.RUnlock()

	for _, fabric := range r.fabrics {
		if fabric.Name == name {
			return true, nil
		}
	}

	return false, nil
}

// Additional helper methods for testing and development

// Clear removes all fabrics from the repository (useful for testing)
func (r *MemoryFabricRepository) Clear() {
	r.mu.Lock()
	defer r.mu.Unlock()
	r.fabrics = make(map[string]*domain.Fabric)
	r.nextID = 1
}

// Count returns the total number of fabrics in the repository
func (r *MemoryFabricRepository) Count() int {
	r.mu.RLock()
	defer r.mu.RUnlock()
	return len(r.fabrics)
}