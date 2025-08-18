/**
 * Real-time WebSocket client for CNOC
 * FORGE Movement 7: Advanced UI Features - Real-time Updates
 */

class CNOCRealtimeClient {
    constructor(options = {}) {
        this.wsUrl = options.wsUrl || this.getWebSocketURL();
        this.reconnectInterval = options.reconnectInterval || 5000;
        this.maxReconnectAttempts = options.maxReconnectAttempts || 10;
        this.subscriptions = new Map();
        this.eventHandlers = new Map();
        this.messageQueue = [];
        this.isConnected = false;
        this.reconnectCount = 0;
        this.socket = null;
        this.heartbeatInterval = null;
        
        // Performance tracking
        this.metrics = {
            messagesReceived: 0,
            messagesQueued: 0,
            averageLatency: 0,
            connectionCount: 0,
            lastLatencyMeasurement: 0
        };
        
        // Connection state callbacks
        this.onConnectionChange = options.onConnectionChange || (() => {});
        this.onError = options.onError || ((error) => console.error('WebSocket error:', error));
        this.onMetricsUpdate = options.onMetricsUpdate || (() => {});
        
        this.init();
    }

    /**
     * Initialize the WebSocket connection
     */
    init() {
        this.connect();
    }

    /**
     * Get WebSocket URL from current page
     */
    getWebSocketURL() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const host = window.location.host;
        return `${protocol}//${host}/ws`;
    }

    /**
     * Connect to WebSocket server
     */
    connect() {
        if (this.socket && this.socket.readyState === WebSocket.CONNECTING) {
            return;
        }

        try {
            console.log(`Connecting to WebSocket: ${this.wsUrl}`);
            this.socket = new WebSocket(this.wsUrl);
            this.setupEventHandlers();
            this.metrics.connectionCount++;
        } catch (error) {
            console.error('Failed to create WebSocket connection:', error);
            this.onError(error);
            this.scheduleReconnect();
        }
    }

    /**
     * Setup WebSocket event handlers
     */
    setupEventHandlers() {
        this.socket.onopen = (event) => {
            console.log('WebSocket connected');
            this.isConnected = true;
            this.reconnectCount = 0;
            this.onConnectionChange(true);
            
            // Send queued messages
            this.processMessageQueue();
            
            // Start heartbeat
            this.startHeartbeat();
            
            // Re-subscribe to events
            this.resubscribeAll();
        };

        this.socket.onmessage = (event) => {
            this.handleMessage(event.data);
        };

        this.socket.onclose = (event) => {
            console.log('WebSocket disconnected:', event.code, event.reason);
            this.isConnected = false;
            this.onConnectionChange(false);
            this.stopHeartbeat();
            
            if (event.code !== 1000) { // Not a normal closure
                this.scheduleReconnect();
            }
        };

        this.socket.onerror = (error) => {
            console.error('WebSocket error:', error);
            this.onError(error);
        };
    }

    /**
     * Handle incoming messages
     */
    handleMessage(data) {
        try {
            const message = JSON.parse(data);
            const receiveTime = Date.now();
            
            // Update metrics
            this.metrics.messagesReceived++;
            
            // Calculate latency if timestamp is available
            if (message.timestamp) {
                const sentTime = new Date(message.timestamp).getTime();
                const latency = receiveTime - sentTime;
                this.updateLatencyMetrics(latency);
            }
            
            this.onMetricsUpdate(this.metrics);
            
            // Handle different message types
            switch (message.type) {
                case 'connection_established':
                    this.handleConnectionEstablished(message);
                    break;
                case 'subscription_confirmed':
                    this.handleSubscriptionConfirmed(message);
                    break;
                case 'pong':
                    this.handlePong(message);
                    break;
                default:
                    this.dispatchEvent(message);
                    break;
            }
        } catch (error) {
            console.error('Failed to parse WebSocket message:', error);
            this.onError(error);
        }
    }

    /**
     * Update latency metrics
     */
    updateLatencyMetrics(latency) {
        // Exponential moving average for latency
        if (this.metrics.averageLatency === 0) {
            this.metrics.averageLatency = latency;
        } else {
            this.metrics.averageLatency = 0.9 * this.metrics.averageLatency + 0.1 * latency;
        }
        this.metrics.lastLatencyMeasurement = latency;
    }

    /**
     * Handle connection established message
     */
    handleConnectionEstablished(message) {
        console.log('Connection established with client ID:', message.payload.client_id);
        this.clientId = message.payload.client_id;
    }

    /**
     * Handle subscription confirmation
     */
    handleSubscriptionConfirmed(message) {
        const eventTypes = message.payload.event_types;
        console.log('Subscription confirmed for:', eventTypes);
        
        // Mark subscriptions as confirmed
        eventTypes.forEach(eventType => {
            const subscription = this.subscriptions.get(eventType);
            if (subscription) {
                subscription.confirmed = true;
            }
        });
    }

    /**
     * Handle pong response
     */
    handlePong(message) {
        console.debug('Received pong from server');
        // Could be used for connection monitoring
    }

    /**
     * Dispatch event to registered handlers
     */
    dispatchEvent(message) {
        const handlers = this.eventHandlers.get(message.type) || [];
        
        handlers.forEach(handler => {
            try {
                handler(message);
            } catch (error) {
                console.error(`Error in event handler for ${message.type}:`, error);
            }
        });
        
        // Also trigger generic event listeners
        const genericHandlers = this.eventHandlers.get('*') || [];
        genericHandlers.forEach(handler => {
            try {
                handler(message);
            } catch (error) {
                console.error('Error in generic event handler:', error);
            }
        });
    }

    /**
     * Subscribe to event types
     */
    subscribe(eventTypes, handler = null) {
        if (typeof eventTypes === 'string') {
            eventTypes = [eventTypes];
        }
        
        // Store subscriptions
        eventTypes.forEach(eventType => {
            this.subscriptions.set(eventType, {
                confirmed: false,
                timestamp: Date.now()
            });
            
            if (handler) {
                this.on(eventType, handler);
            }
        });
        
        // Send subscription message
        const message = {
            type: 'subscribe',
            event_types: eventTypes,
            timestamp: new Date().toISOString()
        };
        
        this.send(message);
    }

    /**
     * Unsubscribe from event types
     */
    unsubscribe(eventTypes) {
        if (typeof eventTypes === 'string') {
            eventTypes = [eventTypes];
        }
        
        // Remove subscriptions
        eventTypes.forEach(eventType => {
            this.subscriptions.delete(eventType);
            this.eventHandlers.delete(eventType);
        });
        
        // Send unsubscription message
        const message = {
            type: 'unsubscribe',
            event_types: eventTypes,
            timestamp: new Date().toISOString()
        };
        
        this.send(message);
    }

    /**
     * Register event handler
     */
    on(eventType, handler) {
        if (!this.eventHandlers.has(eventType)) {
            this.eventHandlers.set(eventType, []);
        }
        this.eventHandlers.get(eventType).push(handler);
    }

    /**
     * Remove event handler
     */
    off(eventType, handler) {
        if (!this.eventHandlers.has(eventType)) {
            return;
        }
        
        const handlers = this.eventHandlers.get(eventType);
        const index = handlers.indexOf(handler);
        if (index > -1) {
            handlers.splice(index, 1);
        }
    }

    /**
     * Send message to server
     */
    send(message) {
        if (this.isConnected && this.socket.readyState === WebSocket.OPEN) {
            try {
                this.socket.send(JSON.stringify(message));
            } catch (error) {
                console.error('Failed to send WebSocket message:', error);
                this.queueMessage(message);
            }
        } else {
            this.queueMessage(message);
        }
    }

    /**
     * Queue message for later sending
     */
    queueMessage(message) {
        this.messageQueue.push(message);
        this.metrics.messagesQueued++;
        
        // Limit queue size
        if (this.messageQueue.length > 100) {
            this.messageQueue.shift(); // Remove oldest message
        }
    }

    /**
     * Process queued messages
     */
    processMessageQueue() {
        while (this.messageQueue.length > 0 && this.isConnected) {
            const message = this.messageQueue.shift();
            this.send(message);
            this.metrics.messagesQueued--;
        }
    }

    /**
     * Start heartbeat to keep connection alive
     */
    startHeartbeat() {
        this.heartbeatInterval = setInterval(() => {
            if (this.isConnected) {
                this.send({
                    type: 'ping',
                    timestamp: new Date().toISOString()
                });
            }
        }, 30000); // Every 30 seconds
    }

    /**
     * Stop heartbeat
     */
    stopHeartbeat() {
        if (this.heartbeatInterval) {
            clearInterval(this.heartbeatInterval);
            this.heartbeatInterval = null;
        }
    }

    /**
     * Schedule reconnection attempt
     */
    scheduleReconnect() {
        if (this.reconnectCount >= this.maxReconnectAttempts) {
            console.error('Max reconnection attempts reached');
            return;
        }

        const delay = Math.min(this.reconnectInterval * Math.pow(2, this.reconnectCount), 30000);
        console.log(`Scheduling reconnect in ${delay}ms (attempt ${this.reconnectCount + 1})`);
        
        setTimeout(() => {
            this.reconnectCount++;
            this.connect();
        }, delay);
    }

    /**
     * Re-subscribe to all active subscriptions
     */
    resubscribeAll() {
        if (this.subscriptions.size > 0) {
            const eventTypes = Array.from(this.subscriptions.keys());
            this.subscribe(eventTypes);
        }
    }

    /**
     * Close the WebSocket connection
     */
    close() {
        this.stopHeartbeat();
        if (this.socket) {
            this.socket.close(1000, 'Client initiated close');
        }
    }

    /**
     * Get connection status
     */
    getStatus() {
        return {
            connected: this.isConnected,
            clientId: this.clientId,
            subscriptions: Array.from(this.subscriptions.keys()),
            metrics: this.metrics,
            reconnectCount: this.reconnectCount
        };
    }
}

