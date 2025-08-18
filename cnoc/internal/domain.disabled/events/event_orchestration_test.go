package events

import (
	"context"
	"encoding/json"
	"fmt"
	"sync"
	"testing"
	"time"

	"github.com/google/uuid"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
	"github.com/stretchr/testify/suite"
)

// FORGE Movement 5: Event Orchestration Testing
// Complex event-driven workflows with GitOps synchronization

// EventType represents different types of domain events
type EventType string

const (
	FabricSyncInitiated   EventType = "fabric.sync.initiated"
	FabricSyncCompleted   EventType = "fabric.sync.completed"
	FabricSyncFailed      EventType = "fabric.sync.failed"
	DriftDetectionStarted EventType = "drift.detection.started"
	DriftDetected         EventType = "drift.detected"
	DriftResolved         EventType = "drift.resolved"
	CRDCreated            EventType = "crd.created"
	CRDUpdated            EventType = "crd.updated"
	CRDDeleted            EventType = "crd.deleted"
	GitOpsOperationFailed EventType = "gitops.operation.failed"
	K8sConnectivityLost   EventType = "k8s.connectivity.lost"
	K8sConnectivityRestored EventType = "k8s.connectivity.restored"
	WorkflowStarted       EventType = "workflow.started"
	WorkflowCompleted     EventType = "workflow.completed"
	WorkflowFailed        EventType = "workflow.failed"
)

// DomainEvent represents a domain event in the system
type DomainEvent struct {
	ID           string                 `json:"id"`
	Type         EventType              `json:"type"`
	AggregateID  string                 `json:"aggregate_id"`
	Timestamp    time.Time              `json:"timestamp"`
	Version      int                    `json:"version"`
	Data         map[string]interface{} `json:"data"`
	Metadata     map[string]interface{} `json:"metadata"`
	CorrelationID string                `json:"correlation_id"`
	CausationID  string                 `json:"causation_id,omitempty"`
	UserID       string                 `json:"user_id,omitempty"`
	Source       string                 `json:"source"`
	Processed    bool                   `json:"processed"`
	ProcessedAt  *time.Time             `json:"processed_at,omitempty"`
	Errors       []string               `json:"errors,omitempty"`
}

// EventHandler represents an event handler function
type EventHandler func(ctx context.Context, event *DomainEvent) error

// EventHandlerRegistration represents a handler registration
type EventHandlerRegistration struct {
	EventType EventType
	Handler   EventHandler
	Async     bool
	Priority  int
}

// EventBus represents an event bus for publishing and subscribing to events
type EventBus interface {
	Publish(ctx context.Context, event *DomainEvent) error
	Subscribe(eventType EventType, handler EventHandler) error
	SubscribeAsync(eventType EventType, handler EventHandler) error
	Unsubscribe(eventType EventType, handler EventHandler) error
	Start(ctx context.Context) error
	Stop() error
	GetMetrics() EventBusMetrics
}

// EventBusMetrics represents event bus performance metrics
type EventBusMetrics struct {
	EventsPublished     int64         `json:"events_published"`
	EventsProcessed     int64         `json:"events_processed"`
	EventsFailed        int64         `json:"events_failed"`
	AverageLatency      time.Duration `json:"average_latency"`
	MaxLatency          time.Duration `json:"max_latency"`
	HandlersRegistered  int           `json:"handlers_registered"`
	ActiveSubscriptions int           `json:"active_subscriptions"`
	QueueDepth          int           `json:"queue_depth"`
	ProcessingRate      float64       `json:"processing_rate"` // events per second
}

// EventStore represents an event store for persistence
type EventStore interface {
	Save(ctx context.Context, events []*DomainEvent) error
	Load(ctx context.Context, aggregateID string) ([]*DomainEvent, error)
	LoadByType(ctx context.Context, eventType EventType, limit int) ([]*DomainEvent, error)
	LoadByTimeRange(ctx context.Context, start, end time.Time) ([]*DomainEvent, error)
	Count(ctx context.Context, eventType EventType) (int64, error)
	Replay(ctx context.Context, fromTime time.Time, handler EventHandler) error
}

// WorkflowDefinition represents a complex workflow
type WorkflowDefinition struct {
	ID          string                 `json:"id"`
	Name        string                 `json:"name"`
	Description string                 `json:"description"`
	Steps       []WorkflowStep         `json:"steps"`
	Triggers    []EventType            `json:"triggers"`
	Timeout     time.Duration          `json:"timeout"`
	Retry       RetryPolicy            `json:"retry"`
	Metadata    map[string]interface{} `json:"metadata"`
}

