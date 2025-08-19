package domain

import (
	"fmt"
	"testing"

	"github.com/hedgehog/cnoc/internal/domain/configuration"
	"github.com/hedgehog/cnoc/internal/domain/shared"
)

// FORGE Movement 1: Enterprise Policy Enforcement Test Suite
//
// CRITICAL: This is RED PHASE testing - ALL tests MUST FAIL initially
// Tests validate enterprise policy enforcement and compliance rules
// Verifies security compliance, component policies, and governance frameworks

// TestEnterpriseConfigurationPolicies validates enterprise-specific configuration constraints
func TestEnterpriseConfigurationPolicies(t *testing.T) {
	t.Run("Enterprise Mode Component Requirements", func(t *testing.T) {
		// FORGE RED PHASE: This MUST fail until enterprise policies are implemented
		
		// Create enterprise configuration
		configID, _ := configuration.NewConfigurationID("enterprise-policy-test")
		configName, _ := configuration.NewConfigurationName("Enterprise Policy Test")
		version, _ := shared.NewVersion("1.0.0")
		metadata := configuration.NewConfigurationMetadata(
			"Enterprise configuration with policy enforcement",
			map[string]string{
				"compliance.cnoc.io/framework": "SOC2",
				"security.cnoc.io/level":      "high",
			},
			map[string]string{
				"policy.cnoc.io/audit-required": "true",
				"governance.cnoc.io/review":     "mandatory",
			},
		)
		
		// Add enterprise configuration settings
		enterpriseConfig, err := configuration.NewEnterpriseConfiguration(
			"SOC2",           // compliance framework
			"high",           // security level
			true,             // audit enabled
			true,             // encryption required
			true,             // backup required
			[]string{         // policy templates
				"security-baseline",
				"compliance-monitoring",
				"audit-logging",
			},
			map[string]string{
				"retention.policy": "7years",
				"encryption.type":  "AES256",
			},
		)
		if err != nil {
			t.Fatalf("❌ FORGE FAIL: Enterprise configuration creation failed: %v", err)
		}
		
		metadata.SetEnterpriseConfig(enterpriseConfig)
		
		config := configuration.NewConfiguration(
			configID,
			configName,
			version,
			configuration.ModeEnterprise,
			metadata,
		)
		
		// ENTERPRISE POLICY TEST: Validate mandatory enterprise components
		requiredComponents := []struct {
			name    string
			version string
			reason  string
		}{
			{"cert-manager", "1.12.0", "TLS certificate management required for enterprise"},
			{"argocd", "2.8.0", "GitOps deployment management required for enterprise"},
			{"prometheus", "2.45.0", "Monitoring and alerting required for enterprise"},
			{"grafana", "9.5.0", "Observability dashboard required for enterprise"},
		}
		
		for _, req := range requiredComponents {
			componentName, _ := configuration.NewComponentName(req.name)
			componentVersion, _ := shared.NewVersion(req.version)
			component := configuration.NewComponentReference(componentName, componentVersion, true)
			
			err := config.AddComponent(component)
			if err != nil {
				t.Errorf("❌ FORGE FAIL: Failed to add required enterprise component %s: %v", req.name, err)
			}
		}
		
		// Validate enterprise policy compliance
		validationResult := config.ValidateIntegrity()
		if !validationResult.Valid {
			t.Errorf("❌ FORGE FAIL: Enterprise configuration failed validation: %v", validationResult.Errors)
		}
		
		// ENTERPRISE POLICY TEST: Validate enterprise-specific constraints
		enterpriseValidation := config.ValidateEnterpriseCompliance()
		if !enterpriseValidation.Valid {
			t.Errorf("❌ FORGE FAIL: Enterprise compliance validation failed: %v", enterpriseValidation.Errors)
		}
		
		// Validate required enterprise metadata
		if !enterpriseConfig.AuditEnabled() {
			t.Errorf("❌ FORGE FAIL: Audit must be enabled for enterprise configuration")
		}
		
		if !enterpriseConfig.EncryptionRequired() {
			t.Errorf("❌ FORGE FAIL: Encryption must be required for enterprise configuration")
		}
		
		if !enterpriseConfig.BackupRequired() {
			t.Errorf("❌ FORGE FAIL: Backup must be required for enterprise configuration")
		}
		
		if enterpriseConfig.ComplianceFramework() != "SOC2" {
			t.Errorf("❌ FORGE FAIL: Compliance framework mismatch")
		}
		
		t.Logf("✅ FORGE EVIDENCE: Enterprise configuration policies enforced")
	})
	
	t.Run("Security Level Constraints", func(t *testing.T) {
		// FORGE RED PHASE: Security level constraints must fail until implementation
		
		// Test different security levels and their constraints
		securityLevels := []struct {
			level           string
			encryptionReq   bool
			auditReq        bool
			backupReq       bool
			allowedComponents []string
			blockedComponents []string
		}{
			{
				level:         "high",
				encryptionReq: true,
				auditReq:      true,
				backupReq:     true,
				allowedComponents: []string{"argocd", "prometheus", "grafana", "cert-manager"},
				blockedComponents: []string{"development-tools", "debug-utilities"},
			},
			{
				level:         "medium",
				encryptionReq: true,
				auditReq:      false,
				backupReq:     true,
				allowedComponents: []string{"argocd", "prometheus", "grafana"},
				blockedComponents: []string{"development-tools"},
			},
			{
				level:         "low",
				encryptionReq: false,
				auditReq:      false,
				backupReq:     false,
				allowedComponents: []string{"argocd", "prometheus"},
				blockedComponents: []string{},
			},
		}
		
		for _, secLevel := range securityLevels {
			t.Run(fmt.Sprintf("Security Level %s", secLevel.level), func(t *testing.T) {
				configID, _ := configuration.NewConfigurationID(fmt.Sprintf("security-%s-test", secLevel.level))
				configName, _ := configuration.NewConfigurationName(fmt.Sprintf("Security Level %s Test", secLevel.level))
				version, _ := shared.NewVersion("1.0.0")
				
				enterpriseConfig, _ := configuration.NewEnterpriseConfiguration(
					"SOC2",
					secLevel.level,
					secLevel.auditReq,
					secLevel.encryptionReq,
					secLevel.backupReq,
					[]string{"security-baseline"},
					map[string]string{},
				)
				
				metadata := configuration.NewConfigurationMetadata("Security level test", nil, nil)
				metadata.SetEnterpriseConfig(enterpriseConfig)
				
				config := configuration.NewConfiguration(
					configID,
					configName,
					version,
					configuration.ModeEnterprise,
					metadata,
				)
				
				// SECURITY POLICY TEST: Validate allowed components can be added
				for _, allowedComp := range secLevel.allowedComponents {
					componentName, _ := configuration.NewComponentName(allowedComp)
					componentVersion, _ := shared.NewVersion("1.0.0")
					component := configuration.NewComponentReference(componentName, componentVersion, true)
					
					err := config.AddComponent(component)
					if err != nil {
						t.Errorf("❌ FORGE FAIL: Allowed component %s rejected for security level %s: %v", allowedComp, secLevel.level, err)
					}
				}
				
				// SECURITY POLICY TEST: Validate blocked components are rejected
				for _, blockedComp := range secLevel.blockedComponents {
					componentName, _ := configuration.NewComponentName(blockedComp)
					componentVersion, _ := shared.NewVersion("1.0.0")
					component := configuration.NewComponentReference(componentName, componentVersion, true)
					
					err := config.AddComponent(component)
					if err == nil {
						t.Errorf("❌ FORGE FAIL: Blocked component %s accepted for security level %s", blockedComp, secLevel.level)
					}
				}
				
				// Validate security constraints
				securityValidation := config.ValidateSecurityConstraints()
				if !securityValidation.Valid {
					t.Errorf("❌ FORGE FAIL: Security constraint validation failed for level %s: %v", secLevel.level, securityValidation.Errors)
				}
			})
		}
		
		t.Logf("✅ FORGE EVIDENCE: Security level constraints enforced")
	})
	
	t.Run("Compliance Framework Validation", func(t *testing.T) {
		// FORGE RED PHASE: Compliance framework validation must fail until implementation
		
		complianceFrameworks := []struct {
			framework    string
			requirements []ComplianceRequirement
			policies     []string
		}{
			{
				framework: "SOC2",
				requirements: []ComplianceRequirement{
					{Type: "audit-logging", Mandatory: true},
					{Type: "encryption-at-rest", Mandatory: true},
					{Type: "access-control", Mandatory: true},
					{Type: "backup-retention", Mandatory: true},
				},
				policies: []string{
					"audit-policy",
					"encryption-policy",
					"access-control-policy",
				},
			},
			{
				framework: "FedRAMP",
				requirements: []ComplianceRequirement{
					{Type: "continuous-monitoring", Mandatory: true},
					{Type: "vulnerability-scanning", Mandatory: true},
					{Type: "incident-response", Mandatory: true},
					{Type: "encryption-in-transit", Mandatory: true},
				},
				policies: []string{
					"fedramp-baseline",
					"continuous-monitoring-policy",
					"incident-response-policy",
				},
			},
			{
				framework: "HIPAA",
				requirements: []ComplianceRequirement{
					{Type: "data-encryption", Mandatory: true},
					{Type: "access-audit", Mandatory: true},
					{Type: "data-retention", Mandatory: true},
					{Type: "breach-notification", Mandatory: true},
				},
				policies: []string{
					"hipaa-safeguards",
					"data-protection-policy",
					"breach-response-policy",
				},
			},
		}
		
		for _, framework := range complianceFrameworks {
			t.Run(fmt.Sprintf("Framework %s", framework.framework), func(t *testing.T) {
				configID, _ := configuration.NewConfigurationID(fmt.Sprintf("compliance-%s-test", framework.framework))
				configName, _ := configuration.NewConfigurationName(fmt.Sprintf("Compliance %s Test", framework.framework))
				version, _ := shared.NewVersion("1.0.0")
				
				enterpriseConfig, _ := configuration.NewEnterpriseConfiguration(
					framework.framework,
					"high",
					true,
					true,
					true,
					framework.policies,
					map[string]string{
						"compliance.framework": framework.framework,
					},
				)
				
				metadata := configuration.NewConfigurationMetadata("Compliance test", nil, nil)
				metadata.SetEnterpriseConfig(enterpriseConfig)
				
				config := configuration.NewConfiguration(
					configID,
					configName,
					version,
					configuration.ModeEnterprise,
					metadata,
				)
				
				// COMPLIANCE POLICY TEST: Validate framework-specific requirements
				complianceValidation := config.ValidateComplianceFramework(framework.framework)
				if !complianceValidation.Valid {
					t.Errorf("❌ FORGE FAIL: Compliance framework validation failed for %s: %v", framework.framework, complianceValidation.Errors)
				}
				
				// Validate each compliance requirement
				for _, req := range framework.requirements {
					isCompliant := config.IsCompliantWithRequirement(req.Type)
					if req.Mandatory && !isCompliant {
						t.Errorf("❌ FORGE FAIL: Mandatory compliance requirement %s not met for framework %s", req.Type, framework.framework)
					}
				}
				
				// Validate policy templates are applied
				policyTemplates := enterpriseConfig.PolicyTemplates()
				for _, expectedPolicy := range framework.policies {
					found := false
					for _, appliedPolicy := range policyTemplates {
						if appliedPolicy == expectedPolicy {
							found = true
							break
						}
					}
					if !found {
						t.Errorf("❌ FORGE FAIL: Required policy template %s not applied for framework %s", expectedPolicy, framework.framework)
					}
				}
			})
		}
		
		t.Logf("✅ FORGE EVIDENCE: Compliance framework validation working")
	})
}

