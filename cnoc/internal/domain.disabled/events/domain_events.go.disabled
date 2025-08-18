package events

import (
	"time"

	"github.com/google/uuid"
)

// DomainEvent represents the base interface for all domain events
// Following event sourcing and CQRS patterns for Symphony-Level coordination
type DomainEvent interface {
	EventID() string
	EventType() string
	AggregateID() string
	OccurredOn() time.Time
	EventData() map[string]interface{}
}

// BaseDomainEvent provides common implementation for domain events
type BaseDomainEvent struct {
	eventID     string
	eventType   string
	aggregateID string
	occurredOn  time.Time
	eventData   map[string]interface{}
}

// NewBaseDomainEvent creates a new base domain event
func NewBaseDomainEvent(eventType, aggregateID string, eventData map[string]interface{}) BaseDomainEvent {
	return BaseDomainEvent{
		eventID:     uuid.New().String(),
		eventType:   eventType,
		aggregateID: aggregateID,
		occurredOn:  time.Now().UTC(),
		eventData:   eventData,
	}
}

// EventID returns the unique event identifier
func (e BaseDomainEvent) EventID() string {
	return e.eventID
}

// EventType returns the event type
func (e BaseDomainEvent) EventType() string {
	return e.eventType
}

// AggregateID returns the aggregate identifier
func (e BaseDomainEvent) AggregateID() string {
	return e.aggregateID
}

// OccurredOn returns when the event occurred
func (e BaseDomainEvent) OccurredOn() time.Time {
	return e.occurredOn
}

// EventData returns the event data
func (e BaseDomainEvent) EventData() map[string]interface{} {
	return e.eventData
}

// Configuration Context Events

// ConfigurationCreated event
type ConfigurationCreated struct {
	BaseDomainEvent
}

// NewConfigurationCreated creates a configuration created event
func NewConfigurationCreated(configID, name, mode string) ConfigurationCreated {
	return ConfigurationCreated{
		BaseDomainEvent: NewBaseDomainEvent("ConfigurationCreated", configID, map[string]interface{}{
			"name": name,
			"mode": mode,
		}),
	}
}

// ConfigurationValidated event
type ConfigurationValidated struct {
	BaseDomainEvent
}

// NewConfigurationValidated creates a configuration validated event
func NewConfigurationValidated(configID string) ConfigurationValidated {
	return ConfigurationValidated{
		BaseDomainEvent: NewBaseDomainEvent("ConfigurationValidated", configID, map[string]interface{}{}),
	}
}

// ConfigurationDeployed event
type ConfigurationDeployed struct {
	BaseDomainEvent
}

// NewConfigurationDeployed creates a configuration deployed event
func NewConfigurationDeployed(configID string) ConfigurationDeployed {
	return ConfigurationDeployed{
		BaseDomainEvent: NewBaseDomainEvent("ConfigurationDeployed", configID, map[string]interface{}{}),
	}
}

// ConfigurationFailed event
type ConfigurationFailed struct {
	BaseDomainEvent
}

// NewConfigurationFailed creates a configuration failed event
func NewConfigurationFailed(configID, reason string) ConfigurationFailed {
	return ConfigurationFailed{
		BaseDomainEvent: NewBaseDomainEvent("ConfigurationFailed", configID, map[string]interface{}{
			"reason": reason,
		}),
	}
}

// ConfigurationArchived event
type ConfigurationArchived struct {
	BaseDomainEvent
}

// NewConfigurationArchived creates a configuration archived event
func NewConfigurationArchived(configID string) ConfigurationArchived {
	return ConfigurationArchived{
		BaseDomainEvent: NewBaseDomainEvent("ConfigurationArchived", configID, map[string]interface{}{}),
	}
}

// ConfigurationUpdated event
type ConfigurationUpdated struct {
	BaseDomainEvent
}

// NewConfigurationUpdated creates a configuration updated event
func NewConfigurationUpdated(configID string) ConfigurationUpdated {
	return ConfigurationUpdated{
		BaseDomainEvent: NewBaseDomainEvent("ConfigurationUpdated", configID, map[string]interface{}{}),
	}
}

// ComponentAdded event
type ComponentAdded struct {
	BaseDomainEvent
}

// NewComponentAdded creates a component added event
func NewComponentAdded(configID, componentName, version string) ComponentAdded {
	return ComponentAdded{
		BaseDomainEvent: NewBaseDomainEvent("ComponentAdded", configID, map[string]interface{}{
			"componentName": componentName,
			"version":       version,
		}),
	}
}

// ComponentRemoved event
type ComponentRemoved struct {
	BaseDomainEvent
}

// NewComponentRemoved creates a component removed event
func NewComponentRemoved(configID, componentName, version string) ComponentRemoved {
	return ComponentRemoved{
		BaseDomainEvent: NewBaseDomainEvent("ComponentRemoved", configID, map[string]interface{}{
			"componentName": componentName,
			"version":       version,
		}),
	}
}

