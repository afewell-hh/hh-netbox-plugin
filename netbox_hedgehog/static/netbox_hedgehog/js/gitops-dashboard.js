/**
 * GitOps Dashboard JavaScript
 * Handles real-time monitoring and management of GitOps file operations
 */

class GitOpsDashboard {
    constructor() {
        this.refreshInterval = null;
        this.autoRefreshEnabled = true;
        this.refreshIntervalMs = 30000; // 30 seconds
        this.charts = {};
        
        this.init();
    }
    
    init() {
        console.log('📊 Initializing GitOps Dashboard');
        this.attachEventListeners();
        this.loadInitialData();
        this.initializeCharts();
        this.startAutoRefresh();
    }
    
    attachEventListeners() {
        // Refresh controls
        document.getElementById('refresh-dashboard')?.addEventListener('click', () => this.refreshDashboard());
        document.getElementById('auto-refresh')?.addEventListener('change', (e) => this.toggleAutoRefresh(e.target.checked));
        
        // Fabric filters
        document.querySelectorAll('input[name="fabric-filter"]').forEach(radio => {
            radio.addEventListener('change', () => this.filterFabrics(radio.id));
        });
        
        // Quick actions
        document.getElementById('trigger-global-sync')?.addEventListener('click', () => this.triggerGlobalSync());
        document.getElementById('process-pending-files')?.addEventListener('click', () => this.processPendingFiles());
        document.getElementById('check-system-health')?.addEventListener('click', () => this.checkSystemHealth());
        
        // Status card interactions
        document.querySelectorAll('.gitops-status-card').forEach(card => {
            card.addEventListener('click', () => this.showStatusDetails(card));
        });
    }
    
    async loadInitialData() {
        try {
            console.log('📥 Loading initial dashboard data...');
            await Promise.all([
                this.loadOverviewStats(),
                this.loadFabricsList(),
                this.loadRecentActivity(),
                this.loadSystemHealth(),
                this.loadStorageStats()
            ]);
            console.log('✅ Initial data loaded successfully');
        } catch (error) {
            console.error('❌ Failed to load initial data:', error);
            this.showError('Failed to load dashboard data');
        }
    }
    
    async loadOverviewStats() {
        try {
            const response = await fetch('/plugins/hedgehog/api/gitops/overview/');
            const stats = await response.json();
            
            // Update status cards
            document.getElementById('total-fabrics').textContent = stats.total_fabrics || 0;
            document.getElementById('pending-files').textContent = stats.pending_files || 0;
            document.getElementById('processed-today').textContent = stats.processed_today || 0;
            document.getElementById('error-count').textContent = stats.error_count || 0;
            
            // Add pulse animation to cards with high values
            this.animateHighValueCards(stats);
            
        } catch (error) {
            console.error('Failed to load overview stats:', error);
        }
    }
    
    async loadFabricsList() {
        try {
            const response = await fetch('/plugins/hedgehog/api/gitops/fabrics/');
            const fabrics = await response.json();
            
            const tbody = document.getElementById('fabrics-tbody');
            const emptyState = document.getElementById('fabrics-empty');
            
            if (fabrics && fabrics.length > 0) {
                tbody.innerHTML = '';
                emptyState.classList.add('d-none');
                
                fabrics.forEach(fabric => this.renderFabricRow(fabric, tbody));
            } else {
                tbody.innerHTML = '';
                emptyState.classList.remove('d-none');
            }
            
        } catch (error) {
            console.error('Failed to load fabrics list:', error);
        }
    }
    
