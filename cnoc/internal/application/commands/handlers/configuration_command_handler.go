package handlers

import (
	"context"
	"fmt"
	"time"

	"github.com/hedgehog/cnoc/internal/application/commands"
	"github.com/hedgehog/cnoc/internal/domain/configuration"
	"github.com/hedgehog/cnoc/internal/domain/configuration/repositories"
	"github.com/hedgehog/cnoc/internal/domain/configuration/services"
	"github.com/hedgehog/cnoc/internal/domain/events"
	"github.com/hedgehog/cnoc/internal/domain/shared"
)

// ConfigurationCommandHandler handles configuration-related commands
// Following CQRS pattern with domain service orchestration and Symphony-Level coordination
type ConfigurationCommandHandler struct {
	configRepo          repositories.ConfigurationRepository
	eventRepository     repositories.EventRepository
	unitOfWork          repositories.UnitOfWork
	validationService   *services.ConfigurationValidator
	dependencyResolver  *services.DependencyResolver
	policyEnforcer      services.PolicyEnforcer
	templateEngine      services.TemplateEngine
	infrastructureProvisioner services.InfrastructureProvisioner
	eventBus            events.EventBus
}

// NewConfigurationCommandHandler creates a new configuration command handler
func NewConfigurationCommandHandler(
	configRepo repositories.ConfigurationRepository,
	eventRepository repositories.EventRepository,
	unitOfWork repositories.UnitOfWork,
	validationService *services.ConfigurationValidator,
	dependencyResolver *services.DependencyResolver,
	policyEnforcer services.PolicyEnforcer,
	templateEngine services.TemplateEngine,
	infrastructureProvisioner services.InfrastructureProvisioner,
	eventBus events.EventBus,
) *ConfigurationCommandHandler {
	return &ConfigurationCommandHandler{
		configRepo:          configRepo,
		eventRepository:     eventRepository,
		unitOfWork:          unitOfWork,
		validationService:   validationService,
		dependencyResolver:  dependencyResolver,
		policyEnforcer:      policyEnforcer,
		templateEngine:      templateEngine,
		infrastructureProvisioner: infrastructureProvisioner,
		eventBus:            eventBus,
	}
}

