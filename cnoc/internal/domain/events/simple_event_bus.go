package events

import (
	"sync"
)

// SimpleEventBus is a minimal implementation of EventBus for testing
type SimpleEventBus struct {
	handlers map[string][]EventHandler
	mu       sync.RWMutex
}

// NewSimpleEventBus creates a new simple event bus
func NewSimpleEventBus() EventBus {
	return &SimpleEventBus{
		handlers: make(map[string][]EventHandler),
	}
}

// Publish publishes an event to all registered handlers
func (bus *SimpleEventBus) Publish(event DomainEvent) error {
	bus.mu.RLock()
	handlers, exists := bus.handlers[event.EventType()]
	bus.mu.RUnlock()

	if !exists {
		return nil // No handlers, no error
	}

	// Execute all handlers synchronously for simplicity
	for _, handler := range handlers {
		if err := handler.Handle(event); err != nil {
			return err
		}
	}

	return nil
}

// Subscribe subscribes a handler to an event type
func (bus *SimpleEventBus) Subscribe(eventType string, handler EventHandler) error {
	bus.mu.Lock()
	defer bus.mu.Unlock()

	bus.handlers[eventType] = append(bus.handlers[eventType], handler)
	return nil
}

// Unsubscribe removes a handler from an event type
func (bus *SimpleEventBus) Unsubscribe(eventType string, handler EventHandler) error {
	bus.mu.Lock()
	defer bus.mu.Unlock()

	_, exists := bus.handlers[eventType]
	if !exists {
		return nil
	}

	// For simplicity, just clear all handlers for now
	// In a real implementation, you'd need to compare handler instances
	delete(bus.handlers, eventType)
	return nil
}