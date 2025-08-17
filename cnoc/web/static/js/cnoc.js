// CNOC JavaScript - Progressive Enhancement and AJAX Operations

// Document Ready
document.addEventListener('DOMContentLoaded', function() {
    console.log('CNOC UI initialized with Symphony-Level coordination');
    
    // Initialize tooltips
    initializeTooltips();
    
    // Initialize AJAX handlers
    initializeAjaxHandlers();
    
    // Initialize real-time updates
    initializeRealTimeUpdates();
});

// Initialize Bootstrap tooltips
function initializeTooltips() {
    const tooltipTriggerList = document.querySelectorAll('[data-bs-toggle="tooltip"]');
    const tooltipList = [...tooltipTriggerList].map(tooltipTriggerEl => new bootstrap.Tooltip(tooltipTriggerEl));
}

// AJAX request handler with CSRF support
function makeAjaxRequest(url, method, data, callback) {
    const xhr = new XMLHttpRequest();
    xhr.open(method, url, true);
    xhr.setRequestHeader('Content-Type', 'application/json');
    
    // Add CSRF token if available
    const csrfToken = document.querySelector('meta[name="csrf-token"]');
    if (csrfToken) {
        xhr.setRequestHeader('X-CSRF-Token', csrfToken.content);
    }
    
    xhr.onreadystatechange = function() {
        if (xhr.readyState === 4) {
            if (xhr.status === 200) {
                const response = JSON.parse(xhr.responseText);
                if (callback) {
                    callback(null, response);
                }
            } else {
                if (callback) {
                    callback(new Error('Request failed: ' + xhr.status), null);
                }
            }
        }
    };
    
    if (data) {
        xhr.send(JSON.stringify(data));
    } else {
        xhr.send();
    }
}

// Initialize AJAX handlers for common operations
function initializeAjaxHandlers() {
    // Sync fabric buttons
    document.querySelectorAll('.btn-sync-fabric').forEach(function(btn) {
        btn.addEventListener('click', function() {
            const fabricId = this.dataset.fabricId;
            syncFabric(fabricId, this);
        });
    });
    
    // Test connection buttons
    document.querySelectorAll('.btn-test-connection').forEach(function(btn) {
        btn.addEventListener('click', function() {
            const repoId = this.dataset.repoId;
            testConnection(repoId, this);
        });
    });
    
    // Delete confirmation modals
    document.querySelectorAll('[data-confirm-delete]').forEach(function(btn) {
        btn.addEventListener('click', function(e) {
            e.preventDefault();
            const message = this.dataset.confirmDelete;
            const href = this.href;
            
            if (confirm(message)) {
                window.location.href = href;
            }
        });
    });
}

// Sync fabric operation
function syncFabric(fabricId, button) {
    // Disable button and show loading
    button.disabled = true;
    const originalHTML = button.innerHTML;
    button.innerHTML = '<span class="spinner-border spinner-border-sm" role="status"></span> Syncing...';
    
    makeAjaxRequest(`/api/fabrics/${fabricId}/sync`, 'POST', null, function(err, response) {
        if (err) {
            showNotification('Sync failed: ' + err.message, 'danger');
            button.disabled = false;
            button.innerHTML = originalHTML;
        } else {
            if (response.success) {
                showNotification('Fabric sync completed successfully', 'success');
                // Reload page to show updated data
                setTimeout(() => location.reload(), 1500);
            } else {
                showNotification('Sync failed: ' + (response.error || 'Unknown error'), 'danger');
                button.disabled = false;
                button.innerHTML = originalHTML;
            }
        }
    });
}

// Test repository connection
function testConnection(repoId, button) {
    // Disable button and show loading
    button.disabled = true;
    const originalHTML = button.innerHTML;
    button.innerHTML = '<span class="spinner-border spinner-border-sm" role="status"></span> Testing...';
    
    makeAjaxRequest(`/api/repositories/${repoId}/test-connection`, 'POST', null, function(err, response) {
        if (err) {
            showNotification('Connection test failed: ' + err.message, 'danger');
            button.disabled = false;
            button.innerHTML = originalHTML;
        } else {
            if (response.success) {
                showNotification('Connection successful!', 'success');
                updateConnectionStatus(repoId, 'connected');
            } else {
                showNotification('Connection failed: ' + (response.error || 'Unknown error'), 'danger');
                updateConnectionStatus(repoId, 'failed');
            }
            button.disabled = false;
            button.innerHTML = originalHTML;
        }
    });
}