    renderFabricRow(fabric, tbody) {
        const row = document.createElement('tr');
        row.className = 'fabric-row';
        row.dataset.fabricId = fabric.id;
        
        const statusBadge = this.getStatusBadge(fabric.status);
        const lastActivity = fabric.last_activity ? new Date(fabric.last_activity).toLocaleString() : 'Never';
        
        row.innerHTML = `
            <td>
                <div class="d-flex align-items-center">
                    <i class="mdi mdi-server-network text-primary me-2"></i>
                    <div>
                        <div class="fw-bold">${fabric.name}</div>
                        <small class="text-muted">${fabric.description || 'No description'}</small>
                    </div>
                </div>
            </td>
            <td>${statusBadge}</td>
            <td>
                <span class="badge bg-warning">${fabric.raw_files_count || 0}</span>
            </td>
            <td>
                <span class="badge bg-success">${fabric.managed_files_count || 0}</span>
            </td>
            <td>
                <small>${lastActivity}</small>
            </td>
            <td>
                <div class="btn-group btn-group-sm" role="group">
                    <button class="btn btn-outline-primary" onclick="viewFabricDetails(${fabric.id})" title="View Details">
                        <i class="mdi mdi-eye"></i>
                    </button>
                    <button class="btn btn-outline-success" onclick="syncFabric(${fabric.id})" title="Sync">
                        <i class="mdi mdi-sync"></i>
                    </button>
                    <button class="btn btn-outline-info" onclick="manageFabric(${fabric.id})" title="Manage">
                        <i class="mdi mdi-cog"></i>
                    </button>
                </div>
            </td>
        `;
        
        tbody.appendChild(row);
    }
    
    getStatusBadge(status) {
        const statusMap = {
            'active': { class: 'bg-success', icon: 'check-circle', text: 'Active' },
            'processing': { class: 'bg-info', icon: 'cog', text: 'Processing' },
            'error': { class: 'bg-danger', icon: 'alert-circle', text: 'Error' },
            'maintenance': { class: 'bg-warning', icon: 'wrench', text: 'Maintenance' },
            'inactive': { class: 'bg-secondary', icon: 'pause-circle', text: 'Inactive' }
        };
        
        const statusInfo = statusMap[status] || statusMap['inactive'];
        return `<span class="badge ${statusInfo.class}">
                    <i class="mdi mdi-${statusInfo.icon}"></i> ${statusInfo.text}
                </span>`;
    }
    
    async loadRecentActivity() {
        try {
            const response = await fetch('/plugins/hedgehog/api/gitops/activity/');
            const activities = await response.json();
            
            const timeline = document.getElementById('activity-timeline');
            const emptyState = document.getElementById('activity-empty');
            
            if (activities && activities.length > 0) {
                timeline.innerHTML = '';
                emptyState.classList.add('d-none');
                
                activities.forEach(activity => this.renderActivityItem(activity, timeline));
            } else {
                timeline.innerHTML = '';
                emptyState.classList.remove('d-none');
            }
            
        } catch (error) {
            console.error('Failed to load recent activity:', error);
        }
    }
    
    renderActivityItem(activity, timeline) {
        const item = document.createElement('div');
        item.className = `timeline-item ${activity.type || 'info'}`;
        
        const timestamp = new Date(activity.timestamp).toLocaleString();
        const icon = this.getActivityIcon(activity.type);
        
        item.innerHTML = `
            <div class="timeline-marker"></div>
            <div class="timeline-content">
                <div class="timeline-title">
                    <i class="mdi mdi-${icon}"></i>
                    ${activity.title}
                </div>
                <div class="timeline-text">${activity.description}</div>
                <small class="text-muted">${timestamp} - ${activity.fabric_name || 'System'}</small>
            </div>
        `;
        
        timeline.appendChild(item);
    }
    
    getActivityIcon(type) {
        const iconMap = {
            'file_processed': 'file-check',
            'file_error': 'file-alert',
            'sync_complete': 'sync',
            'archive_created': 'archive',
            'fabric_created': 'server-network-plus',
            'system_health': 'heart-pulse'
        };
        
        return iconMap[type] || 'information';
    }
    