// Component Context Events

// ComponentEnabled event
type ComponentEnabled struct {
	BaseDomainEvent
}

// NewComponentEnabled creates a component enabled event
func NewComponentEnabled(componentID, name, version string) ComponentEnabled {
	return ComponentEnabled{
		BaseDomainEvent: NewBaseDomainEvent("ComponentEnabled", componentID, map[string]interface{}{
			"name":    name,
			"version": version,
		}),
	}
}

// ComponentDisabled event
type ComponentDisabled struct {
	BaseDomainEvent
}

// NewComponentDisabled creates a component disabled event
func NewComponentDisabled(componentID, name string) ComponentDisabled {
	return ComponentDisabled{
		BaseDomainEvent: NewBaseDomainEvent("ComponentDisabled", componentID, map[string]interface{}{
			"name": name,
		}),
	}
}

// ComponentUpgraded event
type ComponentUpgraded struct {
	BaseDomainEvent
}

// NewComponentUpgraded creates a component upgraded event
func NewComponentUpgraded(componentID, name, fromVersion, toVersion string) ComponentUpgraded {
	return ComponentUpgraded{
		BaseDomainEvent: NewBaseDomainEvent("ComponentUpgraded", componentID, map[string]interface{}{
			"name":        name,
			"fromVersion": fromVersion,
			"toVersion":   toVersion,
		}),
	}
}

// DependencyResolved event
type DependencyResolved struct {
	BaseDomainEvent
}

// NewDependencyResolved creates a dependency resolved event
func NewDependencyResolved(componentID, dependentComponent, requiredComponent string) DependencyResolved {
	return DependencyResolved{
		BaseDomainEvent: NewBaseDomainEvent("DependencyResolved", componentID, map[string]interface{}{
			"dependentComponent": dependentComponent,
			"requiredComponent":  requiredComponent,
		}),
	}
}

// DependencyViolated event
type DependencyViolated struct {
	BaseDomainEvent
}

// NewDependencyViolated creates a dependency violated event
func NewDependencyViolated(componentID, dependentComponent, missingComponent string) DependencyViolated {
	return DependencyViolated{
		BaseDomainEvent: NewBaseDomainEvent("DependencyViolated", componentID, map[string]interface{}{
			"dependentComponent": dependentComponent,
			"missingComponent":   missingComponent,
		}),
	}
}

// Deployment Context Events

// DeploymentStarted event
type DeploymentStarted struct {
	BaseDomainEvent
}

// NewDeploymentStarted creates a deployment started event
func NewDeploymentStarted(deploymentID, configurationID string) DeploymentStarted {
	return DeploymentStarted{
		BaseDomainEvent: NewBaseDomainEvent("DeploymentStarted", deploymentID, map[string]interface{}{
			"configurationID": configurationID,
		}),
	}
}

// NodeProvisioned event
type NodeProvisioned struct {
	BaseDomainEvent
}

// NewNodeProvisioned creates a node provisioned event
func NewNodeProvisioned(deploymentID, nodeID, nodeName string) NodeProvisioned {
	return NodeProvisioned{
		BaseDomainEvent: NewBaseDomainEvent("NodeProvisioned", deploymentID, map[string]interface{}{
			"nodeID":   nodeID,
			"nodeName": nodeName,
		}),
	}
}

// ComponentInstalled event
type ComponentInstalled struct {
	BaseDomainEvent
}

// NewComponentInstalled creates a component installed event
func NewComponentInstalled(deploymentID, componentName, nodeID string) ComponentInstalled {
	return ComponentInstalled{
		BaseDomainEvent: NewBaseDomainEvent("ComponentInstalled", deploymentID, map[string]interface{}{
			"componentName": componentName,
			"nodeID":        nodeID,
		}),
	}
}

// DeploymentCompleted event
type DeploymentCompleted struct {
	BaseDomainEvent
}

// NewDeploymentCompleted creates a deployment completed event
func NewDeploymentCompleted(deploymentID string, duration int64) DeploymentCompleted {
	return DeploymentCompleted{
		BaseDomainEvent: NewBaseDomainEvent("DeploymentCompleted", deploymentID, map[string]interface{}{
			"durationMs": duration,
		}),
	}
}

// DeploymentFailed event
type DeploymentFailed struct {
	BaseDomainEvent
}

// NewDeploymentFailed creates a deployment failed event
func NewDeploymentFailed(deploymentID, reason, phase string) DeploymentFailed {
	return DeploymentFailed{
		BaseDomainEvent: NewBaseDomainEvent("DeploymentFailed", deploymentID, map[string]interface{}{
			"reason": reason,
			"phase":  phase,
		}),
	}
}

// Enterprise Context Events

// PolicyCreated event
type PolicyCreated struct {
	BaseDomainEvent
}