/**
 * CNOC Real-time UI Updates Manager
 * Handles UI updates based on real-time events
 */
class CNOCUIUpdateManager {
    constructor(realtimeClient) {
        this.client = realtimeClient;
        this.updateHandlers = new Map();
        this.animationQueue = [];
        this.isProcessingAnimations = false;
        
        this.setupDefaultHandlers();
    }

    /**
     * Setup default event handlers
     */
    setupDefaultHandlers() {
        // Fabric sync status updates
        this.client.on('fabric_sync_status', (message) => {
            this.updateFabricSyncStatus(message.payload);
        });

        // CRD count changes
        this.client.on('crd_count_change', (message) => {
            this.updateCRDCount(message.payload);
        });

        // Drift detection alerts
        this.client.on('drift_detected', (message) => {
            this.showDriftAlert(message.payload);
        });

        // API operation completion
        this.client.on('api_operation_complete', (message) => {
            this.showOperationNotification(message.payload);
        });
    }

    /**
     * Update fabric sync status in UI
     */
    updateFabricSyncStatus(payload) {
        const fabricId = payload.fabric_id;
        const status = payload.status;
        const progress = payload.progress;
        const message = payload.message;

        // Update progress bars
        this.updateElement(`.fabric-sync-progress[data-fabric="${fabricId}"]`, (element) => {
            element.style.width = `${progress}%`;
            element.setAttribute('aria-valuenow', progress);
        });

        // Update status badges
        this.updateElement(`.fabric-status[data-fabric="${fabricId}"]`, (element) => {
            element.className = `fabric-status badge badge-${this.getStatusClass(status)}`;
            element.textContent = status.charAt(0).toUpperCase() + status.slice(1);
        });

        // Update status messages
        this.updateElement(`.fabric-status-message[data-fabric="${fabricId}"]`, (element) => {
            element.textContent = message;
            this.animateElement(element, 'fade-in');
        });

        // Show notification for completed syncs
        if (status === 'completed') {
            this.showToast(`Fabric ${fabricId} sync completed successfully`, 'success');
        } else if (status === 'failed') {
            this.showToast(`Fabric ${fabricId} sync failed: ${message}`, 'error');
        }
    }

