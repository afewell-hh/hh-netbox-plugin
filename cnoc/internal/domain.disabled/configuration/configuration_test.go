package configuration

import (
	"testing"
	"time"
)

// FORGE Domain Model Unit Tests
// Tests domain business rules and entity behavior with comprehensive validation
// MUST fail initially (red phase) until proper domain implementation exists

// TestConfigurationCreation tests configuration entity creation with business rules
func TestConfigurationCreation(t *testing.T) {
	// FORGE Requirement: Test domain entity creation with comprehensive validation
	
	testCases := []struct {
		name           string
		id             string
		configName     string
		description    string
		mode           string
		version        string
		labels         map[string]string
		expectedError  bool
		validationMsg  string
	}{
		{
			name:        "Valid Configuration Creation",
			id:          "config-123",
			configName:  "production-config",
			description: "Production configuration for CNOC",
			mode:        "production",
			version:     "1.0.0",
			labels: map[string]string{
				"environment": "production",
				"team":        "platform",
			},
			expectedError: false,
		},
		{
			name:          "Empty ID Validation",
			id:            "",
			configName:    "test-config",
			description:   "Test configuration",
			mode:          "development",
			version:       "1.0.0",
			labels:        map[string]string{},
			expectedError: true,
			validationMsg: "Configuration ID cannot be empty",
		},
		{
			name:          "Empty Name Validation", 
			id:            "config-124",
			configName:    "",
			description:   "Test configuration",
			mode:          "development",
			version:       "1.0.0",
			labels:        map[string]string{},
			expectedError: true,
			validationMsg: "Configuration name cannot be empty",
		},
		{
			name:          "Invalid Mode Validation",
			id:            "config-125",
			configName:    "test-config",
			description:   "Test configuration",
			mode:          "invalid-mode",
			version:       "1.0.0",
			labels:        map[string]string{},
			expectedError: true,
			validationMsg: "Invalid configuration mode",
		},
		{
			name:          "Invalid Version Format",
			id:            "config-126",
			configName:    "test-config", 
			description:   "Test configuration",
			mode:          "development",
			version:       "invalid-version",
			labels:        map[string]string{},
			expectedError: true,
			validationMsg: "Invalid version format",
		},
	}
	
	for _, tc := range testCases {
		t.Run(tc.name, func(t *testing.T) {
			// FORGE Red Phase: This will fail until NewConfiguration is implemented
			config, err := NewConfiguration(
				tc.id,
				tc.configName,
				tc.description,
				tc.mode,
				tc.version,
				tc.labels,
			)
			
			// FORGE Quantitative Validation
			if tc.expectedError && err == nil {
				t.Errorf("❌ FORGE FAIL: Expected error but got none")
			}
			if !tc.expectedError && err != nil {
				t.Errorf("❌ FORGE FAIL: Unexpected error: %v", err)
			}
			
			if !tc.expectedError && config != nil {
				// Validate entity state
				if config.ID() != tc.id {
					t.Errorf("❌ FORGE FAIL: ID mismatch: expected %s, got %s", 
						tc.id, config.ID())
				}
				if config.Name() != tc.configName {
					t.Errorf("❌ FORGE FAIL: Name mismatch: expected %s, got %s",
						tc.configName, config.Name())
				}
				if config.Description() != tc.description {
					t.Errorf("❌ FORGE FAIL: Description mismatch: expected %s, got %s",
						tc.description, config.Description())
				}
				if config.Mode() != tc.mode {
					t.Errorf("❌ FORGE FAIL: Mode mismatch: expected %s, got %s",
						tc.mode, config.Mode())
				}
				if config.Version() != tc.version {
					t.Errorf("❌ FORGE FAIL: Version mismatch: expected %s, got %s",
						tc.version, config.Version())
				}
				
				// Validate labels
				configLabels := config.Labels()
				if len(configLabels) != len(tc.labels) {
					t.Errorf("❌ FORGE FAIL: Label count mismatch: expected %d, got %d",
						len(tc.labels), len(configLabels))
				}
				
				for key, expectedValue := range tc.labels {
					if actualValue, exists := configLabels[key]; !exists {
						t.Errorf("❌ FORGE FAIL: Missing label key: %s", key)
					} else if actualValue != expectedValue {
						t.Errorf("❌ FORGE FAIL: Label value mismatch for %s: expected %s, got %s",
							key, expectedValue, actualValue)
					}
				}
				
				// Validate timestamps are set
				if config.CreatedAt().IsZero() {
					t.Errorf("❌ FORGE FAIL: CreatedAt timestamp not set")
				}
				if config.UpdatedAt().IsZero() {
					t.Errorf("❌ FORGE FAIL: UpdatedAt timestamp not set")
				}
			}
			
			t.Logf("✅ FORGE EVIDENCE: %s - Error: %v", tc.name, err != nil)
		})
	}
}