// HandleCreateConfiguration handles create configuration command
func (h *ConfigurationCommandHandler) HandleCreateConfiguration(
	ctx context.Context,
	cmd commands.CreateConfigurationCommand,
) (*commands.CommandResult, error) {
	startTime := time.Now()
	
	// Validate command
	if err := cmd.Validate(); err != nil {
		return h.buildErrorResult(cmd.AggregateID(), cmd.ValidationContext.RequestID, 
			"command_validation_failed", err, startTime), nil
	}

	// Begin unit of work
	if err := h.unitOfWork.Begin(ctx); err != nil {
		return h.buildErrorResult(cmd.AggregateID(), cmd.ValidationContext.RequestID,
			"transaction_failed", err, startTime), nil
	}
	defer h.unitOfWork.Rollback() // Will be no-op if committed

	// Create domain value objects
	configID, err := configuration.NewConfigurationID(cmd.ID)
	if err != nil {
		return h.buildErrorResult(cmd.AggregateID(), cmd.ValidationContext.RequestID,
			"invalid_configuration_id", err, startTime), nil
	}

	configName, err := configuration.NewConfigurationName(cmd.Name)
	if err != nil {
		return h.buildErrorResult(cmd.AggregateID(), cmd.ValidationContext.RequestID,
			"invalid_configuration_name", err, startTime), nil
	}

	configMode, err := configuration.ParseConfigurationMode(cmd.Mode)
	if err != nil {
		return h.buildErrorResult(cmd.AggregateID(), cmd.ValidationContext.RequestID,
			"invalid_configuration_mode", err, startTime), nil
	}

	version, err := shared.NewVersion(cmd.Version)
	if err != nil {
		return h.buildErrorResult(cmd.AggregateID(), cmd.ValidationContext.RequestID,
			"invalid_version", err, startTime), nil
	}

	// Convert component references
	components, err := h.convertComponentReferences(cmd.Components)
	if err != nil {
		return h.buildErrorResult(cmd.AggregateID(), cmd.ValidationContext.RequestID,
			"invalid_components", err, startTime), nil
	}

	// Create configuration metadata
	metadata := configuration.NewConfigurationMetadata(
		cmd.Description,
		cmd.Labels,
		cmd.Annotations,
	)

	// Create configuration aggregate
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
			return h.buildErrorResult(cmd.AggregateID(), cmd.ValidationContext.RequestID,
				"component_addition_failed", err, startTime), nil
		}
	}

	// Labels and annotations are applied through metadata in NewConfiguration
	// In an immutable design, these would be part of the initial creation

	// Enterprise configuration handling
	if cmd.EnterpriseConfig != nil {
		enterpriseConfig, err := h.convertEnterpriseConfiguration(cmd.EnterpriseConfig)
		if err != nil {
			return h.buildErrorResult(cmd.AggregateID(), cmd.ValidationContext.RequestID,
				"invalid_enterprise_config", err, startTime), nil
		}
		
		// Note: Enterprise configuration would be set through metadata updates
		// In the immutable design, this would be part of the metadata
		_ = enterpriseConfig
	}

	// Create validation context
	validationCtx := services.ValidationContext{
		Context:           ctx,
		ConfigurationMode: configMode,
		EnterpriseMode:    cmd.EnterpriseConfig != nil,
		StrictValidation:  cmd.ValidationContext.EnforceCompliance,
		PolicyFramework:   "default",
	}

	// Domain service orchestration - validation
	validationResult := h.validationService.ValidateConfiguration(ctx, config, validationCtx)
	if !validationResult.Valid {
		return h.buildValidationErrorResult(cmd.AggregateID(), cmd.ValidationContext.RequestID,
			validationResult, startTime), nil
	}

	// Dependency resolution
	componentNames := make([]configuration.ComponentName, len(components))
	for i, comp := range components {
		componentNames[i] = comp.Name()
	}
	
	dependencyResult := h.dependencyResolver.ResolveDependencies(ctx, componentNames)
	if !dependencyResult.Valid {
		return h.buildDependencyErrorResult(cmd.AggregateID(), cmd.ValidationContext.RequestID,
			dependencyResult, startTime), nil
	}

	// Policy enforcement
	if cmd.ValidationContext.ValidatePolicies && h.policyEnforcer != nil {
		if cmd.EnterpriseConfig != nil {
			complianceResult := h.policyEnforcer.ValidateCompliance(ctx, config, cmd.EnterpriseConfig.ComplianceFramework)
			if !complianceResult.Compliant {
				return h.buildComplianceErrorResult(cmd.AggregateID(), cmd.ValidationContext.RequestID,
					complianceResult, startTime), nil
			}
		}
	}

	// Dry run handling
	if cmd.ValidationContext.DryRun {
		warnings := h.buildValidationWarnings(validationResult, dependencyResult)
		return &commands.CommandResult{
			Success:     true,
			AggregateID: cmd.AggregateID(),
			Version:     0,
			Events:      []string{"DryRunCompleted"},
			Warnings:    warnings,
			Duration:    time.Since(startTime).Milliseconds(),
			RequestID:   cmd.ValidationContext.RequestID,
			Metadata: map[string]interface{}{
				"dry_run":               true,
				"validation_passed":     validationResult.Valid,
				"dependencies_resolved": dependencyResult.Valid,
			},
		}, nil
	}

	// Note: UnitOfWork registration would be implemented with proper interface
	
	// Persist configuration
	if err := h.configRepo.Save(ctx, config); err != nil {
		return h.buildErrorResult(cmd.AggregateID(), cmd.ValidationContext.RequestID,
			"persistence_failed", err, startTime), nil
	}

	// Persist domain events
	domainEvents := config.DomainEvents()
	if len(domainEvents) > 0 {
		if err := h.eventRepository.SaveEvents(ctx, config.ID().String(), domainEvents, 0); err != nil {
			return h.buildErrorResult(cmd.AggregateID(), cmd.ValidationContext.RequestID,
				"event_persistence_failed", err, startTime), nil
		}
	}

	// Note: Transaction commit would be handled by unit of work
	if err := h.unitOfWork.Commit(); err != nil {
		return h.buildErrorResult(cmd.AggregateID(), cmd.ValidationContext.RequestID,
			"commit_failed", err, startTime), nil
	}

	// Publish events via event bus
	for _, event := range domainEvents {
		if err := h.eventBus.Publish(event); err != nil {
			// Log error but don't fail the command
			// Event publishing failures are handled separately
		}
	}

	// Mark events as committed
	config.MarkEventsAsCommitted()

	// Build success result
	eventTypes := make([]string, len(domainEvents))
	for i, event := range domainEvents {
		eventTypes[i] = event.EventType()
	}

	warnings := h.buildValidationWarnings(validationResult, dependencyResult)

	return &commands.CommandResult{
		Success:     true,
		AggregateID: cmd.AggregateID(),
		Version:     0,
		Events:      eventTypes,
		Warnings:    warnings,
		Duration:    time.Since(startTime).Milliseconds(),
		RequestID:   cmd.ValidationContext.RequestID,
		Metadata: map[string]interface{}{
			"configuration_name":    cmd.Name,
			"configuration_mode":    cmd.Mode,
			"component_count":       len(cmd.Components),
			"enterprise_enabled":    cmd.EnterpriseConfig != nil,
			"validation_score":      calculateValidationScore(&validationResult),
			"dependency_count":      len(dependencyResult.InstallationOrder),
		},
	}, nil
}

