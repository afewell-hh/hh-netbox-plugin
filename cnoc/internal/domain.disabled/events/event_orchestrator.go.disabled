package events

import (
	"context"
	"fmt"
	"sync"
	"time"

	"github.com/google/uuid"
)

// EventBusImpl implements the EventBus interface
type EventBusImpl struct {
	handlers     map[EventType][]EventHandlerRegistration
	metrics      EventBusMetrics
	running      bool
	stopChan     chan struct{}
	eventQueue   chan *DomainEvent
	mu           sync.RWMutex
	wg           sync.WaitGroup
}

// NewEventBus creates a new event bus implementation
func NewEventBus(config map[string]interface{}) EventBus {
	queueSize := 1000
	if qs, exists := config["queue_size"]; exists {
		if size, ok := qs.(int); ok {
			queueSize = size
		}
	}
	
	return &EventBusImpl{
		handlers:   make(map[EventType][]EventHandlerRegistration),
		eventQueue: make(chan *DomainEvent, queueSize),
		stopChan:   make(chan struct{}),
		metrics: EventBusMetrics{
			EventsPublished:     0,
			EventsProcessed:     0,
			EventsFailed:        0,
			AverageLatency:      0,
			MaxLatency:          0,
			HandlersRegistered:  0,
			ActiveSubscriptions: 0,
			QueueDepth:          0,
			ProcessingRate:      0,
		},
	}
}

// Start starts the event bus
func (eb *EventBusImpl) Start(ctx context.Context) error {
	eb.mu.Lock()
	defer eb.mu.Unlock()
	
	if eb.running {
		return fmt.Errorf("event bus already running")
	}
	
	eb.running = true
	
	// Start event processing goroutines
	numWorkers := 5
	for i := 0; i < numWorkers; i++ {
		eb.wg.Add(1)
		go eb.eventProcessor(ctx)
	}
	
	// Start metrics collector
	eb.wg.Add(1)
	go eb.metricsCollector()
	
	return nil
}

// Stop stops the event bus
func (eb *EventBusImpl) Stop() error {
	eb.mu.Lock()
	defer eb.mu.Unlock()
	
	if !eb.running {
		return nil
	}
	
	eb.running = false
	close(eb.stopChan)
	
	// Wait for all workers to finish
	eb.wg.Wait()
	
	return nil
}

// Publish publishes an event to the bus
func (eb *EventBusImpl) Publish(ctx context.Context, event *DomainEvent) error {
	if event == nil {
		return fmt.Errorf("event cannot be nil")
	}
	
	eb.mu.RLock()
	running := eb.running
	eb.mu.RUnlock()
	
	if !running {
		return fmt.Errorf("event bus is not running")
	}
	
	select {
	case eb.eventQueue <- event:
		eb.mu.Lock()
		eb.metrics.EventsPublished++
		eb.metrics.QueueDepth = len(eb.eventQueue)
		eb.mu.Unlock()
		return nil
	case <-ctx.Done():
		return ctx.Err()
	default:
		return fmt.Errorf("event queue is full")
	}
}

// Subscribe subscribes to an event type synchronously
func (eb *EventBusImpl) Subscribe(eventType EventType, handler EventHandler) error {
	return eb.subscribe(eventType, handler, false)
}

// SubscribeAsync subscribes to an event type asynchronously
func (eb *EventBusImpl) SubscribeAsync(eventType EventType, handler EventHandler) error {
	return eb.subscribe(eventType, handler, true)
}

// subscribe internal subscription implementation
func (eb *EventBusImpl) subscribe(eventType EventType, handler EventHandler, async bool) error {
	if handler == nil {
		return fmt.Errorf("handler cannot be nil")
	}
	
	eb.mu.Lock()
	defer eb.mu.Unlock()
	
	registration := EventHandlerRegistration{
		EventType: eventType,
		Handler:   handler,
		Async:     async,
		Priority:  0,
	}
	
	eb.handlers[eventType] = append(eb.handlers[eventType], registration)
	eb.metrics.HandlersRegistered++
	eb.metrics.ActiveSubscriptions++
	
	return nil
}

// Unsubscribe unsubscribes from an event type
func (eb *EventBusImpl) Unsubscribe(eventType EventType, handler EventHandler) error {
	eb.mu.Lock()
	defer eb.mu.Unlock()
	
	handlers, exists := eb.handlers[eventType]
	if !exists {
		return fmt.Errorf("no handlers registered for event type %s", eventType)
	}
	
	// Find and remove the handler
	for i, registration := range handlers {
		// Note: This is a simplified comparison - in production, you'd need a better way to identify handlers
		if fmt.Sprintf("%p", registration.Handler) == fmt.Sprintf("%p", handler) {
			eb.handlers[eventType] = append(handlers[:i], handlers[i+1:]...)
			eb.metrics.ActiveSubscriptions--
			if len(eb.handlers[eventType]) == 0 {
				delete(eb.handlers, eventType)
			}
			return nil
		}
	}
	
	return fmt.Errorf("handler not found for event type %s", eventType)
}