// TestConfigurationUpdate tests configuration updates with business rules
func TestConfigurationUpdate(t *testing.T) {
	// FORGE Requirement: Test entity update behavior with validation
	
	// Create initial configuration
	config, err := NewConfiguration(
		"config-update-test",
		"initial-config",
		"Initial configuration",
		"development",
		"1.0.0",
		map[string]string{"initial": "true"},
	)
	
	if err != nil {
		t.Fatalf("Failed to create initial configuration: %v", err)
	}
	
	initialUpdatedAt := config.UpdatedAt()
	
	// Test description update
	t.Run("Update Description", func(t *testing.T) {
		newDescription := "Updated configuration description"
		
		// FORGE Red Phase: This will fail until UpdateDescription is implemented
		err := config.UpdateDescription(newDescription)
		
		if err != nil {
			t.Errorf("❌ FORGE FAIL: Unexpected error updating description: %v", err)
		}
		
		if config.Description() != newDescription {
			t.Errorf("❌ FORGE FAIL: Description not updated: expected %s, got %s",
				newDescription, config.Description())
		}
		
		// Validate UpdatedAt timestamp changed
		if !config.UpdatedAt().After(initialUpdatedAt) {
			t.Errorf("❌ FORGE FAIL: UpdatedAt timestamp not updated")
		}
		
		t.Logf("✅ FORGE EVIDENCE: Description updated successfully")
	})
	
	// Test labels update
	t.Run("Update Labels", func(t *testing.T) {
		newLabels := map[string]string{
			"environment": "staging",
			"updated":     "true",
			"version":     "2.0",
		}
		
		beforeUpdate := config.UpdatedAt()
		time.Sleep(1 * time.Millisecond) // Ensure timestamp difference
		
		// FORGE Red Phase: This will fail until UpdateLabels is implemented
		err := config.UpdateLabels(newLabels)
		
		if err != nil {
			t.Errorf("❌ FORGE FAIL: Unexpected error updating labels: %v", err)
		}
		
		// Validate all labels were updated
		configLabels := config.Labels()
		for key, expectedValue := range newLabels {
			if actualValue, exists := configLabels[key]; !exists {
				t.Errorf("❌ FORGE FAIL: Missing updated label key: %s", key)
			} else if actualValue != expectedValue {
				t.Errorf("❌ FORGE FAIL: Label not updated for %s: expected %s, got %s",
					key, expectedValue, actualValue)
			}
		}
		
		// Validate UpdatedAt timestamp changed
		if !config.UpdatedAt().After(beforeUpdate) {
			t.Errorf("❌ FORGE FAIL: UpdatedAt timestamp not updated after label change")
		}
		
		t.Logf("✅ FORGE EVIDENCE: Labels updated successfully")
	})
	
	// Test invalid updates
	t.Run("Invalid Description Update", func(t *testing.T) {
		// FORGE Red Phase: This will fail until validation is implemented
		err := config.UpdateDescription("")
		
		if err == nil {
			t.Errorf("❌ FORGE FAIL: Expected error for empty description update")
		}
		
		t.Logf("✅ FORGE EVIDENCE: Invalid description update rejected")
	})
}

