/**
 * Hedgehog NetBox Plugin JavaScript
 * Common functionality for interactive elements
 */

// Hedgehog plugin namespace
window.Hedgehog = window.Hedgehog || {};

(function(Hedgehog) {
    'use strict';

    // Plugin configuration
    Hedgehog.config = {
        apiBase: '/plugins/hedgehog/api/',
        csrfToken: null,
        debug: false
    };

    // Initialize CSRF token
    Hedgehog.init = function() {
        const csrfInput = document.querySelector('[name=csrfmiddlewaretoken]');
        if (csrfInput) {
            Hedgehog.config.csrfToken = csrfInput.value;
        }
        
        // Initialize common handlers
        Hedgehog.initStatusUpdates();
        Hedgehog.initFormValidation();
        Hedgehog.initBulkActions();
        Hedgehog.initTooltips();
    };

    // Utility functions
    Hedgehog.utils = {
        // Show loading state on button
        setButtonLoading: function(button, loading = true) {
            if (loading) {
                button.dataset.originalText = button.innerHTML;
                button.disabled = true;
                button.innerHTML = '<i class="mdi mdi-loading mdi-spin"></i> Loading...';
            } else {
                button.disabled = false;
                button.innerHTML = button.dataset.originalText || 'Submit';
            }
        },

        // Show notification
        showNotification: function(message, type = 'info') {
            const alertClass = `alert-${type}`;
            const iconMap = {
                success: 'check-circle',
                warning: 'alert-circle',
                danger: 'alert-circle',
                info: 'information'
            };
            
            const alert = document.createElement('div');
            alert.className = `alert ${alertClass} alert-dismissible fade show`;
            alert.innerHTML = `
                <i class="mdi mdi-${iconMap[type] || 'information'}"></i>
                ${message}
                <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
            `;
            
            // Add to container or body
            const container = document.querySelector('.hedgehog-wrapper') || document.body;
            container.insertBefore(alert, container.firstChild);
            
            // Auto-dismiss after 5 seconds
            setTimeout(() => {
                if (alert.parentNode) {
                    alert.remove();
                }
            }, 5000);
        },

        // Format timestamp
        formatTimestamp: function(timestamp) {
            return new Date(timestamp).toLocaleString();
        },

        // Validate IP address
        isValidIP: function(ip) {
            const ipv4Regex = /^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$/;
            return ipv4Regex.test(ip);
        },

        // Validate CIDR
        isValidCIDR: function(cidr) {
            const cidrRegex = /^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\/(?:[0-9]|[1-2][0-9]|3[0-2])$/;
            return cidrRegex.test(cidr);
        },

        // Calculate subnet info
        calculateSubnet: function(cidr) {
            // Basic subnet calculation (simplified)
            const [network, prefix] = cidr.split('/');
            const prefixNum = parseInt(prefix);
            const hostBits = 32 - prefixNum;
            const hostCount = Math.pow(2, hostBits) - 2; // Subtract network and broadcast
            
            return {
                network: network,
                prefix: prefixNum,
                hostCount: hostCount
            };
        }
    };

    // API functions
    Hedgehog.api = {
        // Generic API request
        request: function(url, options = {}) {
            const defaultOptions = {
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': Hedgehog.config.csrfToken
                }
            };
            
            const mergedOptions = Object.assign(defaultOptions, options);
            return fetch(url, mergedOptions);
        },

        // Test fabric connection
        testConnection: function(fabricId) {
            return Hedgehog.api.request(`/plugins/hedgehog/fabrics/${fabricId}/test-connection/`, {
                method: 'POST'
            });
        },

        // Sync fabric
        syncFabric: function(fabricId) {
            return Hedgehog.api.request(`/plugins/hedgehog/fabrics/${fabricId}/sync/`, {
                method: 'POST'
            });
        },

        // Apply VPC
        applyVPC: function(vpcId) {
            return Hedgehog.api.request(`/plugins/hedgehog/vpcs/${vpcId}/apply/`, {
                method: 'POST'
            });
        },

        // Bulk operations
        bulkAction: function(endpoint, data) {
            return Hedgehog.api.request(endpoint, {
                method: 'POST',
                body: JSON.stringify(data)
            });
        }
    };

    // Status update handlers
    Hedgehog.initStatusUpdates = function() {
        // Auto-refresh status indicators
        const statusElements = document.querySelectorAll('[data-auto-refresh]');
        statusElements.forEach(function(element) {
            const interval = parseInt(element.dataset.autoRefresh) || 30000;
            setInterval(function() {
                Hedgehog.refreshStatus(element);
            }, interval);
        });
    };

    // Refresh status element
    Hedgehog.refreshStatus = function(element) {
        const endpoint = element.dataset.statusEndpoint;
        if (!endpoint) return;

        fetch(endpoint)
            .then(response => response.json())
            .then(data => {
                if (data.status) {
                    element.textContent = data.status;
                    element.className = `badge bg-${data.statusClass || 'secondary'}`;
                }
            })
            .catch(error => {
                console.error('Status refresh failed:', error);
            });
    };

    // Form validation
    Hedgehog.initFormValidation = function() {
        // VPC name validation
        const vpcNameInputs = document.querySelectorAll('input[name="name"][data-vpc-name]');
        vpcNameInputs.forEach(function(input) {
            input.addEventListener('input', function() {
                const value = this.value;
                const feedback = this.nextElementSibling;
                
                if (value.length > 11) {
                    this.setCustomValidity('VPC name must be 11 characters or less');
                    if (feedback) feedback.textContent = 'VPC name must be 11 characters or less';
                } else if (!/^[a-z0-9-]*$/.test(value)) {
                    this.setCustomValidity('VPC name can only contain lowercase letters, numbers, and hyphens');
                    if (feedback) feedback.textContent = 'Only lowercase letters, numbers, and hyphens allowed';
                } else {
                    this.setCustomValidity('');
                    if (feedback) feedback.textContent = '';
                }
            });
        });

        // IP address validation
        const ipInputs = document.querySelectorAll('input[data-validate-ip]');
        ipInputs.forEach(function(input) {
            input.addEventListener('blur', function() {
                const value = this.value.trim();
                if (value && !Hedgehog.utils.isValidIP(value)) {
                    this.setCustomValidity('Please enter a valid IP address');
                } else {
                    this.setCustomValidity('');
                }
            });
        });

        // CIDR validation
        const cidrInputs = document.querySelectorAll('input[data-validate-cidr]');
        cidrInputs.forEach(function(input) {
            input.addEventListener('blur', function() {
                const value = this.value.trim();
                if (value && !Hedgehog.utils.isValidCIDR(value)) {
                    this.setCustomValidity('Please enter a valid CIDR (e.g., 192.168.1.0/24)');
                } else {
                    this.setCustomValidity('');
                }
            });
        });
    };

    // Bulk actions
    Hedgehog.initBulkActions = function() {
        const bulkForms = document.querySelectorAll('[data-bulk-form]');
        bulkForms.forEach(function(form) {
            const selectAllCheckbox = form.querySelector('[data-select-all]');
            const itemCheckboxes = form.querySelectorAll('[data-bulk-item]');
            const actionSelect = form.querySelector('[data-bulk-action]');
            const submitButton = form.querySelector('[data-bulk-submit]');

            // Select all functionality
            if (selectAllCheckbox) {
                selectAllCheckbox.addEventListener('change', function() {
                    itemCheckboxes.forEach(function(checkbox) {
                        checkbox.checked = selectAllCheckbox.checked;
                    });
                    updateBulkActionState();
                });
            }

            // Update bulk action state
            function updateBulkActionState() {
                const selectedCount = Array.from(itemCheckboxes).filter(cb => cb.checked).length;
                const hasSelection = selectedCount > 0;
                const hasAction = actionSelect ? actionSelect.value : true;

                if (submitButton) {
                    submitButton.disabled = !(hasSelection && hasAction);
                    submitButton.textContent = hasSelection ? 
                        `Apply to ${selectedCount} item${selectedCount !== 1 ? 's' : ''}` : 
                        'Select items';
                }
            }

            // Item checkbox change
            itemCheckboxes.forEach(function(checkbox) {
                checkbox.addEventListener('change', updateBulkActionState);
            });

            // Action select change
            if (actionSelect) {
                actionSelect.addEventListener('change', updateBulkActionState);
            }

            // Form submission
            form.addEventListener('submit', function(e) {
                e.preventDefault();
                
                const selectedItems = Array.from(itemCheckboxes)
                    .filter(cb => cb.checked)
                    .map(cb => cb.value);
                
                if (selectedItems.length === 0) {
                    Hedgehog.utils.showNotification('Please select at least one item', 'warning');
                    return;
                }

                const action = actionSelect ? actionSelect.value : form.dataset.bulkAction;
                if (!action) {
                    Hedgehog.utils.showNotification('Please select an action', 'warning');
                    return;
                }

                // Confirm destructive actions
                const destructiveActions = ['delete', 'remove', 'destroy'];
                if (destructiveActions.includes(action)) {
                    if (!confirm(`Are you sure you want to ${action} ${selectedItems.length} item(s)?`)) {
                        return;
                    }
                }

                Hedgehog.utils.setButtonLoading(submitButton, true);

                // Perform bulk action
                const endpoint = form.action || form.dataset.bulkEndpoint;
                const formData = new FormData(form);
                
                fetch(endpoint, {
                    method: 'POST',
                    body: formData,
                    headers: {
                        'X-CSRFToken': Hedgehog.config.csrfToken
                    }
                })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        Hedgehog.utils.showNotification(data.message || 'Operation completed successfully', 'success');
                        // Reload page or update UI
                        setTimeout(() => window.location.reload(), 1000);
                    } else {
                        Hedgehog.utils.showNotification(data.error || 'Operation failed', 'danger');
                    }
                })
                .catch(error => {
                    Hedgehog.utils.showNotification('Operation failed: ' + error.message, 'danger');
                })
                .finally(() => {
                    Hedgehog.utils.setButtonLoading(submitButton, false);
                });
            });

            // Initial state
            updateBulkActionState();
        });
    };

    // Initialize tooltips
    Hedgehog.initTooltips = function() {
        // Initialize Bootstrap tooltips if available
        if (typeof bootstrap !== 'undefined' && bootstrap.Tooltip) {
            const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
            tooltipTriggerList.map(function(tooltipTriggerEl) {
                return new bootstrap.Tooltip(tooltipTriggerEl);
            });
        }
    };

    // VPC specific functions
    Hedgehog.vpc = {
        // Update subnet preview
        updateSubnetPreview: function(baseNetwork, baseVlan, template) {
            const preview = document.getElementById('subnet-preview');
            if (!preview) return;

            // Generate preview based on template and configuration
            // This would be expanded based on the specific template logic
            let html = '<div class="text-muted">Preview will update based on configuration</div>';
            preview.innerHTML = html;
        },

        // Validate subnet configuration
        validateSubnetConfig: function(config) {
            const errors = [];
            
            // Validate CIDR
            if (!Hedgehog.utils.isValidCIDR(config.subnet)) {
                errors.push('Invalid subnet CIDR');
            }
            
            // Validate gateway
            if (!Hedgehog.utils.isValidIP(config.gateway)) {
                errors.push('Invalid gateway IP');
            }
            
            // Validate VLAN
            if (config.vlan < 1 || config.vlan > 4094) {
                errors.push('VLAN must be between 1 and 4094');
            }
            
            return errors;
        }
    };

    // Fabric specific functions
    Hedgehog.fabric = {
        // Test connection with visual feedback
        testConnection: function(fabricId, button) {
            console.log('Hedgehog.fabric.testConnection called:', fabricId);
            
            // Show loading state
            const originalText = button.innerHTML;
            button.innerHTML = '<i class="mdi mdi-loading mdi-spin"></i> Testing...';
            button.disabled = true;
            
            console.log('Making API request to test connection...');
            Hedgehog.api.testConnection(fabricId)
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        // Show success state
                        button.innerHTML = '<i class="mdi mdi-check"></i> Connected!';
                        button.className = 'btn btn-success';
                        
                        // Show detailed notification
                        const message = data.message + (data.details ? ` (Namespace: ${data.details.namespace})` : '');
                        Hedgehog.utils.showNotification(message, 'success');
                        
                        // Reload page to show updated status
                        setTimeout(() => window.location.reload(), 2000);
                    } else {
                        // Show error state
                        button.innerHTML = '<i class="mdi mdi-close"></i> Failed';
                        button.className = 'btn btn-danger';
                        
                        Hedgehog.utils.showNotification('Connection test failed: ' + data.error, 'danger');
                        
                        // Reset button after delay
                        setTimeout(() => {
                            button.innerHTML = originalText;
                            button.className = 'btn btn-outline-info';
                            button.disabled = false;
                        }, 3000);
                    }
                })
                .catch(error => {
                    button.innerHTML = '<i class="mdi mdi-close"></i> Error';
                    button.className = 'btn btn-danger';
                    
                    Hedgehog.utils.showNotification('Connection test failed: ' + error.message, 'danger');
                    
                    // Reset button after delay
                    setTimeout(() => {
                        button.innerHTML = originalText;
                        button.className = 'btn btn-outline-info';
                        button.disabled = false;
                    }, 3000);
                });
        },

        // Sync fabric with visual feedback
        sync: function(fabricId, button) {
            console.log('Hedgehog.fabric.sync called:', fabricId);
            
            // Show loading state
            const originalText = button.innerHTML;
            button.innerHTML = '<i class="mdi mdi-loading mdi-spin"></i> Syncing...';
            button.disabled = true;
            button.className = 'btn btn-warning';
            
            console.log('Making API request to sync fabric...');
            Hedgehog.api.syncFabric(fabricId)
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        // Show success state
                        button.innerHTML = '<i class="mdi mdi-check"></i> Synchronized!';
                        button.className = 'btn btn-success';
                        
                        // Show detailed notification
                        const message = data.message + (data.stats ? ` (Duration: ${data.stats.duration})` : '');
                        Hedgehog.utils.showNotification(message, 'success');
                        
                        // Reload page to show updated status
                        setTimeout(() => window.location.reload(), 2000);
                    } else {
                        // Show error state
                        button.innerHTML = '<i class="mdi mdi-close"></i> Sync Failed';
                        button.className = 'btn btn-danger';
                        
                        Hedgehog.utils.showNotification('Sync failed: ' + data.error, 'danger');
                        
                        // Reset button after delay
                        setTimeout(() => {
                            button.innerHTML = originalText;
                            button.className = 'btn btn-primary';
                            button.disabled = false;
                        }, 3000);
                    }
                })
                .catch(error => {
                    button.innerHTML = '<i class="mdi mdi-close"></i> Error';
                    button.className = 'btn btn-danger';
                    
                    Hedgehog.utils.showNotification('Sync failed: ' + error.message, 'danger');
                    
                    // Reset button after delay
                    setTimeout(() => {
                        button.innerHTML = originalText;
                        button.className = 'btn btn-primary';
                        button.disabled = false;
                    }, 3000);
                });
        }
    };

    // Initialize when DOM is ready
    document.addEventListener('DOMContentLoaded', function() {
        Hedgehog.init();
        
        if (Hedgehog.config.debug) {
            console.log('Hedgehog plugin initialized');
        }
    });

})(window.Hedgehog);

