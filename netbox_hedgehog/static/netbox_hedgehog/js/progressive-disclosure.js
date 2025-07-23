/**
 * Progressive Disclosure JavaScript
 * Handles collapsible sections, real-time updates, and user interactions
 */

class ProgressiveDisclosure {
    constructor() {
        this.sections = new Map();
        this.preferences = this.loadUserPreferences();
        this.realtimeUpdater = null;
        this.init();
    }

    init() {
        this.bindSectionToggles();
        this.initializeRealtimeUpdates();
        this.setupKeyboardNavigation();
        this.restoreUserPreferences();
        this.bindOperationButtons();
    }

    bindSectionToggles() {
        document.querySelectorAll('.section-toggle').forEach(toggle => {
            const section = toggle.closest('.dashboard-section');
            const content = section.querySelector('.section-content');
            const sectionId = section.dataset.section;
            
            this.sections.set(sectionId, {
                toggle: toggle,
                content: content,
                section: section,
                expanded: !content.classList.contains('collapsed')
            });

            toggle.addEventListener('click', (e) => {
                e.preventDefault();
                this.toggleSection(sectionId);
            });

            // Add keyboard support
            toggle.addEventListener('keydown', (e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    this.toggleSection(sectionId);
                }
            });
        });
    }

    toggleSection(sectionId) {
        const sectionData = this.sections.get(sectionId);
        if (!sectionData) return;

        const { toggle, content, section } = sectionData;
        const isExpanded = !content.classList.contains('collapsed');

        if (isExpanded) {
            // Collapse section
            content.classList.add('collapsed');
            toggle.classList.add('collapsed');
            toggle.setAttribute('aria-expanded', 'false');
            this.animateCollapse(content);
        } else {
            // Expand section
            content.classList.remove('collapsed');
            toggle.classList.remove('collapsed');
            toggle.setAttribute('aria-expanded', 'true');
            this.animateExpand(content);
        }

        // Update internal state
        sectionData.expanded = !isExpanded;
        
        // Save user preference
        this.saveUserPreference(sectionId, !isExpanded);
        
        // Announce change to screen readers
        this.announceToScreenReader(
            `Section ${toggle.textContent.trim()} ${isExpanded ? 'collapsed' : 'expanded'}`
        );
    }

    animateCollapse(content) {
        // Get current height
        const currentHeight = content.scrollHeight;
        content.style.maxHeight = currentHeight + 'px';
        
        // Force reflow
        content.offsetHeight;
        
        // Animate to 0
        content.style.transition = 'max-height 0.3s ease-out, padding 0.3s ease-out';
        content.style.maxHeight = '0px';
        content.style.paddingTop = '0px';
        content.style.paddingBottom = '0px';
        
        setTimeout(() => {
            content.style.transition = '';
            content.style.maxHeight = '';
            content.style.paddingTop = '';
            content.style.paddingBottom = '';
        }, 300);
    }

    animateExpand(content) {
        // Get target height
        content.style.maxHeight = 'none';
        const targetHeight = content.scrollHeight;
        content.style.maxHeight = '0px';
        content.style.paddingTop = '0px';
        content.style.paddingBottom = '0px';
        
        // Force reflow
        content.offsetHeight;
        
        // Animate to target height
        content.style.transition = 'max-height 0.3s ease-out, padding 0.3s ease-out';
        content.style.maxHeight = targetHeight + 'px';
        content.style.paddingTop = '1.5rem';
        content.style.paddingBottom = '1.5rem';
        
        setTimeout(() => {
            content.style.transition = '';
            content.style.maxHeight = '';
            content.style.paddingTop = '';
            content.style.paddingBottom = '';
        }, 300);
    }

    initializeRealtimeUpdates() {
        const fabricId = document.body.dataset.fabricId;
        if (!fabricId) return;

        this.realtimeUpdater = new RealtimeStatusUpdater(fabricId);
        this.realtimeUpdater.onUpdate = (data) => {
            this.updateStatusCards(data);
            this.updateSectionContent(data);
        };
        this.realtimeUpdater.start();
    }

    updateStatusCards(data) {
        // Update connection status
        const connectionStatus = document.querySelector('[data-connection-status]');
        if (connectionStatus && data.connection_status) {
            this.updateStatusBadge(connectionStatus, data.connection_status);
        }

        // Update sync status
        const syncStatus = document.querySelector('[data-sync-status]');
        if (syncStatus && data.sync_status) {
            this.updateStatusBadge(syncStatus, data.sync_status);
        }

        // Update CRD counts
        if (data.crd_counts) {
            Object.keys(data.crd_counts).forEach(type => {
                const element = document.querySelector(`[data-crd-count="${type}"]`);
                if (element) {
                    this.animateCountChange(element, data.crd_counts[type]);
                }
            });
        }
    }

    updateStatusBadge(element, status) {
        const statusMap = {
            'connected': { class: 'bg-success', text: 'Connected' },
            'disconnected': { class: 'bg-danger', text: 'Disconnected' },
            'error': { class: 'bg-danger', text: 'Error' },
            'in_sync': { class: 'bg-success', text: 'In Sync' },
            'out_of_sync': { class: 'bg-warning', text: 'Out of Sync' },
            'syncing': { class: 'bg-info', text: 'Syncing' },
            'never_synced': { class: 'bg-secondary', text: 'Never Synced' }
        };

        const statusInfo = statusMap[status] || { class: 'bg-secondary', text: 'Unknown' };
        
        // Remove old classes
        element.className = element.className.replace(/bg-\w+/g, '');
        element.classList.add('badge', statusInfo.class);
        element.textContent = statusInfo.text;
        
        // Add pulse animation for changes
        element.classList.add('fade-in');
        setTimeout(() => element.classList.remove('fade-in'), 300);
    }

    animateCountChange(element, newValue) {
        const currentValue = parseInt(element.textContent) || 0;
        if (currentValue === newValue) return;

        // Animate the number change
        const increment = newValue > currentValue ? 1 : -1;
        const duration = Math.min(500, Math.abs(newValue - currentValue) * 50);
        const steps = Math.abs(newValue - currentValue);
        const stepDuration = duration / steps;

        let currentStep = 0;
        const interval = setInterval(() => {
            currentStep++;
            const value = currentValue + (increment * currentStep);
            element.textContent = value;
            
            if (currentStep >= steps) {
                clearInterval(interval);
                element.textContent = newValue;
            }
        }, stepDuration);

        // Add highlight effect
        element.classList.add('fade-in');
        setTimeout(() => element.classList.remove('fade-in'), duration);
    }

    updateSectionContent(data) {
        // Update GitOps section if present
        if (data.gitops_status) {
            const gitopsSection = document.querySelector('[data-section="gitops"]');
            if (gitopsSection) {
                this.updateGitOpsSection(gitopsSection, data.gitops_status);
            }
        }

        // Update last sync time
        if (data.last_sync) {
            const lastSyncElements = document.querySelectorAll('[data-last-sync]');
            lastSyncElements.forEach(element => {
                element.textContent = this.formatRelativeTime(data.last_sync);
            });
        }
    }

    updateGitOpsSection(section, gitopsData) {
        // Update drift status
        const driftDisplay = section.querySelector('#gitops-state-display');
        if (driftDisplay && gitopsData.drift_status) {
            this.updateDriftStatus(driftDisplay, gitopsData.drift_status);
        }

        // Update file counts
        if (gitopsData.file_counts) {
            const rawCount = section.querySelector('[data-raw-files]');
            const managedCount = section.querySelector('[data-managed-files]');
            
            if (rawCount) rawCount.textContent = gitopsData.file_counts.raw || 0;
            if (managedCount) managedCount.textContent = gitopsData.file_counts.managed || 0;
        }
    }

    updateDriftStatus(element, driftStatus) {
        const statusMap = {
            'in_sync': {
                badge: 'bg-success',
                icon: 'mdi-check-circle',
                text: 'SYNCED',
                description: 'Git and cluster are aligned'
            },
            'drift_detected': {
                badge: 'bg-warning',
                icon: 'mdi-alert-circle',
                text: 'DRIFT DETECTED',
                description: 'Changes detected between Git and cluster'
            },
            'conflicts': {
                badge: 'bg-danger',
                icon: 'mdi-close-circle',
                text: 'CONFLICTS',
                description: 'Conflicting changes require manual resolution'
            }
        };

        const status = statusMap[driftStatus] || statusMap['in_sync'];
        
        element.innerHTML = `
            <span class="badge ${status.badge}">
                <i class="mdi ${status.icon}"></i> ${status.text}
            </span>
            <small class="text-muted ms-2">${status.description}</small>
        `;
    }

    bindOperationButtons() {
        // Sync from Git button
        const syncButton = document.querySelector('[data-operation="sync-git"]');
        if (syncButton) {
            syncButton.addEventListener('click', (e) => {
                e.preventDefault();
                this.executeSyncOperation(syncButton);
            });
        }

        // GitOps sync button  
        const gitopsSyncButton = document.querySelector('[data-operation="gitops-sync"]');
        if (gitopsSyncButton) {
            gitopsSyncButton.addEventListener('click', (e) => {
                e.preventDefault();
                this.executeGitOpsSyncOperation(gitopsSyncButton);
            });
        }

        // Initialize GitOps button
        const initGitOpsButton = document.querySelector('[data-operation="init-gitops"]');
        if (initGitOpsButton) {
            initGitOpsButton.addEventListener('click', (e) => {
                e.preventDefault();
                this.executeInitGitOpsOperation(initGitOpsButton);
            });
        }
    }

    async executeSyncOperation(button) {
        const fabricId = document.body.dataset.fabricId;
        const progressContainer = document.querySelector('#sync-progress');
        
        try {
            // Show progress
            this.showOperationProgress(button, progressContainer, 'Syncing from Git...');
            
            const response = await fetch(`/api/plugins/hedgehog/gitops-fabrics/${fabricId}/gitops_sync/`, {
                method: 'POST',
                headers: {
                    'Authorization': `Token ${this.getAuthToken()}`,
                    'Content-Type': 'application/json',
                },
            });

            const result = await response.json();
            
            if (result.success) {
                this.showOperationSuccess(button, progressContainer, 'Sync completed successfully');
                // Trigger a page refresh or update status
                setTimeout(() => window.location.reload(), 2000);
            } else {
                this.showOperationError(button, progressContainer, result.error || 'Sync failed');
            }
        } catch (error) {
            this.showOperationError(button, progressContainer, 'Network error occurred');
        }
    }

    async executeInitGitOpsOperation(button) {
        const fabricId = document.body.dataset.fabricId;
        const progressContainer = document.querySelector('#init-gitops-progress');
        
        try {
            this.showOperationProgress(button, progressContainer, 'Initializing GitOps structure...');
            
            const response = await fetch(`/api/plugins/hedgehog/fabrics/${fabricId}/init-gitops/`, {
                method: 'POST',
                headers: {
                    'Authorization': `Token ${this.getAuthToken()}`,
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ force: false })
            });

            const result = await response.json();
            
            if (result.success) {
                this.showOperationSuccess(button, progressContainer, 'GitOps initialized successfully');
                setTimeout(() => window.location.reload(), 2000);
            } else {
                this.showOperationError(button, progressContainer, result.error || 'Initialization failed');
            }
        } catch (error) {
            this.showOperationError(button, progressContainer, 'Network error occurred');
        }
    }

    showOperationProgress(button, progressContainer, message) {
        button.disabled = true;
        button.innerHTML = `<i class="mdi mdi-loading mdi-spin"></i> ${message}`;
        
        if (progressContainer) {
            progressContainer.classList.add('active');
            const progressFill = progressContainer.querySelector('.progress-fill');
            if (progressFill) {
                progressFill.style.width = '50%';
            }
        }
    }

    showOperationSuccess(button, progressContainer, message) {
        button.innerHTML = `<i class="mdi mdi-check"></i> ${message}`;
        button.classList.add('btn-success');
        
        if (progressContainer) {
            const progressFill = progressContainer.querySelector('.progress-fill');
            if (progressFill) {
                progressFill.style.width = '100%';
            }
        }
        
        // Reset after delay
        setTimeout(() => {
            button.disabled = false;
            button.classList.remove('btn-success');
            if (progressContainer) {
                progressContainer.classList.remove('active');
            }
        }, 3000);
    }

    showOperationError(button, progressContainer, message) {
        button.innerHTML = `<i class="mdi mdi-alert"></i> ${message}`;
        button.classList.add('btn-danger');
        
        if (progressContainer) {
            progressContainer.classList.remove('active');
        }
        
        // Reset after delay
        setTimeout(() => {
            button.disabled = false;
            button.classList.remove('btn-danger');
        }, 5000);
    }

    setupKeyboardNavigation() {
        // Add keyboard shortcuts
        document.addEventListener('keydown', (e) => {
            // Alt + number keys to toggle sections
            if (e.altKey && e.key >= '1' && e.key <= '9') {
                e.preventDefault();
                const sectionIndex = parseInt(e.key) - 1;
                const sections = Array.from(this.sections.keys());
                if (sections[sectionIndex]) {
                    this.toggleSection(sections[sectionIndex]);
                }
            }
            
            // Alt + A to expand all sections
            if (e.altKey && e.key.toLowerCase() === 'a') {
                e.preventDefault();
                this.expandAllSections();
            }
            
            // Alt + C to collapse all sections
            if (e.altKey && e.key.toLowerCase() === 'c') {
                e.preventDefault();
                this.collapseAllSections();
            }
        });
    }

    expandAllSections() {
        this.sections.forEach((data, sectionId) => {
            if (!data.expanded) {
                this.toggleSection(sectionId);
            }
        });
    }

    collapseAllSections() {
        this.sections.forEach((data, sectionId) => {
            if (data.expanded) {
                this.toggleSection(sectionId);
            }
        });
    }

    // User Preferences Management
    loadUserPreferences() {
        try {
            const saved = localStorage.getItem('hedgehog-dashboard-preferences');
            return saved ? JSON.parse(saved) : {};
        } catch {
            return {};
        }
    }

    saveUserPreference(sectionId, expanded) {
        this.preferences[sectionId] = expanded;
        try {
            localStorage.setItem('hedgehog-dashboard-preferences', JSON.stringify(this.preferences));
        } catch {
            // Ignore storage errors
        }
    }

    restoreUserPreferences() {
        Object.keys(this.preferences).forEach(sectionId => {
            const sectionData = this.sections.get(sectionId);
            const shouldExpand = this.preferences[sectionId];
            
            if (sectionData && sectionData.expanded !== shouldExpand) {
                this.toggleSection(sectionId);
            }
        });
    }

    // Utility Methods
    getAuthToken() {
        // Get token from meta tag or cookie
        const meta = document.querySelector('meta[name="api-token"]');
        return meta ? meta.content : '';
    }

    formatRelativeTime(timestamp) {
        const now = new Date();
        const time = new Date(timestamp);
        const diffMs = now - time;
        const diffSec = Math.floor(diffMs / 1000);
        
        if (diffSec < 60) return `${diffSec} seconds ago`;
        if (diffSec < 3600) return `${Math.floor(diffSec / 60)} minutes ago`;
        if (diffSec < 86400) return `${Math.floor(diffSec / 3600)} hours ago`;
        return `${Math.floor(diffSec / 86400)} days ago`;
    }

    announceToScreenReader(message) {
        const announcement = document.createElement('div');
        announcement.setAttribute('aria-live', 'polite');
        announcement.setAttribute('aria-atomic', 'true');
        announcement.className = 'sr-only';
        announcement.textContent = message;
        
        document.body.appendChild(announcement);
        setTimeout(() => document.body.removeChild(announcement), 1000);
    }
}

// Real-time Status Updater
class RealtimeStatusUpdater {
    constructor(fabricId) {
        this.fabricId = fabricId;
        this.interval = null;
        this.onUpdate = null;
        this.updateInterval = 30000; // 30 seconds
    }

    start() {
        this.update(); // Initial update
        this.interval = setInterval(() => this.update(), this.updateInterval);
    }

    stop() {
        if (this.interval) {
            clearInterval(this.interval);
            this.interval = null;
        }
    }

    async update() {
        try {
            const response = await fetch(`/api/plugins/hedgehog/fabrics/${this.fabricId}/gitops-status/`, {
                headers: {
                    'Authorization': `Token ${this.getAuthToken()}`
                }
            });
            
            if (response.ok) {
                const data = await response.json();
                if (this.onUpdate) {
                    this.onUpdate(data);
                }
            }
        } catch (error) {
            console.warn('Failed to update status:', error);
        }
    }

    getAuthToken() {
        const meta = document.querySelector('meta[name="api-token"]');
        return meta ? meta.content : '';
    }
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    new ProgressiveDisclosure();
});