// TestConfigurationComponents tests component management
func TestConfigurationComponents(t *testing.T) {
	// FORGE Requirement: Test component aggregation within configuration
	
	config, err := NewConfiguration(
		"config-components-test",
		"component-test-config",
		"Configuration for component testing",
		"development",
		"1.0.0",
		map[string]string{},
	)
	
	if err != nil {
		t.Fatalf("Failed to create configuration: %v", err)
	}
	
	// Test adding components
	t.Run("Add Component", func(t *testing.T) {
		component := ComponentReference{
			Name:    "test-component",
			Version: "1.0.0",
			Enabled: true,
			Resources: ResourceRequirements{
				CPU:      "100m",
				Memory:   "128Mi",
				Replicas: 1,
			},
			Configuration: map[string]interface{}{
				"port": 8080,
				"env":  "test",
			},
		}
		
		// FORGE Red Phase: This will fail until AddComponent is implemented
		err := config.AddComponent(component)
		
		if err != nil {
			t.Errorf("❌ FORGE FAIL: Unexpected error adding component: %v", err)
		}
		
		// Validate component was added
		components := config.Components()
		if len(components) != 1 {
			t.Errorf("❌ FORGE FAIL: Expected 1 component, got %d", len(components))
		}
		
		if len(components) > 0 {
			if components[0].Name != component.Name {
				t.Errorf("❌ FORGE FAIL: Component name mismatch: expected %s, got %s",
					component.Name, components[0].Name)
			}
			if components[0].Version != component.Version {
				t.Errorf("❌ FORGE FAIL: Component version mismatch: expected %s, got %s", 
					component.Version, components[0].Version)
			}
			if components[0].Enabled != component.Enabled {
				t.Errorf("❌ FORGE FAIL: Component enabled mismatch: expected %t, got %t",
					component.Enabled, components[0].Enabled)
			}
		}
		
		t.Logf("✅ FORGE EVIDENCE: Component added successfully")
	})
	
	// Test duplicate component prevention
	t.Run("Prevent Duplicate Components", func(t *testing.T) {
		duplicateComponent := ComponentReference{
			Name:    "test-component", // Same name as before
			Version: "1.1.0",
			Enabled: true,
		}
		
		// FORGE Red Phase: This should fail until validation is implemented
		err := config.AddComponent(duplicateComponent)
		
		if err == nil {
			t.Errorf("❌ FORGE FAIL: Expected error for duplicate component name")
		}
		
		t.Logf("✅ FORGE EVIDENCE: Duplicate component rejected")
	})
	
	// Test component removal
	t.Run("Remove Component", func(t *testing.T) {
		// FORGE Red Phase: This will fail until RemoveComponent is implemented
		err := config.RemoveComponent("test-component")
		
		if err != nil {
			t.Errorf("❌ FORGE FAIL: Unexpected error removing component: %v", err)
		}
		
		// Validate component was removed
		components := config.Components()
		if len(components) != 0 {
			t.Errorf("❌ FORGE FAIL: Expected 0 components after removal, got %d", 
				len(components))
		}
		
		t.Logf("✅ FORGE EVIDENCE: Component removed successfully")
	})
}

// TestConfigurationBusinessRules tests domain business rules
func TestConfigurationBusinessRules(t *testing.T) {
	// FORGE Requirement: Test complex business rules and constraints
	
	t.Run("Production Mode Validation", func(t *testing.T) {
		// Production configurations should have stricter validation
		config, err := NewConfiguration(
			"prod-config",
			"production-config",
			"Production configuration",
			"production",
			"1.0.0",
			map[string]string{
				"environment": "production",
			},
		)
		
		if err != nil {
			t.Errorf("❌ FORGE FAIL: Failed to create production config: %v", err)
			return
		}
		
		// FORGE Red Phase: This will fail until business rules are implemented
		isValid := config.ValidateForProduction()
		
		if !isValid {
			t.Errorf("❌ FORGE FAIL: Valid production config failed validation")
		}
		
		t.Logf("✅ FORGE EVIDENCE: Production validation passed")
	})
	
	t.Run("Component Dependency Validation", func(t *testing.T) {
		config, _ := NewConfiguration(
			"dependency-test",
			"dependency-config",
			"Configuration for dependency testing",
			"development",
			"1.0.0",
			map[string]string{},
		)
		
		// Add components with dependencies
		webComponent := ComponentReference{
			Name:         "web-server",
			Version:      "1.0.0",
			Enabled:      true,
			Dependencies: []string{"database", "cache"},
		}
		
		dbComponent := ComponentReference{
			Name:    "database",
			Version: "1.0.0",
			Enabled: true,
		}
		
		config.AddComponent(webComponent)
		config.AddComponent(dbComponent)
		
		// FORGE Red Phase: This will fail until dependency validation is implemented
		validationResult := config.ValidateDependencies()
		
		// Should fail because "cache" dependency is missing
		if validationResult.Valid {
			t.Errorf("❌ FORGE FAIL: Expected dependency validation to fail")
		}
		
		if len(validationResult.Errors) == 0 {
			t.Errorf("❌ FORGE FAIL: Expected dependency validation errors")
		}
		
		t.Logf("✅ FORGE EVIDENCE: Dependency validation failed as expected")
	})
}