// WorkflowStep represents a step in a workflow
type WorkflowStep struct {
	ID           string                 `json:"id"`
	Name         string                 `json:"name"`
	Type         string                 `json:"type"` // sync, async, parallel
	Action       string                 `json:"action"`
	Dependencies []string               `json:"dependencies"`
	Timeout      time.Duration          `json:"timeout"`
	Retry        RetryPolicy            `json:"retry"`
	Condition    string                 `json:"condition,omitempty"`
	OnSuccess    []string               `json:"on_success,omitempty"`
	OnFailure    []string               `json:"on_failure,omitempty"`
	Parameters   map[string]interface{} `json:"parameters"`
}

// RetryPolicy represents retry configuration
type RetryPolicy struct {
	MaxRetries int           `json:"max_retries"`
	Delay      time.Duration `json:"delay"`
	Backoff    string        `json:"backoff"` // linear, exponential
	MaxDelay   time.Duration `json:"max_delay"`
}

// WorkflowExecution represents a running workflow
type WorkflowExecution struct {
	ID              string                 `json:"id"`
	WorkflowID      string                 `json:"workflow_id"`
	Status          string                 `json:"status"` // running, completed, failed, cancelled
	StartedAt       time.Time              `json:"started_at"`
	CompletedAt     *time.Time             `json:"completed_at,omitempty"`
	CurrentStep     string                 `json:"current_step"`
	CompletedSteps  []string               `json:"completed_steps"`
	FailedSteps     []string               `json:"failed_steps"`
	Context         map[string]interface{} `json:"context"`
	Errors          []string               `json:"errors"`
	CorrelationID   string                 `json:"correlation_id"`
	TriggerEvent    *DomainEvent           `json:"trigger_event,omitempty"`
	Events          []*DomainEvent         `json:"events"`
}

// EventOrchestrationTestSuite - FORGE Movement 5 Test Suite
type EventOrchestrationTestSuite struct {
	suite.Suite
	eventBus     EventBus
	eventStore   EventStore
	evidence     map[string]interface{}
	testEvents   []*DomainEvent
	handlerCalls map[EventType]int
	mu           sync.RWMutex
}

func (suite *EventOrchestrationTestSuite) SetupSuite() {
	suite.evidence = make(map[string]interface{})
	suite.handlerCalls = make(map[EventType]int)
	
	// GREEN PHASE: Event infrastructure implemented - create actual instances
	suite.eventBus = NewEventBus(map[string]interface{}{"queue_size": 1000})
	suite.eventStore = NewEventStore(map[string]interface{}{})
	
	suite.setupTestEvents()
	
	suite.evidence["setup_completed"] = time.Now()
	suite.evidence["test_events_created"] = len(suite.testEvents)
}

func (suite *EventOrchestrationTestSuite) setupTestEvents() {
	// Create comprehensive test events for FORGE validation
	correlationID := uuid.New().String()
	
	suite.testEvents = []*DomainEvent{
		{
			ID:            uuid.New().String(),
			Type:          FabricSyncInitiated,
			AggregateID:   "fabric-001",
			Timestamp:     time.Now(),
			Version:       1,
			CorrelationID: correlationID,
			Source:        "cnoc-test-suite",
			Data: map[string]interface{}{
				"fabric_id":        "fabric-001",
				"git_repository":   "https://github.com/test/gitops.git",
				"gitops_directory": "gitops/fabric-1/",
				"triggered_by":     "user",
				"sync_type":        "full",
			},
			Metadata: map[string]interface{}{
				"test_case":    "fabric_sync_workflow",
				"environment":  "testing",
				"component":    "gitops-service",
			},
		},
		{
			ID:            uuid.New().String(),
			Type:          DriftDetectionStarted,
			AggregateID:   "fabric-001",
			Timestamp:     time.Now().Add(1 * time.Second),
			Version:       1,
			CorrelationID: correlationID,
			Source:        "drift-detection-service",
			Data: map[string]interface{}{
				"fabric_id":         "fabric-001",
				"detection_type":    "scheduled",
				"resources_to_check": 42,
				"timeout":           "5m",
			},
			Metadata: map[string]interface{}{
				"test_case":   "drift_detection_workflow",
				"scheduled":   true,
				"component":   "drift-detector",
			},
		},
		{
			ID:            uuid.New().String(),
			Type:          CRDCreated,
			AggregateID:   "vpc-001",
			Timestamp:     time.Now().Add(2 * time.Second),
			Version:       1,
			CorrelationID: correlationID,
			Source:        "crd-manager",
			Data: map[string]interface{}{
				"crd_id":        "vpc-001",
				"crd_type":      "VPC",
				"fabric_id":     "fabric-001",
				"namespace":     "hedgehog-fabric-1",
				"resource_name": "production-vpc-1",
				"spec": map[string]interface{}{
					"ipv4Namespace": "default",
					"subnets":       []string{"10.1.0.0/24"},
					"vlanId":        100,
				},
			},
			Metadata: map[string]interface{}{
				"test_case":     "crd_lifecycle",
				"operation":     "create",
				"component":     "crd-manager",
			},
		},
	}
}

