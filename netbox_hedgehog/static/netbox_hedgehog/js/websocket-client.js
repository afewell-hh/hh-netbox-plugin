/**
 * Hedgehog NetBox Plugin WebSocket Client
 * Real-time communication library for fabric monitoring
 */

class HedgehogWebSocketClient {
    constructor(fabricId, options = {}) {
        this.fabricId = fabricId;
        this.options = {
            reconnectInterval: 3000,
            maxReconnectAttempts: 10,
            heartbeatInterval: 30000,
            debug: false,
            ...options
        };
        
        this.socket = null;
        this.isConnected = false;
        this.reconnectAttempts = 0;
        this.reconnectTimer = null;
        this.heartbeatTimer = null;
        this.eventHandlers = new Map();
        this.messageQueue = [];
        this.lastHeartbeat = null;
        
        // Bind methods to maintain context
        this.onOpen = this.onOpen.bind(this);
        this.onMessage = this.onMessage.bind(this);
        this.onClose = this.onClose.bind(this);
        this.onError = this.onError.bind(this);
        
        this.log('WebSocket client initialized', { fabricId, options });
    }
    
    /**
     * Connect to WebSocket server
     */
    connect() {
        if (this.socket && this.socket.readyState === WebSocket.OPEN) {
            this.log('Already connected');
            return;
        }
        
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws/fabric/${this.fabricId}/`;
        
        this.log('Connecting to WebSocket', { url: wsUrl });
        
        try {
            this.socket = new WebSocket(wsUrl);
            this.socket.onopen = this.onOpen;
            this.socket.onmessage = this.onMessage;
            this.socket.onclose = this.onClose;
            this.socket.onerror = this.onError;
        } catch (error) {
            this.log('Connection failed', { error });
            this.scheduleReconnect();
        }
    }
    
    /**
     * Disconnect from WebSocket server
     */
    disconnect() {
        this.log('Disconnecting...');
        
        if (this.reconnectTimer) {
            clearTimeout(this.reconnectTimer);
            this.reconnectTimer = null;
        }
        
        if (this.heartbeatTimer) {
            clearInterval(this.heartbeatTimer);
            this.heartbeatTimer = null;
        }
        
        if (this.socket) {
            this.socket.close(1000, 'Client disconnect');
            this.socket = null;
        }
        
        this.isConnected = false;
        this.reconnectAttempts = 0;
    }
    
    /**
     * Send message to server
     */
    send(message) {
        if (!this.isConnected) {
            this.log('Not connected, queuing message', { message });
            this.messageQueue.push(message);
            return false;
        }
        
        try {
            const messageStr = typeof message === 'string' ? message : JSON.stringify(message);
            this.socket.send(messageStr);
            this.log('Message sent', { message });
            return true;
        } catch (error) {
            this.log('Failed to send message', { error, message });
            return false;
        }
    }
    
    /**
     * Register event handler
     */
    on(eventType, handler) {
        if (!this.eventHandlers.has(eventType)) {
            this.eventHandlers.set(eventType, []);
        }
        this.eventHandlers.get(eventType).push(handler);
        this.log('Event handler registered', { eventType });
    }
    
    /**
     * Unregister event handler
     */
    off(eventType, handler) {
        if (this.eventHandlers.has(eventType)) {
            const handlers = this.eventHandlers.get(eventType);
            const index = handlers.indexOf(handler);
            if (index > -1) {
                handlers.splice(index, 1);
                this.log('Event handler removed', { eventType });
            }
        }
    }
    
    /**
     * Subscribe to specific event types
     */
    subscribeToEvents(eventTypes) {
        this.send({
            type: 'subscribe_events',
            events: eventTypes
        });
    }
    
    /**
     * Request current fabric status
     */
    requestStatus() {
        this.send({
            type: 'get_status'
        });
    }
    
    /**
     * Trigger fabric sync
     */
    triggerSync(params = {}) {
        this.send({
            type: 'trigger_sync',
            params: params
        });
    }
    
    /**
     * Send heartbeat ping
     */
    sendHeartbeat() {
        if (this.isConnected) {
            this.send({
                type: 'ping',
                timestamp: new Date().toISOString()
            });
            this.lastHeartbeat = Date.now();
        }
    }
    
    /**
     * WebSocket event handlers
     */
    onOpen(event) {
        this.log('WebSocket connected');
        this.isConnected = true;
        this.reconnectAttempts = 0;
        
        // Process queued messages
        while (this.messageQueue.length > 0) {
            const message = this.messageQueue.shift();
            this.send(message);
        }
        
        // Start heartbeat
        this.startHeartbeat();
        
        // Emit connected event
        this.emit('connected', { fabricId: this.fabricId });
    }
    
    onMessage(event) {
        try {
            const data = JSON.parse(event.data);
            this.log('Message received', { data });
            
            // Handle different message types
            this.handleMessage(data);
            
        } catch (error) {
            this.log('Failed to parse message', { error, data: event.data });
        }
    }
    
    onClose(event) {
        this.log('WebSocket closed', { code: event.code, reason: event.reason });
        this.isConnected = false;
        
        if (this.heartbeatTimer) {
            clearInterval(this.heartbeatTimer);
            this.heartbeatTimer = null;
        }
        
        // Emit disconnected event
        this.emit('disconnected', { 
            fabricId: this.fabricId, 
            code: event.code, 
            reason: event.reason 
        });
        
        // Attempt reconnection if not intentional disconnect
        if (event.code !== 1000) {
            this.scheduleReconnect();
        }
    }
    
    onError(event) {
        this.log('WebSocket error', { error: event });
        this.emit('error', { fabricId: this.fabricId, error: event });
    }
    
    /**
     * Handle incoming messages
     */
    handleMessage(data) {
        const { type, timestamp, fabric_id, data: messageData } = data;
        
        // Handle heartbeat response
        if (type === 'pong') {
            const latency = Date.now() - this.lastHeartbeat;
            this.emit('heartbeat', { latency, timestamp });
            return;
        }
        
        // Emit specific event
        this.emit(type, {
            type,
            timestamp,
            fabricId: fabric_id,
            data: messageData
        });
        
        // Emit general message event
        this.emit('message', data);
    }
    
    /**
     * Emit event to handlers
     */
    emit(eventType, data) {
        if (this.eventHandlers.has(eventType)) {
            const handlers = this.eventHandlers.get(eventType);
            handlers.forEach(handler => {
                try {
                    handler(data);
                } catch (error) {
                    this.log('Event handler error', { error, eventType });
                }
            });
        }
    }
    
    /**
     * Schedule reconnection attempt
     */
    scheduleReconnect() {
        if (this.reconnectAttempts >= this.options.maxReconnectAttempts) {
            this.log('Max reconnection attempts reached');
            this.emit('reconnectFailed', { fabricId: this.fabricId });
            return;
        }
        
        this.reconnectAttempts++;
        const delay = this.options.reconnectInterval * Math.min(this.reconnectAttempts, 5);
        
        this.log('Scheduling reconnection', { 
            attempt: this.reconnectAttempts, 
            delay 
        });
        
        this.reconnectTimer = setTimeout(() => {
            this.log('Attempting reconnection', { attempt: this.reconnectAttempts });
            this.connect();
        }, delay);
        
        this.emit('reconnecting', { 
            fabricId: this.fabricId, 
            attempt: this.reconnectAttempts, 
            maxAttempts: this.options.maxReconnectAttempts,
            delay
        });
    }
    
    /**
     * Start heartbeat mechanism
     */
    startHeartbeat() {
        if (this.options.heartbeatInterval > 0) {
            this.heartbeatTimer = setInterval(() => {
                this.sendHeartbeat();
            }, this.options.heartbeatInterval);
        }
    }
    
    /**
     * Get connection status
     */
    getStatus() {
        return {
            isConnected: this.isConnected,
            fabricId: this.fabricId,
            reconnectAttempts: this.reconnectAttempts,
            readyState: this.socket ? this.socket.readyState : WebSocket.CLOSED,
            queuedMessages: this.messageQueue.length
        };
    }
    
    /**
     * Debug logging
     */
    log(message, data = {}) {
        if (this.options.debug) {
            console.log(`[HedgehogWS:${this.fabricId}] ${message}`, data);
        }
    }
}


/**
 * System-wide WebSocket client for admin notifications
 */
class HedgehogSystemWebSocketClient {
    constructor(options = {}) {
        this.options = {
            reconnectInterval: 5000,
            maxReconnectAttempts: 5,
            debug: false,
            ...options
        };
        
        this.socket = null;
        this.isConnected = false;
        this.reconnectAttempts = 0;
        this.reconnectTimer = null;
        this.eventHandlers = new Map();
        
        // Bind methods
        this.onOpen = this.onOpen.bind(this);
        this.onMessage = this.onMessage.bind(this);
        this.onClose = this.onClose.bind(this);
        this.onError = this.onError.bind(this);
    }
    
    connect() {
        if (this.socket && this.socket.readyState === WebSocket.OPEN) {
            return;
        }
        
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws/system/`;
        
        try {
            this.socket = new WebSocket(wsUrl);
            this.socket.onopen = this.onOpen;
            this.socket.onmessage = this.onMessage;
            this.socket.onclose = this.onClose;
            this.socket.onerror = this.onError;
        } catch (error) {
            this.log('System WebSocket connection failed', { error });
            this.scheduleReconnect();
        }
    }
    
