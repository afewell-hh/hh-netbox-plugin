/**
 * Raw Directory Monitor JavaScript
 * Handles real-time monitoring of raw files and processing queue
 */

class RawDirectoryMonitor {
    constructor() {
        this.autoRefreshEnabled = true;
        this.refreshInterval = null;
        this.refreshIntervalMs = 5000; // 5 seconds for real-time monitoring
        this.selectedFiles = new Set();
        this.processingLog = [];
        
        this.init();
    }
    
    init() {
        console.log('📁 Initializing Raw Directory Monitor');
        this.attachEventListeners();
        this.loadInitialData();
        this.startAutoRefresh();
    }
    
    attachEventListeners() {
        // Refresh controls
        document.getElementById('refresh-monitor')?.addEventListener('click', () => this.refreshMonitor());
        document.getElementById('toggle-auto-refresh')?.addEventListener('click', () => this.toggleAutoRefresh());
        document.getElementById('process-all-files')?.addEventListener('click', () => this.processAllFiles());
        
        // File filtering
        document.querySelectorAll('input[name="file-filter"]').forEach(radio => {
            radio.addEventListener('change', () => this.filterFiles(radio.id));
        });
        
        // File selection
        document.getElementById('select-all-files')?.addEventListener('change', (e) => this.selectAllFiles(e.target.checked));
        
        // File upload
        document.getElementById('upload-files-btn')?.addEventListener('click', () => this.uploadFiles());
        
        // Log controls
        document.querySelectorAll('[onclick="clearLog()"]').forEach(btn => {
            btn.onclick = () => this.clearLog();
        });
        document.querySelectorAll('[onclick="exportLog()"]').forEach(btn => {
            btn.onclick = () => this.exportLog();
        });
    }
    
    async loadInitialData() {
        try {
            console.log('📥 Loading initial monitor data...');
            await Promise.all([
                this.loadStatusCounts(),
                this.loadFilesList(),
                this.loadProcessingQueue(),
                this.loadFabrics()
            ]);
            console.log('✅ Initial monitor data loaded');
        } catch (error) {
            console.error('❌ Failed to load initial data:', error);
            this.showError('Failed to load monitor data');
        }
    }
    
    async loadStatusCounts() {
        try {
            const response = await fetch('/plugins/hedgehog/api/gitops/raw-status/');
            const stats = await response.json();
            
            // Update status cards
            document.getElementById('pending-count').textContent = stats.pending || 0;
            document.getElementById('processing-count').textContent = stats.processing || 0;
            document.getElementById('completed-count').textContent = stats.completed_today || 0;
            document.getElementById('error-count').textContent = stats.errors || 0;
            
        } catch (error) {
            console.error('Failed to load status counts:', error);
        }
    }
    
    async loadFilesList() {
        try {
            const response = await fetch('/plugins/hedgehog/api/gitops/raw-files/');
            const files = await response.json();
            
            const tbody = document.getElementById('files-tbody');
            const emptyState = document.getElementById('files-empty');
            
            if (files && files.length > 0) {
                tbody.innerHTML = '';
                emptyState.classList.add('d-none');
                
                files.forEach(file => this.renderFileRow(file, tbody));
                this.updatePaginationInfo(files.length);
            } else {
                tbody.innerHTML = '';
                emptyState.classList.remove('d-none');
                this.updatePaginationInfo(0);
            }
            
        } catch (error) {
            console.error('Failed to load files list:', error);
        }
    }
    
