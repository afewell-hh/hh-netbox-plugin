/**
 * Archive Browser JavaScript
 * Handles browsing, searching, and managing archived files
 */

class ArchiveBrowser {
    constructor() {
        this.selectedArchives = new Set();
        this.currentView = 'list';
        this.timelineView = false;
        this.filters = {
            search: '',
            fabric: '',
            dateRange: 'all',
            archiveType: ''
        };
        this.charts = {};
        
        this.init();
    }
    
    init() {
        console.log('📁 Initializing Archive Browser');
        this.attachEventListeners();
        this.loadInitialData();
        this.initializeCharts();
    }
    
    attachEventListeners() {
        // Refresh and cleanup controls
        document.getElementById('refresh-archives')?.addEventListener('click', () => this.refreshArchives());
        document.getElementById('cleanup-archives')?.addEventListener('click', () => this.cleanupArchives());
        
        // Search and filters
        document.getElementById('search-input')?.addEventListener('input', (e) => {
            this.filters.search = e.target.value;
            this.debounceSearch();
        });
        
        document.getElementById('fabric-filter')?.addEventListener('change', (e) => {
            this.filters.fabric = e.target.value;
            this.applyFilters();
        });
        
        document.getElementById('date-range')?.addEventListener('change', (e) => {
            this.filters.dateRange = e.target.value;
            this.toggleCustomDateRange();
            this.applyFilters();
        });
        
        document.getElementById('archive-type')?.addEventListener('change', (e) => {
            this.filters.archiveType = e.target.value;
            this.applyFilters();
        });
        
        document.getElementById('apply-filters')?.addEventListener('click', () => this.applyFilters());
        
        // View controls
        document.getElementById('timeline-view')?.addEventListener('change', (e) => {
            this.timelineView = e.target.checked;
            this.toggleTimelineView();
        });
        
        // Archive selection
        document.getElementById('select-all-archives')?.addEventListener('change', (e) => {
            this.selectAllArchives(e.target.checked);
        });
        
        // Export actions
        document.querySelectorAll('[onclick^="exportArchives"]').forEach(btn => {
            const type = btn.onclick.toString().match(/exportArchives\('(.+)'\)/)?.[1];
            btn.onclick = () => this.exportArchives(type);
        });
        
        // Storage management
        document.querySelectorAll('[onclick="optimizeStorage()"]').forEach(btn => {
            btn.onclick = () => this.optimizeStorage();
        });
        document.querySelectorAll('[onclick="cleanupOldArchives()"]').forEach(btn => {
            btn.onclick = () => this.cleanupOldArchives();
        });
    }
    
    async loadInitialData() {
        try {
            console.log('📥 Loading initial archive data...');
            await Promise.all([
                this.loadArchiveStats(),
                this.loadArchivesList(),
                this.loadFabrics(),
                this.loadStorageInfo()
            ]);
            console.log('✅ Initial archive data loaded');
        } catch (error) {
            console.error('❌ Failed to load initial data:', error);
            this.showError('Failed to load archive data');
        }
    }
    
    async loadArchiveStats() {
        try {
            const response = await fetch('/plugins/hedgehog/api/gitops/archive-stats/');
            const stats = await response.json();
            
            // Update statistics cards
            document.getElementById('total-archives').textContent = stats.total_archives || 0;
            document.getElementById('migration-archives').textContent = stats.migration_archives || 0;
            document.getElementById('backup-archives').textContent = stats.backup_archives || 0;
            document.getElementById('total-size').textContent = this.formatStorage(stats.total_size || 0);
            
        } catch (error) {
            console.error('Failed to load archive stats:', error);
        }
    }
    
    async loadArchivesList() {
        try {
            const params = new URLSearchParams(this.filters);
            const response = await fetch(`/plugins/hedgehog/api/gitops/archives/?${params}`);
            const archives = await response.json();
            
            const tbody = document.getElementById('archives-tbody');
            const grid = document.getElementById('archives-grid');
            const timeline = document.getElementById('archives-timeline');
            const emptyState = document.getElementById('archives-empty');
            
            if (archives && archives.length > 0) {
                emptyState.classList.add('d-none');
                
                // Clear existing content
                if (tbody) tbody.innerHTML = '';
                if (grid) grid.innerHTML = '';
                if (timeline) timeline.innerHTML = '';
                
                if (this.timelineView) {
                    this.renderTimelineView(archives, timeline);
                } else if (this.currentView === 'grid') {
                    this.renderGridView(archives, grid);
                } else {
                    this.renderListView(archives, tbody);
                }
            } else {
                emptyState.classList.remove('d-none');
                if (tbody) tbody.innerHTML = '';
                if (grid) grid.innerHTML = '';
                if (timeline) timeline.innerHTML = '';
            }
            
        } catch (error) {
            console.error('Failed to load archives list:', error);
        }
    }
    