// Update connection status badge
function updateConnectionStatus(repoId, status) {
    const statusBadge = document.querySelector(`#repo-status-${repoId}`);
    if (statusBadge) {
        statusBadge.className = 'badge';
        if (status === 'connected') {
            statusBadge.classList.add('bg-success');
            statusBadge.textContent = 'Connected';
        } else if (status === 'failed') {
            statusBadge.classList.add('bg-danger');
            statusBadge.textContent = 'Failed';
        } else {
            statusBadge.classList.add('bg-secondary');
            statusBadge.textContent = 'Unknown';
        }
    }
}

// Show notification
function showNotification(message, type) {
    const alertDiv = document.createElement('div');
    alertDiv.className = `alert alert-${type} alert-dismissible fade show position-fixed top-0 start-50 translate-middle-x mt-3`;
    alertDiv.style.zIndex = '9999';
    alertDiv.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;
    
    document.body.appendChild(alertDiv);
    
    // Auto-dismiss after 5 seconds
    setTimeout(() => {
        alertDiv.remove();
    }, 5000);
}

// Initialize real-time updates for dashboard
function initializeRealTimeUpdates() {
    if (document.getElementById('dashboard-stats')) {
        // Update dashboard stats every 30 seconds
        setInterval(updateDashboardStats, 30000);
    }
    
    if (document.getElementById('recent-activity')) {
        // Update recent activity every 15 seconds
        setInterval(updateRecentActivity, 15000);
    }
}

// Update dashboard statistics
function updateDashboardStats() {
    makeAjaxRequest('/api/dashboard/stats', 'GET', null, function(err, response) {
        if (!err && response) {
            // Update fabric count
            const fabricCount = document.getElementById('fabric-count');
            if (fabricCount) {
                fabricCount.textContent = response.fabric_count || 0;
            }
            
            // Update CRD count
            const crdCount = document.getElementById('crd-count');
            if (crdCount) {
                crdCount.textContent = response.crd_count || 0;
            }
            
            // Update sync status
            const inSyncCount = document.getElementById('in-sync-count');
            if (inSyncCount) {
                inSyncCount.textContent = response.in_sync_count || 0;
            }
            
            // Update drift count
            const driftCount = document.getElementById('drift-count');
            if (driftCount) {
                driftCount.textContent = response.drift_count || 0;
            }
        }
    });
}

// Update recent activity
function updateRecentActivity() {
    makeAjaxRequest('/api/dashboard/activity', 'GET', null, function(err, response) {
        if (!err && response && response.activities) {
            const tbody = document.querySelector('#recent-activity tbody');
            if (tbody) {
                // Clear existing rows
                tbody.innerHTML = '';
                
                // Add new activity rows
                response.activities.forEach(activity => {
                    const row = document.createElement('tr');
                    row.className = 'fade-in';
                    row.innerHTML = `
                        <td>${formatTimestamp(activity.timestamp)}</td>
                        <td>${activity.type}</td>
                        <td>${activity.resource}</td>
                        <td>${activity.action}</td>
                        <td>${formatStatus(activity.status)}</td>
                    `;
                    tbody.appendChild(row);
                });
            }
        }
    });
}

// Format timestamp for display
function formatTimestamp(timestamp) {
    const date = new Date(timestamp);
    const now = new Date();
    const diff = now - date;
    
    // If less than 1 minute ago
    if (diff < 60000) {
        return 'Just now';
    }
    
    // If less than 1 hour ago
    if (diff < 3600000) {
        const minutes = Math.floor(diff / 60000);
        return `${minutes} minute${minutes > 1 ? 's' : ''} ago`;
    }
    
    // If less than 24 hours ago
    if (diff < 86400000) {
        const hours = Math.floor(diff / 3600000);
        return `${hours} hour${hours > 1 ? 's' : ''} ago`;
    }
    
    // Otherwise show date
    return date.toLocaleDateString();
}

// Format status badge
function formatStatus(status) {
    const badgeClass = status === 'success' ? 'bg-success' : 
                       status === 'error' ? 'bg-danger' : 
                       'bg-warning';
    return `<span class="badge ${badgeClass}">${status}</span>`;
}

// Progressive disclosure toggle
function toggleDetails(elementId) {
    const element = document.getElementById(elementId);
    if (element) {
        element.classList.toggle('show');
        
        // Update chevron icon
        const chevron = document.querySelector(`[data-target="${elementId}"] .collapse-indicator`);
        if (chevron) {
            chevron.classList.toggle('collapsed');
        }
    }
}

// Export functions for use in templates
window.CNOC = {
    syncFabric,
    testConnection,
    showNotification,
    toggleDetails
};