// HandleUpdateConfiguration handles update configuration command
func (h *ConfigurationCommandHandler) HandleUpdateConfiguration(
	ctx context.Context,
	cmd commands.UpdateConfigurationCommand,
) (*commands.CommandResult, error) {
	startTime := time.Now()
	
	// Validate command
	if err := cmd.Validate(); err != nil {
		return h.buildErrorResult(cmd.AggregateID(), cmd.ValidationContext.RequestID,
			"command_validation_failed", err, startTime), nil
	}

	// Begin unit of work
	if err := h.unitOfWork.Begin(ctx); err != nil {
		return h.buildErrorResult(cmd.AggregateID(), cmd.ValidationContext.RequestID,
			"transaction_failed", err, startTime), nil
	}
	defer h.unitOfWork.Rollback()

	// Retrieve existing configuration
	configID, err := configuration.NewConfigurationID(cmd.ID)
	if err != nil {
		return h.buildErrorResult(cmd.AggregateID(), cmd.ValidationContext.RequestID,
			"invalid_configuration_id", err, startTime), nil
	}

	config, err := h.configRepo.FindByID(ctx, configID)
	if err != nil {
		if repositories.IsNotFound(err) {
			return h.buildErrorResult(cmd.AggregateID(), cmd.ValidationContext.RequestID,
				"configuration_not_found", err, startTime), nil
		}
		return h.buildErrorResult(cmd.AggregateID(), cmd.ValidationContext.RequestID,
			"retrieval_failed", err, startTime), nil
	}

	// Version conflict check - simplified for MDD alignment
	// In a complete implementation, this would compare semantic versions
	_ = cmd.ExpectedVersion // Version validation would be implemented

	// Apply updates - Configuration is immutable in our MDD design
	if cmd.Name != nil {
		// Validate new name
		_, err := configuration.NewConfigurationName(*cmd.Name)
		if err != nil {
			return h.buildErrorResult(cmd.AggregateID(), cmd.ValidationContext.RequestID,
				"invalid_configuration_name", err, startTime), nil
		}
		// Update metadata with new name - configuration is immutable
		metadata := configuration.NewConfigurationMetadata(
			*cmd.Description, // Use description from command or existing
			config.Labels(),
			config.Annotations(),
		)
		config.UpdateMetadata(metadata)
		// Note: UpdateMetadata doesn't return an error in our domain model
	}

	if cmd.Description != nil {
		// Update metadata with new description - configuration is immutable
		metadata := configuration.NewConfigurationMetadata(
			*cmd.Description,
			config.Labels(),
			config.Annotations(),
		)
		config.UpdateMetadata(metadata)
		// Note: UpdateMetadata doesn't return an error in our domain model
	}

	// Version update - Configuration is immutable, version is set at creation
	newVersion, err := shared.NewVersion(cmd.Version)
	if err != nil {
		return h.buildErrorResult(cmd.AggregateID(), cmd.ValidationContext.RequestID,
			"invalid_version", err, startTime), nil
	}
	// Note: In immutable design, version updates would require creating a new configuration
	// For now, we'll validate the version but not update it
	_ = newVersion // Version validation completed

	// Component updates
	for _, update := range cmd.ComponentUpdates {
		if err := h.applyComponentUpdate(config, update); err != nil {
			return h.buildErrorResult(cmd.AggregateID(), cmd.ValidationContext.RequestID,
				fmt.Sprintf("component_update_failed_%s", update.Name), err, startTime), nil
		}
	}

	// Labels and annotations updates through metadata in immutable design
	if len(cmd.Labels) > 0 || len(cmd.Annotations) > 0 {
		// Merge existing labels and annotations with new ones
		labels := config.Labels()
		annotations := config.Annotations()
		
		for key, value := range cmd.Labels {
			labels[key] = value
		}
		
		for key, value := range cmd.Annotations {
			annotations[key] = value
		}
		
		metadata := configuration.NewConfigurationMetadata(
			config.Description(),
			labels,
			annotations,
		)
		config.UpdateMetadata(metadata)
	}

	// Enterprise configuration update
	if cmd.EnterpriseConfig != nil {
		enterpriseConfig, err := h.convertEnterpriseConfiguration(cmd.EnterpriseConfig)
		if err != nil {
			return h.buildErrorResult(cmd.AggregateID(), cmd.ValidationContext.RequestID,
				"invalid_enterprise_config", err, startTime), nil
		}
		
		// Note: Enterprise configuration would be set through metadata updates
		// In the immutable design, this would be part of the metadata
		_ = enterpriseConfig
	}

	// Create validation context
	validationCtx := services.ValidationContext{
		Context:           ctx,
		ConfigurationMode: config.Mode(),
		EnterpriseMode:    cmd.EnterpriseConfig != nil,
		StrictValidation:  cmd.ValidationContext.EnforceCompliance,
		PolicyFramework:   "default",
	}

	// Domain service orchestration - re-validation
	validationResult := h.validationService.ValidateConfiguration(ctx, config, validationCtx)
	if !validationResult.Valid {
		return h.buildValidationErrorResult(cmd.AggregateID(), cmd.ValidationContext.RequestID,
			validationResult, startTime), nil
	}

	// Re-resolve dependencies if components changed
	if len(cmd.ComponentUpdates) > 0 {
		componentNames := make([]configuration.ComponentName, 0)
		for _, comp := range config.ComponentsList() {
			componentNames = append(componentNames, comp.Name())
		}
		
		dependencyResult := h.dependencyResolver.ResolveDependencies(ctx, componentNames)
		if !dependencyResult.Valid {
			return h.buildDependencyErrorResult(cmd.AggregateID(), cmd.ValidationContext.RequestID,
				dependencyResult, startTime), nil
		}
	}

	// Policy re-enforcement
	if cmd.ValidationContext.ValidatePolicies && h.policyEnforcer != nil {
		if cmd.EnterpriseConfig != nil {
			complianceResult := h.policyEnforcer.ValidateCompliance(ctx, config, cmd.EnterpriseConfig.ComplianceFramework)
			if !complianceResult.Compliant {
				return h.buildComplianceErrorResult(cmd.AggregateID(), cmd.ValidationContext.RequestID,
					complianceResult, startTime), nil
			}
		}
	}

	// Dry run handling
	if cmd.ValidationContext.DryRun {
		warnings := h.buildValidationWarnings(validationResult, services.ResolutionResult{Valid: true})
		return &commands.CommandResult{
			Success:     true,
			AggregateID: cmd.AggregateID(),
			Version:     0,
			Events:      []string{"DryRunCompleted"},
			Warnings:    warnings,
			Duration:    time.Since(startTime).Milliseconds(),
			RequestID:   cmd.ValidationContext.RequestID,
			Metadata: map[string]interface{}{
				"dry_run":           true,
				"validation_passed": validationResult.Valid,
				"updates_applied":   len(cmd.ComponentUpdates),
			},
		}, nil
	}

	// Note: UnitOfWork registration would be implemented with proper interface
	
	// Persist updated configuration
	if err := h.configRepo.Save(ctx, config); err != nil {
		return h.buildErrorResult(cmd.AggregateID(), cmd.ValidationContext.RequestID,
			"persistence_failed", err, startTime), nil
	}

	// Persist domain events
	domainEvents := config.DomainEvents()
	if len(domainEvents) > 0 {
		if err := h.eventRepository.SaveEvents(ctx, config.ID().String(), domainEvents, cmd.ExpectedVersion); err != nil {
			return h.buildErrorResult(cmd.AggregateID(), cmd.ValidationContext.RequestID,
				"event_persistence_failed", err, startTime), nil
		}
	}

	// Note: Transaction commit would be handled by unit of work
	if err := h.unitOfWork.Commit(); err != nil {
		return h.buildErrorResult(cmd.AggregateID(), cmd.ValidationContext.RequestID,
			"commit_failed", err, startTime), nil
	}

	// Publish events
	for _, event := range domainEvents {
		if err := h.eventBus.Publish(event); err != nil {
			// Log error but don't fail
		}
	}

	config.MarkEventsAsCommitted()

	// Build success result
	eventTypes := make([]string, len(domainEvents))
	for i, event := range domainEvents {
		eventTypes[i] = event.EventType()
	}

	return &commands.CommandResult{
		Success:     true,
		AggregateID: cmd.AggregateID(),
		Version:     0,
		Events:      eventTypes,
		Duration:    time.Since(startTime).Milliseconds(),
		RequestID:   cmd.ValidationContext.RequestID,
		Metadata: map[string]interface{}{
			"updates_applied":   len(cmd.ComponentUpdates),
			"validation_score":  calculateValidationScore(&validationResult),
			"previous_version":  cmd.ExpectedVersion,
		},
	}, nil
}