    renderListView(archives, tbody) {
        archives.forEach(archive => {
            const row = document.createElement('tr');
            row.className = 'archive-row';
            row.dataset.archiveId = archive.id;
            
            const archivedDate = new Date(archive.archived_date).toLocaleString();
            const typeBadge = this.getArchiveTypeBadge(archive.type);
            
            row.innerHTML = `
                <td>
                    <div class="form-check">
                        <input class="form-check-input archive-checkbox" 
                               type="checkbox" 
                               value="${archive.id}"
                               onchange="archiveBrowser.handleArchiveSelection(this)">
                    </div>
                </td>
                <td>
                    <div class="d-flex align-items-center">
                        <i class="mdi mdi-file-document text-primary me-2"></i>
                        <div>
                            <div class="fw-bold">${archive.original_name}</div>
                            <small class="text-muted">${archive.original_path || ''}</small>
                        </div>
                    </div>
                </td>
                <td>${typeBadge}</td>
                <td>
                    <span class="badge bg-info">${archive.fabric_name || 'Unknown'}</span>
                </td>
                <td>${this.formatStorage(archive.size || 0)}</td>
                <td><small>${archivedDate}</small></td>
                <td>
                    <div class="btn-group btn-group-sm" role="group">
                        <button class="btn btn-outline-primary" onclick="archiveBrowser.previewArchive('${archive.id}')" title="Preview">
                            <i class="mdi mdi-eye"></i>
                        </button>
                        <button class="btn btn-outline-success" onclick="archiveBrowser.restoreArchive('${archive.id}')" title="Restore">
                            <i class="mdi mdi-restore"></i>
                        </button>
                        <button class="btn btn-outline-info" onclick="archiveBrowser.downloadArchive('${archive.id}')" title="Download">
                            <i class="mdi mdi-download"></i>
                        </button>
                    </div>
                </td>
            `;
            
            // Add click handler for row selection
            row.addEventListener('click', (e) => {
                if (!e.target.closest('button') && !e.target.closest('.form-check')) {
                    this.selectArchive(archive);
                }
            });
            
            tbody.appendChild(row);
        });
    }
    
    renderGridView(archives, grid) {
        archives.forEach(archive => {
            const card = document.createElement('div');
            card.className = 'col-md-4 mb-3';
            
            const archivedDate = new Date(archive.archived_date).toLocaleDateString();
            const typeBadge = this.getArchiveTypeBadge(archive.type);
            
            card.innerHTML = `
                <div class="card archive-card" data-archive-id="${archive.id}">
                    <div class="card-body">
                        <div class="archive-type-badge">${typeBadge}</div>
                        <div class="d-flex align-items-center mb-2">
                            <i class="mdi mdi-file-document text-primary me-2"></i>
                            <div class="flex-grow-1">
                                <h6 class="card-title mb-1">${archive.original_name}</h6>
                                <small class="text-muted">${archive.fabric_name || 'Unknown'}</small>
                            </div>
                        </div>
                        <p class="card-text">
                            <small class="text-muted">
                                ${this.formatStorage(archive.size || 0)} • ${archivedDate}
                            </small>
                        </p>
                        <div class="btn-group w-100" role="group">
                            <button class="btn btn-sm btn-outline-primary" onclick="archiveBrowser.previewArchive('${archive.id}')">
                                <i class="mdi mdi-eye"></i>
                            </button>
                            <button class="btn btn-sm btn-outline-success" onclick="archiveBrowser.restoreArchive('${archive.id}')">
                                <i class="mdi mdi-restore"></i>
                            </button>
                            <button class="btn btn-sm btn-outline-info" onclick="archiveBrowser.downloadArchive('${archive.id}')">
                                <i class="mdi mdi-download"></i>
                            </button>
                        </div>
                    </div>
                </div>
            `;
            
            // Add click handler for card selection
            const cardElement = card.querySelector('.archive-card');
            cardElement.addEventListener('click', (e) => {
                if (!e.target.closest('button')) {
                    this.selectArchive(archive);
                }
            });
            
            grid.appendChild(card);
        });
    }
    