    renderFileRow(file, tbody) {
        const row = document.createElement('tr');
        row.className = 'file-row';
        row.dataset.fileId = file.id;
        row.dataset.status = file.status;
        
        const statusBadge = this.getFileStatusBadge(file.status);
        const addedDate = file.added_date ? new Date(file.added_date).toLocaleString() : 'Unknown';
        
        row.innerHTML = `
            <td>
                <div class="form-check">
                    <input class="form-check-input file-checkbox" 
                           type="checkbox" 
                           value="${file.id}"
                           onchange="monitor.handleFileSelection(this)">
                </div>
            </td>
            <td>
                <div class="d-flex align-items-center">
                    <i class="mdi mdi-file-document-outline text-primary me-2"></i>
                    <div>
                        <div class="fw-bold">${file.name}</div>
                        <small class="text-muted">${file.path || ''}</small>
                    </div>
                </div>
            </td>
            <td>${statusBadge}</td>
            <td>${this.formatFileSize(file.size || 0)}</td>
            <td><small>${addedDate}</small></td>
            <td>
                <span class="badge bg-info">${file.fabric_name || 'Unknown'}</span>
            </td>
            <td>
                <div class="btn-group btn-group-sm" role="group">
                    <button class="btn btn-outline-primary" onclick="monitor.viewFileDetails('${file.id}')" title="View Details">
                        <i class="mdi mdi-eye"></i>
                    </button>
                    <button class="btn btn-outline-success" onclick="monitor.processFile('${file.id}')" title="Process">
                        <i class="mdi mdi-play"></i>
                    </button>
                    <button class="btn btn-outline-danger" onclick="monitor.deleteFile('${file.id}')" title="Delete">
                        <i class="mdi mdi-delete"></i>
                    </button>
                </div>
            </td>
        `;
        
        tbody.appendChild(row);
    }
    
    getFileStatusBadge(status) {
        const statusMap = {
            'pending': { class: 'bg-warning', icon: 'clock', text: 'Pending' },
            'processing': { class: 'bg-info', icon: 'cog', text: 'Processing', spinner: true },
            'completed': { class: 'bg-success', icon: 'check', text: 'Completed' },
            'error': { class: 'bg-danger', icon: 'alert-circle', text: 'Error' },
            'archived': { class: 'bg-secondary', icon: 'archive', text: 'Archived' }
        };
        
        const statusInfo = statusMap[status] || statusMap['pending'];
        const spinner = statusInfo.spinner ? '<div class="spinner"></div>' : '';
        
        return `<span class="file-status ${status}">
                    <span class="badge ${statusInfo.class}">
                        <i class="mdi mdi-${statusInfo.icon}"></i> ${statusInfo.text}
                    </span>
                    ${spinner}
                </span>`;
    }
    
    async loadProcessingQueue() {
        try {
            const response = await fetch('/plugins/hedgehog/api/gitops/processing-queue/');
            const queue = await response.json();
            
            const queueItems = document.getElementById('queue-items');
            const queueEmpty = document.getElementById('queue-empty');
            const queueStatus = document.getElementById('queue-status');
            const queueProgress = document.getElementById('queue-progress');
            const currentProcessing = document.getElementById('current-processing');
            const queueTotal = document.getElementById('queue-total');
            
            if (queue && queue.items && queue.items.length > 0) {
                queueItems.innerHTML = '';
                queueEmpty.classList.add('d-none');
                
                queue.items.forEach((item, index) => {
                    this.renderQueueItem(item, index, queueItems);
                });
                
                // Update queue status
                queueStatus.textContent = queue.status || 'Active';
                queueStatus.className = `badge bg-${queue.status === 'active' ? 'success' : 'secondary'}`;
                
                // Update progress
                const progress = queue.total > 0 ? ((queue.processed / queue.total) * 100) : 0;
                queueProgress.style.width = `${progress}%`;
                currentProcessing.textContent = queue.processed || 0;
                queueTotal.textContent = queue.total || 0;
                
            } else {
                queueItems.innerHTML = '';
                queueEmpty.classList.remove('d-none');
                queueProgress.style.width = '0%';
                currentProcessing.textContent = '0';
                queueTotal.textContent = '0';
            }
            
        } catch (error) {
            console.error('Failed to load processing queue:', error);
        }
    }
    
    renderQueueItem(item, position, container) {
        const queueItem = document.createElement('div');
        queueItem.className = 'queue-item';
        queueItem.dataset.fileId = item.file_id;
        
        const isProcessing = position === 0; // First item is currently processing
        const spinner = isProcessing ? '<div class="processing-spinner"></div>' : '';
        
        queueItem.innerHTML = `
            <div class="queue-position">#${position + 1}</div>
            <div class="file-name" title="${item.file_name}">${item.file_name}</div>
            ${spinner}
        `;
        
        container.appendChild(queueItem);
    }
    
