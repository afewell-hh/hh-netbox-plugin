package eventbus

import (
	"context"
	"fmt"
	"sync"
	"time"

	"github.com/hedgehog/cnoc/internal/domain/events"
)

// InMemoryEventBus implements the event bus with Symphony-Level coordination patterns
// Following anti-corruption layer principles to isolate infrastructure concerns
type InMemoryEventBus struct {
	handlers      map[string][]events.EventHandler
	handlersMutex sync.RWMutex
	
	// Symphony-Level coordination components
	coordinationEngine *CoordinationEngine
	processManager     *ProcessManager
	sagaOrchestrator   *SagaOrchestrator
	
	// Infrastructure concerns
	publishBuffer     chan eventPublication
	metricsCollector  *EventBusMetricsCollector
	errorHandler      *EventBusErrorHandler
	
	// Lifecycle management
	ctx           context.Context
	cancel        context.CancelFunc
	wg           sync.WaitGroup
	isRunning    bool
	runningMutex sync.RWMutex
}

// eventPublication represents an event publication with metadata
type eventPublication struct {
	Event     events.DomainEvent
	Timestamp time.Time
	Context   context.Context
	Metadata  PublicationMetadata
}

// PublicationMetadata provides additional context for event publication
type PublicationMetadata struct {
	Source        string                 `json:"source"`
	CorrelationID string                 `json:"correlation_id"`
	CausationID   string                 `json:"causation_id"`
	UserID        string                 `json:"user_id,omitempty"`
	RequestID     string                 `json:"request_id,omitempty"`
	Context       map[string]interface{} `json:"context,omitempty"`
}

// NewInMemoryEventBus creates a new in-memory event bus with Symphony-Level coordination
func NewInMemoryEventBus(
	ctx context.Context,
	metricsCollector *EventBusMetricsCollector,
	errorHandler *EventBusErrorHandler,
) *InMemoryEventBus {
	busCtx, cancel := context.WithCancel(ctx)
	
	bus := &InMemoryEventBus{
		handlers:          make(map[string][]events.EventHandler),
		coordinationEngine: NewCoordinationEngine(),
		processManager:    NewProcessManager(),
		sagaOrchestrator:  NewSagaOrchestrator(),
		publishBuffer:     make(chan eventPublication, 1000), // Buffered for performance
		metricsCollector:  metricsCollector,
		errorHandler:      errorHandler,
		ctx:              busCtx,
		cancel:           cancel,
	}

	// Start event processing goroutines
	bus.start()
	
	return bus
}

// Publish publishes a domain event with Symphony-Level coordination
func (eb *InMemoryEventBus) Publish(event events.DomainEvent) error {
	if !eb.isRunning {
		return fmt.Errorf("event bus is not running")
	}

	publication := eventPublication{
		Event:     event,
		Timestamp: time.Now(),
		Context:   eb.ctx,
		Metadata:  eb.extractEventMetadata(event),
	}

	// Non-blocking publish with timeout
	select {
	case eb.publishBuffer <- publication:
		eb.metricsCollector.RecordEventPublished(event.EventType())
		return nil
	case <-time.After(5 * time.Second):
		eb.metricsCollector.RecordEventTimeout(event.EventType())
		return fmt.Errorf("event publication timeout for event type: %s", event.EventType())
	case <-eb.ctx.Done():
		return fmt.Errorf("event bus context cancelled")
	}
}

// Subscribe registers an event handler for a specific event type
func (eb *InMemoryEventBus) Subscribe(eventType string, handler events.EventHandler) error {
	if eventType == "" {
		return fmt.Errorf("event type cannot be empty")
	}
	if handler == nil {
		return fmt.Errorf("event handler cannot be nil")
	}

	eb.handlersMutex.Lock()
	defer eb.handlersMutex.Unlock()

	if !handler.CanHandle(eventType) {
		return fmt.Errorf("handler cannot handle event type: %s", eventType)
	}

	eb.handlers[eventType] = append(eb.handlers[eventType], handler)
	eb.metricsCollector.RecordHandlerRegistered(eventType)
	
	return nil
}

// Unsubscribe removes an event handler for a specific event type
func (eb *InMemoryEventBus) Unsubscribe(eventType string, handler events.EventHandler) error {
	eb.handlersMutex.Lock()
	defer eb.handlersMutex.Unlock()

	handlers, exists := eb.handlers[eventType]
	if !exists {
		return fmt.Errorf("no handlers registered for event type: %s", eventType)
	}

	// Find and remove handler
	for i, h := range handlers {
		if h == handler {
			eb.handlers[eventType] = append(handlers[:i], handlers[i+1:]...)
			eb.metricsCollector.RecordHandlerUnregistered(eventType)
			
			// Remove event type if no handlers left
			if len(eb.handlers[eventType]) == 0 {
				delete(eb.handlers, eventType)
			}
			
			return nil
		}
	}

	return fmt.Errorf("handler not found for event type: %s", eventType)
}

