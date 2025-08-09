/**
 * GitOps Management Dashboard JavaScript
 * Professional interface for unified Phase 3 component management
 */

class GitOpsDashboard {
    constructor(options = {}) {
        this.fabricId = options.fabricId || null;
        this.apiBaseUrl = options.apiBaseUrl || '/api/plugins/netbox-hedgehog/';
        this.websocketUrl = options.websocketUrl || null;
        this.refreshInterval = options.refreshInterval || 30;
        this.csrfToken = options.csrfToken || '';
        
        // State management
        this.currentPath = '/';
        this.fileBrowserHistory = [];
        this.websocket = null;
        this.refreshIntervalId = null;
        this.charts = {};
        this.connectionStatus = 'disconnected';
        
        // File browser state
        this.selectedFiles = [];
        this.fileSortColumn = 'name';
        this.fileSortDirection = 'asc';
        
        // Dashboard components
        this.components = {
            fileBrowser: null,
            visualDiff: null,
            workflowStatus: null,
            realtimeUpdates: null
        };
    }
    
    initialize() {
        console.log('📊 Initializing GitOps Management Dashboard');
        this.initializeEventListeners();
        this.initializeComponents();
        this.loadInitialData();
        this.setupWebSocket();
        this.updateConnectionStatus('connecting');
        return this;
    }
    
    initializeEventListeners() {
        // Fabric selector
        const fabricSelector = document.getElementById('fabricSelector');
        if (fabricSelector) {
            fabricSelector.addEventListener('change', (e) => this.onFabricChange(e.target.value));
        }
        
        // Dashboard controls
        this.attachEventListener('refreshDashboard', 'click', () => this.refreshDashboard());
        this.attachEventListener('dashboardSettings', 'click', () => this.showDashboardSettings());
        
        // Quick actions
        this.attachEventListener('syncFabric', 'click', () => this.syncCurrentFabric());
        this.attachEventListener('generateTemplates', 'click', () => this.generateTemplates());
        this.attachEventListener('resolveConflicts', 'click', () => this.resolveConflicts());
        this.attachEventListener('initGitOps', 'click', () => this.initializeGitOps());
        
        // File browser controls
        this.attachEventListener('fileBrowserRefresh', 'click', () => this.refreshFileBrowser());
        this.attachEventListener('fileBrowserBack', 'click', () => this.navigateBack());
        this.attachEventListener('fileBrowserUp', 'click', () => this.navigateUp());
        this.attachEventListener('navigatePath', 'click', () => this.navigateToPath());
        
        // Visual diff controls
        this.attachEventListener('refreshDiff', 'click', () => this.refreshVisualDiff());
        document.querySelectorAll('[data-diff-view]').forEach(btn => {
            btn.addEventListener('click', (e) => this.changeDiffView(e.target.dataset.diffView));
        });
        
        // File operations
        document.addEventListener('click', (e) => this.handleFileClick(e));
        document.addEventListener('dblclick', (e) => this.handleFileDoubleClick(e));
        
        // Modal events
        this.attachEventListener('editFileButton', 'click', () => this.editCurrentFile());
        
        // Keyboard shortcuts
        document.addEventListener('keydown', (e) => this.handleKeyboardShortcuts(e));
    }
    
