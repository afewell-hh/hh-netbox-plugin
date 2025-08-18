/**
 * Batch Operations Manager for CNOC
 * FORGE Movement 7: Advanced UI Features - Batch Operations
 */

class CNOCBatchOperationsManager {
    constructor(options = {}) {
        this.apiBasePath = options.apiBasePath || '/api/v1';
        this.maxBatchSize = options.maxBatchSize || 100;
        this.progressUpdateInterval = options.progressUpdateInterval || 500;
        this.selectedItems = new Set();
        this.activeOperations = new Map();
        this.operationHistory = [];
        
        // Performance tracking
        this.metrics = {
            totalOperations: 0,
            totalItemsProcessed: 0,
            averageProcessingTime: 0,
            successRate: 0,
            activeOperationCount: 0
        };
        
        // Event callbacks
        this.onProgressUpdate = options.onProgressUpdate || (() => {});
        this.onOperationComplete = options.onOperationComplete || (() => {});
        this.onSelectionChange = options.onSelectionChange || (() => {});
        this.onError = options.onError || ((error) => console.error('Batch operation error:', error));
        
        this.init();
    }

    /**
     * Initialize batch operations manager
     */
    init() {
        this.setupEventListeners();
        this.createBatchOperationUI();
        this.updateSelectionDisplay();
    }

    /**
     * Setup event listeners for batch operations
     */
    setupEventListeners() {
        // Handle individual item selection
        document.addEventListener('change', (event) => {
            if (event.target.classList.contains('batch-select-item')) {
                this.handleItemSelection(event.target);
            }
        });

        // Handle select all checkbox
        document.addEventListener('change', (event) => {
            if (event.target.classList.contains('batch-select-all')) {
                this.handleSelectAll(event.target);
            }
        });

        // Handle batch operation buttons
        document.addEventListener('click', (event) => {
            if (event.target.classList.contains('batch-operation-btn')) {
                const operation = event.target.dataset.operation;
                this.startBatchOperation(operation);
            }
        });

        // Handle operation cancellation
        document.addEventListener('click', (event) => {
            if (event.target.classList.contains('cancel-operation-btn')) {
                const operationId = event.target.dataset.operationId;
                this.cancelOperation(operationId);
            }
        });
    }

    /**
     * Create batch operation UI elements
     */
    createBatchOperationUI() {
        // Create batch toolbar if it doesn't exist
        let toolbar = document.querySelector('.batch-operations-toolbar');
        if (!toolbar) {
            toolbar = document.createElement('div');
            toolbar.className = 'batch-operations-toolbar';
            toolbar.innerHTML = this.getBatchToolbarHTML();
            
            // Insert after table header or at beginning of content
            const tableContainer = document.querySelector('.table-responsive') || document.querySelector('.content');
            if (tableContainer) {
                tableContainer.insertBefore(toolbar, tableContainer.firstChild);
            }
        }

        // Create progress modal
        this.createProgressModal();
    }

    /**
     * Get batch toolbar HTML
     */
    getBatchToolbarHTML() {
        return `
            <div class="batch-toolbar-content">
                <div class="batch-selection-info">
                    <span class="selected-count">0</span> items selected
                    <button type="button" class="btn btn-sm btn-outline-secondary clear-selection-btn" 
                            onclick="batchManager.clearSelection()">Clear Selection</button>
                </div>
                <div class="batch-operations">
                    <button type="button" class="btn btn-primary batch-operation-btn" 
                            data-operation="sync" disabled>
                        <i class="fas fa-sync"></i> Batch Sync
                    </button>
                    <button type="button" class="btn btn-warning batch-operation-btn" 
                            data-operation="update" disabled>
                        <i class="fas fa-edit"></i> Batch Update
                    </button>
                    <button type="button" class="btn btn-danger batch-operation-btn" 
                            data-operation="delete" disabled>
                        <i class="fas fa-trash"></i> Batch Delete
                    </button>
                    <div class="btn-group">
                        <button type="button" class="btn btn-info dropdown-toggle batch-operation-btn" 
                                data-bs-toggle="dropdown" disabled>
                            <i class="fas fa-cog"></i> More Actions
                        </button>
                        <ul class="dropdown-menu">
                            <li><a class="dropdown-item batch-operation-btn" href="#" data-operation="export">
                                <i class="fas fa-download"></i> Export Selected
                            </a></li>
                            <li><a class="dropdown-item batch-operation-btn" href="#" data-operation="validate">
                                <i class="fas fa-check"></i> Validate Configuration
                            </a></li>
                            <li><a class="dropdown-item batch-operation-btn" href="#" data-operation="apply">
                                <i class="fas fa-play"></i> Apply Changes
                            </a></li>
                        </ul>
                    </div>
                </div>
            </div>
        `;
    }