// GetHandlerCount returns the number of handlers for an event type
func (eb *InMemoryEventBus) GetHandlerCount(eventType string) int {
	eb.handlersMutex.RLock()
	defer eb.handlersMutex.RUnlock()
	
	return len(eb.handlers[eventType])
}

// GetEventTypes returns all event types with registered handlers
func (eb *InMemoryEventBus) GetEventTypes() []string {
	eb.handlersMutex.RLock()
	defer eb.handlersMutex.RUnlock()
	
	eventTypes := make([]string, 0, len(eb.handlers))
	for eventType := range eb.handlers {
		eventTypes = append(eventTypes, eventType)
	}
	
	return eventTypes
}

// Shutdown gracefully shuts down the event bus
func (eb *InMemoryEventBus) Shutdown(timeout time.Duration) error {
	eb.runningMutex.Lock()
	if !eb.isRunning {
		eb.runningMutex.Unlock()
		return nil
	}
	eb.isRunning = false
	eb.runningMutex.Unlock()

	// Cancel context to signal shutdown
	eb.cancel()

	// Wait for all goroutines to finish with timeout
	done := make(chan struct{})
	go func() {
		eb.wg.Wait()
		close(done)
	}()

	select {
	case <-done:
		return nil
	case <-time.After(timeout):
		return fmt.Errorf("event bus shutdown timeout after %v", timeout)
	}
}

// Private methods for event processing

func (eb *InMemoryEventBus) start() {
	eb.runningMutex.Lock()
	eb.isRunning = true
	eb.runningMutex.Unlock()

	// Start event processing workers
	for i := 0; i < 3; i++ { // Multiple workers for concurrency
		eb.wg.Add(1)
		go eb.eventProcessor(fmt.Sprintf("worker-%d", i))
	}

	// Start coordination engine
	eb.wg.Add(1)
	go eb.coordinationProcessor()
}

func (eb *InMemoryEventBus) eventProcessor(workerID string) {
	defer eb.wg.Done()

	for {
		select {
		case publication := <-eb.publishBuffer:
			eb.processEvent(publication, workerID)
		case <-eb.ctx.Done():
			return
		}
	}
}

func (eb *InMemoryEventBus) processEvent(publication eventPublication, workerID string) {
	startTime := time.Now()
	event := publication.Event
	eventType := event.EventType()

	// Get handlers for this event type
	eb.handlersMutex.RLock()
	handlers := make([]events.EventHandler, len(eb.handlers[eventType]))
	copy(handlers, eb.handlers[eventType])
	eb.handlersMutex.RUnlock()

	if len(handlers) == 0 {
		eb.metricsCollector.RecordEventNoHandlers(eventType)
		return
	}

	// Process handlers concurrently with error handling
	var wg sync.WaitGroup
	errorsCh := make(chan error, len(handlers))

	for _, handler := range handlers {
		wg.Add(1)
		go func(h events.EventHandler) {
			defer wg.Done()
			
			handlerStartTime := time.Now()
			if err := eb.handleEventSafely(h, event, publication.Context); err != nil {
				errorsCh <- fmt.Errorf("handler error for %s: %w", eventType, err)
				eb.metricsCollector.RecordHandlerError(eventType, err)
			} else {
				eb.metricsCollector.RecordHandlerSuccess(eventType, time.Since(handlerStartTime))
			}
		}(handler)
	}

	wg.Wait()
	close(errorsCh)

	// Collect and handle errors
	var errors []error
	for err := range errorsCh {
		errors = append(errors, err)
	}

	if len(errors) > 0 {
		eb.errorHandler.HandleEventProcessingErrors(event, errors)
	}

	// Record processing metrics
	eb.metricsCollector.RecordEventProcessed(eventType, time.Since(startTime), len(handlers), len(errors))

	// Symphony-Level coordination processing
	eb.coordinationEngine.ProcessEvent(event, publication.Metadata)
}

func (eb *InMemoryEventBus) handleEventSafely(handler events.EventHandler, event events.DomainEvent, ctx context.Context) (err error) {
	// Panic recovery for handler safety
	defer func() {
		if r := recover(); r != nil {
			err = fmt.Errorf("handler panic: %v", r)
		}
	}()

	// Create timeout context for handler execution
	handlerCtx, cancel := context.WithTimeout(ctx, 30*time.Second)
	defer cancel()

	// Execute handler with context
	done := make(chan error, 1)
	go func() {
		done <- handler.Handle(event)
	}()

	select {
	case err = <-done:
		return err
	case <-handlerCtx.Done():
		return fmt.Errorf("handler timeout")
	}
}