    async loadFabrics() {
        try {
            const response = await fetch('/plugins/hedgehog/api/fabrics/');
            const fabrics = await response.json();
            
            const fabricSelect = document.getElementById('fabric-select');
            if (fabricSelect) {
                fabricSelect.innerHTML = '<option value="">Select a fabric...</option>';
                fabrics.forEach(fabric => {
                    const option = document.createElement('option');
                    option.value = fabric.id;
                    option.textContent = fabric.name;
                    fabricSelect.appendChild(option);
                });
            }
            
        } catch (error) {
            console.error('Failed to load fabrics:', error);
        }
    }
    
    filterFiles(filterId) {
        const rows = document.querySelectorAll('.file-row');
        
        rows.forEach(row => {
            let show = true;
            const status = row.dataset.status;
            
            if (filterId === 'filter-pending') {
                show = status === 'pending';
            } else if (filterId === 'filter-processing') {
                show = status === 'processing';
            } else if (filterId === 'filter-errors') {
                show = status === 'error';
            }
            
            row.style.display = show ? '' : 'none';
        });
    }
    
    selectAllFiles(checked) {
        const checkboxes = document.querySelectorAll('.file-checkbox');
        checkboxes.forEach(checkbox => {
            checkbox.checked = checked;
            this.handleFileSelection(checkbox);
        });
    }
    
    handleFileSelection(checkbox) {
        const fileId = checkbox.value;
        
        if (checkbox.checked) {
            this.selectedFiles.add(fileId);
        } else {
            this.selectedFiles.delete(fileId);
        }
        
        this.updateBulkActions();
    }
    
    updateBulkActions() {
        const bulkActions = document.getElementById('bulk-actions');
        const selectedCount = document.getElementById('selected-count');
        
        if (this.selectedFiles.size > 0) {
            bulkActions.classList.remove('d-none');
            selectedCount.textContent = this.selectedFiles.size;
        } else {
            bulkActions.classList.add('d-none');
        }
    }
    
    updatePaginationInfo(totalFiles) {
        document.getElementById('showing-start').textContent = totalFiles > 0 ? '1' : '0';
        document.getElementById('showing-end').textContent = totalFiles.toString();
        document.getElementById('total-files').textContent = totalFiles.toString();
    }
    
    async processAllFiles() {
        if (!confirm('Are you sure you want to process all pending files?')) {
            return;
        }
        
        try {
            this.showLoadingButton('process-all-files');
            
            const response = await fetch('/plugins/hedgehog/api/gitops/process-all/', {
                method: 'POST',
                headers: {
                    'X-CSRFToken': this.getCSRFToken()
                }
            });
            
            const result = await response.json();
            
            if (result.success) {
                this.showSuccess(`Processing initiated for ${result.file_count} files`);
                this.addLogEntry('info', `Bulk processing started for ${result.file_count} files`);
                this.refreshMonitor();
            } else {
                this.showError(result.error || 'Processing failed');
            }
            
        } catch (error) {
            console.error('Process all files failed:', error);
            this.showError('Failed to process files');
        } finally {
            this.resetLoadingButton('process-all-files', '<i class="mdi mdi-play"></i> Process All');
        }
    }
    
    async processFile(fileId) {
        try {
            const response = await fetch(`/plugins/hedgehog/api/gitops/process-file/${fileId}/`, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': this.getCSRFToken()
                }
            });
            
            const result = await response.json();
            