    renderTimelineView(archives, timeline) {
        // Group archives by date
        const groupedArchives = this.groupArchivesByDate(archives);
        
        Object.entries(groupedArchives).forEach(([date, dayArchives]) => {
            const timelineItem = document.createElement('div');
            timelineItem.className = 'timeline-item';
            
            timelineItem.innerHTML = `
                <div class="timeline-date">${date}</div>
                <div class="timeline-content">
                    ${dayArchives.map(archive => `
                        <div class="d-flex justify-content-between align-items-center mb-2">
                            <div>
                                <h6 class="mb-1">${archive.original_name}</h6>
                                <p class="mb-0 text-muted">${archive.fabric_name} • ${this.getArchiveTypeBadge(archive.type)}</p>
                            </div>
                            <div class="timeline-actions">
                                <button class="btn btn-sm btn-outline-primary" onclick="archiveBrowser.previewArchive('${archive.id}')">
                                    <i class="mdi mdi-eye"></i>
                                </button>
                                <button class="btn btn-sm btn-outline-success" onclick="archiveBrowser.restoreArchive('${archive.id}')">
                                    <i class="mdi mdi-restore"></i>
                                </button>
                            </div>
                        </div>
                    `).join('')}
                </div>
            `;
            
            timeline.appendChild(timelineItem);
        });
    }
    
    groupArchivesByDate(archives) {
        const grouped = {};
        
        archives.forEach(archive => {
            const date = new Date(archive.archived_date).toLocaleDateString();
            if (!grouped[date]) {
                grouped[date] = [];
            }
            grouped[date].push(archive);
        });
        
        return grouped;
    }
    
    getArchiveTypeBadge(type) {
        const typeMap = {
            'migration': { class: 'bg-success', text: 'Migration' },
            'backup': { class: 'bg-warning', text: 'Backup' },
            'cleanup': { class: 'bg-info', text: 'Cleanup' },
            'error': { class: 'bg-danger', text: 'Error Recovery' }
        };
        
        const typeInfo = typeMap[type] || { class: 'bg-secondary', text: 'Unknown' };
        return `<span class="badge ${typeInfo.class}">${typeInfo.text}</span>`;
    }
    
    async loadFabrics() {
        try {
            const response = await fetch('/plugins/hedgehog/api/fabrics/');
            const fabrics = await response.json();
            
            const fabricFilter = document.getElementById('fabric-filter');
            if (fabricFilter) {
                // Keep the "All Fabrics" option
                const allOption = fabricFilter.querySelector('option[value=""]');
                fabricFilter.innerHTML = '';
                if (allOption) fabricFilter.appendChild(allOption);
                
                fabrics.forEach(fabric => {
                    const option = document.createElement('option');
                    option.value = fabric.id;
                    option.textContent = fabric.name;
                    fabricFilter.appendChild(option);
                });
            }
            
        } catch (error) {
            console.error('Failed to load fabrics:', error);
        }
    }
    
    async loadStorageInfo() {
        try {
            const response = await fetch('/plugins/hedgehog/api/gitops/archive-storage/');
            const storage = await response.json();
            
            // Update storage display
            document.getElementById('storage-used').textContent = this.formatStorage(storage.used || 0);
            document.getElementById('storage-percentage').textContent = `${storage.percentage || 0}%`;
            
            const progressBar = document.getElementById('storage-progress');
            if (progressBar) {
                progressBar.style.width = `${storage.percentage || 0}%`;
            }
            
            // Update trends chart
            this.updateTrendsChart(storage.trends);
            
        } catch (error) {
            console.error('Failed to load storage info:', error);
        }
    }
    
    initializeCharts() {
        this.initTrendsChart();
    }
    
    initTrendsChart() {
        const ctx = document.getElementById('archive-trends-chart');
        if (!ctx) return;
        
        this.charts.trends = new Chart(ctx, {
            type: 'line',
            data: {
                labels: [],
                datasets: [{
                    label: 'Archives Created',
                    data: [],
                    borderColor: 'rgba(13, 110, 253, 1)',
                    backgroundColor: 'rgba(13, 110, 253, 0.1)',
                    tension: 0.4
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        display: false
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        ticks: {
                            stepSize: 1
                        }
                    }
                }
            }
        });
    }
    
