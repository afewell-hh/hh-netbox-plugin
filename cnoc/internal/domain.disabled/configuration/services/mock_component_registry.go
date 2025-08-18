package services

import (
	"fmt"

	"github.com/hedgehog/cnoc/internal/domain/configuration"
	"github.com/hedgehog/cnoc/internal/domain/shared"
)

// mustParseVersion parses a version string and panics on error (for testing/initialization only)
func mustParseVersion(version string) shared.Version {
	v, err := shared.NewVersion(version)
	if err != nil {
		panic(fmt.Sprintf("invalid version %s: %v", version, err))
	}
	return v
}

// mustParseComponentName parses a component name and panics on error (for testing/initialization only)
func mustParseComponentName(name string) configuration.ComponentName {
	cn, err := configuration.NewComponentName(name)
	if err != nil {
		panic(fmt.Sprintf("invalid component name %s: %v", name, err))
	}
	return cn
}

// mustParseVersionConstraint parses a version constraint and panics on error (for testing/initialization only)
func mustParseVersionConstraint(constraint string) shared.VersionConstraint {
	vc, err := shared.NewVersionConstraint(constraint)
	if err != nil {
		panic(fmt.Sprintf("invalid version constraint %s: %v", constraint, err))
	}
	return vc
}

// MockComponentRegistry provides a mock implementation of ComponentRegistry for testing and development
type MockComponentRegistry struct {
	components map[configuration.ComponentName]*ComponentInfo
}

// NewMockComponentRegistry creates a new mock component registry with default components
func NewMockComponentRegistry() *MockComponentRegistry {
	registry := &MockComponentRegistry{
		components: make(map[configuration.ComponentName]*ComponentInfo),
	}
	
	// Populate with default components for testing
	registry.populateDefaultComponents()
	
	return registry
}

// Exists checks if a component exists in the registry
func (r *MockComponentRegistry) Exists(name configuration.ComponentName) bool {
	_, exists := r.components[name]
	return exists
}

// GetVersion retrieves the version for a component
func (r *MockComponentRegistry) GetVersion(name configuration.ComponentName) (shared.Version, error) {
	component, exists := r.components[name]
	if !exists {
		return shared.Version{}, fmt.Errorf("component %s not found", name)
	}
	
	return component.LatestVersion, nil
}

// GetDependencies retrieves dependencies for a component
func (r *MockComponentRegistry) GetDependencies(name configuration.ComponentName) ([]DependencyRequirement, error) {
	component, exists := r.components[name]
	if !exists {
		return nil, fmt.Errorf("component %s not found", name)
	}
	
	return component.Dependencies, nil
}

// GetComponentInfo retrieves detailed component information
func (r *MockComponentRegistry) GetComponentInfo(name configuration.ComponentName) (*ComponentInfo, error) {
	component, exists := r.components[name]
	if !exists {
		return nil, fmt.Errorf("component %s not found", name)
	}
	
	// Return a copy to prevent modification
	infoCopy := *component
	return &infoCopy, nil
}

// ListAvailable returns all available components
func (r *MockComponentRegistry) ListAvailable() ([]configuration.ComponentName, error) {
	names := make([]configuration.ComponentName, 0, len(r.components))
	for name := range r.components {
		names = append(names, name)
	}
	
	return names, nil
}

// ValidateComponent validates component configuration
func (r *MockComponentRegistry) ValidateComponent(name configuration.ComponentName, config map[string]interface{}) error {
	if !r.Exists(name) {
		return fmt.Errorf("component %s not found", name)
	}
	
	// Basic validation - in production this would validate against component schema
	if config == nil {
		return fmt.Errorf("component configuration cannot be nil")
	}
	
	// Check for required configuration fields based on component
	kubernetesName, _ := configuration.NewComponentName("kubernetes")
	argocdName, _ := configuration.NewComponentName("argocd")
	prometheusName, _ := configuration.NewComponentName("prometheus")
	
	switch name {
	case kubernetesName:
		if _, exists := config["cluster_name"]; !exists {
			return fmt.Errorf("kubernetes component requires cluster_name configuration")
		}
	case argocdName:
		if _, exists := config["server_url"]; !exists {
			return fmt.Errorf("argocd component requires server_url configuration")
		}
	case prometheusName:
		if _, exists := config["retention"]; !exists {
			return fmt.Errorf("prometheus component requires retention configuration")
		}
	}
	
	return nil
}

// GetDefaultConfiguration returns default configuration for a component
func (r *MockComponentRegistry) GetDefaultConfiguration(name configuration.ComponentName) (map[string]interface{}, error) {
	if !r.Exists(name) {
		return nil, fmt.Errorf("component %s not found", name)
	}
	
	// Return default configurations for known components
	kubernetesName, _ := configuration.NewComponentName("kubernetes")
	argocdName, _ := configuration.NewComponentName("argocd") 
	prometheusName, _ := configuration.NewComponentName("prometheus")
	grafanaName, _ := configuration.NewComponentName("grafana")
	certManagerName, _ := configuration.NewComponentName("cert-manager")
	veleroName, _ := configuration.NewComponentName("velero")
	
	defaults := map[configuration.ComponentName]map[string]interface{}{
		kubernetesName: {
			"cluster_name":      "cnoc-cluster",
			"node_count":        3,
			"kubernetes_version": "1.28",
			"network_plugin":    "cilium",
		},
		argocdName: {
			"server_url":     "https://argocd.example.com",
			"admin_enabled":  true,
			"dex_enabled":    true,
			"rbac_enabled":   true,
		},
		prometheusName: {
			"retention":           "30d",
			"storage_size":        "10Gi",
			"scrape_interval":     "15s",
			"evaluation_interval": "15s",
		},
		grafanaName: {
			"admin_password": "admin",
			"persistence":    true,
			"storage_size":   "5Gi",
			"plugins":        []string{"grafana-piechart-panel"},
		},
		certManagerName: {
			"cluster_issuer": "letsencrypt-prod",
			"dns_provider":   "cloudflare",
			"webhook":        true,
		},
		veleroName: {
			"provider":      "aws",
			"bucket_name":   "cnoc-backups",
			"schedule":      "0 1 * * *",
		},
	}
	
	if config, exists := defaults[name]; exists {
		return config, nil
	}
	
	// Return generic default for unknown components
	return map[string]interface{}{
		"enabled": true,
	}, nil
}

