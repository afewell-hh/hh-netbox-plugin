# Drift Detection Design

**Purpose**: Comprehensive drift detection architecture for HNP GitOps monitoring  
**Status**: Basic UI implemented, enhanced detection approved for implementation  
**Current Feature**: Prominent drift detection UI with dynamic styling

## Drift Detection Overview

Drift detection serves as a first-class feature in HNP, providing immediate visibility into configuration differences between git repository content and synchronized database records. The design emphasizes operational importance through prominent UI placement and sophisticated visual design.

## User Interface Architecture

### Drift Spotlight Section Design
The drift detection interface occupies the second major section on fabric detail pages with prominent placement and dynamic styling:

```html
<!-- Drift Spotlight: Second Major Section -->
<div class="drift-spotlight">
    <div class="drift-header">
        <h3>Configuration Drift Status</h3>
        <div class="drift-status-badge">{{ drift_status }}</div>
    </div>
    
    <div class="drift-summary-cards">
        <div class="drift-summary-card">
            <div class="card-label">Resources with Drift</div>
            <div class="card-value">{{ drift_count }}/{{ total_resources }}</div>
        </div>
        <div class="drift-summary-card">
            <div class="card-label">Last Check</div>
            <div class="card-value">{{ last_check|timesince }} ago</div>
        </div>
        <div class="drift-summary-card">
            <div class="card-label">Severity Level</div>
            <div class="card-value">{{ severity_level }}</div>
        </div>
        <div class="drift-summary-card">
            <div class="card-label">Sync Status</div>
            <div class="card-value">{{ sync_status }}</div>
        </div>
    </div>
    
    <div class="drift-actions">
        <button class="btn btn-primary" onclick="analyzeDrift()">Analyze Drift</button>
        <button class="btn btn-success" onclick="syncFromGit()">Sync from Git</button>
        <button class="btn btn-info" onclick="checkForDrift()">Check for Drift</button>
        <button class="btn btn-secondary" onclick="configureDrift()">Configure Detection</button>
    </div>
</div>
```

### Dynamic Visual Design
Status-based background styling provides immediate visual feedback:

```css
/* Dynamic Background Styling */
.drift-spotlight.in-sync {
    background: linear-gradient(135deg, #28a745 0%, #20c997 100%);
    color: white;
}

.drift-spotlight.warning {
    background: linear-gradient(135deg, #ffc107 0%, #fd7e14 100%);
    color: white;
}

.drift-spotlight.critical {
    background: linear-gradient(135deg, #dc3545 0%, #e83e8c 100%);
    color: white;
}
```

### Responsive Grid Layout
```css
/* Summary Cards Grid */
.drift-summary-cards {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 1rem;
    margin: 1rem 0;
}

.drift-summary-card {
    background: rgba(255, 255, 255, 0.1);
    padding: 1rem;
    border-radius: 0.5rem;
    text-align: center;
}
```

## Drift Status Classification

### Status Hierarchy
```python
# Drift status enumeration:
DRIFT_STATUS_CHOICES = [
    ('in_sync', 'Configuration In Sync'),
    ('drift_detected', 'Configuration Drift Detected'),
    ('critical', 'Critical Drift Level'),
    ('unknown', 'Drift Status Unknown'),
    ('checking', 'Drift Check in Progress')
]
```

### Severity Level Calculation
```python
def calculate_drift_severity(drift_count, total_resources):
    """
    Calculate drift severity based on affected resource count
    """
    if drift_count == 0:
        return 'in_sync'
    elif drift_count > 5:
        return 'critical'
    elif drift_count >= 1:
        return 'important'
    else:
        return 'unknown'

# Severity level mapping:
SEVERITY_LEVELS = {
    'in_sync': {
        'label': 'All Resources In Sync',
        'color': 'success',
        'background_class': 'in-sync'
    },
    'important': {
        'label': '1-5 Resources with Drift',
        'color': 'warning', 
        'background_class': 'warning'
    },
    'critical': {
        'label': 'More than 5 Resources with Drift',
        'color': 'danger',
        'background_class': 'critical'
    }
}
```

## Drift Detection Logic

### Core Detection Algorithm
```python
def detect_configuration_drift(fabric):
    """
    Comprehensive drift detection between git repository and database
    """
    drift_results = {
        'total_resources': 0,
        'resources_with_drift': 0,
        'drift_details': [],
        'last_check': datetime.now(),
        'status': 'unknown'
    }
    
    try:
        # 1. Fetch current git repository content
        git_content = fetch_gitops_directory_content(
            fabric.git_repository,
            fabric.gitops_directory
        )
        
        # 2. Parse YAML files into expected CRD structure
        expected_crds = parse_yaml_files_to_crds(git_content)
        
        # 3. Fetch current database CRD records
        current_crds = fetch_fabric_crd_records(fabric)
        
        # 4. Compare expected vs current
        drift_analysis = compare_crd_configurations(expected_crds, current_crds)
        
        # 5. Generate drift summary
        drift_results.update({
            'total_resources': len(current_crds),
            'resources_with_drift': len(drift_analysis['differences']),
            'drift_details': drift_analysis['differences'],
            'status': calculate_drift_status(drift_analysis)
        })
        
    except Exception as e:
        drift_results['status'] = 'error'
        drift_results['error'] = str(e)
    
    return drift_results
```