// GetMetrics returns current event bus metrics
func (eb *EventBusImpl) GetMetrics() EventBusMetrics {
	eb.mu.RLock()
	defer eb.mu.RUnlock()
	return eb.metrics
}

// eventProcessor processes events from the queue
func (eb *EventBusImpl) eventProcessor(ctx context.Context) {
	defer eb.wg.Done()
	
	for {
		select {
		case event := <-eb.eventQueue:
			eb.processEvent(ctx, event)
		case <-eb.stopChan:
			return
		case <-ctx.Done():
			return
		}
	}
}

// processEvent processes a single event
func (eb *EventBusImpl) processEvent(ctx context.Context, event *DomainEvent) {
	start := time.Now()
	
	eb.mu.RLock()
	handlers, exists := eb.handlers[event.Type]
	eb.mu.RUnlock()
	
	if !exists {
		// No handlers for this event type
		return
	}
	
	processed := false
	failed := false
	
	for _, registration := range handlers {
		if registration.Async {
			// Process asynchronously
			go func(reg EventHandlerRegistration) {
				if err := reg.Handler(ctx, event); err != nil {
					// Log error (in production, you'd use a proper logger)
					fmt.Printf("Async handler error for event %s: %v\n", event.Type, err)
				}
			}(registration)
		} else {
			// Process synchronously
			if err := registration.Handler(ctx, event); err != nil {
				fmt.Printf("Handler error for event %s: %v\n", event.Type, err)
				failed = true
			} else {
				processed = true
			}
		}
	}
	
	// Update metrics
	eb.mu.Lock()
	defer eb.mu.Unlock()
	
	duration := time.Since(start)
	
	if processed {
		eb.metrics.EventsProcessed++
	}
	
	if failed {
		eb.metrics.EventsFailed++
	}
	
	// Update latency metrics
	if eb.metrics.MaxLatency < duration {
		eb.metrics.MaxLatency = duration
	}
	
	// Update average latency (simplified calculation)
	totalEvents := eb.metrics.EventsProcessed + eb.metrics.EventsFailed
	if totalEvents > 0 {
		eb.metrics.AverageLatency = time.Duration(
			(int64(eb.metrics.AverageLatency)*int64(totalEvents-1) + int64(duration)) / int64(totalEvents),
		)
	}
	
	eb.metrics.QueueDepth = len(eb.eventQueue)
	
	// Mark event as processed
	event.Processed = true
	now := time.Now()
	event.ProcessedAt = &now
}

// metricsCollector collects performance metrics
func (eb *EventBusImpl) metricsCollector() {
	defer eb.wg.Done()
	
	ticker := time.NewTicker(1 * time.Second)
	defer ticker.Stop()
	
	var lastProcessed int64
	
	for {
		select {
		case <-ticker.C:
			eb.mu.Lock()
			currentProcessed := eb.metrics.EventsProcessed
			eb.metrics.ProcessingRate = float64(currentProcessed - lastProcessed)
			lastProcessed = currentProcessed
			eb.mu.Unlock()
		case <-eb.stopChan:
			return
		}
	}
}

// EventStoreImpl implements the EventStore interface
type EventStoreImpl struct {
	events map[string][]*DomainEvent // aggregateID -> events
	mu     sync.RWMutex
}

// NewEventStore creates a new event store implementation
func NewEventStore(config map[string]interface{}) EventStore {
	return &EventStoreImpl{
		events: make(map[string][]*DomainEvent),
	}
}

// Save saves events to the store
func (es *EventStoreImpl) Save(ctx context.Context, events []*DomainEvent) error {
	if events == nil || len(events) == 0 {
		return fmt.Errorf("no events to save")
	}
	
	es.mu.Lock()
	defer es.mu.Unlock()
	
	for _, event := range events {
		if event.AggregateID == "" {
			return fmt.Errorf("event aggregate ID cannot be empty")
		}
		
		es.events[event.AggregateID] = append(es.events[event.AggregateID], event)
	}
	
	return nil
}