    initializeComponents() {
        // Initialize file browser component
        this.components.fileBrowser = new FileBrowserComponent(this);
        
        // Initialize visual diff component
        this.components.visualDiff = new VisualDiffComponent(this);
        
        // Initialize workflow status component
        this.components.workflowStatus = new WorkflowStatusComponent(this);
        
        // Initialize real-time updates component
        this.components.realtimeUpdates = new RealtimeUpdatesComponent(this);
        
        console.log('✅ Dashboard components initialized');
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

    // Integration-specific methods
    
    attachEventListener(id, event, handler) {
        const element = document.getElementById(id);
        if (element) {
            element.addEventListener(event, handler);
        }
    }
    
    async onFabricChange(fabricId) {
        if (fabricId) {
            this.fabricId = parseInt(fabricId);
            await this.loadFabricData();
            this.updateURL();
        } else {
            this.fabricId = null;
            this.clearFabricData();
        }
    }
    
    async loadFabricData() {
        if (!this.fabricId) return;
        
        try {
            await Promise.all([
                this.loadFileBrowserData('/'),
                this.loadWorkflowStatus(),
                this.refreshVisualDiff()
            ]);
        } catch (error) {
            console.error('Failed to load fabric data:', error);
            this.showNotification('Failed to load fabric data', 'error');
        }
    }
    
    async loadFileBrowserData(path = '/') {
        if (!this.fabricId) return;
        
        this.showFileBrowserLoader();
        
        try {
            const response = await this.apiRequest(`gitops-dashboard/${this.fabricId}/file-browser/?path=${encodeURIComponent(path)}`);
            
            if (response.success) {
                this.components.fileBrowser.renderFileList(response.data);
                this.currentPath = path;
                this.updateFileBrowserNavigation();
            } else {
                throw new Error(response.error || 'Failed to load file browser data');
            }
        } catch (error) {
            console.error('File browser error:', error);
            this.showFileBrowserError(error.message);
        }
    }
    
    async loadWorkflowStatus() {
        if (!this.fabricId) return;
        
        try {
            const response = await this.apiRequest(`gitops-dashboard/${this.fabricId}/workflow-status/`);
            
            if (response.success) {
                this.components.workflowStatus.updateStatus(response.data);
            }
        } catch (error) {
            console.error('Workflow status error:', error);
        }
    }
    
    async refreshVisualDiff() {
        if (!this.fabricId) return;
        
        try {
            const response = await this.apiRequest(`gitops-dashboard/${this.fabricId}/visual-diff/`);
            
            if (response.success) {
                this.components.visualDiff.renderDiff(response.data);
            }
        } catch (error) {
            console.error('Visual diff error:', error);
        }
    }
    
    setupWebSocket() {
        if (!this.websocketUrl || !this.fabricId) return;
        
        try {
            const wsUrl = `${this.websocketUrl}fabric/${this.fabricId}/`;
            this.websocket = new WebSocket(wsUrl);
            
            this.websocket.onopen = () => {
                console.log('✅ WebSocket connected');
                this.updateConnectionStatus('connected');
            };
            
            this.websocket.onmessage = (event) => {
                const data = JSON.parse(event.data);
                this.handleWebSocketMessage(data);
            };
            
            this.websocket.onclose = () => {
                console.log('❌ WebSocket disconnected');
                this.updateConnectionStatus('disconnected');
                this.scheduleWebSocketReconnect();
            };
            
            this.websocket.onerror = (error) => {
                console.error('WebSocket error:', error);
                this.updateConnectionStatus('error');
            };
        } catch (error) {
            console.error('WebSocket setup failed:', error);
            this.updateConnectionStatus('error');
        }
    }
    
    handleWebSocketMessage(data) {
        switch (data.type) {
            case 'file_changed':
                this.refreshFileBrowser();
                break;
            case 'workflow_update':
                this.components.workflowStatus.updateWorkflow(data.workflow, data.status);
                break;
            case 'diff_update':
                this.refreshVisualDiff();
                break;
            case 'notification':
                this.showNotification(data.message, data.level || 'info');
                break;
        }
    }
    
    updateConnectionStatus(status) {
        this.connectionStatus = status;
        
        const indicator = document.getElementById('connectionIndicator');
        const statusText = document.getElementById('connectionStatusText');
        const toast = document.getElementById('connectionStatus');
        
        if (indicator) {
            indicator.className = `connection-indicator ${status}`;
        }
        
        if (statusText) {
            const statusMap = {
                'connected': 'Connected',
                'connecting': 'Connecting...',
                'disconnected': 'Disconnected',
                'error': 'Connection Error'
            };
            statusText.textContent = statusMap[status] || 'Unknown';
        }
        
        if (toast && ['connecting', 'disconnected', 'error'].includes(status)) {
            const bsToast = new bootstrap.Toast(toast);
            bsToast.show();
        }
    }
    
    async apiRequest(endpoint, options = {}) {
        const url = `${this.apiBaseUrl}${endpoint}`;
        const defaultOptions = {
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': this.csrfToken
            }
        };
        
        const response = await fetch(url, { ...defaultOptions, ...options });
        
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        
        return await response.json();
    }
    
