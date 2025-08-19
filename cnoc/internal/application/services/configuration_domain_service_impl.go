package services

import (
	"errors"
	"fmt"

	"github.com/hedgehog/cnoc/internal/domain/configuration"
)

// ConfigurationDomainServiceImpl implements ConfigurationDomainService interface
// This is a simple implementation for FORGE GREEN phase testing
type ConfigurationDomainServiceImpl struct {
	shouldFailValidation bool // For testing purposes
}

// NewConfigurationDomainService creates a new configuration domain service
func NewConfigurationDomainService() ConfigurationDomainService {
	return &ConfigurationDomainServiceImpl{}
}

// ValidateConfiguration validates configuration against domain rules
func (s *ConfigurationDomainServiceImpl) ValidateConfiguration(config *configuration.Configuration) error {
	if s.shouldFailValidation {
		return errors.New("mock validation failure")
	}
	
	if config == nil {
		return errors.New("configuration cannot be nil")
	}
	
	// Basic validation checks
	if config.ID().String() == "" {
		return errors.New("configuration ID cannot be empty")
	}
	
	if config.Name().String() == "" {
		return errors.New("configuration name cannot be empty")
	}
	
	if config.Version().String() == "" {
		return errors.New("configuration version cannot be empty")
	}
	
	return nil
}

// ValidateBusinessRules validates business-specific rules
func (s *ConfigurationDomainServiceImpl) ValidateBusinessRules(config *configuration.Configuration) error {
	if s.shouldFailValidation {
		return errors.New("mock business rule validation failure")
	}
	
	if config == nil {
		return errors.New("configuration cannot be nil")
	}
	
	// Business rule validation
	switch config.Mode() {
	case configuration.ModeEnterprise:
		// Enterprise mode requires at least one component
		if config.Components().Size() == 0 {
			return errors.New("enterprise mode requires at least one component")
		}
		
	case configuration.ModeMinimal:
		// Minimal mode has component limits
		if config.Components().Size() > 3 {
			return errors.New("minimal mode cannot have more than 3 components")
		}
		
	case configuration.ModeDevelopment:
		// Development mode is more flexible
		// No specific restrictions
	}
	
	return nil
}

// ResolveDependencies resolves component dependencies
func (s *ConfigurationDomainServiceImpl) ResolveDependencies(config *configuration.Configuration) error {
	if config == nil {
		return errors.New("configuration cannot be nil")
	}
	
	// Simplified dependency resolution
	// In a real implementation, this would analyze component dependencies
	// and ensure all required dependencies are present
	
	components := config.ComponentsList()
	dependencyMap := map[string][]string{
		"grafana": {"prometheus"},
		"argocd":  {"cert-manager"},
	}
	
	for _, component := range components {
		componentName := component.Name().String()
		if deps, exists := dependencyMap[componentName]; exists {
			for _, dep := range deps {
				found := false
				for _, other := range components {
					if other.Name().String() == dep {
						found = true
						break
					}
				}
				if !found {
					return fmt.Errorf("component '%s' requires dependency '%s' which is not present", 
						componentName, dep)
				}
			}
		}
	}
	
	return nil
}

// ApplyPolicies applies enterprise policies to configuration
func (s *ConfigurationDomainServiceImpl) ApplyPolicies(config *configuration.Configuration) error {
	if config == nil {
		return errors.New("configuration cannot be nil")
	}
	
	// Apply enterprise policies if configuration has enterprise settings
	enterpriseConfig := config.EnterpriseConfiguration()
	if enterpriseConfig == nil {
		return nil // No enterprise policies to apply
	}
	
	// Validate compliance framework requirements
	framework := enterpriseConfig.ComplianceFramework()
	switch framework {
	case "SOC2", "HIPAA", "PCI-DSS":
		// These frameworks require encryption
		if !enterpriseConfig.EncryptionRequired() {
			return fmt.Errorf("compliance framework '%s' requires encryption to be enabled", framework)
		}
		
		// And audit logging
		if !enterpriseConfig.AuditEnabled() {
			return fmt.Errorf("compliance framework '%s' requires audit logging to be enabled", framework)
		}
		
	case "ISO27001":
		// ISO27001 requires backup
		if !enterpriseConfig.BackupRequired() {
			return fmt.Errorf("ISO27001 compliance requires backup to be enabled")
		}
	}
	
	return nil
}

// Mock domain service for testing that allows injection of failures
type MockConfigurationDomainService struct {
	shouldFailValidation bool
	validationCallCount  int
}

func NewMockConfigurationDomainService() *MockConfigurationDomainService {
	return &MockConfigurationDomainService{}
}

func (m *MockConfigurationDomainService) ValidateConfiguration(config *configuration.Configuration) error {
	m.validationCallCount++
	if m.shouldFailValidation {
		return errors.New("mock validation failure")
	}
	return nil
}

func (m *MockConfigurationDomainService) ValidateBusinessRules(config *configuration.Configuration) error {
	m.validationCallCount++
	if m.shouldFailValidation {
		return errors.New("mock business rule validation failure")
	}
	return nil
}

func (m *MockConfigurationDomainService) ResolveDependencies(config *configuration.Configuration) error {
	return nil
}

func (m *MockConfigurationDomainService) ApplyPolicies(config *configuration.Configuration) error {
	return nil
}