    /**
     * Create progress modal
     */
    createProgressModal() {
        const modalHTML = `
            <div class="modal fade" id="batchProgressModal" tabindex="-1">
                <div class="modal-dialog modal-lg">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h5 class="modal-title">Batch Operation Progress</h5>
                            <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                        </div>
                        <div class="modal-body">
                            <div class="operation-summary mb-3">
                                <h6 class="operation-title"></h6>
                                <p class="operation-description"></p>
                            </div>
                            
                            <div class="progress-container">
                                <div class="progress mb-2">
                                    <div class="progress-bar" role="progressbar" 
                                         style="width: 0%" aria-valuenow="0" aria-valuemin="0" aria-valuemax="100">
                                        0%
                                    </div>
                                </div>
                                <div class="progress-text">
                                    <span class="current-item">0</span> / <span class="total-items">0</span> items processed
                                </div>
                            </div>

                            <div class="operation-status mt-3">
                                <div class="status-summary row">
                                    <div class="col-md-3">
                                        <div class="status-card success">
                                            <h6 class="status-count success-count">0</h6>
                                            <p class="status-label">Successful</p>
                                        </div>
                                    </div>
                                    <div class="col-md-3">
                                        <div class="status-card failed">
                                            <h6 class="status-count failed-count">0</h6>
                                            <p class="status-label">Failed</p>
                                        </div>
                                    </div>
                                    <div class="col-md-3">
                                        <div class="status-card pending">
                                            <h6 class="status-count pending-count">0</h6>
                                            <p class="status-label">Pending</p>
                                        </div>
                                    </div>
                                    <div class="col-md-3">
                                        <div class="status-card metrics">
                                            <h6 class="status-count avg-time">0ms</h6>
                                            <p class="status-label">Avg Time</p>
                                        </div>
                                    </div>
                                </div>
                            </div>

                            <div class="operation-log mt-3">
                                <h6>Operation Log</h6>
                                <div class="log-container" style="max-height: 200px; overflow-y: auto;">
                                    <ul class="log-entries list-unstyled"></ul>
                                </div>
                            </div>
                        </div>
                        <div class="modal-footer">
                            <button type="button" class="btn btn-danger cancel-operation-btn" 
                                    data-operation-id="">Cancel Operation</button>
                            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Close</button>
                        </div>
                    </div>
                </div>
            </div>
        `;
        
        // Add modal to DOM if it doesn't exist
        if (!document.querySelector('#batchProgressModal')) {
            document.body.insertAdjacentHTML('beforeend', modalHTML);
        }
    }

    /**
     * Handle individual item selection
     */
    handleItemSelection(checkbox) {
        const itemId = checkbox.value;
        const itemData = this.getItemData(checkbox);
        
        if (checkbox.checked) {
            this.selectedItems.add({ id: itemId, ...itemData });
        } else {
            // Remove item with matching ID
            this.selectedItems.forEach(item => {
                if (item.id === itemId) {
                    this.selectedItems.delete(item);
                }
            });
        }
        
        this.updateSelectionDisplay();
        this.onSelectionChange(Array.from(this.selectedItems));
    }

    /**
     * Handle select all checkbox
     */
    handleSelectAll(checkbox) {
        const itemCheckboxes = document.querySelectorAll('.batch-select-item');
        
        itemCheckboxes.forEach(itemCheckbox => {
            itemCheckbox.checked = checkbox.checked;
            this.handleItemSelection(itemCheckbox);
        });
    }

    /**
     * Get item data from DOM element
     */
    getItemData(checkbox) {
        const row = checkbox.closest('tr') || checkbox.closest('.item-row');
        if (!row) return {};
        
        return {
            name: row.dataset.itemName || '',
            type: row.dataset.itemType || '',
            status: row.dataset.itemStatus || '',
            fabric: row.dataset.fabricId || ''
        };
    }