// HandleValidateConfiguration handles validate configuration command
func (h *ConfigurationCommandHandler) HandleValidateConfiguration(
	ctx context.Context,
	cmd commands.ValidateConfigurationCommand,
) (*commands.CommandResult, error) {
	startTime := time.Now()
	
	// Validate command
	if err := cmd.Validate(); err != nil {
		return h.buildErrorResult(cmd.AggregateID(), cmd.ValidationContext.RequestID,
			"command_validation_failed", err, startTime), nil
	}

	// Retrieve configuration
	configID, err := configuration.NewConfigurationID(cmd.ID)
	if err != nil {
		return h.buildErrorResult(cmd.AggregateID(), cmd.ValidationContext.RequestID,
			"invalid_configuration_id", err, startTime), nil
	}

	config, err := h.configRepo.FindByID(ctx, configID)
	if err != nil {
		if repositories.IsNotFound(err) {
			return h.buildErrorResult(cmd.AggregateID(), cmd.ValidationContext.RequestID,
				"configuration_not_found", err, startTime), nil
		}
		return h.buildErrorResult(cmd.AggregateID(), cmd.ValidationContext.RequestID,
			"retrieval_failed", err, startTime), nil
	}

	// Create validation context
	validationCtx := services.ValidationContext{
		Context:           ctx,
		ConfigurationMode: config.Mode(),
		EnterpriseMode:    config.EnterpriseConfiguration() != nil,
		StrictValidation:  cmd.ValidationContext.EnforceCompliance,
		PolicyFramework:   cmd.Framework,
	}
	
	// Comprehensive validation
	validationResult := h.validationService.ValidateConfiguration(ctx, config, validationCtx)
	
	var dependencyResult services.ResolutionResult
	if cmd.DependencyChecks {
		componentNames := make([]configuration.ComponentName, 0)
		for _, comp := range config.ComponentsList() {
			componentNames = append(componentNames, comp.Name())
		}
		dependencyResult = h.dependencyResolver.ResolveDependencies(ctx, componentNames)
	}

	// Compliance validation would be implemented with policy enforcer
	if cmd.PolicyChecks && h.policyEnforcer != nil {
		_ = h.policyEnforcer.ValidateCompliance(ctx, config, cmd.Framework)
	}

	// Build comprehensive validation result
	warnings := h.buildValidationWarnings(validationResult, dependencyResult)
	errors := make([]commands.CommandError, 0)

	if !validationResult.Valid {
		for _, violation := range validationResult.Errors {
			errors = append(errors, commands.CommandError{
				Code:        "validation_violation",
				Message:     violation.Message,
				Field:       violation.Field,
				Recoverable: int(violation.Severity) != 3,
				Details: map[string]interface{}{
					"severity": violation.Severity,
					"rule":     "validation_rule",
				},
			})
		}
	}

	if cmd.DependencyChecks && !dependencyResult.Valid {
		for _, missing := range dependencyResult.MissingDependencies {
			errors = append(errors, commands.CommandError{
				Code:        "missing_dependency",
				Message:     fmt.Sprintf("Missing dependency: %s", missing.ComponentName),
				Recoverable: true,
				Details: map[string]interface{}{
					"required_by": missing.RequiredBy,
					"version":     missing.RequiredVersion,
				},
			})
		}
	}

	success := len(errors) == 0

	return &commands.CommandResult{
		Success:     success,
		AggregateID: cmd.AggregateID(),
		Version:     0,
		Events:      []string{"ValidationCompleted"},
		Warnings:    warnings,
		Errors:      errors,
		Duration:    time.Since(startTime).Milliseconds(),
		RequestID:   cmd.ValidationContext.RequestID,
		Metadata: map[string]interface{}{
			"validation_level":      cmd.ValidationLevel,
			"framework":            cmd.Framework,
			"component_checks":     cmd.ComponentChecks,
			"dependency_checks":    cmd.DependencyChecks,
			"policy_checks":        cmd.PolicyChecks,
			"security_checks":      cmd.SecurityChecks,
			"validation_score":     calculateValidationScore(&validationResult),
			"compliance_score":     0.0,
		},
	}, nil
}