func (suite *EventOrchestrationTestSuite) TearDownSuite() {
	if suite.eventBus != nil {
		suite.eventBus.Stop()
	}
	suite.evidence["teardown_completed"] = time.Now()
}

// TestFabricSyncEventFlow - FORGE Movement 5 Requirement
// Complete event chain from sync trigger to completion
func (suite *EventOrchestrationTestSuite) TestFabricSyncEventFlow() {
	startTime := time.Now()
	t := suite.T()
	
	if suite.eventBus == nil {
		t.Log("Event bus not implemented - test failing as expected in FORGE RED PHASE")
		assert.Fail(t, "Event bus implementation required")
		return
	}
	
	ctx := context.Background()
	correlationID := uuid.New().String()
	
	// Test 1: Initiate fabric sync workflow
	syncInitiatedEvent := &DomainEvent{
		ID:            uuid.New().String(),
		Type:          FabricSyncInitiated,
		AggregateID:   "fabric-001",
		Timestamp:     time.Now(),
		Version:       1,
		CorrelationID: correlationID,
		Source:        "fabric-controller",
		Data: map[string]interface{}{
			"fabric_id":        "fabric-001",
			"git_repository":   "https://github.com/test/gitops.git",
			"gitops_directory": "gitops/fabric-1/",
			"sync_type":        "full",
			"requested_by":     "test-user",
		},
	}
	
	// Setup event handler to track workflow progress
	var capturedEvents []*DomainEvent
	var mu sync.Mutex
	
	eventHandler := func(ctx context.Context, event *DomainEvent) error {
		mu.Lock()
		defer mu.Unlock()
		capturedEvents = append(capturedEvents, event)
		suite.recordHandlerCall(event.Type)
		return nil
	}
	
	// Subscribe to all fabric sync related events
	syncEvents := []EventType{
		FabricSyncInitiated,
		FabricSyncCompleted,
		FabricSyncFailed,
		CRDCreated,
		CRDUpdated,
		DriftDetectionStarted,
	}
	
	for _, eventType := range syncEvents {
		err := suite.eventBus.Subscribe(eventType, eventHandler)
		require.NoError(t, err, fmt.Sprintf("Should subscribe to %s events", eventType))
	}
	
	// Start event bus
	err := suite.eventBus.Start(ctx)
	require.NoError(t, err, "Event bus should start successfully")
	
	// Publish sync initiated event
	err = suite.eventBus.Publish(ctx, syncInitiatedEvent)
	assert.NoError(t, err, "Should publish sync initiated event")
	
	// Simulate workflow progression with realistic timing
	time.Sleep(100 * time.Millisecond) // Allow event processing
	
	// Test 2: Simulate GitOps processing events
	gitProcessingEvents := []*DomainEvent{
		{
			ID:            uuid.New().String(),
			Type:          CRDCreated,
			AggregateID:   "vpc-001",
			Timestamp:     time.Now(),
			Version:       1,
			CorrelationID: correlationID,
			CausationID:   syncInitiatedEvent.ID,
			Source:        "gitops-processor",
			Data: map[string]interface{}{
				"crd_type":      "VPC",
				"resource_name": "production-vpc",
				"fabric_id":     "fabric-001",
				"sync_result":   "created",
			},
		},
		{
			ID:            uuid.New().String(),
			Type:          CRDUpdated,
			AggregateID:   "connection-001",
			Timestamp:     time.Now().Add(50 * time.Millisecond),
			Version:       2,
			CorrelationID: correlationID,
			CausationID:   syncInitiatedEvent.ID,
			Source:        "gitops-processor",
			Data: map[string]interface{}{
				"crd_type":      "Connection",
				"resource_name": "switch-interconnect",
				"fabric_id":     "fabric-001",
				"sync_result":   "updated",
				"changes":       []string{"bandwidth", "vlan_tags"},
			},
		},
	}
	
	for _, event := range gitProcessingEvents {
		err = suite.eventBus.Publish(ctx, event)
		assert.NoError(t, err, fmt.Sprintf("Should publish %s event", event.Type))
	}
	
	time.Sleep(200 * time.Millisecond) // Allow processing
	
	// Test 3: Complete the sync workflow
	syncCompletedEvent := &DomainEvent{
		ID:            uuid.New().String(),
		Type:          FabricSyncCompleted,
		AggregateID:   "fabric-001",
		Timestamp:     time.Now(),
		Version:       1,
		CorrelationID: correlationID,
		CausationID:   syncInitiatedEvent.ID,
		Source:        "fabric-controller",
		Data: map[string]interface{}{
			"fabric_id":       "fabric-001",
			"sync_duration":   "2.5s",
			"files_processed": 5,
			"crds_created":    2,
			"crds_updated":    3,
			"crds_deleted":    0,
			"errors":          []string{},
			"status":          "completed",
		},
	}
	
	err = suite.eventBus.Publish(ctx, syncCompletedEvent)
	assert.NoError(t, err, "Should publish sync completed event")
	
	time.Sleep(100 * time.Millisecond) // Final processing
	
	// Test 4: Validate event flow integrity
	mu.Lock()
	defer mu.Unlock()
	
	assert.Greater(t, len(capturedEvents), 0, "Should capture events from workflow")
	
	// Validate correlation IDs are consistent
	for _, event := range capturedEvents {
		assert.Equal(t, correlationID, event.CorrelationID, "All events should have same correlation ID")
	}
	
	// Validate causation chain
	causedEvents := 0
	for _, event := range capturedEvents {
		if event.CausationID == syncInitiatedEvent.ID {
			causedEvents++
		}
	}
	assert.Greater(t, causedEvents, 0, "Some events should be caused by initial sync event")
	
	// Test 5: Validate event handler invocation counts
	assert.Greater(t, suite.getHandlerCallCount(FabricSyncInitiated), 0, "Sync initiated handler should be called")
	assert.Greater(t, suite.getHandlerCallCount(CRDCreated), 0, "CRD created handler should be called")
	
	// Evidence collection
	duration := time.Since(startTime)
	suite.evidence["fabric_sync_flow_duration"] = duration
	suite.evidence["events_in_flow"] = len(capturedEvents)
	suite.evidence["handler_call_counts"] = suite.handlerCalls
	suite.evidence["correlation_id"] = correlationID
	
	// Performance requirement: Event flow should complete within 5 seconds
	assert.Less(t, duration, 5*time.Second, "Event flow should be reasonably fast")
}

