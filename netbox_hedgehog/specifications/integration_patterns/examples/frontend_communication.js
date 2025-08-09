/**
 * Frontend Communication Integration Examples
 * Demonstrates best practices for frontend-backend communication
 */

class IntegrationAPI {
    constructor(baseUrl = '/plugins/hedgehog/api') {
        this.baseUrl = baseUrl;
        this.csrfToken = this.getCSRFToken();
        this.defaultHeaders = {
            'Content-Type': 'application/json',
            'X-CSRFToken': this.csrfToken,
        };
    }

    getCSRFToken() {
        const token = document.querySelector('[name=csrfmiddlewaretoken]');
        return token ? token.value : '';
    }

    async request(method, endpoint, data = null, options = {}) {
        const url = `${this.baseUrl}${endpoint}`;
        
        const config = {
            method,
            headers: { ...this.defaultHeaders, ...options.headers },
            credentials: 'same-origin',
        };

        if (data && ['POST', 'PUT', 'PATCH'].includes(method)) {
            config.body = JSON.stringify(data);
        }

        try {
            const response = await fetch(url, config);
            
            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                throw new Error(errorData.error || `HTTP ${response.status}`);
            }

            const contentType = response.headers.get('content-type');
            if (contentType && contentType.includes('application/json')) {
                return await response.json();
            }

            return await response.text();
        } catch (error) {
            console.error('API request failed:', error);
            throw error;
        }
    }

    // CRUD operations
    async get(endpoint, params = {}) {
        const queryString = new URLSearchParams(params).toString();
        const url = endpoint + (queryString ? `?${queryString}` : '');
        return this.request('GET', url);
    }

    async post(endpoint, data) {
        return this.request('POST', endpoint, data);
    }

    async put(endpoint, data) {
        return this.request('PUT', endpoint, data);
    }

    async patch(endpoint, data) {
        return this.request('PATCH', endpoint, data);
    }

    async delete(endpoint) {
        return this.request('DELETE', endpoint);
    }
}

// Real-time status updates using WebSocket
class StatusUpdater {
    constructor(url = '/ws/status/') {
        this.url = url;
        this.socket = null;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 5;
        this.reconnectDelay = 1000;
        this.eventHandlers = {};
        
        this.connect();
    }

    connect() {
        try {
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            this.socket = new WebSocket(`${protocol}//${window.location.host}${this.url}`);
            
            this.socket.onopen = () => {
                console.log('WebSocket connected');
                this.reconnectAttempts = 0;
                this.emit('connected');
            };
            
            this.socket.onmessage = (event) => {
                try {
                    const data = JSON.parse(event.data);
                    this.handleMessage(data);
                } catch (error) {
                    console.error('Failed to parse WebSocket message:', error);
                }
            };
            
            this.socket.onclose = () => {
                console.log('WebSocket disconnected');
                this.emit('disconnected');
                this.attemptReconnect();
            };
            
            this.socket.onerror = (error) => {
                console.error('WebSocket error:', error);
                this.emit('error', error);
            };
            
        } catch (error) {
            console.error('Failed to connect WebSocket:', error);
            this.attemptReconnect();
        }
    }

    attemptReconnect() {
        if (this.reconnectAttempts < this.maxReconnectAttempts) {
            this.reconnectAttempts++;
            const delay = this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1);
            
            console.log(`Attempting to reconnect in ${delay}ms (attempt ${this.reconnectAttempts})`);
            setTimeout(() => this.connect(), delay);
        }
    }

    handleMessage(data) {
        const { type, ...payload } = data;
        this.emit(type, payload);
    }

    send(data) {
        if (this.socket && this.socket.readyState === WebSocket.OPEN) {
            this.socket.send(JSON.stringify(data));
        } else {
            console.warn('WebSocket not connected');
        }
    }

    on(event, handler) {
        if (!this.eventHandlers[event]) {
            this.eventHandlers[event] = [];
        }
        this.eventHandlers[event].push(handler);
    }

    off(event, handler) {
        if (this.eventHandlers[event]) {
            this.eventHandlers[event] = this.eventHandlers[event].filter(h => h !== handler);
        }
    }

    emit(event, data) {
        if (this.eventHandlers[event]) {
            this.eventHandlers[event].forEach(handler => handler(data));
        }
    }

    disconnect() {
        if (this.socket) {
            this.socket.close();
        }
    }
}

// Form handling with validation
class SmartForm {
    constructor(formElement) {
        this.form = formElement;
        this.api = new IntegrationAPI();
        this.validators = {};
        
        this.initialize();
    }

    initialize() {
        this.setupValidation();
        this.setupAutoSave();
        this.setupSubmitHandler();
    }

    setupValidation() {
        // Real-time validation
        const inputs = this.form.querySelectorAll('input, textarea, select');
        inputs.forEach(input => {
            input.addEventListener('blur', () => this.validateField(input));
            input.addEventListener('input', () => this.clearFieldError(input));
        });
    }