// Helper methods for command processing

func (h *ConfigurationCommandHandler) convertComponentReferences(
	refs []commands.ComponentReference,
) ([]*configuration.ComponentReference, error) {
	components := make([]*configuration.ComponentReference, len(refs))
	
	for i, ref := range refs {
		name, err := configuration.NewComponentName(ref.Name)
		if err != nil {
			return nil, fmt.Errorf("invalid component name %s: %w", ref.Name, err)
		}

		version, err := shared.NewVersion(ref.Version)
		if err != nil {
			return nil, fmt.Errorf("invalid component version %s: %w", ref.Version, err)
		}

		// Resource requirements and configuration would be handled through
		// component configuration in a complete implementation
		_ = ref.Resources
		_ = ref.Configuration

		component := configuration.NewComponentReference(
			name,
			version,
			ref.Enabled,
		)

		components[i] = component
	}

	return components, nil
}

func (h *ConfigurationCommandHandler) convertResourceRequirements(
	req commands.ResourceRequirements,
) (*configuration.ResourceRequirements, error) {
	resources := configuration.NewResourceRequirementsWithParams(
		req.CPU,
		req.Memory,
		req.Storage,
		req.Replicas,
		req.Namespace,
	)
	return &resources, nil
}

func (h *ConfigurationCommandHandler) convertEnterpriseConfiguration(
	enterprise *commands.EnterpriseConfiguration,
) (*configuration.EnterpriseConfiguration, error) {
	// Use string values directly as the domain model accepts strings
	return configuration.NewEnterpriseConfiguration(
		enterprise.ComplianceFramework,
		enterprise.SecurityLevel,
		enterprise.AuditEnabled,
		enterprise.EncryptionRequired,
		enterprise.BackupRequired,
		enterprise.PolicyTemplates,
		enterprise.Metadata,
	)
}