            if (result.success) {
                this.showSuccess('File processing initiated');
                this.addLogEntry('info', `Processing started for file: ${result.filename}`);
                this.refreshMonitor();
            } else {
                this.showError(result.error || 'Processing failed');
                this.addLogEntry('error', `Processing failed for file: ${result.filename}`);
            }
            
        } catch (error) {
            console.error('Process file failed:', error);
            this.showError('Failed to process file');
        }
    }
    
    async deleteFile(fileId) {
        if (!confirm('Are you sure you want to delete this file? This action cannot be undone.')) {
            return;
        }
        
        try {
            const response = await fetch(`/plugins/hedgehog/api/gitops/delete-file/${fileId}/`, {
                method: 'DELETE',
                headers: {
                    'X-CSRFToken': this.getCSRFToken()
                }
            });
            
            const result = await response.json();
            
            if (result.success) {
                this.showSuccess('File deleted successfully');
                this.addLogEntry('warning', `File deleted: ${result.filename}`);
                this.refreshMonitor();
            } else {
                this.showError(result.error || 'Delete failed');
            }
            
        } catch (error) {
            console.error('Delete file failed:', error);
            this.showError('Failed to delete file');
        }
    }
    
    viewFileDetails(fileId) {
        console.log('👁️ Viewing file details:', fileId);
        // Load file details and show modal
        this.loadFileDetails(fileId);
    }
    
    async loadFileDetails(fileId) {
        try {
            const response = await fetch(`/plugins/hedgehog/api/gitops/file-details/${fileId}/`);
            const details = await response.json();
            
            const modalBody = document.getElementById('file-details-body');
            if (modalBody) {
                modalBody.innerHTML = `
                    <div class="row">
                        <div class="col-md-6">
                            <h6>File Information</h6>
                            <table class="table table-sm table-borderless">
                                <tr><th>Name:</th><td>${details.name}</td></tr>
                                <tr><th>Size:</th><td>${this.formatFileSize(details.size)}</td></tr>
                                <tr><th>Status:</th><td>${this.getFileStatusBadge(details.status)}</td></tr>
                                <tr><th>Added:</th><td>${new Date(details.added_date).toLocaleString()}</td></tr>
                                <tr><th>Fabric:</th><td>${details.fabric_name}</td></tr>
                            </table>
                        </div>
                        <div class="col-md-6">
                            <h6>Processing Information</h6>
                            <table class="table table-sm table-borderless">
                                <tr><th>Resources:</th><td>${details.resource_count || 0}</td></tr>
                                <tr><th>Validation:</th><td>${details.is_valid ? 'Valid' : 'Invalid'}</td></tr>
                                <tr><th>Last Processed:</th><td>${details.last_processed || 'Never'}</td></tr>
                                <tr><th>Error Count:</th><td>${details.error_count || 0}</td></tr>
                            </table>
                        </div>
                    </div>
                    ${details.content ? `
                        <div class="mt-3">
                            <h6>File Preview</h6>
                            <pre class="bg-light p-3 rounded" style="max-height: 300px; overflow-y: auto;">${details.content}</pre>
                        </div>
                    ` : ''}
                `;
                
                // Show modal
                const modal = new bootstrap.Modal(document.getElementById('fileDetailsModal'));
                modal.show();
            }
            
        } catch (error) {
            console.error('Failed to load file details:', error);
            this.showError('Failed to load file details');
        }
    }
    
    async uploadFiles() {
        const fileInput = document.getElementById('file-input');
        const fabricSelect = document.getElementById('fabric-select');
        const autoProcess = document.getElementById('auto-process');
        
        if (!fileInput.files.length) {
            this.showError('Please select files to upload');
            return;
        }
        
        if (!fabricSelect.value) {
            this.showError('Please select a target fabric');
            return;
        }
        
        try {
            this.showLoadingButton('upload-files-btn');
            
            const formData = new FormData();
            formData.append('fabric_id', fabricSelect.value);
            formData.append('auto_process', autoProcess.checked);
            
            for (let i = 0; i < fileInput.files.length; i++) {
                formData.append('files', fileInput.files[i]);
            }
            
            const response = await fetch('/plugins/hedgehog/api/gitops/upload-files/', {
                method: 'POST',
                headers: {
                    'X-CSRFToken': this.getCSRFToken()
                },
                body: formData
            });
            
            const result = await response.json();
            
            if (result.success) {
                this.showSuccess(`${result.uploaded_count} files uploaded successfully`);
                this.addLogEntry('success', `Uploaded ${result.uploaded_count} files`);
                
                // Close modal and refresh
                const modal = bootstrap.Modal.getInstance(document.getElementById('fileUploadModal'));
                modal.hide();
                this.refreshMonitor();
            } else {
                this.showError(result.error || 'Upload failed');
            }
            
        } catch (error) {
            console.error('File upload failed:', error);
            this.showError('Failed to upload files');
        } finally {
            this.resetLoadingButton('upload-files-btn', '<i class="mdi mdi-upload"></i> Upload');
        }
    }
    
    addLogEntry(level, message) {
        const logContainer = document.getElementById('processing-log');
        if (!logContainer) return;
        
        const timestamp = new Date().toLocaleTimeString();
        const entry = document.createElement('div');
        entry.className = 'log-entry';
        entry.innerHTML = `
            <span class="timestamp">${timestamp}</span>
            <span class="level ${level}">${level.toUpperCase()}</span>
            <span class="message">${message}</span>
        `;
        
        logContainer.appendChild(entry);
        this.processingLog.push({ timestamp, level, message });
        
        // Keep only last 100 entries
        if (this.processingLog.length > 100) {
            this.processingLog.shift();
            logContainer.removeChild(logContainer.firstChild);
        }
        
        // Scroll to bottom
        logContainer.scrollTop = logContainer.scrollHeight;
    }
    
    clearLog() {
        const logContainer = document.getElementById('processing-log');
        if (logContainer) {
            logContainer.innerHTML = '';
            this.processingLog = [];
        }
    }
    
    exportLog() {
        if (this.processingLog.length === 0) {
            this.showError('No log entries to export');
            return;
        }
        
        const logText = this.processingLog.map(entry => 
            `${entry.timestamp} [${entry.level.toUpperCase()}] ${entry.message}`
        ).join('\n');
        
        const blob = new Blob([logText], { type: 'text/plain' });
        const url = URL.createObjectURL(blob);
        
        const a = document.createElement('a');
        a.href = url;
        a.download = `raw-directory-log-${new Date().toISOString().slice(0, 19)}.txt`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
        
        this.showSuccess('Log exported successfully');
    }
    
    toggleAutoRefresh() {
        const btn = document.getElementById('toggle-auto-refresh');
        
        if (this.autoRefreshEnabled) {
            this.stopAutoRefresh();
            this.autoRefreshEnabled = false;
            btn.innerHTML = '<i class="mdi mdi-play"></i> Auto-refresh';
            btn.classList.remove('btn-outline-info');
            btn.classList.add('btn-outline-secondary');
        } else {
            this.startAutoRefresh();
            this.autoRefreshEnabled = true;
            btn.innerHTML = '<i class="mdi mdi-pause"></i> Auto-refresh';
            btn.classList.remove('btn-outline-secondary');
            btn.classList.add('btn-outline-info');
        }
    }
    
    startAutoRefresh() {
        if (this.autoRefreshEnabled) {
            this.refreshInterval = setInterval(() => {
                this.refreshMonitor();
            }, this.refreshIntervalMs);
        }
    }
    
    stopAutoRefresh() {
        if (this.refreshInterval) {
            clearInterval(this.refreshInterval);
            this.refreshInterval = null;
        }
    }
    
    async refreshMonitor() {
        console.log('🔄 Refreshing raw directory monitor...');
        
        try {
            await Promise.all([
                this.loadStatusCounts(),
                this.loadFilesList(),
                this.loadProcessingQueue()
            ]);
        } catch (error) {
            console.error('Failed to refresh monitor:', error);
        }
    }
    
    // Utility functions
    formatFileSize(bytes) {
        if (bytes === 0) return '0 B';
        const k = 1024;
        const sizes = ['B', 'KB', 'MB', 'GB'];
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
}