    /**
     * Update selection display
     */
    updateSelectionDisplay() {
        const count = this.selectedItems.size;
        const countElement = document.querySelector('.selected-count');
        if (countElement) {
            countElement.textContent = count;
        }
        
        // Enable/disable batch operation buttons
        const batchButtons = document.querySelectorAll('.batch-operation-btn');
        batchButtons.forEach(button => {
            button.disabled = count === 0;
        });
        
        // Update select all checkbox state
        const selectAllCheckbox = document.querySelector('.batch-select-all');
        const itemCheckboxes = document.querySelectorAll('.batch-select-item');
        
        if (selectAllCheckbox && itemCheckboxes.length > 0) {
            const checkedCount = Array.from(itemCheckboxes).filter(cb => cb.checked).length;
            selectAllCheckbox.checked = checkedCount === itemCheckboxes.length;
            selectAllCheckbox.indeterminate = checkedCount > 0 && checkedCount < itemCheckboxes.length;
        }
    }

    /**
     * Start batch operation
     */
    async startBatchOperation(operationType) {
        if (this.selectedItems.size === 0) {
            this.showError('No items selected for batch operation');
            return;
        }
        
        if (this.selectedItems.size > this.maxBatchSize) {
            this.showError(`Cannot process more than ${this.maxBatchSize} items at once`);
            return;
        }

        // Confirm dangerous operations
        if (['delete', 'update'].includes(operationType)) {
            if (!await this.confirmDangerousOperation(operationType)) {
                return;
            }
        }

        const operationId = this.generateOperationId();
        const operation = {
            id: operationId,
            type: operationType,
            items: Array.from(this.selectedItems),
            status: 'starting',
            progress: 0,
            startTime: Date.now(),
            successCount: 0,
            failureCount: 0,
            pendingCount: this.selectedItems.size,
            log: [],
            cancelled: false
        };

        this.activeOperations.set(operationId, operation);
        this.metrics.activeOperationCount++;

        // Show progress modal
        this.showProgressModal(operation);
        
        // Start processing
        try {
            await this.executeOperation(operation);
        } catch (error) {
            this.handleOperationError(operation, error);
        }
    }

    /**
     * Execute batch operation
     */
    async executeOperation(operation) {
        operation.status = 'running';
        operation.log.push({ 
            timestamp: Date.now(), 
            message: `Starting ${operation.type} operation on ${operation.items.length} items`,
            type: 'info' 
        });
        
        this.updateProgressDisplay(operation);
        
        const batchSize = 5; // Process in smaller batches
        const batches = this.chunkArray(operation.items, batchSize);
        
        for (let i = 0; i < batches.length && !operation.cancelled; i++) {
            const batch = batches[i];
            await this.processBatch(operation, batch, i);
            
            // Update progress
            operation.progress = Math.round(((i + 1) / batches.length) * 100);
            this.updateProgressDisplay(operation);
            
            // Small delay to allow UI updates and cancellation
            await this.delay(100);
        }
        
        // Complete operation
        operation.status = operation.cancelled ? 'cancelled' : 'completed';
        operation.endTime = Date.now();
        operation.totalTime = operation.endTime - operation.startTime;
        
        // Update metrics
        this.updateMetrics(operation);
        
        // Log completion
        operation.log.push({
            timestamp: Date.now(),
            message: `Operation ${operation.status}. Processed ${operation.items.length} items in ${operation.totalTime}ms`,
            type: operation.cancelled ? 'warning' : 'success'
        });
        
        this.updateProgressDisplay(operation);
        this.onOperationComplete(operation);
        
        // Store in history
        this.operationHistory.push(operation);
        this.activeOperations.delete(operation.id);
        this.metrics.activeOperationCount--;
    }

    /**
     * Process a batch of items
     */
    async processBatch(operation, batch, batchIndex) {
        const batchPromises = batch.map(item => this.processItem(operation, item));
        const results = await Promise.allSettled(batchPromises);
        
        results.forEach((result, index) => {
            const item = batch[index];
            if (result.status === 'fulfilled') {
                operation.successCount++;
                operation.log.push({
                    timestamp: Date.now(),
                    message: `✅ ${item.name}: ${result.value.message || 'Success'}`,
                    type: 'success'
                });
            } else {
                operation.failureCount++;
                operation.log.push({
                    timestamp: Date.now(),
                    message: `❌ ${item.name}: ${result.reason.message || 'Failed'}`,
                    type: 'error'
                });
            }
            operation.pendingCount--;
        });
    }