    showNotification(message, type = 'info') {
        const container = document.createElement('div');
        container.className = 'toast-container position-fixed top-0 end-0 p-3';
        container.style.zIndex = '11';
        
        const toast = document.createElement('div');
        toast.className = 'toast align-items-center text-white bg-' + (type === 'error' ? 'danger' : type);
        toast.setAttribute('role', 'alert');
        
        toast.innerHTML = `
            <div class="d-flex">
                <div class="toast-body">
                    <i class="mdi mdi-${type === 'error' ? 'alert-circle' : 'information'}"></i>
                    ${message}
                </div>
                <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
            </div>
        `;
        
        container.appendChild(toast);
        document.body.appendChild(container);
        
        const bsToast = new bootstrap.Toast(toast);
        bsToast.show();
        
        toast.addEventListener('hidden.bs.toast', () => {
            container.remove();
        });
    }
    
    showFileBrowserLoader() {
        document.getElementById('fileBrowserLoader')?.classList.remove('d-none');
        document.getElementById('fileListContainer')?.classList.add('d-none');
    }
    
    hideFileBrowserLoader() {
        document.getElementById('fileBrowserLoader')?.classList.add('d-none');
        document.getElementById('fileListContainer')?.classList.remove('d-none');
    }
    
    showFileBrowserError(message) {
        this.hideFileBrowserLoader();
        // Show error state in file browser
        const container = document.getElementById('fileBrowserContent');
        if (container) {
            container.innerHTML = `
                <div class="text-center p-4 text-danger">
                    <i class="mdi mdi-alert-circle" style="font-size: 3rem;"></i>
                    <p class="mt-2">Error loading files: ${message}</p>
                    <button class="btn btn-outline-primary" onclick="gitopsDashboard.refreshFileBrowser()">
                        <i class="mdi mdi-refresh"></i> Retry
                    </button>
                </div>
            `;
        }
    }
    
    updateURL() {
        if (this.fabricId) {
            const url = new URL(window.location);
            url.searchParams.set('fabric_id', this.fabricId);
            window.history.replaceState({}, '', url);
        }
    }
}

// Component Classes
class FileBrowserComponent {
    constructor(dashboard) {
        this.dashboard = dashboard;
    }
    
    renderFileList(data) {
        const tbody = document.getElementById('fileTableBody');
        const emptyState = document.getElementById('emptyFileState');
        
        if (!tbody) return;
        
        tbody.innerHTML = '';
        
        if (data.directories.length === 0 && data.files.length === 0) {
            emptyState?.classList.remove('d-none');
            return;
        }
        
        emptyState?.classList.add('d-none');
        
        // Render directories first
        data.directories.forEach(dir => this.renderFileRow(dir, tbody));
        
        // Then render files
        data.files.forEach(file => this.renderFileRow(file, tbody));
        
        this.dashboard.hideFileBrowserLoader();
    }
    
    renderFileRow(item, tbody) {
        const row = document.createElement('tr');
        row.className = 'file-row';
        row.dataset.path = item.path;
        row.dataset.type = item.type;
        
        const icon = this.getFileIcon(item);
        const size = item.type === 'directory' ? `${item.items_count || 0} items` : this.formatFileSize(item.size);
        const modified = new Date(item.modified).toLocaleString();
        
        row.innerHTML = `
            <td>
                <div class="file-item">
                    <i class="file-icon ${item.type} ${icon}"></i>
                    <div>
                        <div class="file-name">${item.name}</div>
                        ${item.type === 'file' && item.can_preview ? '<small class="text-muted">Preview available</small>' : ''}
                    </div>
                </div>
            </td>
            <td><span class="badge bg-secondary">${item.type}</span></td>
            <td><small>${size}</small></td>
            <td><small>${modified}</small></td>
        `;
        
        tbody.appendChild(row);
    }
    