// Global functions for template callbacks
window.uploadFiles = function() {
    const modal = new bootstrap.Modal(document.getElementById('fileUploadModal'));
    modal.show();
};

window.bulkProcess = function() {
    if (monitor.selectedFiles.size === 0) {
        monitor.showError('No files selected');
        return;
    }
    
    if (confirm(`Process ${monitor.selectedFiles.size} selected files?`)) {
        console.log('🔄 Bulk processing files:', monitor.selectedFiles);
        monitor.showSuccess(`Processing ${monitor.selectedFiles.size} files`);
    }
};

window.bulkPrioritize = function() {
    if (monitor.selectedFiles.size === 0) {
        monitor.showError('No files selected');
        return;
    }
    
    console.log('⭐ Prioritizing files:', monitor.selectedFiles);
    monitor.showSuccess(`Prioritized ${monitor.selectedFiles.size} files`);
};

window.bulkDelete = function() {
    if (monitor.selectedFiles.size === 0) {
        monitor.showError('No files selected');
        return;
    }
    
    if (confirm(`Delete ${monitor.selectedFiles.size} selected files? This cannot be undone.`)) {
        console.log('🗑️ Bulk deleting files:', monitor.selectedFiles);
        monitor.showSuccess(`Deleted ${monitor.selectedFiles.size} files`);
    }
};

// Global monitor instance
let monitor;

// Initialize monitor when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    console.log('🌟 Raw Directory Monitor DOM loaded');
    monitor = new RawDirectoryMonitor();
});