// TestComponentSecurityPolicies validates component-specific security policies
func TestComponentSecurityPolicies(t *testing.T) {
	t.Run("Component Security Classification", func(t *testing.T) {
		// FORGE RED PHASE: Component security classification must fail until implementation
		
		// Define component security classifications
		componentSecurityLevels := map[string]struct {
			level            string
			encryptionReq    bool
			networkPolicies  bool
			resourceLimits   bool
			securityContext  bool
			allowedModes     []configuration.ConfigurationMode
		}{
			"argocd": {
				level:            "high",
				encryptionReq:    true,
				networkPolicies:  true,
				resourceLimits:   true,
				securityContext:  true,
				allowedModes:     []configuration.ConfigurationMode{configuration.ModeEnterprise},
			},
			"prometheus": {
				level:            "medium",
				encryptionReq:    true,
				networkPolicies:  true,
				resourceLimits:   true,
				securityContext:  true,
				allowedModes:     []configuration.ConfigurationMode{configuration.ModeEnterprise, configuration.ModeDevelopment},
			},
			"grafana": {
				level:            "medium",
				encryptionReq:    false,
				networkPolicies:  true,
				resourceLimits:   false,
				securityContext:  true,
				allowedModes:     []configuration.ConfigurationMode{configuration.ModeEnterprise, configuration.ModeDevelopment},
			},
			"development-tools": {
				level:            "low",
				encryptionReq:    false,
				networkPolicies:  false,
				resourceLimits:   false,
				securityContext:  false,
				allowedModes:     []configuration.ConfigurationMode{configuration.ModeDevelopment},
			},
		}
		
		for componentName, secLevel := range componentSecurityLevels {
			t.Run(fmt.Sprintf("Component %s Security", componentName), func(t *testing.T) {
				// Test component security validation
				compName, _ := configuration.NewComponentName(componentName)
				compVersion, _ := shared.NewVersion("1.0.0")
				component := configuration.NewComponentReference(compName, compVersion, true)
				
				// COMPONENT SECURITY TEST: Validate security requirements are enforced
				securityValidation := component.ValidateSecurityRequirements()
				if !securityValidation.Valid {
					t.Errorf("❌ FORGE FAIL: Component security validation failed for %s: %v", componentName, securityValidation.Errors)
				}
				
				// Test configuration mode compatibility
				for _, mode := range []configuration.ConfigurationMode{
					configuration.ModeEnterprise,
					configuration.ModeDevelopment,
					configuration.ModeMinimal,
				} {
					configID, _ := configuration.NewConfigurationID(fmt.Sprintf("security-test-%s-%s", componentName, mode.String()))
					configName, _ := configuration.NewConfigurationName(fmt.Sprintf("Security Test %s", componentName))
					version, _ := shared.NewVersion("1.0.0")
					metadata := configuration.NewConfigurationMetadata("Security test", nil, nil)
					
					config := configuration.NewConfiguration(
						configID,
						configName,
						version,
						mode,
						metadata,
					)
					
					err := config.AddComponent(component)
					
					// Check if mode is allowed for this component
					modeAllowed := false
					for _, allowedMode := range secLevel.allowedModes {
						if mode == allowedMode {
							modeAllowed = true
							break
						}
					}
					
					if modeAllowed && err != nil {
						t.Errorf("❌ FORGE FAIL: Component %s should be allowed in mode %s but was rejected: %v", componentName, mode.String(), err)
					}
					
					if !modeAllowed && err == nil {
						t.Errorf("❌ FORGE FAIL: Component %s should be blocked in mode %s but was accepted", componentName, mode.String())
					}
				}
				
				// Validate component-specific security requirements
				if secLevel.encryptionReq {
					if !component.IsEncryptionRequired() {
						t.Errorf("❌ FORGE FAIL: Component %s should require encryption", componentName)
					}
				}
				
				if secLevel.networkPolicies {
					if !component.RequiresNetworkPolicies() {
						t.Errorf("❌ FORGE FAIL: Component %s should require network policies", componentName)
					}
				}
				
				if secLevel.resourceLimits {
					if !component.RequiresResourceLimits() {
						t.Errorf("❌ FORGE FAIL: Component %s should require resource limits", componentName)
					}
				}
				
				if secLevel.securityContext {
					if !component.RequiresSecurityContext() {
						t.Errorf("❌ FORGE FAIL: Component %s should require security context", componentName)
					}
				}
			})
		}
		
		t.Logf("✅ FORGE EVIDENCE: Component security classification working")
	})
	
	t.Run("Component Dependency Security Validation", func(t *testing.T) {
		// FORGE RED PHASE: Component dependency security must fail until implementation
		
		configID, _ := configuration.NewConfigurationID("dependency-security-test")
		configName, _ := configuration.NewConfigurationName("Dependency Security Test")
		version, _ := shared.NewVersion("1.0.0")
		metadata := configuration.NewConfigurationMetadata("Dependency security test", nil, nil)
		
		config := configuration.NewConfiguration(
			configID,
			configName,
			version,
			configuration.ModeEnterprise,
			metadata,
		)
		
		// Test secure dependency chain: ArgoCD -> cert-manager (both high security)
		certManagerName, _ := configuration.NewComponentName("cert-manager")
		certManagerVersion, _ := shared.NewVersion("1.12.0")
		certManager := configuration.NewComponentReference(certManagerName, certManagerVersion, true)
		
		argoCDName, _ := configuration.NewComponentName("argocd")
		argoCDVersion, _ := shared.NewVersion("2.8.0")
		argoCD := configuration.NewComponentReference(argoCDName, argoCDVersion, true)
		
		// Add components in dependency order
		err := config.AddComponent(certManager)
		if err != nil {
			t.Errorf("❌ FORGE FAIL: Failed to add cert-manager: %v", err)
		}
		
		err = config.AddComponent(argoCD)
		if err != nil {
			t.Errorf("❌ FORGE FAIL: Failed to add ArgoCD: %v", err)
		}
		
		// DEPENDENCY SECURITY TEST: Validate dependency security constraints
		dependencyValidation := config.ValidateDependencySecurityConstraints()
		if !dependencyValidation.Valid {
			t.Errorf("❌ FORGE FAIL: Dependency security validation failed: %v", dependencyValidation.Errors)
		}
		
		// Test insecure dependency (high security component depending on low security)
		// This should fail validation
		devToolsName, _ := configuration.NewComponentName("development-tools")
		devToolsVersion, _ := shared.NewVersion("1.0.0")
		devTools := configuration.NewComponentReference(devToolsName, devToolsVersion, true)
		
		// Create modified ArgoCD that depends on development tools (should fail)
		insecureArgoCD := argoCD.Clone()
		insecureArgoCD.AddDependency("development-tools")
		
		// Add development tools first
		config2ID, _ := configuration.NewConfigurationID("insecure-dependency-test")
		config2Name, _ := configuration.NewConfigurationName("Insecure Dependency Test")
		config2 := configuration.NewConfiguration(
			config2ID,
			config2Name,
			version,
			configuration.ModeDevelopment, // Allow dev tools in development mode
			metadata,
		)
		
		err = config2.AddComponent(devTools)
		if err != nil {
			t.Errorf("❌ FORGE FAIL: Failed to add development tools: %v", err)
		}
		
		err = config2.AddComponent(insecureArgoCD)
		if err != nil {
			t.Errorf("❌ FORGE FAIL: Failed to add insecure ArgoCD: %v", err)
		}
		
		// Validate dependency security constraint violation
		insecureDependencyValidation := config2.ValidateDependencySecurityConstraints()
		if insecureDependencyValidation.Valid {
			t.Errorf("❌ FORGE FAIL: Expected dependency security validation to fail for insecure dependency")
		}
		
		t.Logf("✅ FORGE EVIDENCE: Component dependency security validation working")
	})
}