    disconnect() {
        if (this.reconnectTimer) {
            clearTimeout(this.reconnectTimer);
            this.reconnectTimer = null;
        }
        
        if (this.socket) {
            this.socket.close(1000, 'Client disconnect');
            this.socket = null;
        }
        
        this.isConnected = false;
        this.reconnectAttempts = 0;
    }
    
    on(eventType, handler) {
        if (!this.eventHandlers.has(eventType)) {
            this.eventHandlers.set(eventType, []);
        }
        this.eventHandlers.get(eventType).push(handler);
    }
    
    off(eventType, handler) {
        if (this.eventHandlers.has(eventType)) {
            const handlers = this.eventHandlers.get(eventType);
            const index = handlers.indexOf(handler);
            if (index > -1) {
                handlers.splice(index, 1);
            }
        }
    }
    
    onOpen(event) {
        this.log('System WebSocket connected');
        this.isConnected = true;
        this.reconnectAttempts = 0;
        this.emit('connected', {});
    }
    
    onMessage(event) {
        try {
            const data = JSON.parse(event.data);
            this.log('System message received', { data });
            this.emit(data.type, data);
            this.emit('message', data);
        } catch (error) {
            this.log('Failed to parse system message', { error });
        }
    }
    
    onClose(event) {
        this.log('System WebSocket closed', { code: event.code });
        this.isConnected = false;
        this.emit('disconnected', { code: event.code });
        
        if (event.code !== 1000) {
            this.scheduleReconnect();
        }
    }
    