// TestConfigurationVersioning tests configuration versioning behavior
func TestConfigurationVersioning(t *testing.T) {
	config, _ := NewConfiguration(
		"version-test",
		"version-config",
		"Configuration for version testing",
		"development",
		"1.0.0",
		map[string]string{},
	)
	
	t.Run("Version Comparison", func(t *testing.T) {
		// FORGE Red Phase: This will fail until version comparison is implemented
		isNewerVersion := config.IsNewerThan("0.9.0")
		if !isNewerVersion {
			t.Errorf("❌ FORGE FAIL: Version comparison failed: 1.0.0 should be newer than 0.9.0")
		}
		
		isOlderVersion := config.IsNewerThan("1.1.0")
		if isOlderVersion {
			t.Errorf("❌ FORGE FAIL: Version comparison failed: 1.0.0 should not be newer than 1.1.0")
		}
		
		t.Logf("✅ FORGE EVIDENCE: Version comparison working")
	})
	
	t.Run("Version Update", func(t *testing.T) {
		// FORGE Red Phase: This will fail until version update is implemented
		err := config.UpdateVersion("1.1.0")
		
		if err != nil {
			t.Errorf("❌ FORGE FAIL: Failed to update version: %v", err)
		}
		
		if config.Version() != "1.1.0" {
			t.Errorf("❌ FORGE FAIL: Version not updated: expected 1.1.0, got %s",
				config.Version())
		}
		
		t.Logf("✅ FORGE EVIDENCE: Version updated successfully")
	})
}

// Fake domain types - these will fail until real implementation exists
type Configuration struct {
	id          string
	name        string
	description string
	mode        string
	version     string
	labels      map[string]string
	components  []ComponentReference
	createdAt   time.Time
	updatedAt   time.Time
}

type ComponentReference struct {
	Name          string
	Version       string
	Enabled       bool
	Dependencies  []string
	Resources     ResourceRequirements
	Configuration map[string]interface{}
}

type ResourceRequirements struct {
	CPU      string
	Memory   string
	Replicas int
}

type ValidationResult struct {
	Valid  bool
	Errors []string
}

// Fake constructor - will fail until real implementation
func NewConfiguration(id, name, description, mode, version string, labels map[string]string) (*Configuration, error) {
	// FORGE RED PHASE: Return error until implementation exists
	return nil, fmt.Errorf("NewConfiguration not implemented")
}

// Fake methods - will fail until real implementation
func (c *Configuration) ID() string                        { return c.id }
func (c *Configuration) Name() string                      { return c.name }
func (c *Configuration) Description() string               { return c.description }
func (c *Configuration) Mode() string                      { return c.mode }
func (c *Configuration) Version() string                   { return c.version }
func (c *Configuration) Labels() map[string]string         { return c.labels }
func (c *Configuration) Components() []ComponentReference  { return c.components }
func (c *Configuration) CreatedAt() time.Time              { return c.createdAt }
func (c *Configuration) UpdatedAt() time.Time              { return c.updatedAt }

func (c *Configuration) UpdateDescription(description string) error {
	return fmt.Errorf("UpdateDescription not implemented")
}

func (c *Configuration) UpdateLabels(labels map[string]string) error {
	return fmt.Errorf("UpdateLabels not implemented")
}

func (c *Configuration) AddComponent(component ComponentReference) error {
	return fmt.Errorf("AddComponent not implemented")
}

func (c *Configuration) RemoveComponent(name string) error {
	return fmt.Errorf("RemoveComponent not implemented")
}

func (c *Configuration) ValidateForProduction() bool {
	return false // Fail until implemented
}

func (c *Configuration) ValidateDependencies() ValidationResult {
	return ValidationResult{Valid: false, Errors: []string{"ValidateDependencies not implemented"}}
}

func (c *Configuration) IsNewerThan(version string) bool {
	return false // Fail until implemented
}

func (c *Configuration) UpdateVersion(version string) error {
	return fmt.Errorf("UpdateVersion not implemented")
}

// FORGE Domain Test Requirements Summary:
//
// 1. BUSINESS RULE VALIDATION:
//    - Entity creation with comprehensive validation
//    - Domain constraints enforcement (empty fields, invalid values)
//    - Mode-specific business rules (production vs development)
//    - Component dependency validation
//
// 2. ENTITY BEHAVIOR TESTING:
//    - State changes with proper timestamp updates
//    - Aggregate operations (component management)
//    - Version management and comparison
//    - Label management with validation
//
// 3. QUANTITATIVE VALIDATION:
//    - Field-by-field value verification
//    - Collection size validation (labels, components)
//    - Timestamp validation and chronological ordering
//    - Business rule compliance metrics
//
// 4. RED PHASE ENFORCEMENT:
//    - All domain methods return errors/false until implemented
//    - Fake structs ensure compilation but runtime failures
//    - Comprehensive test coverage of all entity methods
//    - Business rule validation triggers test failures
//
// 5. MUTATION TESTING PREPARATION:
//    - Tests validate all entity fields and behaviors
//    - Business rule modifications would trigger failures
//    - State change validation ensures mutation detection
//    - Dependency validation catches business logic mutations