package web

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"sync"
	"time"

	"github.com/gorilla/websocket"
	"github.com/google/uuid"
)

// WebSocketManager manages WebSocket connections for real-time updates
type WebSocketManager struct {
	upgrader    websocket.Upgrader
	clients     map[string]*WebSocketClient
	clientsMux  sync.RWMutex
	broadcast   chan []byte
	register    chan *WebSocketClient
	unregister  chan *WebSocketClient
	ctx         context.Context
	cancel      context.CancelFunc
}

// WebSocketClient represents a connected WebSocket client
type WebSocketClient struct {
	ID           string
	conn         *websocket.Conn
	send         chan []byte
	subscriptions map[string]bool
	subscriptionsMux sync.RWMutex
	manager      *WebSocketManager
	lastPing     time.Time
}

// RealTimeEvent represents a real-time event sent to clients
type RealTimeEvent struct {
	ID        string                 `json:"id"`
	Type      string                 `json:"type"`
	Timestamp time.Time              `json:"timestamp"`
	Source    string                 `json:"source"`
	Target    string                 `json:"target"`
	Payload   map[string]interface{} `json:"payload"`
}

// EventSubscription represents a client's event subscription
type EventSubscription struct {
	ClientID  string   `json:"client_id"`
	EventTypes []string `json:"event_types"`
	Filters   map[string]interface{} `json:"filters,omitempty"`
}

// NewWebSocketManager creates a new WebSocket manager
func NewWebSocketManager() *WebSocketManager {
	ctx, cancel := context.WithCancel(context.Background())
	
	return &WebSocketManager{
		upgrader: websocket.Upgrader{
			ReadBufferSize:  1024,
			WriteBufferSize: 1024,
			CheckOrigin: func(r *http.Request) bool {
				// Allow all origins in development - restrict in production
				return true
			},
		},
		clients:    make(map[string]*WebSocketClient),
		broadcast:  make(chan []byte, 256),
		register:   make(chan *WebSocketClient, 32),
		unregister: make(chan *WebSocketClient, 32),
		ctx:        ctx,
		cancel:     cancel,
	}
}

// Start starts the WebSocket manager's main loop
func (wsm *WebSocketManager) Start() {
	go wsm.run()
	go wsm.pingClients()
}

// Stop stops the WebSocket manager
func (wsm *WebSocketManager) Stop() {
	wsm.cancel()
	close(wsm.broadcast)
	close(wsm.register)
	close(wsm.unregister)
}

// HandleWebSocket handles WebSocket connection upgrades
func (wsm *WebSocketManager) HandleWebSocket(w http.ResponseWriter, r *http.Request) {
	conn, err := wsm.upgrader.Upgrade(w, r, nil)
	if err != nil {
		log.Printf("WebSocket upgrade error: %v", err)
		return
	}

	clientID := uuid.New().String()
	client := &WebSocketClient{
		ID:            clientID,
		conn:          conn,
		send:          make(chan []byte, 256),
		subscriptions: make(map[string]bool),
		manager:       wsm,
		lastPing:      time.Now(),
	}

	wsm.register <- client

	// Start client goroutines
	go client.readPump()
	go client.writePump()
}

// run handles the main WebSocket manager loop
func (wsm *WebSocketManager) run() {
	defer func() {
		// Close all client connections
		wsm.clientsMux.Lock()
		for _, client := range wsm.clients {
			client.conn.Close()
		}
		wsm.clientsMux.Unlock()
	}()

	for {
		select {
		case <-wsm.ctx.Done():
			return

		case client := <-wsm.register:
			wsm.clientsMux.Lock()
			wsm.clients[client.ID] = client
			wsm.clientsMux.Unlock()
			
			log.Printf("WebSocket client connected: %s", client.ID)
			
			// Send welcome message
			welcome := RealTimeEvent{
				ID:        uuid.New().String(),
				Type:      "connection_established",
				Timestamp: time.Now(),
				Source:    "websocket-manager",
				Target:    "client",
				Payload: map[string]interface{}{
					"client_id": client.ID,
					"message":   "Connected to CNOC real-time updates",
				},
			}
			client.sendEvent(&welcome)

		case client := <-wsm.unregister:
			wsm.clientsMux.Lock()
			if _, exists := wsm.clients[client.ID]; exists {
				delete(wsm.clients, client.ID)
				close(client.send)
				log.Printf("WebSocket client disconnected: %s", client.ID)
			}
			wsm.clientsMux.Unlock()

		case message := <-wsm.broadcast:
			// Broadcast message to all connected clients
			wsm.clientsMux.RLock()
			for _, client := range wsm.clients {
				select {
				case client.send <- message:
				default:
					// Client send buffer is full, close connection
					close(client.send)
					delete(wsm.clients, client.ID)
				}
			}
			wsm.clientsMux.RUnlock()
		}
	}
}

