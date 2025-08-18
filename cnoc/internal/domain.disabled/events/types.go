package events

import "time"

// EventType represents the type of an event
type EventType string

// Common event types
const (
	EventTypeConfigurationCreated EventType = "configuration_created"
	EventTypeConfigurationUpdated EventType = "configuration_updated"
	EventTypeConfigurationDeleted EventType = "configuration_deleted"
	EventTypeSyncStarted          EventType = "sync_started"
	EventTypeSyncCompleted        EventType = "sync_completed"
	EventTypeDriftDetected        EventType = "drift_detected"
)

// EventHandlerRegistration represents a registered event handler
type EventHandlerRegistration struct {
	ID          string
	EventType   EventType
	Handler     func(interface{}) error
	HandlerFunc func(interface{}) error
	Async       bool
	Priority    int
	CreatedAt   time.Time
}

// EventBusMetrics holds metrics about the event bus
type EventBusMetrics struct {
	EventsPublished     int64
	EventsProcessed     int64
	EventsFailed        int64
	HandlersRegistered  int64
	ProcessingErrors    int64
	ActiveSubscriptions int64
	QueueDepth          int64
	ProcessingRate      float64
	AverageLatency      time.Duration
	MaxLatency          time.Duration
}

// WorkflowDefinition defines a workflow
type WorkflowDefinition struct {
	ID          string
	Name        string
	Description string
	Steps       []WorkflowStep
	CreatedAt   time.Time
}

// WorkflowStep represents a step in a workflow
type WorkflowStep struct {
	ID          string
	Name        string
	Type        string
	Config      map[string]interface{}
	Order       int
}

// WorkflowExecution tracks workflow execution
type WorkflowExecution struct {
	ID           string
	WorkflowID   string
	Status       string
	StartedAt    time.Time
	CompletedAt  *time.Time
	CurrentStep  int
	Result       map[string]interface{}
	Error        string
}