// Helper method to populate default components
func (r *MockComponentRegistry) populateDefaultComponents() {
	// Kubernetes
	kubernetesName, _ := configuration.NewComponentName("kubernetes")
	r.components[kubernetesName] = &ComponentInfo{
		Name:          kubernetesName,
		LatestVersion: mustParseVersion("1.28.0"),
		AvailableVersions: []shared.Version{
			mustParseVersion("1.26.0"),
			mustParseVersion("1.27.0"),
			mustParseVersion("1.28.0"),
		},
		Description: "Kubernetes container orchestration platform",
		Category:    "orchestration",
		Dependencies: []DependencyRequirement{
			{
				ComponentName:     mustParseComponentName("containerd"),
				VersionConstraint: mustParseVersionConstraint(">=1.6.0"),
				Optional:          false,
				Reason:           "Container runtime required for Kubernetes",
			},
		},
		Resources: DefaultResourceRequirements{
			MinCPU:    "2",
			MinMemory: "4Gi",
			MaxCPU:    "8",
			MaxMemory: "16Gi",
			Storage:   "20Gi",
		},
		Documentation: DocumentationLinks{
			Homepage:      "https://kubernetes.io",
			Documentation: "https://kubernetes.io/docs",
			Repository:    "https://github.com/kubernetes/kubernetes",
		},
		Maturity: MaturityStable,
		SupportedModes: []configuration.ConfigurationMode{
			configuration.ModeEnterprise,
			configuration.ModeMinimal,
		},
	}
	
	// ArgoCD
	argocdName, _ := configuration.NewComponentName("argocd")
	r.components[argocdName] = &ComponentInfo{
		Name:          argocdName,
		LatestVersion: mustParseVersion("2.8.4"),
		AvailableVersions: []shared.Version{
			mustParseVersion("2.6.0"),
			mustParseVersion("2.7.0"),
			mustParseVersion("2.8.4"),
		},
		Description: "Declarative continuous delivery for Kubernetes",
		Category:    "gitops",
		Dependencies: []DependencyRequirement{
			{
				ComponentName:     mustParseComponentName("kubernetes"),
				VersionConstraint: mustParseVersionConstraint(">=1.22.0"),
				Optional:          false,
				Reason:           "Kubernetes cluster required for ArgoCD",
			},
		},
		Resources: DefaultResourceRequirements{
			MinCPU:    "1",
			MinMemory: "2Gi",
			MaxCPU:    "4",
			MaxMemory: "8Gi",
			Storage:   "5Gi",
		},
		Documentation: DocumentationLinks{
			Homepage:      "https://argo-cd.readthedocs.io",
			Documentation: "https://argo-cd.readthedocs.io/en/stable",
			Repository:    "https://github.com/argoproj/argo-cd",
		},
		Maturity: MaturityStable,
		SupportedModes: []configuration.ConfigurationMode{
			configuration.ModeEnterprise,
			configuration.ModeMinimal,
		},
	}
	
	// Prometheus
	prometheusName, _ := configuration.NewComponentName("prometheus")
	r.components[prometheusName] = &ComponentInfo{
		Name:          prometheusName,
		LatestVersion: mustParseVersion("2.45.0"),
		AvailableVersions: []shared.Version{
			mustParseVersion("2.40.0"),
			mustParseVersion("2.42.0"),
			mustParseVersion("2.45.0"),
		},
		Description: "Monitoring system and time series database",
		Category:    "monitoring",
		Dependencies: []DependencyRequirement{
			{
				ComponentName:     mustParseComponentName("kubernetes"),
				VersionConstraint: mustParseVersionConstraint(">=1.20.0"),
				Optional:          false,
				Reason:           "Kubernetes cluster required for Prometheus",
			},
		},
		Resources: DefaultResourceRequirements{
			MinCPU:    "1",
			MinMemory: "2Gi",
			MaxCPU:    "4",
			MaxMemory: "16Gi",
			Storage:   "50Gi",
		},
		Documentation: DocumentationLinks{
			Homepage:      "https://prometheus.io",
			Documentation: "https://prometheus.io/docs",
			Repository:    "https://github.com/prometheus/prometheus",
		},
		Maturity: MaturityStable,
		SupportedModes: []configuration.ConfigurationMode{
			configuration.ModeEnterprise,
			configuration.ModeMinimal,
		},
	}
	
	// Add more components as needed...
}

// AddComponent adds a new component to the registry (for testing)
func (r *MockComponentRegistry) AddComponent(info *ComponentInfo) {
	r.components[info.Name] = info
}

// RemoveComponent removes a component from the registry (for testing)
func (r *MockComponentRegistry) RemoveComponent(name configuration.ComponentName) {
	delete(r.components, name)
}