// pingClients sends periodic ping messages to keep connections alive
func (wsm *WebSocketManager) pingClients() {
	ticker := time.NewTicker(30 * time.Second)
	defer ticker.Stop()

	for {
		select {
		case <-wsm.ctx.Done():
			return
		case <-ticker.C:
			wsm.clientsMux.RLock()
			for _, client := range wsm.clients {
				// Check if client is stale (no ping response in 60 seconds)
				if time.Since(client.lastPing) > 60*time.Second {
					wsm.unregister <- client
					continue
				}
				
				// Send ping
				if err := client.conn.WriteMessage(websocket.PingMessage, []byte{}); err != nil {
					wsm.unregister <- client
				}
			}
			wsm.clientsMux.RUnlock()
		}
	}
}

// BroadcastEvent broadcasts an event to all connected clients
func (wsm *WebSocketManager) BroadcastEvent(event *RealTimeEvent) {
	data, err := json.Marshal(event)
	if err != nil {
		log.Printf("Error marshaling event: %v", err)
		return
	}

	select {
	case wsm.broadcast <- data:
	default:
		log.Printf("Broadcast channel full, dropping event")
	}
}

// SendToClient sends an event to a specific client
func (wsm *WebSocketManager) SendToClient(clientID string, event *RealTimeEvent) error {
	wsm.clientsMux.RLock()
	client, exists := wsm.clients[clientID]
	wsm.clientsMux.RUnlock()
	
	if !exists {
		return fmt.Errorf("client %s not found", clientID)
	}
	
	return client.sendEvent(event)
}

// SendToSubscribers sends an event to all clients subscribed to the event type
func (wsm *WebSocketManager) SendToSubscribers(eventType string, event *RealTimeEvent) {
	wsm.clientsMux.RLock()
	defer wsm.clientsMux.RUnlock()
	
	for _, client := range wsm.clients {
		client.subscriptionsMux.RLock()
		subscribed := client.subscriptions[eventType]
		client.subscriptionsMux.RUnlock()
		
		if subscribed {
			client.sendEvent(event)
		}
	}
}

// GetConnectedClients returns the number of connected clients
func (wsm *WebSocketManager) GetConnectedClients() int {
	wsm.clientsMux.RLock()
	defer wsm.clientsMux.RUnlock()
	return len(wsm.clients)
}

// readPump handles reading messages from the WebSocket client
func (c *WebSocketClient) readPump() {
	defer func() {
		c.manager.unregister <- c
		c.conn.Close()
	}()

	c.conn.SetReadLimit(512)
	c.conn.SetReadDeadline(time.Now().Add(60 * time.Second))
	c.conn.SetPongHandler(func(string) error {
		c.lastPing = time.Now()
		c.conn.SetReadDeadline(time.Now().Add(60 * time.Second))
		return nil
	})

	for {
		messageType, message, err := c.conn.ReadMessage()
		if err != nil {
			if websocket.IsUnexpectedCloseError(err, websocket.CloseGoingAway, websocket.CloseAbnormalClosure) {
				log.Printf("WebSocket error: %v", err)
			}
			break
		}

		if messageType == websocket.TextMessage {
			c.handleMessage(message)
		}
	}
}

// writePump handles writing messages to the WebSocket client
func (c *WebSocketClient) writePump() {
	ticker := time.NewTicker(54 * time.Second)
	defer func() {
		ticker.Stop()
		c.conn.Close()
	}()

	for {
		select {
		case message, ok := <-c.send:
			c.conn.SetWriteDeadline(time.Now().Add(10 * time.Second))
			if !ok {
				c.conn.WriteMessage(websocket.CloseMessage, []byte{})
				return
			}

			if err := c.conn.WriteMessage(websocket.TextMessage, message); err != nil {
				log.Printf("WebSocket write error: %v", err)
				return
			}

		case <-ticker.C:
			c.conn.SetWriteDeadline(time.Now().Add(10 * time.Second))
			if err := c.conn.WriteMessage(websocket.PingMessage, nil); err != nil {
				return
			}
		}
	}
}

// handleMessage processes messages received from the client
func (c *WebSocketClient) handleMessage(message []byte) {
	var msg map[string]interface{}
	if err := json.Unmarshal(message, &msg); err != nil {
		log.Printf("Invalid message format: %v", err)
		return
	}

	msgType, exists := msg["type"].(string)
	if !exists {
		return
	}

	switch msgType {
	case "subscribe":
		c.handleSubscription(msg)
	case "unsubscribe":
		c.handleUnsubscription(msg)
	case "ping":
		c.handlePing()
	default:
		log.Printf("Unknown message type: %s", msgType)
	}
}