// Load loads events for an aggregate
func (es *EventStoreImpl) Load(ctx context.Context, aggregateID string) ([]*DomainEvent, error) {
	if aggregateID == "" {
		return nil, fmt.Errorf("aggregate ID cannot be empty")
	}
	
	es.mu.RLock()
	defer es.mu.RUnlock()
	
	events, exists := es.events[aggregateID]
	if !exists {
		return []*DomainEvent{}, nil
	}
	
	// Return a copy to avoid race conditions
	result := make([]*DomainEvent, len(events))
	copy(result, events)
	
	return result, nil
}

// LoadByType loads events by type with a limit
func (es *EventStoreImpl) LoadByType(ctx context.Context, eventType EventType, limit int) ([]*DomainEvent, error) {
	es.mu.RLock()
	defer es.mu.RUnlock()
	
	var result []*DomainEvent
	count := 0
	
	for _, aggregateEvents := range es.events {
		for _, event := range aggregateEvents {
			if event.Type == eventType {
				result = append(result, event)
				count++
				if limit > 0 && count >= limit {
					break
				}
			}
		}
		if limit > 0 && count >= limit {
			break
		}
	}
	
	return result, nil
}

// LoadByTimeRange loads events within a time range
func (es *EventStoreImpl) LoadByTimeRange(ctx context.Context, start, end time.Time) ([]*DomainEvent, error) {
	es.mu.RLock()
	defer es.mu.RUnlock()
	
	var result []*DomainEvent
	
	for _, aggregateEvents := range es.events {
		for _, event := range aggregateEvents {
			if event.Timestamp.After(start) && event.Timestamp.Before(end) {
				result = append(result, event)
			}
		}
	}
	
	return result, nil
}

// Count counts events by type
func (es *EventStoreImpl) Count(ctx context.Context, eventType EventType) (int64, error) {
	es.mu.RLock()
	defer es.mu.RUnlock()
	
	var count int64
	
	for _, aggregateEvents := range es.events {
		for _, event := range aggregateEvents {
			if event.Type == eventType {
				count++
			}
		}
	}
	
	return count, nil
}

// Replay replays events from a specific time
func (es *EventStoreImpl) Replay(ctx context.Context, fromTime time.Time, handler EventHandler) error {
	if handler == nil {
		return fmt.Errorf("handler cannot be nil")
	}
	
	es.mu.RLock()
	defer es.mu.RUnlock()
	
	for _, aggregateEvents := range es.events {
		for _, event := range aggregateEvents {
			if event.Timestamp.After(fromTime) || event.Timestamp.Equal(fromTime) {
				if err := handler(ctx, event); err != nil {
					return fmt.Errorf("replay handler error for event %s: %w", event.ID, err)
				}
			}
		}
	}
	
	return nil
}

// WorkflowOrchestrator manages complex workflows
type WorkflowOrchestrator struct {
	eventBus      EventBus
	workflows     map[string]*WorkflowDefinition
	executions    map[string]*WorkflowExecution
	mu           sync.RWMutex
}

// NewWorkflowOrchestrator creates a new workflow orchestrator
func NewWorkflowOrchestrator(eventBus EventBus) *WorkflowOrchestrator {
	return &WorkflowOrchestrator{
		eventBus:   eventBus,
		workflows:  make(map[string]*WorkflowDefinition),
		executions: make(map[string]*WorkflowExecution),
	}
}

// RegisterWorkflow registers a workflow definition
func (wo *WorkflowOrchestrator) RegisterWorkflow(workflow *WorkflowDefinition) error {
	if workflow == nil {
		return fmt.Errorf("workflow cannot be nil")
	}
	
	if workflow.ID == "" {
		return fmt.Errorf("workflow ID cannot be empty")
	}
	
	wo.mu.Lock()
	defer wo.mu.Unlock()
	
	wo.workflows[workflow.ID] = workflow
	
	// Subscribe to trigger events
	for _, trigger := range workflow.Triggers {
		wo.eventBus.Subscribe(trigger, wo.createWorkflowTriggerHandler(workflow.ID))
	}
	
	return nil
}

