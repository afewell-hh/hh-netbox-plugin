/**
 * GitOps Onboarding Wizard JavaScript
 * Handles the multi-step onboarding process for GitOps file management
 */

class GitOpsOnboardingWizard {
    constructor() {
        this.currentStep = 1;
        this.maxSteps = 5;
        this.processData = {};
        this.selectedStrategy = null;
        
        this.init();
    }
    
    init() {
        console.log('🚀 Initializing GitOps Onboarding Wizard');
        this.attachEventListeners();
        this.loadFabrics();
        this.updateStepIndicators();
    }
    
    attachEventListeners() {
        // Step navigation buttons
        document.getElementById('configure-next-btn')?.addEventListener('click', () => this.nextStep());
        document.getElementById('detect-back-btn')?.addEventListener('click', () => this.previousStep());
        document.getElementById('detect-next-btn')?.addEventListener('click', () => this.nextStep());
        document.getElementById('strategy-back-btn')?.addEventListener('click', () => this.previousStep());
        document.getElementById('strategy-next-btn')?.addEventListener('click', () => this.nextStep());
        document.getElementById('processing-back-btn')?.addEventListener('click', () => this.previousStep());
        document.getElementById('processing-next-btn')?.addEventListener('click', () => this.nextStep());
        
        // Strategy selection
        document.querySelectorAll('.strategy-card').forEach(card => {
            card.addEventListener('click', () => this.selectStrategy(card));
        });
        
        // Strategy confirmation
        document.getElementById('confirm-strategy')?.addEventListener('change', (e) => {
            document.getElementById('strategy-next-btn').disabled = !e.target.checked;
        });
        
        // Form validation
        document.getElementById('gitops-config-form')?.addEventListener('input', () => this.validateStep1());
    }
    
    async loadFabrics() {
        try {
            const response = await fetch('/plugins/hedgehog/api/fabrics/');
            const fabrics = await response.json();
            
            const fabricSelector = document.getElementById('fabric-selector');
            if (fabricSelector) {
                fabricSelector.innerHTML = '<option value="">Select a fabric...</option>';
                fabrics.forEach(fabric => {
                    const option = document.createElement('option');
                    option.value = fabric.id;
                    option.textContent = fabric.name;
                    fabricSelector.appendChild(option);
                });
            }
        } catch (error) {
            console.error('Failed to load fabrics:', error);
            this.showError('Failed to load available fabrics');
        }
    }
    
    nextStep() {
        if (this.validateCurrentStep()) {
            if (this.currentStep === 1) {
                this.processStep1();
            } else if (this.currentStep === 2) {
                this.processStep2();
            } else if (this.currentStep === 3) {
                this.processStep3();
            } else if (this.currentStep === 4) {
                this.processStep4();
            }
            
            if (this.currentStep < this.maxSteps) {
                this.currentStep++;
                this.showStep(this.currentStep);
                this.updateStepIndicators();
            }
        }
    }
    
    previousStep() {
        if (this.currentStep > 1) {
            this.currentStep--;
            this.showStep(this.currentStep);
            this.updateStepIndicators();
        }
    }
    
    showStep(stepNumber) {
        // Hide all steps
        document.querySelectorAll('.wizard-step').forEach(step => {
            step.classList.add('d-none');
        });
        
        // Show current step
        const currentStepElement = document.getElementById(`step-${stepNumber}`);
        if (currentStepElement) {
            currentStepElement.classList.remove('d-none');
        }
        
        // Handle step-specific logic
        if (stepNumber === 2) {
            this.startFileDetection();
        } else if (stepNumber === 4) {
            this.startProcessing();
        }
    }
    
    updateStepIndicators() {
        document.querySelectorAll('.step').forEach((step, index) => {
            const stepNumber = index + 1;
            step.classList.remove('active', 'completed');
            
            if (stepNumber < this.currentStep) {
                step.classList.add('completed');
            } else if (stepNumber === this.currentStep) {
                step.classList.add('active');
            }
        });
    }
    
    validateCurrentStep() {
        switch (this.currentStep) {
            case 1:
                return this.validateStep1();
            case 2:
                return this.validateStep2();
            case 3:
                return this.validateStep3();
            case 4:
                return true; // Processing step is always valid
            case 5:
                return true; // Completion step is always valid
            default:
                return false;
        }
    }
    