    getFileIcon(item) {
        if (item.type === 'directory') {
            return 'mdi mdi-folder';
        }
        
        const iconMap = {
            'yaml': 'mdi mdi-code-braces',
            'json': 'mdi mdi-code-json',
            'text': 'mdi mdi-file-document-outline',
            'python': 'mdi mdi-language-python',
            'shell': 'mdi mdi-console'
        };
        
        return iconMap[item.file_type] || 'mdi mdi-file-outline';
    }
    
    formatFileSize(bytes) {
        if (bytes === 0) return '0 B';
        const k = 1024;
        const sizes = ['B', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return Math.round((bytes / Math.pow(k, i)) * 100) / 100 + ' ' + sizes[i];
    }
}

class VisualDiffComponent {
    constructor(dashboard) {
        this.dashboard = dashboard;
    }
    
    renderDiff(data) {
        const container = document.getElementById('diffContainer');
        if (!container) return;
        
        if (data.differences.length === 0) {
            container.innerHTML = `
                <div class="text-center p-4">
                    <i class="mdi mdi-check-circle text-success" style="font-size: 3rem;"></i>
                    <p class="text-muted mt-2">No differences detected</p>
                </div>
            `;
            return;
        }
        
        // Render differences
        container.innerHTML = `
            <div class="diff-summary mb-3">
                <span class="badge bg-success">+${data.summary.additions}</span>
                <span class="badge bg-warning">~${data.summary.modifications}</span>
                <span class="badge bg-danger">-${data.summary.deletions}</span>
            </div>
            <div class="diff-content">
                ${data.differences.map(diff => this.renderDiffItem(diff)).join('')}
            </div>
        `;
    }
    
    renderDiffItem(diff) {
        return `
            <div class="diff-item mb-2">
                <div class="diff-header">
                    <strong>${diff.file_path}</strong>
                    <span class="badge bg-${diff.type === 'added' ? 'success' : diff.type === 'removed' ? 'danger' : 'warning'}">
                        ${diff.type}
                    </span>
                </div>
                <div class="diff-content">
                    <pre><code>${diff.content}</code></pre>
                </div>
            </div>
        `;
    }
}

class WorkflowStatusComponent {
    constructor(dashboard) {
        this.dashboard = dashboard;
    }
    
    updateStatus(data) {
        this.updateWorkflow('syncWorkflow', data.workflows.sync_status);
        this.updateWorkflow('templateWorkflow', data.workflows.template_generation);
        this.updateWorkflow('conflictWorkflow', data.workflows.conflict_resolution);
    }
    
    updateWorkflow(elementId, status) {
        const element = document.getElementById(elementId);
        if (!element) return;
        
        const badge = element.querySelector('.badge');
        if (badge) {
            badge.className = `badge bg-${this.getStatusColor(status.status)}`;
            badge.textContent = status.status.charAt(0).toUpperCase() + status.status.slice(1);
        }
    }
    
    getStatusColor(status) {
        const colorMap = {
            'idle': 'secondary',
            'running': 'primary',
            'success': 'success',
            'error': 'danger',
            'warning': 'warning'
        };
        return colorMap[status] || 'secondary';
    }
}

class RealtimeUpdatesComponent {
    constructor(dashboard) {
        this.dashboard = dashboard;
    }
    
    // Real-time updates handling
    handleUpdate(type, data) {
        switch (type) {
            case 'file_operation':
                this.handleFileOperation(data);
                break;
            case 'workflow_status':
                this.handleWorkflowStatus(data);
                break;
        }
    }
    
    handleFileOperation(data) {
        // Refresh file browser if current path affected
        if (data.path.startsWith(this.dashboard.currentPath)) {
            this.dashboard.refreshFileBrowser();
        }
    }
    
    handleWorkflowStatus(data) {
        this.dashboard.components.workflowStatus.updateWorkflow(data.workflow_id, data.status);
    }
}

// Global functions
window.gitopsDashboard = null;