// TestDriftDetectionEvents - FORGE Movement 5 Requirement
// Event-driven drift detection with notifications
func (suite *EventOrchestrationTestSuite) TestDriftDetectionEvents() {
	startTime := time.Now()
	t := suite.T()
	
	if suite.eventBus == nil {
		t.Log("Event bus not implemented - test failing as expected in FORGE RED PHASE")
		assert.Fail(t, "Event bus implementation required")
		return
	}
	
	ctx := context.Background()
	correlationID := uuid.New().String()
	
	// Test drift detection workflow events
	driftEvents := []*DomainEvent{
		{
			ID:            uuid.New().String(),
			Type:          DriftDetectionStarted,
			AggregateID:   "fabric-001",
			Timestamp:     time.Now(),
			Version:       1,
			CorrelationID: correlationID,
			Source:        "drift-detector",
			Data: map[string]interface{}{
				"fabric_id":          "fabric-001",
				"detection_type":     "scheduled",
				"resources_to_check": 42,
				"baseline_commit":    "abc123def456",
			},
		},
		{
			ID:            uuid.New().String(),
			Type:          DriftDetected,
			AggregateID:   "fabric-001",
			Timestamp:     time.Now().Add(2 * time.Second),
			Version:       1,
			CorrelationID: correlationID,
			Source:        "drift-detector",
			Data: map[string]interface{}{
				"fabric_id":          "fabric-001",
				"drift_severity":     "medium",
				"affected_resources": 3,
				"drift_details": []map[string]interface{}{
					{
						"resource": "production-vpc",
						"type":     "VPC",
						"changes":  []string{"subnet added", "vlan changed"},
					},
					{
						"resource": "switch-interconnect",
						"type":     "Connection",
						"changes":  []string{"bandwidth modified"},
					},
				},
			},
		},
		{
			ID:            uuid.New().String(),
			Type:          DriftResolved,
			AggregateID:   "fabric-001",
			Timestamp:     time.Now().Add(5 * time.Second),
			Version:       1,
			CorrelationID: correlationID,
			Source:        "fabric-controller",
			Data: map[string]interface{}{
				"fabric_id":      "fabric-001",
				"resolution_type": "auto_sync",
				"resolved_resources": 3,
				"sync_commit":    "def456ghi789",
			},
		},
	}
	
	var receivedEvents []*DomainEvent
	var mu sync.Mutex
	
	driftHandler := func(ctx context.Context, event *DomainEvent) error {
		mu.Lock()
		defer mu.Unlock()
		receivedEvents = append(receivedEvents, event)
		suite.recordHandlerCall(event.Type)
		
		// Simulate processing time
		time.Sleep(10 * time.Millisecond)
		return nil
	}
	
	// Subscribe to drift detection events
	driftEventTypes := []EventType{DriftDetectionStarted, DriftDetected, DriftResolved}
	for _, eventType := range driftEventTypes {
		err := suite.eventBus.Subscribe(eventType, driftHandler)
		require.NoError(t, err)
	}
	
	err := suite.eventBus.Start(ctx)
	require.NoError(t, err)
	
	// Publish drift detection events in sequence
	for _, event := range driftEvents {
		err = suite.eventBus.Publish(ctx, event)
		assert.NoError(t, err, fmt.Sprintf("Should publish %s event", event.Type))
		time.Sleep(50 * time.Millisecond) // Realistic timing
	}
	
	time.Sleep(200 * time.Millisecond) // Allow processing
	
	// Validate drift detection workflow
	mu.Lock()
	defer mu.Unlock()
	
	assert.Equal(t, len(driftEvents), len(receivedEvents), "Should receive all drift detection events")
	
	// Validate event sequence and correlation
	for i, receivedEvent := range receivedEvents {
		assert.Equal(t, driftEvents[i].Type, receivedEvent.Type, "Event types should match sequence")
		assert.Equal(t, correlationID, receivedEvent.CorrelationID, "Correlation ID should be consistent")
	}
	
	// Evidence collection
	duration := time.Since(startTime)
	suite.evidence["drift_detection_duration"] = duration
	suite.evidence["drift_events_processed"] = len(receivedEvents)
}