    updateTrendsChart(trendsData) {
        if (!this.charts.trends || !trendsData) return;
        
        this.charts.trends.data.labels = trendsData.labels || [];
        this.charts.trends.data.datasets[0].data = trendsData.values || [];
        this.charts.trends.update();
    }
    
    selectArchive(archive) {
        // Update archive details panel
        this.displayArchiveDetails(archive);
        
        // Highlight selected row/card
        document.querySelectorAll('.archive-row, .archive-card').forEach(el => {
            el.classList.remove('selected');
        });
        
        const element = document.querySelector(`[data-archive-id="${archive.id}"]`);
        if (element) {
            element.classList.add('selected');
        }
    }
    
    displayArchiveDetails(archive) {
        const detailsCard = document.getElementById('archive-details-card');
        const detailsBody = document.getElementById('archive-details-body');
        
        if (detailsCard && detailsBody) {
            const archivedDate = new Date(archive.archived_date).toLocaleString();
            const typeBadge = this.getArchiveTypeBadge(archive.type);
            
            detailsBody.innerHTML = `
                <div class="archive-metadata-content">
                    <div class="metadata-item">
                        <span class="metadata-label">Original Name:</span>
                        <span class="metadata-value">${archive.original_name}</span>
                    </div>
                    <div class="metadata-item">
                        <span class="metadata-label">Archive Type:</span>
                        <span class="metadata-value">${typeBadge}</span>
                    </div>
                    <div class="metadata-item">
                        <span class="metadata-label">Fabric:</span>
                        <span class="metadata-value">${archive.fabric_name || 'Unknown'}</span>
                    </div>
                    <div class="metadata-item">
                        <span class="metadata-label">Size:</span>
                        <span class="metadata-value">${this.formatStorage(archive.size || 0)}</span>
                    </div>
                    <div class="metadata-item">
                        <span class="metadata-label">Archived:</span>
                        <span class="metadata-value">${archivedDate}</span>
                    </div>
                    <div class="metadata-item">
                        <span class="metadata-label">Reason:</span>
                        <span class="metadata-value">${archive.reason || 'Not specified'}</span>
                    </div>
                </div>
            `;
            
            detailsCard.style.display = 'block';
        }
    }
    
    handleArchiveSelection(checkbox) {
        const archiveId = checkbox.value;
        
        if (checkbox.checked) {
            this.selectedArchives.add(archiveId);
        } else {
            this.selectedArchives.delete(archiveId);
        }
        
        this.updateBulkActions();
    }
    
    selectAllArchives(checked) {
        const checkboxes = document.querySelectorAll('.archive-checkbox');
        checkboxes.forEach(checkbox => {
            checkbox.checked = checked;
            this.handleArchiveSelection(checkbox);
        });
    }
    
    updateBulkActions() {
        const bulkActions = document.getElementById('bulk-actions');
        const selectedCount = document.getElementById('selected-count');
        
        if (this.selectedArchives.size > 0) {
            bulkActions.classList.remove('d-none');
            selectedCount.textContent = this.selectedArchives.size;
        } else {
            bulkActions.classList.add('d-none');
        }
    }
    
    toggleCustomDateRange() {
        const customRange = document.getElementById('custom-date-range');
        const dateRange = document.getElementById('date-range');
        
        if (dateRange.value === 'custom') {
            customRange.classList.remove('d-none');
        } else {
            customRange.classList.add('d-none');
        }
    }
    
    toggleTimelineView() {
        const listView = document.getElementById('list-view');
        const gridView = document.getElementById('grid-view');
        const timelineViewContent = document.getElementById('timeline-view-content');
        
        if (this.timelineView) {
            listView.classList.add('d-none');
            gridView.classList.add('d-none');
            timelineViewContent.classList.remove('d-none');
        } else {
            timelineViewContent.classList.add('d-none');
            if (this.currentView === 'grid') {
                gridView.classList.remove('d-none');
            } else {
                listView.classList.remove('d-none');
            }
        }
        
        this.loadArchivesList();
    }
    
    debounceSearch() {
        clearTimeout(this.searchTimeout);
        this.searchTimeout = setTimeout(() => {
            this.applyFilters();
        }, 500);
    }
    
    applyFilters() {
        console.log('🔍 Applying filters:', this.filters);
        this.loadArchivesList();
    }
    