// NewPolicyCreated creates a policy created event
func NewPolicyCreated(policyID, name, complianceType string) PolicyCreated {
	return PolicyCreated{
		BaseDomainEvent: NewBaseDomainEvent("PolicyCreated", policyID, map[string]interface{}{
			"name":           name,
			"complianceType": complianceType,
		}),
	}
}

// PolicyApplied event
type PolicyApplied struct {
	BaseDomainEvent
}

// NewPolicyApplied creates a policy applied event
func NewPolicyApplied(policyID, targetID, targetType string) PolicyApplied {
	return PolicyApplied{
		BaseDomainEvent: NewBaseDomainEvent("PolicyApplied", policyID, map[string]interface{}{
			"targetID":   targetID,
			"targetType": targetType,
		}),
	}
}

// ComplianceValidated event
type ComplianceValidated struct {
	BaseDomainEvent
}

// NewComplianceValidated creates a compliance validated event
func NewComplianceValidated(targetID, complianceType string, passed bool) ComplianceValidated {
	return ComplianceValidated{
		BaseDomainEvent: NewBaseDomainEvent("ComplianceValidated", targetID, map[string]interface{}{
			"complianceType": complianceType,
			"passed":         passed,
		}),
	}
}

// SecurityConfigured event
type SecurityConfigured struct {
	BaseDomainEvent
}

// NewSecurityConfigured creates a security configured event
func NewSecurityConfigured(targetID, securityType string) SecurityConfigured {
	return SecurityConfigured{
		BaseDomainEvent: NewBaseDomainEvent("SecurityConfigured", targetID, map[string]interface{}{
			"securityType": securityType,
		}),
	}
}

// AuthenticationConfigured event
type AuthenticationConfigured struct {
	BaseDomainEvent
}

// NewAuthenticationConfigured creates an authentication configured event
func NewAuthenticationConfigured(providerID, providerType string) AuthenticationConfigured {
	return AuthenticationConfigured{
		BaseDomainEvent: NewBaseDomainEvent("AuthenticationConfigured", providerID, map[string]interface{}{
			"providerType": providerType,
		}),
	}
}

// Event Bus Interface for Symphony-Level Coordination

// EventBus provides event publishing and subscription capabilities
type EventBus interface {
	Publish(event DomainEvent) error
	Subscribe(eventType string, handler EventHandler) error
	Unsubscribe(eventType string, handler EventHandler) error
}

// EventHandler handles domain events
type EventHandler interface {
	Handle(event DomainEvent) error
	CanHandle(eventType string) bool
}

// EventStore provides event persistence for event sourcing
type EventStore interface {
	SaveEvents(aggregateID string, events []DomainEvent, expectedVersion int) error
	GetEvents(aggregateID string) ([]DomainEvent, error)
	GetEventsAfter(aggregateID string, version int) ([]DomainEvent, error)
}

// EventStream represents a stream of events for an aggregate
type EventStream struct {
	AggregateID string
	Events      []DomainEvent
	Version     int
}

// NewEventStream creates a new event stream
func NewEventStream(aggregateID string, events []DomainEvent) EventStream {
	return EventStream{
		AggregateID: aggregateID,
		Events:      events,
		Version:     len(events),
	}
}

// AddEvent adds an event to the stream
func (es *EventStream) AddEvent(event DomainEvent) {
	es.Events = append(es.Events, event)
	es.Version++
}

// EventMetadata provides additional context for events
type EventMetadata struct {
	CorrelationID string
	CausationID   string
	UserID        string
	Source        string
	Version       int
}

// EnhancedDomainEvent extends DomainEvent with metadata
type EnhancedDomainEvent interface {
	DomainEvent
	Metadata() EventMetadata
	WithMetadata(metadata EventMetadata) EnhancedDomainEvent
}

// EnhancedBaseDomainEvent provides enhanced domain event implementation
type EnhancedBaseDomainEvent struct {
	BaseDomainEvent
	metadata EventMetadata
}

// NewEnhancedDomainEvent creates a new enhanced domain event
func NewEnhancedDomainEvent(eventType, aggregateID string, eventData map[string]interface{}, metadata EventMetadata) EnhancedBaseDomainEvent {
	return EnhancedBaseDomainEvent{
		BaseDomainEvent: NewBaseDomainEvent(eventType, aggregateID, eventData),
		metadata:        metadata,
	}
}

// Metadata returns the event metadata
func (e EnhancedBaseDomainEvent) Metadata() EventMetadata {
	return e.metadata
}

// WithMetadata returns a copy of the event with new metadata
func (e EnhancedBaseDomainEvent) WithMetadata(metadata EventMetadata) EnhancedDomainEvent {
	return EnhancedBaseDomainEvent{
		BaseDomainEvent: e.BaseDomainEvent,
		metadata:        metadata,
	}
}