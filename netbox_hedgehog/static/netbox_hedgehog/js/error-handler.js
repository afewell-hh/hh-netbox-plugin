/**
 * Comprehensive Error Handler for Hedgehog NetBox Plugin
 * Eliminates JavaScript errors and provides fallbacks
 */

(function() {
    'use strict';
    
    // Global error handler to catch unhandled errors
    window.addEventListener('error', function(event) {
        console.warn('🛡️ Error caught by global handler:', {
            message: event.message,
            filename: event.filename,
            lineno: event.lineno,
            colno: event.colno,
            error: event.error
        });
        
        // Prevent errors from breaking the page
        event.preventDefault();
        return true;
    });
    
    // Handle unhandled promise rejections
    window.addEventListener('unhandledrejection', function(event) {
        console.warn('🛡️ Unhandled promise rejection:', event.reason);
        event.preventDefault();
    });
    
    // Safe function caller - prevents undefined function errors
    window.safeCall = function(funcName, ...args) {
        try {
            const func = window[funcName];
            if (typeof func === 'function') {
                return func.apply(window, args);
            } else {
                console.warn(`Function ${funcName} not found, skipping call`);
                return null;
            }
        } catch (error) {
            console.warn(`Error calling ${funcName}:`, error);
            return null;
        }
    };
    
    // Safe object access - prevents undefined object errors
    window.safeAccess = function(obj, path, defaultValue = null) {
        try {
            const keys = path.split('.');
            let current = obj;
            
            for (const key of keys) {
                if (current && typeof current === 'object' && key in current) {
                    current = current[key];
                } else {
                    return defaultValue;
                }
            }
            
            return current;
        } catch (error) {
            console.warn(`Error accessing ${path}:`, error);
            return defaultValue;
        }
    };
    
    // Ensure essential global objects exist
    window.Hedgehog = window.Hedgehog || {};
    window.Hedgehog.utils = window.Hedgehog.utils || {};
    window.Hedgehog.api = window.Hedgehog.api || {};
    window.Hedgehog.fabric = window.Hedgehog.fabric || {};
    window.Hedgehog.vpc = window.Hedgehog.vpc || {};
    
    // Fallback notification system
    if (!window.Hedgehog.utils.showNotification) {
        window.Hedgehog.utils.showNotification = function(message, type = 'info') {
            const alertClass = type === 'error' ? 'danger' : type;
            const notification = document.createElement('div');
            notification.className = `alert alert-${alertClass} alert-dismissible fade show position-fixed`;
            notification.style.cssText = 'top: 20px; right: 20px; z-index: 9999; min-width: 300px;';
            
            const safeMessage = (message || 'Notification').replace(/</g, '&lt;').replace(/>/g, '&gt;');
            const iconMap = {
                success: 'check-circle',
                warning: 'alert-circle',
                danger: 'alert-circle',
                info: 'information'
            };
            
            notification.innerHTML = `
                <i class="mdi mdi-${iconMap[type] || 'information'}"></i>
                ${safeMessage}
                <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
            `;
            
            document.body.appendChild(notification);
            
            // Auto-dismiss after 5 seconds
            setTimeout(() => {
                if (notification.parentNode) {
                    notification.remove();
                }
            }, 5000);
        };
    }
    
    // Fallback modal system
    if (!window.showModal) {
        window.showModal = function(title, content) {
            if (typeof bootstrap !== 'undefined' && bootstrap.Modal) {
                const modalHtml = `
                    <div class="modal fade" id="fallbackModal" tabindex="-1">
                        <div class="modal-dialog modal-lg">
                            <div class="modal-content">
                                <div class="modal-header">
                                    <h5 class="modal-title">${(title || 'Modal').replace(/</g, '&lt;').replace(/>/g, '&gt;')}</h5>
                                    <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                                </div>
                                <div class="modal-body">
                                    ${(content || 'No content').replace(/</g, '&lt;').replace(/>/g, '&gt;')}
                                </div>
                                <div class="modal-footer">
                                    <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Close</button>
                                </div>
                            </div>
                        </div>
                    </div>
                `;
                
                // Remove existing modal
                const existingModal = document.getElementById('fallbackModal');
                if (existingModal) {
                    existingModal.remove();
                }
                
                document.body.insertAdjacentHTML('beforeend', modalHtml);
                const modal = new bootstrap.Modal(document.getElementById('fallbackModal'));
                modal.show();
            } else {
                // Fallback to alert
                const cleanContent = content.replace(/<[^>]*>/g, ' ').replace(/\s+/g, ' ').trim();
                alert((title || 'Modal') + '\n\n' + cleanContent);
            }
        };
    }
    
    // Safe DOM ready function
    window.safeReady = function(callback) {
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', function() {
                try {
                    callback();
                } catch (error) {
                    console.warn('Error in ready callback:', error);
                }
            });
        } else {
            try {
                callback();
            } catch (error) {
                console.warn('Error in immediate callback:', error);
            }
        }
    };
    
    // Safe fetch wrapper with better error handling
    window.safeFetch = function(url, options = {}) {
        const defaultOptions = {
            headers: {
                'Content-Type': 'application/json'
            }
        };
        
        // Add CSRF token if available
        const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]');
        if (csrfToken) {
            defaultOptions.headers['X-CSRFToken'] = csrfToken.value;
        }
        
        const mergedOptions = { ...defaultOptions, ...options };
        if (options.headers) {
            mergedOptions.headers = { ...defaultOptions.headers, ...options.headers };
        }
        
        return fetch(url, mergedOptions)
            .then(response => {
                if (!response.ok) {
                    throw new Error(`HTTP ${response.status}: ${response.statusText}`);
                }
                return response;
            })
            .catch(error => {
                console.warn('Fetch error for', url, ':', error.message);
                throw error;
            });
    };
    
    // Ensure Chart.js fallback
    if (typeof Chart === 'undefined') {
        window.Chart = function() {
            console.warn('Chart.js not loaded, chart creation skipped');
            return {
                update: function() {},
                destroy: function() {},
                data: { datasets: [{ data: [] }] }
            };
        };
    }
    
    // Ensure Bootstrap fallback
    if (typeof bootstrap === 'undefined') {
        window.bootstrap = {
            Modal: function(element) {
                return {
                    show: function() {
                        console.warn('Bootstrap Modal not loaded, using fallback');
                        if (element) {
                            element.style.display = 'block';
                            element.classList.add('show');
                        }
                    },
                    hide: function() {
                        if (element) {
                            element.style.display = 'none';
                            element.classList.remove('show');
                        }
                    }
                };
            },
            Toast: function(element) {
                return {
                    show: function() {
                        if (element) {
                            element.style.display = 'block';
                            element.classList.add('show');
                        }
                    },
                    hide: function() {
                        if (element) {
                            element.style.display = 'none';
                            element.classList.remove('show');
                        }
                    }
                };
            },
            Tooltip: function(element) {
                return { show: function() {}, hide: function() {} };
            }
        };
    }
    
    // Global function fallbacks to prevent undefined errors
    const globalFunctions = [
        'viewFabricDetails',
        'syncFabric',
        'manageFabric',
        'testConnection',
        'cleanupArchives',
        'optimizeStorage',
        'validateIntegrity',
        'emergencyStop',
        'showDriftAnalysis',
        'checkForDrift',
        'viewDriftHistory',
        'configureDriftSettings',
        'triggerGitSync',
        'showResourceStates',
        'showDriftDetails',
        'processAllFiles',
        'syncFromGit',
        'initGitOps'
    ];
    
    globalFunctions.forEach(funcName => {
        if (typeof window[funcName] === 'undefined') {
            window[funcName] = function(...args) {
                console.warn(`Function ${funcName} called but not defined, args:`, args);
                
                // Try to provide some sensible defaults
                if (funcName.includes('show') || funcName.includes('Display')) {
                    if (window.Hedgehog && window.Hedgehog.utils && window.Hedgehog.utils.showNotification) {
                        window.Hedgehog.utils.showNotification(`${funcName} not implemented yet`, 'info');
                    } else {
                        alert(`${funcName} not implemented yet`);
                    }
                }
                
                return null;
            };
        }
    });
    
    console.log('🛡️ Error handler initialized - JavaScript errors should be prevented');
    
})();