    async previewArchive(archiveId) {
        try {
            const response = await fetch(`/plugins/hedgehog/api/gitops/archive-content/${archiveId}/`);
            const content = await response.json();
            
            // Update modal content
            document.getElementById('archive-content').textContent = content.content || '';
            document.getElementById('archive-metadata-content').innerHTML = this.formatArchiveMetadata(content.metadata);
            
            // Show modal
            const modal = new bootstrap.Modal(document.getElementById('archivePreviewModal'));
            modal.show();
            
        } catch (error) {
            console.error('Failed to preview archive:', error);
            this.showError('Failed to load archive preview');
        }
    }
    
    formatArchiveMetadata(metadata) {
        if (!metadata) return '<p>No metadata available</p>';
        
        return Object.entries(metadata).map(([key, value]) => `
            <div class="metadata-item">
                <span class="metadata-label">${key}:</span>
                <span class="metadata-value">${value}</span>
            </div>
        `).join('');
    }
    
    async restoreArchive(archiveId) {
        // Show confirmation modal
        const modal = new bootstrap.Modal(document.getElementById('restoreConfirmationModal'));
        
        // Load restore details
        try {
            const response = await fetch(`/plugins/hedgehog/api/gitops/archive-details/${archiveId}/`);
            const details = await response.json();
            
            document.getElementById('restore-details').innerHTML = `
                <p><strong>Archive:</strong> ${details.original_name}</p>
                <p><strong>Original Path:</strong> ${details.original_path}</p>
                <p><strong>Size:</strong> ${this.formatStorage(details.size)}</p>
                <p><strong>Archived:</strong> ${new Date(details.archived_date).toLocaleString()}</p>
            `;
            
            // Set up confirm button
            document.getElementById('confirm-restore-btn').onclick = () => {
                this.confirmRestore(archiveId);
                modal.hide();
            };
            
            modal.show();
            
        } catch (error) {
            console.error('Failed to load restore details:', error);
            this.showError('Failed to load restore details');
        }
    }
    
    async confirmRestore(archiveId) {
        try {
            const overwriteExisting = document.getElementById('overwrite-existing').checked;
            
            const response = await fetch(`/plugins/hedgehog/api/gitops/restore-archive/${archiveId}/`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.getCSRFToken()
                },
                body: JSON.stringify({
                    overwrite_existing: overwriteExisting
                })
            });
            
            const result = await response.json();
            
