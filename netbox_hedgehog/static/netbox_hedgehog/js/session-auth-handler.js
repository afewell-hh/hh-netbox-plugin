/**
 * Session Authentication Handler
 * Handles session timeouts gracefully for sync operations
 */

class SessionAuthHandler {
    constructor() {
        this.alertContainer = null;
        this.redirectDelay = 2000; // 2 seconds before redirect
    }

    /**
     * Initialize the session auth handler
     */
    init() {
        this.setupAlertContainer();
        return this;
    }

    /**
     * Set up alert container for displaying messages
     */
    setupAlertContainer() {
        let container = document.getElementById('auth-alerts');
        if (!container) {
            container = document.createElement('div');
            container.id = 'auth-alerts';
            container.style.cssText = 'position: fixed; top: 20px; right: 20px; z-index: 9999; min-width: 300px;';
            document.body.appendChild(container);
        }
        this.alertContainer = container;
    }

    /**
     * Display an alert message
     */
    showAlert(message, type = 'info') {
        const alertTypes = {
            success: { class: 'alert-success', icon: 'mdi-check-circle' },
            warning: { class: 'alert-warning', icon: 'mdi-alert-circle' },
            danger: { class: 'alert-danger', icon: 'mdi-alert-circle' },
            info: { class: 'alert-info', icon: 'mdi-information' }
        };

        const alertConfig = alertTypes[type] || alertTypes.info;
        const alertId = 'alert-' + Date.now();
        
        const alert = document.createElement('div');
        alert.id = alertId;
        alert.className = `alert ${alertConfig.class} alert-dismissible fade show`;
        alert.style.marginBottom = '10px';
        
        const safeMessage = (message || 'Notification').replace(/</g, '&lt;').replace(/>/g, '&gt;');
        
        alert.innerHTML = `
            <i class="mdi ${alertConfig.icon}"></i>
            ${safeMessage}
            <button type="button" class="btn-close" aria-label="Close" onclick="this.parentElement.remove()"></button>
        `;
        
        this.alertContainer.appendChild(alert);
        
        // Auto-remove after 5 seconds unless it's a session timeout
        if (type !== 'warning' || !message.includes('session')) {
            setTimeout(() => {
                if (document.getElementById(alertId)) {
                    alert.remove();
                }
            }, 5000);
        }
        
        return alert;
    }

    /**
     * Handle authentication errors from sync responses
     */
    handleAuthError(response, error) {
        // Check if this is a session timeout error
        if (response && (response.requires_login || response.action === 'redirect_to_login')) {
            this.handleSessionTimeout(response.error || 'Your session has expired. Please login again.');
            return true;
        }
        
        // Check for 401 status
        if (error && error.message && error.message.includes('401')) {
            this.handleSessionTimeout('Your session has expired. Please login again.');
            return true;
        }
        
        return false;
    }

    /**
     * Handle session timeout - show message and redirect to login
     */
    handleSessionTimeout(message) {
        const alert = this.showAlert(message + ' Redirecting to login...', 'warning');
        
        // Disable all sync buttons to prevent further attempts
        this.disableAllSyncButtons();
        
        // Redirect to login after delay
        setTimeout(() => {
            window.location.href = '/login/?next=' + encodeURIComponent(window.location.pathname);
        }, this.redirectDelay);
    }

    /**
     * Disable all sync buttons to prevent multiple failed attempts
     */
    disableAllSyncButtons() {
        const syncButtons = document.querySelectorAll(
            '[id*="sync"], [class*="sync"], [onclick*="sync"], .fabric-sync-btn, .btn-sync-fabric'
        );
        
        syncButtons.forEach(button => {
            button.disabled = true;
            button.style.opacity = '0.6';
            
            // Update button text to indicate session expired
            const originalText = button.innerHTML;
            if (!originalText.includes('Session Expired')) {
                button.innerHTML = '<i class="mdi mdi-lock-alert"></i> Session Expired';
            }
        });
    }

    /**
     * Enhanced fetch with authentication error handling
     */
    async fetchWithAuth(url, options = {}) {
        try {
            // Add X-Requested-With header for AJAX detection
            const headers = {
                'X-Requested-With': 'XMLHttpRequest',
                ...options.headers
            };

            const response = await fetch(url, {
                ...options,
                headers
            });

            // Check for authentication errors
            if (response.status === 401) {
                try {
                    const errorData = await response.json();
                    this.handleAuthError(errorData, null);
                    throw new Error('Session expired. Please login again.');
                } catch (jsonError) {
                    // If JSON parsing fails, still handle as auth error
                    this.handleSessionTimeout('Your session has expired. Please login again.');
                    throw new Error('Session expired. Please login again.');
                }
            }

            return response;
        } catch (error) {
            // Check if the error indicates authentication issues
            if (error.message.includes('401') || error.message.includes('session')) {
                this.handleAuthError(null, error);
            }
            throw error;
        }
    }

    /**
     * Helper method to get CSRF token
     */
    getCsrfToken() {
        // Try multiple methods to get CSRF token
        return document.querySelector('[name=csrfmiddlewaretoken]')?.value || 
               document.querySelector('meta[name=csrf-token]')?.getAttribute('content') || 
               this.getCookie('csrftoken');
    }

    /**
     * Helper method to get cookie value
     */
    getCookie(name) {
        let cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            const cookies = document.cookie.split(';');
            for (let i = 0; i < cookies.length; i++) {
                const cookie = cookies[i].trim();
                if (cookie.substring(0, name.length + 1) === (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    }
}

// Create global instance
window.sessionAuthHandler = new SessionAuthHandler().init();

// Export for module usage
if (typeof module !== 'undefined' && module.exports) {
    module.exports = SessionAuthHandler;
}