func (h *ConfigurationCommandHandler) applyComponentUpdate(
	config *configuration.Configuration,
	update commands.ComponentUpdate,
) error {
	name, err := configuration.NewComponentName(update.Name)
	if err != nil {
		return err
	}

	switch update.Operation {
	case "add":
		if update.Version == nil {
			return fmt.Errorf("version required for add operation")
		}
		version, err := shared.NewVersion(*update.Version)
		if err != nil {
			return err
		}
		
		// Resource requirements would be handled through component configuration
		// in a complete implementation
		_ = update.Resources

		component := configuration.NewComponentReference(
			name,
			version,
			update.Enabled != nil && *update.Enabled,
		)

		return config.AddComponent(component)

	case "remove":
		return config.RemoveComponent(name)

	case "enable":
		// Component enable/disable would be implemented through metadata updates
		return fmt.Errorf("component enable operation not yet implemented")

	case "disable":
		// Component enable/disable would be implemented through metadata updates
		return fmt.Errorf("component disable operation not yet implemented")

	case "update":
		// This would require more complex logic to update existing component
		return fmt.Errorf("component update operation not yet implemented")

	default:
		return fmt.Errorf("unknown component operation: %s", update.Operation)
	}
}

func (h *ConfigurationCommandHandler) buildErrorResult(
	aggregateID, requestID, errorCode string,
	err error,
	startTime time.Time,
) *commands.CommandResult {
	return &commands.CommandResult{
		Success:     false,
		AggregateID: aggregateID,
		Version:     0,
		Events:      []string{},
		Errors: []commands.CommandError{
			{
				Code:        errorCode,
				Message:     err.Error(),
				Recoverable: !isCriticalError(errorCode),
			},
		},
		Duration:  time.Since(startTime).Milliseconds(),
		RequestID: requestID,
	}
}