// TestTemplateEngineValidation validates template engine security and policy enforcement
func TestTemplateEngineValidation(t *testing.T) {
	t.Run("Template Security Validation", func(t *testing.T) {
		// FORGE RED PHASE: Template engine validation must fail until implementation
		
		// Test secure template patterns
		secureTemplates := []struct {
			name     string
			template string
			valid    bool
			reason   string
		}{
			{
				name:     "Secure Resource Template",
				template: `{{ .component.name }}-{{ .component.version }}`,
				valid:    true,
				reason:   "Uses whitelisted template variables",
			},
			{
				name:     "Secure Configuration Template", 
				template: `replicas: {{ .component.resources.replicas }}`,
				valid:    true,
				reason:   "Uses resource configuration variables",
			},
			{
				name:     "Insecure System Template",
				template: `{{ system("rm -rf /") }}`,
				valid:    false,
				reason:   "Contains system command execution",
			},
			{
				name:     "Insecure File Access Template",
				template: `{{ .Files.Get "/etc/passwd" }}`,
				valid:    false,
				reason:   "Attempts to access system files",
			},
			{
				name:     "Insecure Network Template",
				template: `{{ httpGet "http://malicious.com/data" }}`,
				valid:    false,
				reason:   "Attempts external network access",
			},
		}
		
		templateValidator := NewTemplateValidator()
		
		for _, tmpl := range secureTemplates {
			t.Run(tmpl.name, func(t *testing.T) {
				// TEMPLATE SECURITY TEST: Validate template security constraints
				validationResult := templateValidator.ValidateTemplate(tmpl.template)
				
				if tmpl.valid && !validationResult.Valid {
					t.Errorf("❌ FORGE FAIL: Secure template %s rejected: %v", tmpl.name, validationResult.Errors)
				}
				
				if !tmpl.valid && validationResult.Valid {
					t.Errorf("❌ FORGE FAIL: Insecure template %s accepted: %s", tmpl.name, tmpl.reason)
				}
				
				// Validate security constraints are checked
				if !tmpl.valid {
					securityViolationFound := false
					for _, error := range validationResult.Errors {
						if error.Code == "SECURITY_VIOLATION" {
							securityViolationFound = true
							break
						}
					}
					if !securityViolationFound {
						t.Errorf("❌ FORGE FAIL: Security violation not detected for template %s", tmpl.name)
					}
				}
			})
		}
		
		t.Logf("✅ FORGE EVIDENCE: Template security validation working")
	})
	
	t.Run("Template Policy Enforcement", func(t *testing.T) {
		// FORGE RED PHASE: Template policy enforcement must fail until implementation
		
		// Test policy-based template validation
		policyTemplates := []struct {
			policy   string
			template string
			allowed  bool
		}{
			{
				policy:   "enterprise-security",
				template: `{{ .component.name }}: {{ .component.version }}`,
				allowed:  true,
			},
			{
				policy:   "enterprise-security",
				template: `debug: {{ .debug.enabled }}`,
				allowed:  false, // Debug templates not allowed in enterprise
			},
			{
				policy:   "development-flexibility",
				template: `debug: {{ .debug.enabled }}`,
				allowed:  true, // Debug templates allowed in development
			},
			{
				policy:   "minimal-resources",
				template: `cpu: {{ .component.resources.cpu }}`,
				allowed:  true,
			},
			{
				policy:   "minimal-resources",
				template: `gpu: {{ .component.resources.gpu }}`,
				allowed:  false, // GPU resources not allowed in minimal mode
			},
		}
		
		templateValidator := NewTemplateValidator()
		
		for _, pt := range policyTemplates {
			t.Run(fmt.Sprintf("Policy %s", pt.policy), func(t *testing.T) {
				// TEMPLATE POLICY TEST: Validate policy-based template restrictions
				policyResult := templateValidator.ValidateTemplateWithPolicy(pt.template, pt.policy)
				
				if pt.allowed && !policyResult.Valid {
					t.Errorf("❌ FORGE FAIL: Template should be allowed under policy %s but was rejected: %v", pt.policy, policyResult.Errors)
				}
				
				if !pt.allowed && policyResult.Valid {
					t.Errorf("❌ FORGE FAIL: Template should be blocked under policy %s but was accepted", pt.policy)
				}
			})
		}
		
		t.Logf("✅ FORGE EVIDENCE: Template policy enforcement working")
	})
}