// Global helper functions for template use
function syncFabric(fabricId) {
    console.log('🚀 syncFabric called with fabricId:', fabricId);
    const button = event.target;
    console.log('Button element:', button);
    
    // Immediate visual feedback
    const originalText = button.innerHTML;
    button.innerHTML = '<i class="mdi mdi-loading mdi-spin"></i> Starting Sync...';
    button.disabled = true;
    
    if (window.Hedgehog && Hedgehog.fabric && Hedgehog.fabric.sync) {
        console.log('✅ Calling Hedgehog.fabric.sync...');
        Hedgehog.fabric.sync(fabricId, button);
    } else {
        console.error('❌ Hedgehog.fabric.sync not available');
        alert('Sync functionality not loaded. Please refresh the page.');
        
        // Reset button
        setTimeout(() => {
            button.innerHTML = originalText;
            button.disabled = false;
        }, 2000);
    }
}

function testConnection(fabricId) {
    console.log('🔍 testConnection called with fabricId:', fabricId);
    const button = event.target;
    console.log('Button element:', button);
    
    // Immediate visual feedback
    const originalText = button.innerHTML;
    button.innerHTML = '<i class="mdi mdi-loading mdi-spin"></i> Testing...';
    button.disabled = true;
    
    if (window.Hedgehog && Hedgehog.fabric && Hedgehog.fabric.testConnection) {
        console.log('✅ Calling Hedgehog.fabric.testConnection...');
        Hedgehog.fabric.testConnection(fabricId, button);
    } else {
        console.error('❌ Hedgehog.fabric.testConnection not available');
        alert('Test connection functionality not loaded. Please refresh the page.');
        
        // Reset button
        setTimeout(() => {
            button.innerHTML = originalText;
            button.disabled = false;
        }, 2000);
    }
}

// Export for use in other scripts
if (typeof module !== 'undefined' && module.exports) {
    module.exports = window.Hedgehog;
}