func (eb *InMemoryEventBus) coordinationProcessor() {
	defer eb.wg.Done()

	ticker := time.NewTicker(100 * time.Millisecond) // Process coordination every 100ms
	defer ticker.Stop()

	for {
		select {
		case <-ticker.C:
			// Process coordination engine
			eb.coordinationEngine.ProcessPendingCoordination()
			
			// Process saga orchestration
			eb.sagaOrchestrator.ProcessPendingSagas()
			
			// Process long-running processes
			eb.processManager.ProcessPendingProcesses()
			
		case <-eb.ctx.Done():
			return
		}
	}
}

func (eb *InMemoryEventBus) extractEventMetadata(event events.DomainEvent) PublicationMetadata {
	metadata := PublicationMetadata{
		Source: "cnoc-event-bus",
	}

	// Extract enhanced metadata if available
	if enhancedEvent, ok := event.(events.EnhancedDomainEvent); ok {
		eventMetadata := enhancedEvent.Metadata()
		metadata.CorrelationID = eventMetadata.CorrelationID
		metadata.CausationID = eventMetadata.CausationID
		metadata.UserID = eventMetadata.UserID
	}

	return metadata
}

// Symphony-Level Coordination Components

// CoordinationEngine handles Symphony-Level event coordination
type CoordinationEngine struct {
	pendingCoordination []CoordinationTask
	mutex              sync.RWMutex
}

// CoordinationTask represents a coordination task
type CoordinationTask struct {
	Event        events.DomainEvent
	Metadata     PublicationMetadata
	CreatedAt    time.Time
	ProcessedAt  *time.Time
	Status       CoordinationStatus
}

// CoordinationStatus represents coordination task status
type CoordinationStatus string

const (
	CoordinationStatusPending   CoordinationStatus = "pending"
	CoordinationStatusProcessing CoordinationStatus = "processing"
	CoordinationStatusCompleted CoordinationStatus = "completed"
	CoordinationStatusFailed    CoordinationStatus = "failed"
)

// NewCoordinationEngine creates a new coordination engine
func NewCoordinationEngine() *CoordinationEngine {
	return &CoordinationEngine{
		pendingCoordination: make([]CoordinationTask, 0),
	}
}

// ProcessEvent adds an event to coordination processing
func (ce *CoordinationEngine) ProcessEvent(event events.DomainEvent, metadata PublicationMetadata) {
	ce.mutex.Lock()
	defer ce.mutex.Unlock()

	task := CoordinationTask{
		Event:     event,
		Metadata:  metadata,
		CreatedAt: time.Now(),
		Status:    CoordinationStatusPending,
	}

	ce.pendingCoordination = append(ce.pendingCoordination, task)
}

// ProcessPendingCoordination processes pending coordination tasks
func (ce *CoordinationEngine) ProcessPendingCoordination() {
	ce.mutex.Lock()
	defer ce.mutex.Unlock()

	// Process pending tasks
	for i := range ce.pendingCoordination {
		task := &ce.pendingCoordination[i]
		if task.Status == CoordinationStatusPending {
			ce.processCoordinationTask(task)
		}
	}

	// Clean up completed tasks older than 1 hour
	ce.cleanupCompletedTasks()
}

func (ce *CoordinationEngine) processCoordinationTask(task *CoordinationTask) {
	task.Status = CoordinationStatusProcessing

	// Implement Symphony-Level coordination logic here
	// This would include pattern recognition, event correlation, and process coordination
	
	now := time.Now()
	task.ProcessedAt = &now
	task.Status = CoordinationStatusCompleted
}

func (ce *CoordinationEngine) cleanupCompletedTasks() {
	cutoff := time.Now().Add(-1 * time.Hour)
	remaining := make([]CoordinationTask, 0)

	for _, task := range ce.pendingCoordination {
		if task.Status != CoordinationStatusCompleted || task.CreatedAt.After(cutoff) {
			remaining = append(remaining, task)
		}
	}

	ce.pendingCoordination = remaining
}

// ProcessManager handles long-running business processes
type ProcessManager struct {
	activeProcesses map[string]*BusinessProcess
	mutex          sync.RWMutex
}

// BusinessProcess represents a long-running business process
type BusinessProcess struct {
	ID          string
	Type        string
	Status      ProcessStatus
	StartedAt   time.Time
	UpdatedAt   time.Time
	Events      []events.DomainEvent
	Context     map[string]interface{}
}

// ProcessStatus represents process status
type ProcessStatus string

const (
	ProcessStatusStarted   ProcessStatus = "started"
	ProcessStatusRunning   ProcessStatus = "running"
	ProcessStatusCompleted ProcessStatus = "completed"
	ProcessStatusFailed    ProcessStatus = "failed"
	ProcessStatusAborted   ProcessStatus = "aborted"
)