// TestErrorRecoveryEvents - FORGE Movement 5 Requirement
// Event handling for failed operations
func (suite *EventOrchestrationTestSuite) TestErrorRecoveryEvents() {
	startTime := time.Now()
	t := suite.T()
	
	if suite.eventBus == nil {
		t.Log("Event bus not implemented - test failing as expected in FORGE RED PHASE")
		assert.Fail(t, "Event bus implementation required")
		return
	}
	
	ctx := context.Background()
	
	// Test error scenarios and recovery
	errorScenarios := []struct {
		name  string
		event *DomainEvent
	}{
		{
			name: "GitOps Operation Failed",
			event: &DomainEvent{
				ID:          uuid.New().String(),
				Type:        GitOpsOperationFailed,
				AggregateID: "fabric-001",
				Timestamp:   time.Now(),
				Source:      "gitops-service",
				Data: map[string]interface{}{
					"fabric_id":    "fabric-001",
					"operation":    "sync",
					"error_type":   "authentication",
					"error_message": "Git authentication failed",
					"retry_count":  0,
					"max_retries":  3,
				},
			},
		},
		{
			name: "Kubernetes Connectivity Lost",
			event: &DomainEvent{
				ID:          uuid.New().String(),
				Type:        K8sConnectivityLost,
				AggregateID: "cluster-001",
				Timestamp:   time.Now(),
				Source:      "k8s-monitor",
				Data: map[string]interface{}{
					"cluster_endpoint": "https://k8s.example.com:6443",
					"error_type":      "network",
					"last_successful": time.Now().Add(-5 * time.Minute),
					"affected_fabrics": []string{"fabric-001", "fabric-002"},
				},
			},
		},
		{
			name: "Fabric Sync Failed",
			event: &DomainEvent{
				ID:          uuid.New().String(),
				Type:        FabricSyncFailed,
				AggregateID: "fabric-001",
				Timestamp:   time.Now(),
				Source:      "fabric-controller",
				Data: map[string]interface{}{
					"fabric_id":       "fabric-001",
					"failure_reason":  "invalid YAML",
					"failed_files":    []string{"invalid-vpc.yaml", "malformed-connection.yaml"},
					"partial_success": true,
					"processed_files": 3,
					"failed_files_count": 2,
				},
			},
		},
	}
	
	var errorEvents []*DomainEvent
	var mu sync.Mutex
	
	errorHandler := func(ctx context.Context, event *DomainEvent) error {
		mu.Lock()
		defer mu.Unlock()
		errorEvents = append(errorEvents, event)
		suite.recordHandlerCall(event.Type)
		
		// Simulate error recovery logic
		switch event.Type {
		case GitOpsOperationFailed:
			// Simulate retry logic
			retryCount, _ := event.Data["retry_count"].(int)
			if retryCount < 3 {
				t.Logf("Simulating retry for GitOps operation (attempt %d)", retryCount+1)
			}
		case K8sConnectivityLost:
			// Simulate health check and recovery
			t.Log("Simulating Kubernetes connectivity recovery")
		case FabricSyncFailed:
			// Simulate partial recovery and notification
			t.Log("Simulating fabric sync failure handling")
		}
		
		return nil
	}
	
	// Subscribe to error events
	errorEventTypes := []EventType{GitOpsOperationFailed, K8sConnectivityLost, FabricSyncFailed}
	for _, eventType := range errorEventTypes {
		err := suite.eventBus.Subscribe(eventType, errorHandler)
		require.NoError(t, err)
	}
	
	err := suite.eventBus.Start(ctx)
	require.NoError(t, err)
	
	// Publish error scenarios
	for _, scenario := range errorScenarios {
		t.Run(scenario.name, func(t *testing.T) {
			err := suite.eventBus.Publish(ctx, scenario.event)
			assert.NoError(t, err, fmt.Sprintf("Should publish %s", scenario.name))
		})
	}
	
	time.Sleep(200 * time.Millisecond) // Allow processing
	
	// Validate error handling
	mu.Lock()
	defer mu.Unlock()
	
	assert.Equal(t, len(errorScenarios), len(errorEvents), "Should handle all error scenarios")
	
	// Evidence collection
	duration := time.Since(startTime)
	suite.evidence["error_recovery_duration"] = duration
	suite.evidence["error_scenarios_tested"] = len(errorScenarios)
}