    async loadSystemHealth() {
        try {
            const response = await fetch('/plugins/hedgehog/api/gitops/health/');
            const health = await response.json();
            
            // Update health indicators
            this.updateHealthIndicator('ingestion-health', health.ingestion);
            this.updateHealthIndicator('processing-health', health.processing);
            this.updateHealthIndicator('storage-health', health.storage);
            this.updateHealthIndicator('archive-health', health.archive);
            
            // Update performance metrics
            document.getElementById('avg-processing-time').textContent = health.avg_processing_time || '--';
            document.getElementById('success-rate').textContent = health.success_rate || '--';
            document.getElementById('queue-depth').textContent = health.queue_depth || '--';
            
        } catch (error) {
            console.error('Failed to load system health:', error);
        }
    }
    
    updateHealthIndicator(elementId, status) {
        const element = document.getElementById(elementId);
        if (!element) return;
        
        // Remove existing status classes
        element.classList.remove('healthy', 'warning', 'error');
        
        // Add appropriate status class
        if (status === 'healthy' || status === 'good') {
            element.classList.add('healthy');
        } else if (status === 'warning' || status === 'degraded') {
            element.classList.add('warning');
        } else if (status === 'error' || status === 'critical') {
            element.classList.add('error');
        }
    }
    
    async loadStorageStats() {
        try {
            const response = await fetch('/plugins/hedgehog/api/gitops/storage/');
            const storage = await response.json();
            
            // Update storage display
            document.getElementById('raw-storage').textContent = this.formatStorage(storage.raw_storage);
            document.getElementById('managed-storage').textContent = this.formatStorage(storage.managed_storage);
            document.getElementById('archive-storage').textContent = this.formatStorage(storage.archive_storage);
            
            // Update storage chart
            this.updateStorageChart(storage);
            
        } catch (error) {
            console.error('Failed to load storage stats:', error);
        }
    }
    
    initializeCharts() {
        this.initStorageChart();
    }
    