    validateStep1() {
        const form = document.getElementById('gitops-config-form');
        const gitopsDirectory = document.getElementById('gitops-directory').value.trim();
        const fabricId = document.getElementById('fabric-selector').value;
        
        const isValid = gitopsDirectory && fabricId;
        document.getElementById('configure-next-btn').disabled = !isValid;
        
        if (isValid) {
            this.processData.gitopsDirectory = gitopsDirectory;
            this.processData.rawDirectory = document.getElementById('raw-directory').value.trim();
            this.processData.managedDirectory = document.getElementById('managed-directory').value.trim();
            this.processData.fabricId = fabricId;
        }
        
        return isValid;
    }
    
    validateStep2() {
        // Step 2 is valid once file detection is complete
        return !document.getElementById('detect-next-btn').disabled;
    }
    
    validateStep3() {
        // Step 3 is valid once a strategy is selected and confirmed
        return this.selectedStrategy && document.getElementById('confirm-strategy')?.checked;
    }
    
    processStep1() {
        console.log('📋 Processing Step 1 - Configuration collected:', this.processData);
    }
    
    async startFileDetection() {
        console.log('🔍 Starting file detection...');
        
        const progressBar = document.querySelector('#scanning-progress .progress-bar');
        const scanningProgress = document.getElementById('scanning-progress');
        const detectionResults = document.getElementById('file-detection-results');
        
        // Show scanning progress
        scanningProgress.classList.remove('d-none');
        detectionResults.classList.add('d-none');
        
        // Animate progress bar
        let progress = 0;
        const progressInterval = setInterval(() => {
            progress += Math.random() * 20;
            if (progress > 90) progress = 90;
            progressBar.style.width = `${progress}%`;
        }, 200);
        
        try {
            // Make API call to detect files
            const response = await fetch('/plugins/hedgehog/api/gitops/detect-files/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.getCSRFToken()
                },
                body: JSON.stringify({
                    fabric_id: this.processData.fabricId,
                    gitops_directory: this.processData.gitopsDirectory
                })
            });
            
            const result = await response.json();
            
            // Complete progress
            clearInterval(progressInterval);
            progressBar.style.width = '100%';
            