// Mock types for enterprise policy testing

type ComplianceRequirement struct {
	Type      string `json:"type"`
	Mandatory bool   `json:"mandatory"`
}

type SecurityValidationResult struct {
	Valid  bool                    `json:"valid"`
	Errors []SecurityValidationError `json:"errors"`
}

type SecurityValidationError struct {
	Code    string `json:"code"`
	Message string `json:"message"`
	Field   string `json:"field"`
}

type ComplianceValidationResult struct {
	Valid  bool                         `json:"valid"`
	Errors []ComplianceValidationError  `json:"errors"`
}

type ComplianceValidationError struct {
	RequirementType string `json:"requirement_type"`
	Message        string `json:"message"`
	Severity       string `json:"severity"`
}

type TemplateValidationResult struct {
	Valid  bool                       `json:"valid"`
	Errors []TemplateValidationError  `json:"errors"`
}

type TemplateValidationError struct {
	Code    string `json:"code"`
	Message string `json:"message"`
	Line    int    `json:"line"`
}

type TemplateValidator struct {
	policies map[string]TemplatePolicy
}

type TemplatePolicy struct {
	AllowedFunctions []string `json:"allowed_functions"`
	BlockedPatterns  []string `json:"blocked_patterns"`
	RequiredChecks   []string `json:"required_checks"`
}