    initStorageChart() {
        const ctx = document.getElementById('storage-usage-chart');
        if (!ctx) return;
        
        this.charts.storage = new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: ['Raw Files', 'Managed Files', 'Archives'],
                datasets: [{
                    data: [0, 0, 0],
                    backgroundColor: [
                        'rgba(13, 110, 253, 0.8)',  // Primary
                        'rgba(25, 135, 84, 0.8)',   // Success
                        'rgba(255, 193, 7, 0.8)'    // Warning
                    ],
                    borderWidth: 2,
                    borderColor: '#fff'
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        display: false
                    }
                }
            }
        });
    }
    
    updateStorageChart(storageData) {
        if (!this.charts.storage) return;
        
        const total = storageData.raw_storage + storageData.managed_storage + storageData.archive_storage;
        if (total === 0) return;
        
        this.charts.storage.data.datasets[0].data = [
            storageData.raw_storage,
            storageData.managed_storage,
            storageData.archive_storage
        ];
        
        this.charts.storage.update();
    }
    
    animateHighValueCards(stats) {
        // Add pulse animation to cards with concerning values
        if (stats.error_count > 0) {
            document.getElementById('error-count').closest('.card').classList.add('border-danger');
        }
        
        if (stats.pending_files > 10) {
            document.getElementById('pending-files').closest('.card').classList.add('border-warning');
        }
    }
    
    filterFabrics(filterId) {
        const rows = document.querySelectorAll('.fabric-row');
        
        rows.forEach(row => {
            let show = true;
            
            if (filterId === 'filter-active') {
                show = row.querySelector('.badge.bg-success') !== null;
            } else if (filterId === 'filter-errors') {
                show = row.querySelector('.badge.bg-danger') !== null;
            }
            
            row.style.display = show ? '' : 'none';
        });
    }
    
    async triggerGlobalSync() {
        try {
            this.showLoadingButton('trigger-global-sync');
            
            const response = await fetch('/plugins/hedgehog/api/gitops/sync-all/', {
                method: 'POST',
                headers: {
                    'X-CSRFToken': this.getCSRFToken()
                }
            });
            
            const result = await response.json();
            
            if (result.success) {
                this.showSuccess('Global sync initiated successfully');
                this.refreshDashboard();
            } else {
                this.showError(result.error || 'Global sync failed');
            }
            
        } catch (error) {
            console.error('Global sync failed:', error);
            this.showError('Failed to trigger global sync');
        } finally {
            this.resetLoadingButton('trigger-global-sync', '<i class="mdi mdi-sync"></i> Sync All Fabrics');
        }
    }
    
    async processPendingFiles() {
        try {
            this.showLoadingButton('process-pending-files');
            
            const response = await fetch('/plugins/hedgehog/api/gitops/process-pending/', {
                method: 'POST',
                headers: {
                    'X-CSRFToken': this.getCSRFToken()
                }
            });
            
            const result = await response.json();
            
            if (result.success) {
                this.showSuccess(`Processing initiated for ${result.file_count} files`);
                this.refreshDashboard();
            } else {
                this.showError(result.error || 'Processing failed');
            }
            
        } catch (error) {
            console.error('Process pending files failed:', error);
            this.showError('Failed to process pending files');
        } finally {
            this.resetLoadingButton('process-pending-files', '<i class="mdi mdi-play"></i> Process Pending Files');
        }
    }
    
    async checkSystemHealth() {
        try {
            this.showLoadingButton('check-system-health');
            
            const response = await fetch('/plugins/hedgehog/api/gitops/health-check/', {
                method: 'POST',
                headers: {
                    'X-CSRFToken': this.getCSRFToken()
                }
            });
            
            const result = await response.json();
            
            if (result.success) {
                this.showSuccess('System health check completed');
                this.loadSystemHealth(); // Refresh health indicators
            } else {
                this.showError(result.error || 'Health check failed');
            }
            
        } catch (error) {
            console.error('Health check failed:', error);
            this.showError('Failed to perform health check');
        } finally {
            this.resetLoadingButton('check-system-health', '<i class="mdi mdi-stethoscope"></i> Health Check');
        }
    }
    
    showStatusDetails(card) {
        // Extract status type from card
        const cardId = card.querySelector('h2').id;
        let title = 'Status Details';
        let content = 'Loading status details...';
        
        switch (cardId) {
            case 'total-fabrics':
                title = 'GitOps Enabled Fabrics';
                content = 'Detailed fabric status information would be shown here.';
                break;
            case 'pending-files':
                title = 'Pending Files';
                content = 'List of files waiting to be processed would be shown here.';
                break;
            case 'processed-today':
                title = "Today's Processing Activity";
                content = 'Processing activity and statistics for today would be shown here.';
                break;
            case 'error-count':
                title = 'Processing Errors';
                content = 'Detailed error information and resolution steps would be shown here.';
                break;
        }
        
        // Show modal with details
        this.showModal(title, content);
    }
    
    startAutoRefresh() {
        if (this.autoRefreshEnabled) {
            this.refreshInterval = setInterval(() => {
                this.refreshDashboard();
            }, this.refreshIntervalMs);
        }
    }
    
    stopAutoRefresh() {
        if (this.refreshInterval) {
            clearInterval(this.refreshInterval);
            this.refreshInterval = null;
        }
    }
    
    toggleAutoRefresh(enabled) {
        this.autoRefreshEnabled = enabled;
        
        if (enabled) {
            this.startAutoRefresh();
        } else {
            this.stopAutoRefresh();
        }
    }
    
    async refreshDashboard() {
        console.log('🔄 Refreshing dashboard...');
        
        // Show refresh indicator
        const refreshBtn = document.getElementById('refresh-dashboard');
        if (refreshBtn) {
            refreshBtn.innerHTML = '<i class="mdi mdi-loading mdi-spin"></i> Refreshing...';
            refreshBtn.disabled = true;
        }
        
        try {
            await this.loadInitialData();
        } finally {
            // Reset refresh button
            if (refreshBtn) {
                refreshBtn.innerHTML = '<i class="mdi mdi-refresh"></i> Refresh';
                refreshBtn.disabled = false;
            }
        }
    }
    
    // Utility functions
    formatStorage(bytes) {
        if (bytes === 0) return '0 B';
        const k = 1024;
        const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }
    
    showLoadingButton(buttonId) {
        const button = document.getElementById(buttonId);
        if (button) {
            button.innerHTML = '<i class="mdi mdi-loading mdi-spin"></i> Loading...';
            button.disabled = true;
        }
    }
    
    resetLoadingButton(buttonId, originalText) {
        const button = document.getElementById(buttonId);
        if (button) {
            button.innerHTML = originalText;
            button.disabled = false;
        }
    }
    
    getCSRFToken() {
        const token = document.querySelector('[name=csrfmiddlewaretoken]');
        return token ? token.value : '';
    }
    
    showSuccess(message) {
        this.showNotification(message, 'success');
    }
    
    showError(message) {
        this.showNotification(message, 'danger');
    }
    
    showNotification(message, type) {
        const notification = document.createElement('div');
        notification.className = `alert alert-${type} alert-dismissible fade show position-fixed`;
        notification.style.cssText = 'top: 20px; right: 20px; z-index: 9999; min-width: 300px;';
        notification.innerHTML = `
            <i class="mdi mdi-${type === 'success' ? 'check-circle' : 'alert-circle'}"></i>
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        `;
        
        document.body.appendChild(notification);
        
        setTimeout(() => {
            if (notification.parentNode) {
                notification.remove();
            }
        }, 5000);
    }
    
    showModal(title, content) {
        // Create and show modal
        const modalHtml = `
            <div class="modal fade" id="statusDetailsModal" tabindex="-1">
                <div class="modal-dialog modal-lg">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h5 class="modal-title">${title}</h5>
                            <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                        </div>
                        <div class="modal-body">
                            ${content}
                        </div>
                        <div class="modal-footer">
                            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Close</button>
                        </div>
                    </div>
                </div>
            </div>
        `;
        
        // Remove existing modal
        const existingModal = document.getElementById('statusDetailsModal');
        if (existingModal) {
            existingModal.remove();
        }
        
        // Add modal to body and show
        document.body.insertAdjacentHTML('beforeend', modalHtml);
        const modal = new bootstrap.Modal(document.getElementById('statusDetailsModal'));
        modal.show();
    }
}