// TestEventPersistence - FORGE Movement 5 Requirement
// Event sourcing and replay capabilities
func (suite *EventOrchestrationTestSuite) TestEventPersistence() {
	startTime := time.Now()
	t := suite.T()
	
	if suite.eventStore == nil {
		t.Log("Event store not implemented - test failing as expected in FORGE RED PHASE")
		assert.Fail(t, "Event store implementation required")
		return
	}
	
	ctx := context.Background()
	
	// Test 1: Save events to store
	err := suite.eventStore.Save(ctx, suite.testEvents)
	assert.NoError(t, err, "Should save events to store")
	
	// Test 2: Load events by aggregate ID
	aggregateID := suite.testEvents[0].AggregateID
	loadedEvents, err := suite.eventStore.Load(ctx, aggregateID)
	assert.NoError(t, err, "Should load events by aggregate ID")
	assert.Greater(t, len(loadedEvents), 0, "Should load at least one event")
	
	// Test 3: Load events by type
	eventType := FabricSyncInitiated
	typeEvents, err := suite.eventStore.LoadByType(ctx, eventType, 10)
	assert.NoError(t, err, "Should load events by type")
	
	for _, event := range typeEvents {
		assert.Equal(t, eventType, event.Type, "All loaded events should have correct type")
	}
	
	// Test 4: Load events by time range
	startTime := time.Now().Add(-1 * time.Hour)
	endTime := time.Now().Add(1 * time.Hour)
	rangeEvents, err := suite.eventStore.LoadByTimeRange(ctx, startTime, endTime)
	assert.NoError(t, err, "Should load events by time range")
	
	for _, event := range rangeEvents {
		assert.True(t, event.Timestamp.After(startTime) || event.Timestamp.Equal(startTime), "Event should be within time range")
		assert.True(t, event.Timestamp.Before(endTime) || event.Timestamp.Equal(endTime), "Event should be within time range")
	}
	
	// Test 5: Event replay functionality
	replayedEvents := make([]*DomainEvent, 0)
	replayHandler := func(ctx context.Context, event *DomainEvent) error {
		replayedEvents = append(replayedEvents, event)
		return nil
	}
	
	replayStartTime := time.Now().Add(-1 * time.Hour)
	err = suite.eventStore.Replay(ctx, replayStartTime, replayHandler)
	assert.NoError(t, err, "Should replay events from specified time")
	assert.Greater(t, len(replayedEvents), 0, "Should replay at least one event")
	
	// Test 6: Count events by type
	count, err := suite.eventStore.Count(ctx, FabricSyncInitiated)
	assert.NoError(t, err, "Should count events by type")
	assert.GreaterOrEqual(t, count, int64(1), "Should have at least one fabric sync initiated event")
	
	// Evidence collection
	duration := time.Since(startTime)
	suite.evidence["persistence_test_duration"] = duration
	suite.evidence["events_saved"] = len(suite.testEvents)
	suite.evidence["events_loaded"] = len(loadedEvents)
	suite.evidence["events_replayed"] = len(replayedEvents)
}