func NewTemplateValidator() *TemplateValidator {
	return &TemplateValidator{
		policies: map[string]TemplatePolicy{
			"enterprise-security": {
				AllowedFunctions: []string{"component", "resources", "metadata"},
				BlockedPatterns:  []string{"system", "exec", "debug", "Files.Get"},
				RequiredChecks:   []string{"security-context", "resource-limits"},
			},
			"development-flexibility": {
				AllowedFunctions: []string{"component", "resources", "metadata", "debug"},
				BlockedPatterns:  []string{"system", "exec", "Files.Get"},
				RequiredChecks:   []string{},
			},
			"minimal-resources": {
				AllowedFunctions: []string{"component", "resources.cpu", "resources.memory"},
				BlockedPatterns:  []string{"gpu", "storage", "system"},
				RequiredChecks:   []string{"resource-efficiency"},
			},
		},
	}
}

func (tv *TemplateValidator) ValidateTemplate(template string) TemplateValidationResult {
	// FORGE RED PHASE: Return error until implementation exists
	return TemplateValidationResult{
		Valid: false,
		Errors: []TemplateValidationError{
			{Code: "NOT_IMPLEMENTED", Message: "Template validation not implemented"},
		},
	}
}

func (tv *TemplateValidator) ValidateTemplateWithPolicy(template, policy string) TemplateValidationResult {
	// FORGE RED PHASE: Return error until implementation exists
	return TemplateValidationResult{
		Valid: false,
		Errors: []TemplateValidationError{
			{Code: "NOT_IMPLEMENTED", Message: "Template policy validation not implemented"},
		},
	}
}