### CRD Comparison Logic
```python
def compare_crd_configurations(expected_crds, current_crds):
    """
    Detailed comparison between expected and current CRD configurations
    """
    comparison_results = {
        'matching': [],
        'differences': [],
        'missing_in_db': [],
        'extra_in_db': []
    }
    
    # Create lookup dictionaries
    expected_lookup = {crd.identifier: crd for crd in expected_crds}
    current_lookup = {crd.identifier: crd for crd in current_crds}
    
    # Compare configurations
    for identifier, expected_crd in expected_lookup.items():
        if identifier in current_lookup:
            current_crd = current_lookup[identifier]
            if not crds_match(expected_crd, current_crd):
                comparison_results['differences'].append({
                    'identifier': identifier,
                    'expected': expected_crd.to_dict(),
                    'current': current_crd.to_dict(),
                    'differences': get_crd_differences(expected_crd, current_crd)
                })
            else:
                comparison_results['matching'].append(identifier)
        else:
            comparison_results['missing_in_db'].append(expected_crd)
    
    # Check for extra records in database
    for identifier, current_crd in current_lookup.items():
        if identifier not in expected_lookup:
            comparison_results['extra_in_db'].append(current_crd)
    
    return comparison_results
```

## Context Data Integration

### Fabric Detail View Integration
```python
class FabricDetailView(LoginRequiredMixin, DetailView):
    """
    Enhanced fabric detail view with drift detection context
    """
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        fabric = self.get_object()
        
        # Generate drift detection context
        drift_summary = self.generate_drift_context(fabric)
        context.update({
            'drift_summary': drift_summary,
            'drift_status_class': self.get_drift_status_class(drift_summary),
            'show_drift_actions': True
        })
        
        return context
    
    def generate_drift_context(self, fabric):
        """
        Generate comprehensive drift detection context for template
        """
        try:
            # Get cached drift results or perform fresh detection
            drift_results = self.get_or_compute_drift_results(fabric)
            
            return {
                'status': drift_results.get('status', 'unknown'),
                'count': drift_results.get('resources_with_drift', 0),
                'total': drift_results.get('total_resources', 0),
                'last_check': drift_results.get('last_check'),
                'severity': calculate_drift_severity(
                    drift_results.get('resources_with_drift', 0),
                    drift_results.get('total_resources', 0)
                ),
                'details': drift_results.get('drift_details', [])
            }
            
        except Exception as e:
            return {
                'status': 'error',
                'error': str(e),
                'count': 0,
                'total': fabric.cached_crd_count
            }
```

## Interactive Drift Actions

### Analyze Drift Modal
```javascript
// Drift analysis modal functionality
function analyzeDrift() {
    // Show loading state
    showDriftAnalysisModal();
    
    // Fetch detailed drift analysis
    fetch(`/api/fabrics/${fabricId}/analyze-drift/`, {
        method: 'POST',
        headers: {
            'X-CSRFToken': getCsrfToken(),
            'Content-Type': 'application/json'
        }
    })
    .then(response => response.json())
    .then(data => {
        populateDriftAnalysisModal(data);
    })
    .catch(error => {
        showDriftAnalysisError(error);
    });
}

// Drift analysis modal content
function populateDriftAnalysisModal(driftData) {
    const modalContent = `
        <div class="drift-analysis-details">
            <h4>Configuration Drift Analysis</h4>
            
            <div class="drift-summary">
                <p><strong>Total Resources:</strong> ${driftData.total_resources}</p>
                <p><strong>Resources with Drift:</strong> ${driftData.resources_with_drift}</p>
                <p><strong>Last Check:</strong> ${formatDateTime(driftData.last_check)}</p>
            </div>
            
            <div class="drift-details">
                ${driftData.drift_details.map(detail => `
                    <div class="drift-item">
                        <h5>${detail.identifier}</h5>
                        <div class="drift-changes">
                            ${detail.differences.map(diff => `
                                <div class="change-item">
                                    <strong>${diff.field}:</strong>
                                    <span class="old-value">${diff.old_value}</span> →
                                    <span class="new-value">${diff.new_value}</span>
                                </div>
                            `).join('')}
                        </div>
                    </div>
                `).join('')}
            </div>
        </div>
    `;
    
    document.getElementById('drift-analysis-modal-body').innerHTML = modalContent;
}
```