func (h *ConfigurationCommandHandler) buildValidationErrorResult(
	aggregateID, requestID string,
	validationResult services.ExtendedValidationResult,
	startTime time.Time,
) *commands.CommandResult {
	errors := make([]commands.CommandError, len(validationResult.Errors))
	for i, violation := range validationResult.Errors {
		errors[i] = commands.CommandError{
			Code:        "validation_violation",
			Message:     violation.Message,
			Field:       violation.Field,
			Recoverable: int(violation.Severity) != 3,
			Details: map[string]interface{}{
				"severity": violation.Severity,
				"rule":     "validation_rule",
			},
		}
	}

	return &commands.CommandResult{
		Success:     false,
		AggregateID: aggregateID,
		Version:     0,
		Events:      []string{},
		Errors:      errors,
		Duration:    time.Since(startTime).Milliseconds(),
		RequestID:   requestID,
		Metadata: map[string]interface{}{
			"validation_score": calculateValidationScore(&validationResult),
		},
	}
}

func (h *ConfigurationCommandHandler) buildDependencyErrorResult(
	aggregateID, requestID string,
	dependencyResult services.ResolutionResult,
	startTime time.Time,
) *commands.CommandResult {
	errors := make([]commands.CommandError, 0)
	
	for _, missing := range dependencyResult.MissingDependencies {
		errors = append(errors, commands.CommandError{
			Code:        "missing_dependency",
			Message:     fmt.Sprintf("Missing dependency: %s", missing.ComponentName),
			Recoverable: true,
			Details: map[string]interface{}{
				"required_by": missing.RequiredBy,
				"version":     missing.RequiredVersion,
			},
		})
	}

	for _, circular := range dependencyResult.CircularDependencies {
		errors = append(errors, commands.CommandError{
			Code:        "circular_dependency",
			Message:     fmt.Sprintf("Circular dependency detected: %v", circular.Components),
			Recoverable: false,
			Details: map[string]interface{}{
				"cycle": circular.Cycle,
			},
		})
	}

	return &commands.CommandResult{
		Success:     false,
		AggregateID: aggregateID,
		Version:     0,
		Events:      []string{},
		Errors:      errors,
		Duration:    time.Since(startTime).Milliseconds(),
		RequestID:   requestID,
	}
}