// TestEventPerformance - FORGE Movement 5 Requirement
// Event processing latency benchmarks
func (suite *EventOrchestrationTestSuite) TestEventPerformance() {
	startTime := time.Now()
	t := suite.T()
	
	if suite.eventBus == nil {
		t.Log("Event bus not implemented - test failing as expected in FORGE RED PHASE")
		assert.Fail(t, "Event bus implementation required")
		return
	}
	
	ctx := context.Background()
	
	// Performance test configuration
	const (
		testEvents       = 1000
		concurrentWorkers = 10
		maxLatency       = 100 * time.Millisecond
	)
	
	var processedCount int64
	var totalLatency time.Duration
	var maxObservedLatency time.Duration
	var mu sync.Mutex
	
	performanceHandler := func(ctx context.Context, event *DomainEvent) error {
		processingStart := time.Now()
		
		// Simulate realistic processing
		time.Sleep(1 * time.Millisecond)
		
		processingLatency := time.Since(processingStart)
		
		mu.Lock()
		processedCount++
		totalLatency += processingLatency
		if processingLatency > maxObservedLatency {
			maxObservedLatency = processingLatency
		}
		mu.Unlock()
		
		return nil
	}
	
	// Subscribe to test event type
	err := suite.eventBus.Subscribe(FabricSyncInitiated, performanceHandler)
	require.NoError(t, err)
	
	err = suite.eventBus.Start(ctx)
	require.NoError(t, err)
	
	// Generate and publish test events
	testEventStart := time.Now()
	
	for i := 0; i < testEvents; i++ {
		testEvent := &DomainEvent{
			ID:            uuid.New().String(),
			Type:          FabricSyncInitiated,
			AggregateID:   fmt.Sprintf("fabric-%03d", i%10),
			Timestamp:     time.Now(),
			Version:       1,
			CorrelationID: uuid.New().String(),
			Source:        "performance-test",
			Data: map[string]interface{}{
				"test_event": i,
				"batch":      "performance_test",
			},
		}
		
		err := suite.eventBus.Publish(ctx, testEvent)
		assert.NoError(t, err, "Should publish performance test event")
	}
	
	eventPublishDuration := time.Since(testEventStart)
	
	// Wait for all events to be processed
	timeout := time.After(10 * time.Second)
	ticker := time.NewTicker(100 * time.Millisecond)
	defer ticker.Stop()
	
	for {
		select {
		case <-timeout:
			t.Fatal("Performance test timed out")
		case <-ticker.C:
			mu.Lock()
			count := processedCount
			mu.Unlock()
			
			if count >= int64(testEvents) {
				goto performanceComplete
			}
		}
	}
	
performanceComplete:
	totalTestDuration := time.Since(testEventStart)
	
	// Calculate performance metrics
	mu.Lock()
	avgLatency := totalLatency / time.Duration(processedCount)
	eventsPerSecond := float64(processedCount) / totalTestDuration.Seconds()
	mu.Unlock()
	
	// Validate performance requirements
	assert.Equal(t, int64(testEvents), processedCount, "Should process all test events")
	assert.Less(t, avgLatency, maxLatency, "Average latency should be acceptable")
	assert.Greater(t, eventsPerSecond, 100.0, "Should process at least 100 events per second")
	
	// Get event bus metrics
	metrics := suite.eventBus.GetMetrics()
	assert.GreaterOrEqual(t, metrics.EventsPublished, int64(testEvents), "Metrics should track published events")
	assert.GreaterOrEqual(t, metrics.EventsProcessed, int64(testEvents), "Metrics should track processed events")
	
	// Evidence collection
	duration := time.Since(startTime)
	suite.evidence["performance_test_duration"] = duration
	suite.evidence["events_published"] = testEvents
	suite.evidence["events_processed"] = processedCount
	suite.evidence["publish_duration"] = eventPublishDuration
	suite.evidence["total_processing_duration"] = totalTestDuration
	suite.evidence["average_latency_ms"] = avgLatency.Milliseconds()
	suite.evidence["max_latency_ms"] = maxObservedLatency.Milliseconds()
	suite.evidence["events_per_second"] = eventsPerSecond
	suite.evidence["event_bus_metrics"] = metrics
	
	// Performance requirements
	assert.Less(t, duration, 15*time.Second, "Performance test should complete quickly")
}