// NewProcessManager creates a new process manager
func NewProcessManager() *ProcessManager {
	return &ProcessManager{
		activeProcesses: make(map[string]*BusinessProcess),
	}
}

// ProcessPendingProcesses processes pending business processes
func (pm *ProcessManager) ProcessPendingProcesses() {
	pm.mutex.Lock()
	defer pm.mutex.Unlock()

	for _, process := range pm.activeProcesses {
		if process.Status == ProcessStatusRunning {
			pm.processBusinessProcess(process)
		}
	}
}

func (pm *ProcessManager) processBusinessProcess(process *BusinessProcess) {
	// Implement business process logic here
	// This would include process state management and event-driven workflows
	process.UpdatedAt = time.Now()
}

// SagaOrchestrator handles distributed transactions with compensation patterns
type SagaOrchestrator struct {
	activeSagas map[string]*SagaInstance
	mutex       sync.RWMutex
}

// SagaInstance represents a saga instance
type SagaInstance struct {
	ID              string
	Type            string
	Status          SagaStatus
	StartedAt       time.Time
	UpdatedAt       time.Time
	Steps           []SagaStep
	CompensationSteps []SagaStep
	Context         map[string]interface{}
}

// SagaStatus represents saga status
type SagaStatus string

const (
	SagaStatusStarted     SagaStatus = "started"
	SagaStatusRunning     SagaStatus = "running"
	SagaStatusCompleted   SagaStatus = "completed"
	SagaStatusCompensating SagaStatus = "compensating"
	SagaStatusFailed      SagaStatus = "failed"
	SagaStatusAborted     SagaStatus = "aborted"
)

// SagaStep represents a step in a saga
type SagaStep struct {
	ID           string
	Type         string
	Status       StepStatus
	ExecutedAt   *time.Time
	CompensatedAt *time.Time
	Error        error
}

// StepStatus represents saga step status
type StepStatus string

const (
	StepStatusPending     StepStatus = "pending"
	StepStatusExecuting   StepStatus = "executing"
	StepStatusCompleted   StepStatus = "completed"
	StepStatusFailed      StepStatus = "failed"
	StepStatusCompensated StepStatus = "compensated"
)

// NewSagaOrchestrator creates a new saga orchestrator
func NewSagaOrchestrator() *SagaOrchestrator {
	return &SagaOrchestrator{
		activeSagas: make(map[string]*SagaInstance),
	}
}

// ProcessPendingSagas processes pending sagas
func (so *SagaOrchestrator) ProcessPendingSagas() {
	so.mutex.Lock()
	defer so.mutex.Unlock()

	for _, saga := range so.activeSagas {
		if saga.Status == SagaStatusRunning || saga.Status == SagaStatusCompensating {
			so.processSagaInstance(saga)
		}
	}
}

func (so *SagaOrchestrator) processSagaInstance(saga *SagaInstance) {
	// Implement saga orchestration logic here
	// This would include step execution, compensation logic, and error handling
	saga.UpdatedAt = time.Now()
}

// EventBusMetricsCollector collects metrics about event bus operations
type EventBusMetricsCollector struct {
	// Implementation would collect comprehensive metrics
}

func (mc *EventBusMetricsCollector) RecordEventPublished(eventType string) {
	// Implementation would record event publication metrics
}

func (mc *EventBusMetricsCollector) RecordEventTimeout(eventType string) {
	// Implementation would record event timeout metrics
}

func (mc *EventBusMetricsCollector) RecordHandlerRegistered(eventType string) {
	// Implementation would record handler registration metrics
}

func (mc *EventBusMetricsCollector) RecordHandlerUnregistered(eventType string) {
	// Implementation would record handler unregistration metrics
}

func (mc *EventBusMetricsCollector) RecordEventNoHandlers(eventType string) {
	// Implementation would record no handlers metrics
}

func (mc *EventBusMetricsCollector) RecordHandlerError(eventType string, err error) {
	// Implementation would record handler error metrics
}

func (mc *EventBusMetricsCollector) RecordHandlerSuccess(eventType string, duration time.Duration) {
	// Implementation would record handler success metrics
}

func (mc *EventBusMetricsCollector) RecordEventProcessed(eventType string, duration time.Duration, handlerCount, errorCount int) {
	// Implementation would record event processing metrics
}

// EventBusErrorHandler handles errors in event processing
type EventBusErrorHandler struct {
	// Implementation would handle errors with retry logic, dead letter queues, etc.
}

func (eh *EventBusErrorHandler) HandleEventProcessingErrors(event events.DomainEvent, errors []error) {
	// Implementation would handle processing errors with appropriate strategies
}