// handleSubscription processes event subscriptions
func (c *WebSocketClient) handleSubscription(msg map[string]interface{}) {
	eventTypes, exists := msg["event_types"].([]interface{})
	if !exists {
		return
	}

	c.subscriptionsMux.Lock()
	defer c.subscriptionsMux.Unlock()

	for _, eventType := range eventTypes {
		if eventTypeStr, ok := eventType.(string); ok {
			c.subscriptions[eventTypeStr] = true
			log.Printf("Client %s subscribed to %s", c.ID, eventTypeStr)
		}
	}

	// Send confirmation
	confirmation := RealTimeEvent{
		ID:        uuid.New().String(),
		Type:      "subscription_confirmed",
		Timestamp: time.Now(),
		Source:    "websocket-manager",
		Target:    "client",
		Payload: map[string]interface{}{
			"client_id":   c.ID,
			"event_types": eventTypes,
			"status":      "subscribed",
		},
	}
	c.sendEvent(&confirmation)
}

// handleUnsubscription processes event unsubscriptions
func (c *WebSocketClient) handleUnsubscription(msg map[string]interface{}) {
	eventTypes, exists := msg["event_types"].([]interface{})
	if !exists {
		return
	}

	c.subscriptionsMux.Lock()
	defer c.subscriptionsMux.Unlock()

	for _, eventType := range eventTypes {
		if eventTypeStr, ok := eventType.(string); ok {
			delete(c.subscriptions, eventTypeStr)
			log.Printf("Client %s unsubscribed from %s", c.ID, eventTypeStr)
		}
	}
}

// handlePing responds to client ping
func (c *WebSocketClient) handlePing() {
	pong := RealTimeEvent{
		ID:        uuid.New().String(),
		Type:      "pong",
		Timestamp: time.Now(),
		Source:    "websocket-manager",
		Target:    "client",
		Payload: map[string]interface{}{
			"client_id": c.ID,
			"timestamp": time.Now().Unix(),
		},
	}
	c.sendEvent(&pong)
}

// sendEvent sends an event to the client
func (c *WebSocketClient) sendEvent(event *RealTimeEvent) error {
	data, err := json.Marshal(event)
	if err != nil {
		return fmt.Errorf("failed to marshal event: %w", err)
	}

	select {
	case c.send <- data:
		return nil
	default:
		return fmt.Errorf("client send buffer full")
	}
}

// EventBroadcaster provides methods to broadcast various types of events
type EventBroadcaster struct {
	wsManager *WebSocketManager
}

// NewEventBroadcaster creates a new event broadcaster
func NewEventBroadcaster(wsManager *WebSocketManager) *EventBroadcaster {
	return &EventBroadcaster{
		wsManager: wsManager,
	}
}

// BroadcastFabricSyncStatus broadcasts fabric sync status updates
func (eb *EventBroadcaster) BroadcastFabricSyncStatus(fabricID, status string, progress int, message string) {
	event := &RealTimeEvent{
		ID:        uuid.New().String(),
		Type:      "fabric_sync_status",
		Timestamp: time.Now(),
		Source:    "gitops-service",
		Target:    "fabric-detail-page",
		Payload: map[string]interface{}{
			"fabric_id": fabricID,
			"status":    status,
			"progress":  progress,
			"message":   message,
		},
	}
	
	eb.wsManager.SendToSubscribers("fabric_sync_status", event)
}

// BroadcastCRDCountChange broadcasts CRD count changes
func (eb *EventBroadcaster) BroadcastCRDCountChange(fabricID string, oldCount, newCount int, changeType string) {
	event := &RealTimeEvent{
		ID:        uuid.New().String(),
		Type:      "crd_count_change",
		Timestamp: time.Now(),
		Source:    "kubernetes-service",
		Target:    "dashboard-statistics",
		Payload: map[string]interface{}{
			"fabric_id":   fabricID,
			"old_count":   oldCount,
			"new_count":   newCount,
			"change_type": changeType,
		},
	}
	
	eb.wsManager.SendToSubscribers("crd_count_change", event)
}

// BroadcastDriftDetection broadcasts drift detection alerts
func (eb *EventBroadcaster) BroadcastDriftDetection(fabricID, severity string, affectedCRDs []string) {
	event := &RealTimeEvent{
		ID:        uuid.New().String(),
		Type:      "drift_detected",
		Timestamp: time.Now(),
		Source:    "drift-detector",
		Target:    "drift-status-widget",
		Payload: map[string]interface{}{
			"fabric_id":      fabricID,
			"drift_severity": severity,
			"affected_crds":  affectedCRDs,
			"detection_time": time.Now().Format(time.RFC3339),
		},
	}
	
	eb.wsManager.SendToSubscribers("drift_detected", event)
}

// BroadcastAPIOperationComplete broadcasts API operation completion
func (eb *EventBroadcaster) BroadcastAPIOperationComplete(operationID, operationType, status, result string) {
	event := &RealTimeEvent{
		ID:        uuid.New().String(),
		Type:      "api_operation_complete",
		Timestamp: time.Now(),
		Source:    "api-service",
		Target:    "notification-center",
		Payload: map[string]interface{}{
			"operation_id":   operationID,
			"operation_type": operationType,
			"status":         status,
			"result":         result,
		},
	}
	
	eb.wsManager.SendToSubscribers("api_operation_complete", event)
}