    setupAutoSave() {
        let saveTimeout;
        const inputs = this.form.querySelectorAll('input, textarea, select');
        
        inputs.forEach(input => {
            input.addEventListener('input', () => {
                clearTimeout(saveTimeout);
                saveTimeout = setTimeout(() => {
                    this.autoSave();
                }, 2000);
            });
        });
    }

    setupSubmitHandler() {
        this.form.addEventListener('submit', async (e) => {
            e.preventDefault();
            await this.submitForm();
        });
    }

    async validateField(field) {
        const validator = this.validators[field.name];
        if (validator) {
            try {
                const isValid = await validator(field.value, field);
                if (!isValid) {
                    this.showFieldError(field, 'Invalid value');
                } else {
                    this.clearFieldError(field);
                }
            } catch (error) {
                console.error('Validation error:', error);
            }
        }
    }

    addValidator(fieldName, validatorFunction) {
        this.validators[fieldName] = validatorFunction;
    }

    showFieldError(field, message) {
        this.clearFieldError(field);
        
        field.classList.add('is-invalid');
        
        const errorDiv = document.createElement('div');
        errorDiv.className = 'invalid-feedback';
        errorDiv.textContent = message;
        
        field.parentNode.appendChild(errorDiv);
    }

    clearFieldError(field) {
        field.classList.remove('is-invalid');
        
        const errorDiv = field.parentNode.querySelector('.invalid-feedback');
        if (errorDiv) {
            errorDiv.remove();
        }
    }

    async autoSave() {
        const formData = new FormData(this.form);
        const data = Object.fromEntries(formData.entries());
        
        // Only auto-save if there's an ID (existing object)
        const objectId = data.id;
        if (!objectId) return;
        
        try {
            await this.api.patch(`/objects/${objectId}/`, data);
            this.showSaveIndicator('Auto-saved', 'success');
        } catch (error) {
            console.error('Auto-save failed:', error);
            this.showSaveIndicator('Auto-save failed', 'error');
        }
    }

    async submitForm() {
        const formData = new FormData(this.form);
        const data = Object.fromEntries(formData.entries());
        
        try {
            this.setFormLoading(true);
            
            const objectId = data.id;
            let result;
            
            if (objectId) {
                // Update existing
                result = await this.api.put(`/objects/${objectId}/`, data);
            } else {
                // Create new
                result = await this.api.post('/objects/', data);
            }
            
            this.showNotification('Saved successfully!', 'success');
            
            // Redirect or update form
            if (!objectId && result.id) {
                // Redirect to edit page for new object
                window.location.href = `/objects/${result.id}/edit/`;
            }
            
        } catch (error) {
            console.error('Form submission failed:', error);
            this.showNotification(`Error: ${error.message}`, 'error');
        } finally {
            this.setFormLoading(false);
        }
    }

    setFormLoading(isLoading) {
        const submitButton = this.form.querySelector('[type="submit"]');
        const inputs = this.form.querySelectorAll('input, textarea, select, button');
        
        inputs.forEach(input => {
            input.disabled = isLoading;
        });
        
        if (submitButton) {
            submitButton.textContent = isLoading ? 'Saving...' : 'Save';
        }
    }

    showSaveIndicator(message, type) {
        let indicator = this.form.querySelector('.save-indicator');
        
        if (!indicator) {
            indicator = document.createElement('div');
            indicator.className = 'save-indicator';
            this.form.appendChild(indicator);
        }
        
        indicator.className = `save-indicator alert alert-${type === 'success' ? 'success' : 'danger'}`;
        indicator.textContent = message;
        indicator.style.display = 'block';
        
        setTimeout(() => {
            indicator.style.display = 'none';
        }, 3000);
    }

    showNotification(message, type) {
        // Create toast notification
        const toast = document.createElement('div');
        toast.className = `toast align-items-center text-white bg-${type === 'success' ? 'success' : 'danger'} border-0`;
        toast.setAttribute('role', 'alert');
        
        toast.innerHTML = `
            <div class="d-flex">
                <div class="toast-body">${message}</div>
                <button type="button" class="btn-close btn-close-white me-2 m-auto" 
                        data-bs-dismiss="toast"></button>
            </div>
        `;
        
        // Add to toast container
        let container = document.querySelector('.toast-container');
        if (!container) {
            container = document.createElement('div');
            container.className = 'toast-container position-fixed top-0 end-0 p-3';
            document.body.appendChild(container);
        }
        
        container.appendChild(toast);
        
        // Show toast
        const bsToast = new bootstrap.Toast(toast);
        bsToast.show();
        
        // Remove after hiding
        toast.addEventListener('hidden.bs.toast', () => {
            toast.remove();
        });
    }
}

// Status indicator component
class StatusIndicator {
    constructor(element) {
        this.element = element;
        this.updateInterval = null;
    }