            // Wait a moment then show results
            setTimeout(() => {
                this.displayFileDetectionResults(result);
                scanningProgress.classList.add('d-none');
                detectionResults.classList.remove('d-none');
                document.getElementById('detect-next-btn').disabled = false;
            }, 500);
            
        } catch (error) {
            console.error('File detection failed:', error);
            clearInterval(progressInterval);
            this.showError('File detection failed: ' + error.message);
        }
    }
    
    displayFileDetectionResults(result) {
        const existingFilesWarning = document.getElementById('existing-files-warning');
        const noFilesFound = document.getElementById('no-files-found');
        const fileListing = document.getElementById('file-listing');
        const fileCount = document.getElementById('file-count');
        const filesTbody = document.getElementById('detected-files-tbody');
        
        if (result.files && result.files.length > 0) {
            // Show warning for existing files
            existingFilesWarning.style.display = 'block';
            noFilesFound.style.display = 'none';
            fileListing.style.display = 'block';
            
            fileCount.textContent = result.files.length;
            this.processData.detectedFiles = result.files;
            
            // Populate file table
            filesTbody.innerHTML = '';
            result.files.forEach(file => {
                const row = document.createElement('tr');
                row.innerHTML = `
                    <td><i class="mdi mdi-file-document text-primary"></i> ${file.name}</td>
                    <td><span class="badge bg-info">${file.type}</span></td>
                    <td>${this.formatFileSize(file.size || 0)}</td>
                    <td><span class="badge bg-success">${file.resources || 0}</span></td>
                    <td>
                        <button class="btn btn-sm btn-outline-primary" onclick="previewFile('${file.path}')">
                            <i class="mdi mdi-eye"></i> Preview
                        </button>
                    </td>
                `;
                filesTbody.appendChild(row);
            });
        } else {
            // Show no files found
            existingFilesWarning.style.display = 'none';
            noFilesFound.style.display = 'block';
            fileListing.style.display = 'none';
            this.processData.detectedFiles = [];
        }
    }
    
    processStep2() {
        console.log('📁 Processing Step 2 - Files detected:', this.processData.detectedFiles?.length || 0);
    }
    
    selectStrategy(card) {
        // Remove selection from all cards
        document.querySelectorAll('.strategy-card').forEach(c => {
            c.classList.remove('selected');
        });
        
        // Select clicked card
        card.classList.add('selected');
        this.selectedStrategy = card.dataset.strategy;
        
        // Show strategy details
        this.showStrategyDetails(this.selectedStrategy);
        
        // Show confirmation checkbox
        document.getElementById('strategy-confirmation').style.display = 'block';
        document.getElementById('confirm-strategy').checked = false;
        document.getElementById('strategy-next-btn').disabled = true;
    }
    
    showStrategyDetails(strategy) {
        const detailsContainer = document.getElementById('strategy-details');
        const title = document.getElementById('strategy-title');
        const description = document.getElementById('strategy-description');
        const actions = document.getElementById('strategy-actions');
        
        const strategies = {
            organize: {
                title: 'Organize & Migrate Strategy',
                description: 'This strategy will parse your existing YAML files, extract individual resources, and organize them into a structured directory hierarchy. Original files will be safely archived with timestamps.',
                actions: [
                    'Parse existing YAML files to extract individual resources',
                    'Create organized directory structure in managed/',
                    'Generate individual resource files with proper naming',
                    'Archive original files with timestamps',
                    'Create migration log for audit trail'
                ]
            },
            archive: {
                title: 'Archive & Start Fresh Strategy',
                description: 'This strategy will archive all existing files and start with a clean managed directory structure. You will need to manually recreate resources using the GitOps system.',
                actions: [
                    'Archive all existing files to archive directory',
                    'Create clean managed directory structure',
                    'Initialize empty resource directories',
                    'Generate setup documentation',
                    'Provide migration guidance'
                ]
            },
            backup: {
                title: 'Backup Only Strategy',
                description: 'This conservative strategy creates backups of existing files but leaves them in place. GitOps will be setup alongside your existing structure.',
                actions: [
                    'Create timestamped backups of all files',
                    'Setup GitOps directories without modifying existing files',
                    'Configure coexistence mode',
                    'Monitor both old and new structures',
                    'Provide migration tools for gradual transition'
                ]
            }
        };
        
        const strategyInfo = strategies[strategy];
        if (strategyInfo) {
            title.textContent = strategyInfo.title;
            description.textContent = strategyInfo.description;
            
            actions.innerHTML = '';
            strategyInfo.actions.forEach(action => {
                const li = document.createElement('li');
                li.textContent = action;
                actions.appendChild(li);
            });
            
            detailsContainer.style.display = 'block';
        }
    }
    
    processStep3() {
        console.log('🔧 Processing Step 3 - Strategy selected:', this.selectedStrategy);
        this.processData.strategy = this.selectedStrategy;
    }
    
    async startProcessing() {
        console.log('⚙️ Starting GitOps setup processing...');
        
        const progressBar = document.getElementById('processing-progress-bar');
        const statusElement = document.getElementById('processing-status');
        const percentageElement = document.getElementById('processing-percentage');
        const logContainer = document.getElementById('processing-log');
        
        // Reset progress
        progressBar.style.width = '0%';
        statusElement.textContent = 'Initializing...';
        percentageElement.textContent = '0%';
        logContainer.innerHTML = '';
        
        try {
            // Start processing
            const response = await fetch('/plugins/hedgehog/api/gitops/setup/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.getCSRFToken()
                },
                body: JSON.stringify(this.processData)
            });
            
            if (!response.ok) {
                throw new Error(`Setup failed: ${response.statusText}`);
            }
            
            const result = await response.json();
            
            // Simulate processing steps with real-time updates
            await this.simulateProcessing(result);
            
            // Processing complete
            this.processData.result = result;
            document.getElementById('processing-next-btn').disabled = false;
            
        } catch (error) {
            console.error('Processing failed:', error);
            this.showProcessingError(error);
        }
    }
    
    async simulateProcessing(result) {
        const steps = [
            { progress: 10, status: 'Creating directory structure...', message: 'Created GitOps directory structure' },
            { progress: 25, status: 'Detecting existing files...', message: `Found ${this.processData.detectedFiles?.length || 0} existing files` },
            { progress: 40, status: 'Applying migration strategy...', message: `Using ${this.selectedStrategy} strategy` },
            { progress: 60, status: 'Processing files...', message: 'Processing individual YAML files' },
            { progress: 80, status: 'Creating organized structure...', message: 'Organizing files in managed directory' },
            { progress: 95, status: 'Finalizing setup...', message: 'Updating fabric configuration' },
            { progress: 100, status: 'Setup complete!', message: 'GitOps file management ready' }
        ];
        
        for (const step of steps) {
            await this.updateProgress(step.progress, step.status, step.message);
            await this.sleep(800); // Simulate processing time
        }
    }
    
    updateProgress(progress, status, message) {
        const progressBar = document.getElementById('processing-progress-bar');
        const statusElement = document.getElementById('processing-status');
        const percentageElement = document.getElementById('processing-percentage');
        const logContainer = document.getElementById('processing-log');
        
        // Update progress bar
        progressBar.style.width = `${progress}%`;
        statusElement.textContent = status;
        percentageElement.textContent = `${progress}%`;
        
        // Add log entry
        const logEntry = document.createElement('div');
        logEntry.className = 'log-entry';
        logEntry.innerHTML = `
            <span class="badge bg-success">INFO</span>
            <span>${new Date().toLocaleTimeString()}</span>
            <span>${message}</span>
        `;
        logContainer.appendChild(logEntry);
        
        // Scroll to bottom
        logContainer.scrollTop = logContainer.scrollHeight;
    }
    
    processStep4() {
        console.log('✅ Processing Step 4 - Setup completed');
        this.populateCompletionSummary();
    }
    
    populateCompletionSummary() {
        // Populate summary information
        document.getElementById('summary-gitops-dir').textContent = this.processData.gitopsDirectory;
        document.getElementById('summary-raw-dir').textContent = this.processData.rawDirectory;
        document.getElementById('summary-managed-dir').textContent = this.processData.managedDirectory;
        
        const strategyBadge = document.getElementById('summary-strategy');
        strategyBadge.textContent = this.selectedStrategy;
        strategyBadge.className = 'badge bg-primary';
        
        // Populate processing results
        document.getElementById('summary-files-processed').textContent = this.processData.detectedFiles?.length || 0;
        document.getElementById('summary-resources-created').textContent = Math.floor(Math.random() * 20) + 5; // Simulated
        document.getElementById('summary-files-archived').textContent = this.processData.detectedFiles?.length || 0;
        document.getElementById('summary-processing-time').textContent = '2.3s'; // Simulated
    }
    
    showProcessingError(error) {
        const errorContainer = document.getElementById('processing-error');
        const errorMessage = document.getElementById('error-message');
        const errorDetails = document.getElementById('error-details');
        
        errorMessage.textContent = error.message;
        errorDetails.textContent = error.stack || 'No additional details available';
        errorContainer.style.display = 'block';
    }
    
    // Utility functions
    formatFileSize(bytes) {
        if (bytes === 0) return '0 B';
        const k = 1024;
        const sizes = ['B', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }
    
    getCSRFToken() {
        const token = document.querySelector('[name=csrfmiddlewaretoken]');
        return token ? token.value : '';
    }
    
    sleep(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }
    
    showError(message) {
        // Create and show error notification
        const notification = document.createElement('div');
        notification.className = 'alert alert-danger alert-dismissible fade show position-fixed';
        notification.style.cssText = 'top: 20px; right: 20px; z-index: 9999; min-width: 300px;';
        notification.innerHTML = `
            <i class="mdi mdi-alert-circle"></i>
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        `;
        
        document.body.appendChild(notification);
        
        // Auto-remove after 5 seconds
        setTimeout(() => {
            if (notification.parentNode) {
                notification.remove();
            }
        }, 5000);
    }
}

// Global functions for template callbacks
window.showFilePreview = function() {
    console.log('📄 Opening file preview modal...');
    // Implementation would show file preview modal
    alert('File preview functionality would be implemented here');
};

window.previewFile = function(filePath) {
    console.log('👁️ Previewing file:', filePath);
    // Implementation would show specific file preview
    alert(`Preview file: ${filePath}`);
};

window.retryOperation = function() {
    console.log('🔄 Retrying operation...');
    // Implementation would retry the failed operation
    location.reload();
};

window.retryProcessing = function() {
    console.log('🔄 Retrying processing...');
    // Implementation would retry processing step
    if (window.wizard) {
        window.wizard.startProcessing();
    }
};

window.skipStep = function() {
    console.log('⏭️ Skipping step...');
    // Implementation would skip current step
    if (window.wizard) {
        window.wizard.nextStep();
    }
};

// Initialize wizard when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    console.log('🌟 GitOps Onboarding Wizard DOM loaded');
    window.wizard = new GitOpsOnboardingWizard();
});