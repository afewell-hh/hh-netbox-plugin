package domain

import (
	"context"

	"github.com/hedgehog/cnoc/internal/domain/events"
	"github.com/hedgehog/cnoc/internal/domain/configuration"
)

// EventBus alias for easier access from domain package
type EventBus = events.EventBus

// Type aliases for configuration types
type Configuration = configuration.Configuration
type ComponentReference = configuration.ComponentReference
type ConfigurationMetadata = configuration.ConfigurationMetadata
type EnterpriseConfiguration = configuration.EnterpriseConfiguration

// These types are already defined in this package (domain.go, fabric.go, crd.go)
// so we don't need aliases for them

// ConfigurationDomainService defines domain services for configuration management
type ConfigurationDomainService interface {
	ValidateConfiguration(config *configuration.Configuration) error
	ResolveDependencies(config *configuration.Configuration) error
	ApplyPolicies(config *configuration.Configuration) error
}

// ConfigurationRepository defines the repository interface for configurations
type ConfigurationRepository interface {
	Save(ctx context.Context, config *configuration.Configuration) error
	GetByID(ctx context.Context, id string) (*configuration.Configuration, error)
	GetByName(ctx context.Context, name string) (*configuration.Configuration, error)
	List(ctx context.Context, offset, limit int) ([]*configuration.Configuration, int, error)
	Delete(ctx context.Context, id string) error
}