    /**
     * Update CRD count displays
     */
    updateCRDCount(payload) {
        const fabricId = payload.fabric_id;
        const oldCount = payload.old_count;
        const newCount = payload.new_count;
        const changeType = payload.change_type;

        // Update count displays with animation
        this.updateElement(`.crd-count[data-fabric="${fabricId}"]`, (element) => {
            this.animateCounterChange(element, oldCount, newCount);
        });

        // Update dashboard statistics
        this.updateElement('.dashboard-crd-total', (element) => {
            const currentTotal = parseInt(element.textContent) || 0;
            const difference = newCount - oldCount;
            const newTotal = currentTotal + difference;
            this.animateCounterChange(element, currentTotal, newTotal);
        });

        // Show change indicator
        if (changeType === 'increase') {
            this.showChangeIndicator(fabricId, '+' + (newCount - oldCount), 'success');
        } else if (changeType === 'decrease') {
            this.showChangeIndicator(fabricId, '-' + (oldCount - newCount), 'warning');
        }
    }

    /**
     * Show drift detection alert
     */
    showDriftAlert(payload) {
        const fabricId = payload.fabric_id;
        const severity = payload.drift_severity;
        const affectedCRDs = payload.affected_crds;

        // Update drift status indicators
        this.updateElement(`.drift-status[data-fabric="${fabricId}"]`, (element) => {
            element.className = `drift-status badge badge-${this.getDriftSeverityClass(severity)}`;
            element.textContent = `${severity.toUpperCase()} DRIFT`;
            this.animateElement(element, 'pulse');
        });

        // Show detailed drift information
        this.updateElement(`.drift-details[data-fabric="${fabricId}"]`, (element) => {
            element.innerHTML = `
                <div class="drift-alert alert-${this.getDriftSeverityClass(severity)}">
                    <strong>Drift Detected:</strong> ${severity} severity
                    <br><strong>Affected CRDs:</strong> ${affectedCRDs.join(', ')}
                </div>
            `;
            element.style.display = 'block';
            this.animateElement(element, 'slide-down');
        });

        // Show toast notification
        this.showToast(
            `${severity.toUpperCase()} drift detected in fabric ${fabricId}`, 
            this.getDriftSeverityClass(severity)
        );
    }