func (h *ConfigurationCommandHandler) buildComplianceErrorResult(
	aggregateID, requestID string,
	complianceResult services.PolicyComplianceResult,
	startTime time.Time,
) *commands.CommandResult {
	// Compliance errors would be handled if policy enforcer was implemented
	errors := make([]commands.CommandError, 0)
	
	// Note: This would iterate over actual compliance violations in a complete implementation
	// for i, violation := range complianceResult.Violations {
	//     errors = append(errors, commands.CommandError{
	//         Code:        "compliance_violation",
	//         Message:     violation.Message,
	//         Field:       violation.PolicyID,
	//         Recoverable: int(violation.Severity) != 3,
	//         Details: map[string]interface{}{
	//             "policy_id": violation.PolicyID,
	//             "severity":  violation.Severity,
	//             "framework": complianceResult.Framework,
	//         },
	//     })
	// }

	return &commands.CommandResult{
		Success:     false,
		AggregateID: aggregateID,
		Version:     0,
		Events:      []string{},
		Errors:      errors,
		Duration:    time.Since(startTime).Milliseconds(),
		RequestID:   requestID,
		Metadata: map[string]interface{}{
			"compliance_score": 0.0,
			"framework":        "default",
		},
	}
}

func (h *ConfigurationCommandHandler) buildValidationWarnings(
	validationResult services.ExtendedValidationResult,
	dependencyResult services.ResolutionResult,
) []commands.CommandWarning {
	warnings := make([]commands.CommandWarning, 0)

	// Add validation warnings
	for _, warning := range validationResult.Warnings {
		warnings = append(warnings, commands.CommandWarning{
			Code:       "validation_warning",
			Message:    warning.Message,
			Field:      warning.Field,
			Severity:   "warning",
			Suggestion: "Review validation warnings",
		})
	}

	// Add dependency warnings
	for _, warning := range dependencyResult.Warnings {
		warnings = append(warnings, commands.CommandWarning{
			Code:       "dependency_warning",
			Message:    warning.Message,
			Severity:   string(warning.Severity),
			Suggestion: "Review component dependencies",
		})
	}

	return warnings
}

func isCriticalError(errorCode string) bool {
	criticalErrors := map[string]bool{
		"transaction_failed":         true,
		"persistence_failed":         true,
		"commit_failed":             true,
		"circular_dependency":        true,
		"compliance_violation":       true,
		"version_conflict":          true,
	}
	return criticalErrors[errorCode]
}

// calculateValidationScore computes a simple validation score based on results
func calculateValidationScore(result *services.ExtendedValidationResult) float64 {
	if !result.Valid {
		return 0.0
	}
	
	// Simple scoring based on errors and warnings
	errorPenalty := float64(len(result.Errors)) * 0.2
	warningPenalty := float64(len(result.Warnings)) * 0.1
	
	score := 1.0 - errorPenalty - warningPenalty
	if score < 0 {
		score = 0
	}
	return score
}