### Sync from Git Functionality
```javascript
// Synchronization with progress tracking
function syncFromGit() {
    if (!confirm('This will update database records to match git repository content. Continue?')) {
        return;
    }
    
    // Show sync progress
    showSyncProgressModal();
    
    fetch(`/api/fabrics/${fabricId}/sync-from-git/`, {
        method: 'POST',
        headers: {
            'X-CSRFToken': getCsrfToken(),
            'Content-Type': 'application/json'
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showSyncSuccess(data);
            // Refresh drift detection after sync
            setTimeout(checkForDrift, 1000);
        } else {
            showSyncError(data.error);
        }
    })
    .catch(error => {
        showSyncError(error);
    });
}
```

## API Endpoints for Drift Detection

### Drift Analysis API
```python
# API endpoint for drift analysis
@api_view(['POST'])
def analyze_fabric_drift(request, fabric_id):
    """
    Perform comprehensive drift analysis for fabric
    """
    try:
        fabric = HedgehogFabric.objects.get(id=fabric_id)
        drift_results = detect_configuration_drift(fabric)
        
        return Response({
            'success': True,
            'drift_analysis': drift_results
        })
        
    except HedgehogFabric.DoesNotExist:
        return Response({
            'success': False,
            'error': 'Fabric not found'
        }, status=404)
        
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=500)

# API endpoint for git synchronization
@api_view(['POST'])
def sync_fabric_from_git(request, fabric_id):
    """
    Synchronize fabric configuration from git repository
    """
    try:
        fabric = HedgehogFabric.objects.get(id=fabric_id)
        sync_results = trigger_gitops_sync(fabric)
        
        return Response({
            'success': True,
            'sync_results': sync_results
        })
        
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=500)
```

## Caching and Performance

### Drift Detection Caching
```python
# Drift detection caching strategy
def get_or_compute_drift_results(fabric, force_refresh=False):
    """
    Get cached drift results or compute fresh if needed
    """
    cache_key = f"drift_results_{fabric.id}"
    cache_timeout = 300  # 5 minutes
    
    if not force_refresh:
        cached_results = cache.get(cache_key)
        if cached_results:
            return cached_results
    
    # Compute fresh drift results
    drift_results = detect_configuration_drift(fabric)
    
    # Cache results
    cache.set(cache_key, drift_results, cache_timeout)
    
    return drift_results
```

### Background Drift Monitoring
```python
# Scheduled drift detection
@periodic_task(run_every=timedelta(minutes=15))
def monitor_fabric_drift():
    """
    Background task for periodic drift detection
    """
    fabrics = HedgehogFabric.objects.filter(
        git_repository__connection_status='connected'
    )
    
    for fabric in fabrics:
        try:
            drift_results = detect_configuration_drift(fabric)
            
            # Update fabric drift status
            fabric.drift_status = drift_results['status']
            fabric.drift_count = drift_results['resources_with_drift']
            fabric.last_drift_check = timezone.now()
            fabric.save()
            
            # Send alerts for critical drift
            if drift_results['status'] == 'critical':
                send_drift_alert(fabric, drift_results)
                
        except Exception as e:
            logger.error(f"Drift detection failed for fabric {fabric.id}: {e}")
```

## Implementation Status

### Current Capabilities
- **✅ UI Implementation**: Prominent drift detection section with dynamic styling
- **✅ Visual Design**: Status-based background gradients and responsive layout
- **✅ Context Integration**: Drift summary context in fabric detail views
- **✅ Action Buttons**: Interactive elements for drift analysis and sync operations

### Enhancement Requirements
- **🔄 Drift Detection Logic**: Comprehensive comparison algorithm implementation
- **🔄 API Endpoints**: Drift analysis and sync endpoints
- **🔄 Caching Strategy**: Performance optimization with result caching
- **🔄 Background Monitoring**: Scheduled drift detection tasks
- **🔄 Alert System**: Notifications for critical drift conditions

## Success Metrics

### User Experience Metrics
- **Drift Visibility**: Immediate visual feedback on configuration drift status
- **Action Accessibility**: One-click access to drift analysis and sync operations
- **Information Clarity**: Clear presentation of drift details and resolution options

### Technical Performance Metrics
- **Detection Accuracy**: 100% accurate identification of configuration differences
- **Response Time**: Drift analysis completed within 10 seconds
- **Cache Efficiency**: 80% cache hit rate for drift detection queries
- **Background Monitoring**: All fabrics checked within 15-minute intervals

## References
- [GitOps Architecture Overview](gitops_overview.md)
- [Directory Management Specification](directory_management_specification.md)
- [System Overview](../../system_overview.md)
- [ADR-006: Drift Detection as First-Class Feature](../../../01_architectural_decisions/approved_decisions/adr-006-drift-detection-first-class.md)