    /**
     * Show operation notification
     */
    showOperationNotification(payload) {
        const operationType = payload.operation_type;
        const status = payload.status;
        const result = payload.result;

        const message = `${operationType.replace('_', ' ').toUpperCase()}: ${result}`;
        const type = status === 'success' ? 'success' : 'error';
        
        this.showToast(message, type);
    }

    /**
     * Update DOM element safely
     */
    updateElement(selector, updater) {
        const elements = document.querySelectorAll(selector);
        elements.forEach(element => {
            try {
                updater(element);
            } catch (error) {
                console.error(`Error updating element ${selector}:`, error);
            }
        });
    }

    /**
     * Animate counter changes
     */
    animateCounterChange(element, fromValue, toValue) {
        const duration = 1000;
        const startTime = Date.now();
        const difference = toValue - fromValue;

        const animate = () => {
            const elapsed = Date.now() - startTime;
            const progress = Math.min(elapsed / duration, 1);
            const currentValue = Math.round(fromValue + difference * this.easeOutCubic(progress));
            
            element.textContent = currentValue;
            
            if (progress < 1) {
                requestAnimationFrame(animate);
            }
        };
        
        requestAnimationFrame(animate);
    }

    /**
     * Animate element with CSS class
     */
    animateElement(element, animationClass) {
        element.classList.add(animationClass);
        setTimeout(() => {
            element.classList.remove(animationClass);
        }, 1000);
    }