    onError(event) {
        this.log('System WebSocket error', { error: event });
        this.emit('error', { error: event });
    }
    
    emit(eventType, data) {
        if (this.eventHandlers.has(eventType)) {
            const handlers = this.eventHandlers.get(eventType);
            handlers.forEach(handler => {
                try {
                    handler(data);
                } catch (error) {
                    this.log('System event handler error', { error, eventType });
                }
            });
        }
    }
    
    scheduleReconnect() {
        if (this.reconnectAttempts >= this.options.maxReconnectAttempts) {
            this.log('Max system reconnection attempts reached');
            return;
        }
        
        this.reconnectAttempts++;
        const delay = this.options.reconnectInterval;
        
        this.reconnectTimer = setTimeout(() => {
            this.connect();
        }, delay);
    }
    
    log(message, data = {}) {
        if (this.options.debug) {
            console.log(`[HedgehogSystemWS] ${message}`, data);
        }
    }
}


/**
 * WebSocket Manager - manages multiple fabric connections
 */
class HedgehogWebSocketManager {
    constructor(options = {}) {
        this.options = {
            debug: false,
            ...options
        };
        
        this.fabricClients = new Map();
        this.systemClient = null;
        this.globalHandlers = new Map();
    }
    
    /**
     * Connect to fabric WebSocket
     */
    connectToFabric(fabricId, options = {}) {
        if (this.fabricClients.has(fabricId)) {
            return this.fabricClients.get(fabricId);
        }
        
        const client = new HedgehogWebSocketClient(fabricId, {
            ...this.options,
            ...options
        });
        
        // Forward events to global handlers
        client.on('message', (data) => {
            this.emit('fabricMessage', { fabricId, ...data });
        });
        
        client.on('connected', () => {
            this.emit('fabricConnected', { fabricId });
        });
        
        client.on('disconnected', () => {
            this.emit('fabricDisconnected', { fabricId });
        });
        
        this.fabricClients.set(fabricId, client);
        client.connect();
        
        return client;
    }
    