// ExecuteWorkflow executes a workflow
func (wo *WorkflowOrchestrator) ExecuteWorkflow(ctx context.Context, workflowID string, triggerEvent *DomainEvent) (*WorkflowExecution, error) {
	wo.mu.RLock()
	workflow, exists := wo.workflows[workflowID]
	wo.mu.RUnlock()
	
	if !exists {
		return nil, fmt.Errorf("workflow %s not found", workflowID)
	}
	
	execution := &WorkflowExecution{
		ID:              uuid.New().String(),
		WorkflowID:      workflowID,
		Status:          "running",
		StartedAt:       time.Now(),
		CurrentStep:     "",
		CompletedSteps:  []string{},
		FailedSteps:     []string{},
		Context:         make(map[string]interface{}),
		Errors:          []string{},
		CorrelationID:   triggerEvent.CorrelationID,
		TriggerEvent:    triggerEvent,
		Events:          []*DomainEvent{triggerEvent},
	}
	
	wo.mu.Lock()
	wo.executions[execution.ID] = execution
	wo.mu.Unlock()
	
	// Publish workflow started event
	startedEvent := &DomainEvent{
		ID:            uuid.New().String(),
		Type:          WorkflowStarted,
		AggregateID:   execution.ID,
		Timestamp:     time.Now(),
		Version:       1,
		CorrelationID: triggerEvent.CorrelationID,
		CausationID:   triggerEvent.ID,
		Source:        "workflow-orchestrator",
		Data: map[string]interface{}{
			"workflow_id":     workflowID,
			"execution_id":    execution.ID,
			"trigger_event":   triggerEvent.Type,
		},
	}
	
	wo.eventBus.Publish(ctx, startedEvent)
	
	// Execute workflow steps (simplified implementation)
	go wo.executeWorkflowSteps(ctx, execution, workflow)
	
	return execution, nil
}

// createWorkflowTriggerHandler creates a handler for workflow triggers
func (wo *WorkflowOrchestrator) createWorkflowTriggerHandler(workflowID string) EventHandler {
	return func(ctx context.Context, event *DomainEvent) error {
		_, err := wo.ExecuteWorkflow(ctx, workflowID, event)
		return err
	}
}

// executeWorkflowSteps executes workflow steps
func (wo *WorkflowOrchestrator) executeWorkflowSteps(ctx context.Context, execution *WorkflowExecution, workflow *WorkflowDefinition) {
	defer func() {
		// Mark execution as completed or failed
		wo.mu.Lock()
		if len(execution.Errors) > 0 {
			execution.Status = "failed"
		} else {
			execution.Status = "completed"
		}
		now := time.Now()
		execution.CompletedAt = &now
		wo.mu.Unlock()
		
		// Publish completion event
		eventType := WorkflowCompleted
		if execution.Status == "failed" {
			eventType = WorkflowFailed
		}
		
		completionEvent := &DomainEvent{
			ID:            uuid.New().String(),
			Type:          eventType,
			AggregateID:   execution.ID,
			Timestamp:     time.Now(),
			Version:       1,
			CorrelationID: execution.CorrelationID,
			Source:        "workflow-orchestrator",
			Data: map[string]interface{}{
				"workflow_id":    workflow.ID,
				"execution_id":   execution.ID,
				"status":         execution.Status,
				"duration":       time.Since(execution.StartedAt).String(),
			},
		}
		
		wo.eventBus.Publish(ctx, completionEvent)
	}()
	
	// Simple step execution (in production, this would be more sophisticated)
	for _, step := range workflow.Steps {
		wo.mu.Lock()
		execution.CurrentStep = step.ID
		wo.mu.Unlock()
		
		// Simulate step execution
		time.Sleep(10 * time.Millisecond)
		
		// Check for step conditions and dependencies
		if wo.canExecuteStep(step, execution) {
			if wo.executeStep(ctx, step, execution) {
				wo.mu.Lock()
				execution.CompletedSteps = append(execution.CompletedSteps, step.ID)
				wo.mu.Unlock()
			} else {
				wo.mu.Lock()
				execution.FailedSteps = append(execution.FailedSteps, step.ID)
				execution.Errors = append(execution.Errors, fmt.Sprintf("Step %s failed", step.ID))
				wo.mu.Unlock()
				break // Stop on first failure (configurable in production)
			}
		}
	}
}

// canExecuteStep checks if a step can be executed
func (wo *WorkflowOrchestrator) canExecuteStep(step WorkflowStep, execution *WorkflowExecution) bool {
	// Check dependencies
	for _, dep := range step.Dependencies {
		found := false
		for _, completed := range execution.CompletedSteps {
			if completed == dep {
				found = true
				break
			}
		}
		if !found {
			return false
		}
	}
	
	// TODO: Check conditions (simplified for now)
	return true
}

// executeStep executes a single workflow step
func (wo *WorkflowOrchestrator) executeStep(ctx context.Context, step WorkflowStep, execution *WorkflowExecution) bool {
	// Simulate step execution based on action
	switch step.Action {
	case "sync_fabric":
		// Simulate fabric sync
		time.Sleep(100 * time.Millisecond)
		return true
	case "detect_drift":
		// Simulate drift detection
		time.Sleep(50 * time.Millisecond)
		return true
	case "validate_resources":
		// Simulate resource validation
		time.Sleep(25 * time.Millisecond)
		return true
	default:
		// Unknown action
		return false
	}
}