    updateStatus(status, message = '', timestamp = null) {
        // Remove existing status classes
        this.element.classList.remove('status-pending', 'status-syncing', 'status-synced', 'status-error');
        
        // Add new status class
        this.element.classList.add(`status-${status}`);
        
        // Update content
        this.element.innerHTML = `
            <span class="status-badge badge">${status.toUpperCase()}</span>
            ${message ? `<span class="status-message">${message}</span>` : ''}
            ${timestamp ? `<small class="status-timestamp">${new Date(timestamp).toLocaleString()}</small>` : ''}
        `;
    }

    startPolling(url, interval = 30000) {
        this.stopPolling();
        
        const poll = async () => {
            try {
                const api = new IntegrationAPI();
                const status = await api.get(url);
                this.updateStatus(status.status, status.message, status.timestamp);
            } catch (error) {
                console.error('Status polling failed:', error);
            }
        };
        
        // Poll immediately, then at intervals
        poll();
        this.updateInterval = setInterval(poll, interval);
    }

    stopPolling() {
        if (this.updateInterval) {
            clearInterval(this.updateInterval);
            this.updateInterval = null;
        }
    }
}

// Action button handler
class ActionButtons {
    constructor() {
        this.api = new IntegrationAPI();
        this.initialize();
    }

    initialize() {
        document.addEventListener('click', (e) => {
            if (e.target.matches('[data-action]')) {
                e.preventDefault();
                this.handleAction(e.target);
            }
        });
    }

    async handleAction(button) {
        const action = button.dataset.action;
        const objectId = button.dataset.objectId;
        const confirmMessage = button.dataset.confirm;
        
        // Show confirmation if required
        if (confirmMessage && !confirm(confirmMessage)) {
            return;
        }
        
        try {
            this.setButtonLoading(button, true);
            
            let result;
            switch (action) {
                case 'sync':
                    result = await this.api.post(`/objects/${objectId}/sync/`);
                    break;
                case 'delete':
                    result = await this.api.delete(`/objects/${objectId}/`);
                    break;
                default:
                    console.warn(`Unknown action: ${action}`);
                    return;
            }
            
            this.handleActionResult(button, action, result);
            
        } catch (error) {
            console.error(`Action ${action} failed:`, error);
            this.showActionError(button, error.message);
        } finally {
            this.setButtonLoading(button, false);
        }
    }

    setButtonLoading(button, isLoading) {
        if (isLoading) {
            button.disabled = true;
            button.dataset.originalText = button.textContent;
            button.innerHTML = '<i class="mdi mdi-loading mdi-spin"></i> Loading...';
        } else {
            button.disabled = false;
            button.textContent = button.dataset.originalText || button.textContent;
        }
    }

    handleActionResult(button, action, result) {
        switch (action) {
            case 'sync':
                this.showActionSuccess(button, 'Sync started successfully');
                // Update status indicator if present
                const statusIndicator = document.querySelector(`[data-object-id="${button.dataset.objectId}"] .status-indicator`);
                if (statusIndicator) {
                    new StatusIndicator(statusIndicator).updateStatus('syncing', 'Sync in progress...');
                }
                break;
                
            case 'delete':
                this.showActionSuccess(button, 'Deleted successfully');
                // Remove row or redirect
                const row = button.closest('tr');
                if (row) {
                    row.remove();
                } else {
                    window.location.href = '/objects/';
                }
                break;
        }
    }

    showActionSuccess(button, message) {
        // Show temporary success message
        const originalText = button.textContent;
        button.textContent = '✓ ' + message;
        button.classList.add('btn-success');
        
        setTimeout(() => {
            button.textContent = originalText;
            button.classList.remove('btn-success');
        }, 2000);
    }

    showActionError(button, message) {
        // Show temporary error message
        const originalText = button.textContent;
        button.textContent = '✗ Error';
        button.classList.add('btn-danger');
        
        setTimeout(() => {
            button.textContent = originalText;
            button.classList.remove('btn-danger');
        }, 3000);
        
        // Also show toast notification
        const smartForm = new SmartForm(document.createElement('form'));
        smartForm.showNotification(`Error: ${message}`, 'error');
    }
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    // Initialize global API client
    window.integrationAPI = new IntegrationAPI();
    
    // Initialize status updater for real-time updates
    window.statusUpdater = new StatusUpdater();
    
    // Initialize smart forms
    const forms = document.querySelectorAll('.smart-form');
    forms.forEach(form => {
        new SmartForm(form);
    });
    
    // Initialize status indicators
    const statusIndicators = document.querySelectorAll('.status-indicator[data-poll-url]');
    statusIndicators.forEach(indicator => {
        const statusIndicatorInstance = new StatusIndicator(indicator);
        statusIndicatorInstance.startPolling(indicator.dataset.pollUrl);
    });
    
    // Initialize action buttons
    new ActionButtons();
    
    console.log('Frontend integration initialized');
});

// Export for module use
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        IntegrationAPI,
        StatusUpdater,
        SmartForm,
        StatusIndicator,
        ActionButtons
    };
}