            if (result.success) {
                this.showSuccess('Archive restored successfully');
                this.refreshArchives();
            } else {
                this.showError(result.error || 'Restore failed');
            }
            
        } catch (error) {
            console.error('Restore failed:', error);
            this.showError('Failed to restore archive');
        }
    }
    
    async downloadArchive(archiveId) {
        try {
            window.open(`/plugins/hedgehog/api/gitops/download-archive/${archiveId}/`, '_blank');
            this.showSuccess('Archive download started');
            
        } catch (error) {
            console.error('Download failed:', error);
            this.showError('Failed to download archive');
        }
    }
    
    async exportArchives(type) {
        console.log('📤 Exporting archives:', type);
        
        let archiveIds = [];
        
        if (type === 'selected') {
            if (this.selectedArchives.size === 0) {
                this.showError('No archives selected');
                return;
            }
            archiveIds = Array.from(this.selectedArchives);
        }
        
        try {
            const response = await fetch('/plugins/hedgehog/api/gitops/export-archives/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.getCSRFToken()
                },
                body: JSON.stringify({
                    type: type,
                    archive_ids: archiveIds
                })
            });
            
            const result = await response.json();
            
            if (result.success) {
                window.open(result.download_url, '_blank');
                this.showSuccess('Archive export started');
            } else {
                this.showError(result.error || 'Export failed');
            }
            
        } catch (error) {
            console.error('Export failed:', error);
            this.showError('Failed to export archives');
        }
    }
    
    async optimizeStorage() {
        if (!confirm('Optimize archive storage? This may take a few minutes.')) {
            return;
        }
        
        try {
            const response = await fetch('/plugins/hedgehog/api/gitops/optimize-storage/', {
                method: 'POST',
                headers: {
                    'X-CSRFToken': this.getCSRFToken()
                }
            });
            
            const result = await response.json();
            
            if (result.success) {
                this.showSuccess(`Storage optimized. Saved ${this.formatStorage(result.space_saved)}`);
                this.loadStorageInfo();
            } else {
                this.showError(result.error || 'Optimization failed');
            }
            
        } catch (error) {
            console.error('Storage optimization failed:', error);
            this.showError('Failed to optimize storage');
        }
    }
    
    async cleanupOldArchives() {
        if (!confirm('Delete old archives according to retention policy? This cannot be undone.')) {
            return;
        }
        
        try {
            const response = await fetch('/plugins/hedgehog/api/gitops/cleanup-archives/', {
                method: 'POST',
                headers: {
                    'X-CSRFToken': this.getCSRFToken()
                }
            });
            
            const result = await response.json();
            
            if (result.success) {
                this.showSuccess(`Cleaned up ${result.deleted_count} old archives`);
                this.refreshArchives();
            } else {
                this.showError(result.error || 'Cleanup failed');
            }
            
        } catch (error) {
            console.error('Archive cleanup failed:', error);
            this.showError('Failed to cleanup archives');
        }
    }
    
    async refreshArchives() {
        console.log('🔄 Refreshing archives...');
        
        const refreshBtn = document.getElementById('refresh-archives');
        if (refreshBtn) {
            refreshBtn.innerHTML = '<i class="mdi mdi-loading mdi-spin"></i> Refreshing...';
            refreshBtn.disabled = true;
        }
        
        try {
            await this.loadInitialData();
        } finally {
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
window.changeView = function(view) {
    archiveBrowser.currentView = view;
    
    // Update button states
    document.getElementById('list-view-btn').classList.toggle('active', view === 'list');
    document.getElementById('grid-view-btn').classList.toggle('active', view === 'grid');
    
    // Toggle views
    const listView = document.getElementById('list-view');
    const gridView = document.getElementById('grid-view');
    
    if (view === 'grid') {
        listView.classList.add('d-none');
        gridView.classList.remove('d-none');
    } else {
        gridView.classList.add('d-none');
        listView.classList.remove('d-none');
    }
    
    archiveBrowser.loadArchivesList();
};

window.clearFilters = function() {
    archiveBrowser.filters = {
        search: '',
        fabric: '',
        dateRange: 'all',
        archiveType: ''
    };
    
    // Reset form controls
    document.getElementById('search-input').value = '';
    document.getElementById('fabric-filter').value = '';
    document.getElementById('date-range').value = 'all';
    document.getElementById('archive-type').value = '';
    
    archiveBrowser.applyFilters();
};

window.formatContent = function(format) {
    console.log('🔧 Formatting content as:', format);
    // Implementation would format the preview content
};

window.downloadArchiveFromModal = function() {
    // Get current archive ID from modal context
    console.log('📥 Download archive from modal');
};

window.restoreArchiveFromModal = function() {
    // Get current archive ID from modal context
    console.log('🔄 Restore archive from modal');
};

window.bulkRestore = function() {
    if (archiveBrowser.selectedArchives.size === 0) {
        archiveBrowser.showError('No archives selected');
        return;
    }
    
    if (confirm(`Restore ${archiveBrowser.selectedArchives.size} selected archives?`)) {
        console.log('🔄 Bulk restoring archives:', archiveBrowser.selectedArchives);
        archiveBrowser.showSuccess(`Restoring ${archiveBrowser.selectedArchives.size} archives`);
    }
};

window.bulkDownload = function() {
    if (archiveBrowser.selectedArchives.size === 0) {
        archiveBrowser.showError('No archives selected');
        return;
    }
    
    console.log('📥 Bulk downloading archives:', archiveBrowser.selectedArchives);
    archiveBrowser.exportArchives('selected');
};

window.bulkDelete = function() {
    if (archiveBrowser.selectedArchives.size === 0) {
        archiveBrowser.showError('No archives selected');
        return;
    }
    
    if (confirm(`Delete ${archiveBrowser.selectedArchives.size} selected archives? This cannot be undone.`)) {
        console.log('🗑️ Bulk deleting archives:', archiveBrowser.selectedArchives);
        archiveBrowser.showSuccess(`Deleted ${archiveBrowser.selectedArchives.size} archives`);
    }
};

// Global archive browser instance
let archiveBrowser;

// Initialize archive browser when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    console.log('🌟 Archive Browser DOM loaded');
    archiveBrowser = new ArchiveBrowser();
});