    /**
     * Show change indicator
     */
    showChangeIndicator(fabricId, change, type) {
        const indicator = document.createElement('div');
        indicator.className = `change-indicator ${type}`;
        indicator.textContent = change;
        
        const target = document.querySelector(`.crd-count[data-fabric="${fabricId}"]`);
        if (target) {
            target.parentNode.appendChild(indicator);
            setTimeout(() => {
                indicator.classList.add('fade-out');
                setTimeout(() => indicator.remove(), 300);
            }, 2000);
        }
    }

    /**
     * Show toast notification
     */
    showToast(message, type = 'info') {
        // Create toast container if it doesn't exist
        let container = document.querySelector('.toast-container');
        if (!container) {
            container = document.createElement('div');
            container.className = 'toast-container';
            document.body.appendChild(container);
        }

        // Create toast element
        const toast = document.createElement('div');
        toast.className = `toast toast-${type}`;
        toast.innerHTML = `
            <div class="toast-content">
                <span class="toast-message">${message}</span>
                <button class="toast-close" onclick="this.parentElement.parentElement.remove()">&times;</button>
            </div>
        `;

        container.appendChild(toast);

        // Auto-remove after 5 seconds
        setTimeout(() => {
            if (toast.parentNode) {
                toast.classList.add('fade-out');
                setTimeout(() => toast.remove(), 300);
            }
        }, 5000);
    }

    /**
     * Get status CSS class
     */
    getStatusClass(status) {
        const statusClasses = {
            'pending': 'secondary',
            'syncing': 'primary',
            'completed': 'success',
            'failed': 'danger',
            'error': 'danger'
        };
        return statusClasses[status] || 'secondary';
    }

    /**
     * Get drift severity CSS class
     */
    getDriftSeverityClass(severity) {
        const severityClasses = {
            'low': 'info',
            'medium': 'warning',
            'high': 'danger',
            'critical': 'danger'
        };
        return severityClasses[severity] || 'info';
    }

    /**
     * Easing function for animations
     */
    easeOutCubic(t) {
        return 1 - Math.pow(1 - t, 3);
    }
}

// Initialize global CNOC real-time client
window.CNOCRealtime = null;
window.CNOCUIUpdates = null;

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', function() {
    // Initialize real-time client
    window.CNOCRealtime = new CNOCRealtimeClient({
        onConnectionChange: (connected) => {
            const indicator = document.querySelector('.connection-indicator');
            if (indicator) {
                indicator.className = `connection-indicator ${connected ? 'connected' : 'disconnected'}`;
                indicator.title = connected ? 'Connected to real-time updates' : 'Disconnected from real-time updates';
            }
        },
        onMetricsUpdate: (metrics) => {
            // Update connection metrics in UI
            const metricsEl = document.querySelector('.realtime-metrics');
            if (metricsEl) {
                metricsEl.innerHTML = `
                    Messages: ${metrics.messagesReceived} | 
                    Avg Latency: ${Math.round(metrics.averageLatency)}ms |
                    Queued: ${metrics.messagesQueued}
                `;
            }
        }
    });

    // Initialize UI update manager
    window.CNOCUIUpdates = new CNOCUIUpdateManager(window.CNOCRealtime);

    // Subscribe to common events
    window.CNOCRealtime.subscribe([
        'fabric_sync_status',
        'crd_count_change', 
        'drift_detected',
        'api_operation_complete'
    ]);
});

// Cleanup on page unload
window.addEventListener('beforeunload', function() {
    if (window.CNOCRealtime) {
        window.CNOCRealtime.close();
    }
});