    /**
     * Process individual item
     */
    async processItem(operation, item) {
        const startTime = Date.now();
        
        try {
            let response;
            switch (operation.type) {
                case 'sync':
                    response = await this.syncItem(item);
                    break;
                case 'update':
                    response = await this.updateItem(item);
                    break;
                case 'delete':
                    response = await this.deleteItem(item);
                    break;
                case 'export':
                    response = await this.exportItem(item);
                    break;
                case 'validate':
                    response = await this.validateItem(item);
                    break;
                case 'apply':
                    response = await this.applyItem(item);
                    break;
                default:
                    throw new Error(`Unknown operation type: ${operation.type}`);
            }
            
            const processingTime = Date.now() - startTime;
            return { message: response.message || 'Success', processingTime };
            
        } catch (error) {
            const processingTime = Date.now() - startTime;
            throw { message: error.message || 'Unknown error', processingTime };
        }
    }

    /**
     * API methods for different operations
     */
    async syncItem(item) {
        const response = await fetch(`${this.apiBasePath}/items/${item.id}/sync`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ force: false })
        });
        
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        
        return await response.json();
    }

    async updateItem(item) {
        const response = await fetch(`${this.apiBasePath}/items/${item.id}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ batch_update: true })
        });
        
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        
        return await response.json();
    }

    async deleteItem(item) {
        const response = await fetch(`${this.apiBasePath}/items/${item.id}`, {
            method: 'DELETE'
        });
        
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        
        return { message: 'Deleted successfully' };
    }

    async exportItem(item) {
        const response = await fetch(`${this.apiBasePath}/items/${item.id}/export`);
        
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        
        return { message: 'Exported successfully' };
    }

    async validateItem(item) {
        const response = await fetch(`${this.apiBasePath}/items/${item.id}/validate`, {
            method: 'POST'
        });
        
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        
        const result = await response.json();
        return { message: result.valid ? 'Valid' : `Invalid: ${result.errors.join(', ')}` };
    }

    async applyItem(item) {
        const response = await fetch(`${this.apiBasePath}/items/${item.id}/apply`, {
            method: 'POST'
        });
        
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        
        return await response.json();
    }

    /**
     * Cancel active operation
     */
    cancelOperation(operationId) {
        const operation = this.activeOperations.get(operationId);
        if (operation) {
            operation.cancelled = true;
            operation.status = 'cancelling';
            operation.log.push({
                timestamp: Date.now(),
                message: 'Operation cancelled by user',
                type: 'warning'
            });
            this.updateProgressDisplay(operation);
        }
    }

    /**
     * Show progress modal
     */
    showProgressModal(operation) {
        const modal = document.querySelector('#batchProgressModal');
        const modalInstance = new bootstrap.Modal(modal);
        
        // Update modal content
        modal.querySelector('.operation-title').textContent = 
            `${operation.type.charAt(0).toUpperCase() + operation.type.slice(1)} Operation`;
        modal.querySelector('.operation-description').textContent = 
            `Processing ${operation.items.length} selected items`;
        modal.querySelector('.cancel-operation-btn').dataset.operationId = operation.id;
        
        modalInstance.show();
        
        // Update initial progress
        this.updateProgressDisplay(operation);
    }

    /**
     * Update progress display
     */
    updateProgressDisplay(operation) {
        const modal = document.querySelector('#batchProgressModal');
        if (!modal) return;
        
        // Update progress bar
        const progressBar = modal.querySelector('.progress-bar');
        progressBar.style.width = `${operation.progress}%`;
        progressBar.setAttribute('aria-valuenow', operation.progress);
        progressBar.textContent = `${operation.progress}%`;
        
        // Update progress text
        const processedItems = operation.successCount + operation.failureCount;
        modal.querySelector('.current-item').textContent = processedItems;
        modal.querySelector('.total-items').textContent = operation.items.length;
        
        // Update status counts
        modal.querySelector('.success-count').textContent = operation.successCount;
        modal.querySelector('.failed-count').textContent = operation.failureCount;
        modal.querySelector('.pending-count').textContent = operation.pendingCount;
        
        // Update average time
        if (processedItems > 0 && operation.totalTime) {
            const avgTime = Math.round(operation.totalTime / processedItems);
            modal.querySelector('.avg-time').textContent = `${avgTime}ms`;
        }
        
        // Update log
        const logContainer = modal.querySelector('.log-entries');
        const latestEntries = operation.log.slice(-10); // Show last 10 entries
        logContainer.innerHTML = latestEntries.map(entry => 
            `<li class="log-entry ${entry.type}">
                <span class="timestamp">${new Date(entry.timestamp).toLocaleTimeString()}</span>
                <span class="message">${entry.message}</span>
            </li>`
        ).join('');
        
        // Scroll to bottom
        logContainer.scrollTop = logContainer.scrollHeight;
        
        // Update cancel button
        const cancelBtn = modal.querySelector('.cancel-operation-btn');
        if (operation.status === 'completed' || operation.status === 'cancelled') {
            cancelBtn.style.display = 'none';
        }
    }

    /**
     * Confirm dangerous operations
     */
    async confirmDangerousOperation(operationType) {
        const count = this.selectedItems.size;
        const message = operationType === 'delete' ? 
            `Are you sure you want to delete ${count} items? This action cannot be undone.` :
            `Are you sure you want to update ${count} items? This will modify their configuration.`;
        
        return confirm(message);
    }

    /**
     * Clear selection
     */
    clearSelection() {
        this.selectedItems.clear();
        
        // Uncheck all checkboxes
        document.querySelectorAll('.batch-select-item').forEach(checkbox => {
            checkbox.checked = false;
        });
        document.querySelectorAll('.batch-select-all').forEach(checkbox => {
            checkbox.checked = false;
            checkbox.indeterminate = false;
        });
        
        this.updateSelectionDisplay();
        this.onSelectionChange([]);
    }

    /**
     * Utility methods
     */
    generateOperationId() {
        return 'batch_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
    }

    chunkArray(array, chunkSize) {
        const chunks = [];
        for (let i = 0; i < array.length; i += chunkSize) {
            chunks.push(array.slice(i, i + chunkSize));
        }
        return chunks;
    }

    delay(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }

    updateMetrics(operation) {
        this.metrics.totalOperations++;
        this.metrics.totalItemsProcessed += operation.items.length;
        
        // Update average processing time
        const totalTime = this.operationHistory.reduce((sum, op) => sum + (op.totalTime || 0), 0);
        this.metrics.averageProcessingTime = totalTime / this.metrics.totalOperations;
        
        // Update success rate
        const totalSuccess = this.operationHistory.reduce((sum, op) => sum + op.successCount, 0);
        this.metrics.successRate = (totalSuccess / this.metrics.totalItemsProcessed) * 100;
    }

    handleOperationError(operation, error) {
        operation.status = 'error';
        operation.log.push({
            timestamp: Date.now(),
            message: `Operation failed: ${error.message}`,
            type: 'error'
        });
        this.updateProgressDisplay(operation);
        this.onError(error);
    }

    showError(message) {
        // Use toast notification or alert
        if (window.CNOCUIUpdates) {
            window.CNOCUIUpdates.showToast(message, 'error');
        } else {
            alert(message);
        }
    }

    /**
     * Get operation metrics
     */
    getMetrics() {
        return this.metrics;
    }

    /**
     * Get active operations
     */
    getActiveOperations() {
        return Array.from(this.activeOperations.values());
    }

    /**
     * Get operation history
     */
    getOperationHistory() {
        return this.operationHistory;
    }
}

// Initialize global batch operations manager
window.batchManager = null;

document.addEventListener('DOMContentLoaded', function() {
    window.batchManager = new CNOCBatchOperationsManager({
        onProgressUpdate: (operation) => {
            console.log(`Operation ${operation.id} progress: ${operation.progress}%`);
        },
        onOperationComplete: (operation) => {
            console.log(`Operation ${operation.id} completed:`, operation);
            // Show success message
            if (window.CNOCUIUpdates) {
                const message = `${operation.type} operation completed: ${operation.successCount} successful, ${operation.failureCount} failed`;
                const type = operation.failureCount > 0 ? 'warning' : 'success';
                window.CNOCUIUpdates.showToast(message, type);
            }
        },
        onSelectionChange: (selectedItems) => {
            console.log(`Selection changed: ${selectedItems.length} items selected`);
        }
    });
});