    /**
     * Disconnect from fabric WebSocket
     */
    disconnectFromFabric(fabricId) {
        if (this.fabricClients.has(fabricId)) {
            const client = this.fabricClients.get(fabricId);
            client.disconnect();
            this.fabricClients.delete(fabricId);
        }
    }
    
    /**
     * Connect to system WebSocket
     */
    connectToSystem(options = {}) {
        if (this.systemClient) {
            return this.systemClient;
        }
        
        this.systemClient = new HedgehogSystemWebSocketClient({
            ...this.options,
            ...options
        });
        
        // Forward system events
        this.systemClient.on('message', (data) => {
            this.emit('systemMessage', data);
        });
        
        this.systemClient.connect();
        return this.systemClient;
    }
    
    /**
     * Disconnect from system WebSocket
     */
    disconnectFromSystem() {
        if (this.systemClient) {
            this.systemClient.disconnect();
            this.systemClient = null;
        }
    }
    
    /**
     * Get fabric client
     */
    getFabricClient(fabricId) {
        return this.fabricClients.get(fabricId);
    }
    
    /**
     * Get system client
     */
    getSystemClient() {
        return this.systemClient;
    }
    
    /**
     * Disconnect all clients
     */
    disconnectAll() {
        this.fabricClients.forEach(client => client.disconnect());
        this.fabricClients.clear();
        
        if (this.systemClient) {
            this.systemClient.disconnect();
            this.systemClient = null;
        }
    }
    
    /**
     * Register global event handler
     */
    on(eventType, handler) {
        if (!this.globalHandlers.has(eventType)) {
            this.globalHandlers.set(eventType, []);
        }
        this.globalHandlers.get(eventType).push(handler);
    }
    
    /**
     * Emit global event
     */
    emit(eventType, data) {
        if (this.globalHandlers.has(eventType)) {
            const handlers = this.globalHandlers.get(eventType);
            handlers.forEach(handler => {
                try {
                    handler(data);
                } catch (error) {
                    console.error('Global handler error:', error);
                }
            });
        }
    }
    
    /**
     * Get status of all connections
     */
    getStatus() {
        const fabricStatuses = {};
        this.fabricClients.forEach((client, fabricId) => {
            fabricStatuses[fabricId] = client.getStatus();
        });
        
        return {
            fabrics: fabricStatuses,
            system: this.systemClient ? {
                isConnected: this.systemClient.isConnected,
                reconnectAttempts: this.systemClient.reconnectAttempts
            } : null
        };
    }
}


// Export for use in other modules
window.HedgehogWebSocket = {
    Client: HedgehogWebSocketClient,
    SystemClient: HedgehogSystemWebSocketClient,
    Manager: HedgehogWebSocketManager
};