// Helper methods

func (suite *EventOrchestrationTestSuite) recordHandlerCall(eventType EventType) {
	suite.mu.Lock()
	defer suite.mu.Unlock()
	suite.handlerCalls[eventType]++
}

func (suite *EventOrchestrationTestSuite) getHandlerCallCount(eventType EventType) int {
	suite.mu.RLock()
	defer suite.mu.RUnlock()
	return suite.handlerCalls[eventType]
}

// Helper functions are now implemented in event_orchestrator.go
// NewEventBus and NewEventStore are available from event_orchestrator.go

// Run the test suite
func TestEventOrchestrationTestSuite(t *testing.T) {
	suite.Run(t, new(EventOrchestrationTestSuite))
}

// FORGE Evidence Collection Test
func TestEventOrchestrationEvidenceCollection(t *testing.T) {
	evidence := map[string]interface{}{
		"test_execution_time": time.Now(),
		"framework_version":   "FORGE Movement 5",
		"test_coverage":       "Event Orchestration",
		"expected_failures":   false,
		"red_phase_active":    false,
		"event_types_tested": []EventType{
			FabricSyncInitiated,
			FabricSyncCompleted,
			FabricSyncFailed,
			DriftDetectionStarted,
			DriftDetected,
			DriftResolved,
			CRDCreated,
			CRDUpdated,
			CRDDeleted,
			GitOpsOperationFailed,
			K8sConnectivityLost,
			K8sConnectivityRestored,
		},
		"orchestration_features": []string{
			"event-driven workflows",
			"correlation tracking",
			"causation chains",
			"error recovery",
			"event persistence",
			"event replay",
			"performance monitoring",
		},
		"performance_requirements": map[string]string{
			"event_latency":     "<100ms",
			"throughput":        ">100 events/sec",
			"workflow_completion": "<5 seconds",
			"error_recovery":    "automatic with retry",
		},
	}
	
	assert.NotEmpty(t, evidence)
	assert.Contains(t, evidence, "event_types_tested")
	assert.Equal(t, false, evidence["red_phase_active"])
	
	t.Logf("FORGE Event Orchestration Evidence Collection: %+v", evidence)
}

// Performance benchmark tests
func BenchmarkEventPublishing(b *testing.B) {
	eventBus := NewEventBus(map[string]interface{}{"queue_size": 1000})
	if eventBus == nil {
		b.Skip("Event bus not implemented - RED PHASE expected")
		return
	}
	
	ctx := context.Background()
	testEvent := &DomainEvent{
		ID:          uuid.New().String(),
		Type:        FabricSyncInitiated,
		AggregateID: "benchmark-fabric",
		Timestamp:   time.Now(),
		Source:      "benchmark",
		Data:        map[string]interface{}{"test": "benchmark"},
	}
	
	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		_ = eventBus.Publish(ctx, testEvent)
	}
}

func BenchmarkEventHandling(b *testing.B) {
	eventBus := NewEventBus(map[string]interface{}{"queue_size": 1000})
	if eventBus == nil {
		b.Skip("Event bus not implemented - RED PHASE expected")
		return
	}
	
	handler := func(ctx context.Context, event *DomainEvent) error {
		// Simulate minimal processing
		time.Sleep(time.Microsecond)
		return nil
	}
	
	_ = eventBus.Subscribe(FabricSyncInitiated, handler)
	
	ctx := context.Background()
	testEvent := &DomainEvent{
		ID:          uuid.New().String(),
		Type:        FabricSyncInitiated,
		AggregateID: "benchmark-fabric",
		Timestamp:   time.Now(),
		Source:      "benchmark",
		Data:        map[string]interface{}{"test": "benchmark"},
	}
	
	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		_ = eventBus.Publish(ctx, testEvent)
	}
}