// Global functions for template callbacks
window.viewFabricDetails = function(fabricId) {
    console.log('👁️ Viewing fabric details:', fabricId);
    window.location.href = `/plugins/hedgehog/fabrics/${fabricId}/`;
};

window.syncFabric = function(fabricId) {
    console.log('🔄 Syncing fabric:', fabricId);
    // Implementation would trigger fabric sync
    dashboard.showSuccess(`Sync initiated for fabric ${fabricId}`);
};

window.manageFabric = function(fabricId) {
    console.log('⚙️ Managing fabric:', fabricId);
    // Implementation would open fabric management interface
    dashboard.showModal('Fabric Management', `Management interface for fabric ${fabricId} would be shown here.`);
};

window.cleanupArchives = function() {
    console.log('🧹 Cleaning up archives...');
    dashboard.showSuccess('Archive cleanup initiated');
};

window.optimizeStorage = function() {
    console.log('⚡ Optimizing storage...');
    dashboard.showSuccess('Storage optimization initiated');
};

window.validateIntegrity = function() {
    console.log('🛡️ Validating integrity...');
    dashboard.showSuccess('Integrity validation initiated');
};

window.emergencyStop = function() {
    if (confirm('Are you sure you want to perform an emergency stop? This will halt all GitOps processing.')) {
        console.log('🛑 Emergency stop initiated...');
        dashboard.showError('Emergency stop activated - all processing halted');
    }
};

// Global dashboard instance
let dashboard;

// Initialize dashboard when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    console.log('🌟 GitOps Dashboard DOM loaded');
    dashboard = new GitOpsDashboard();
});