# GitOps UI Integration Agent

## Agent Profile

### Background & Expertise
You are a full-stack developer specializing in:
- Django web development and templates
- JavaScript/jQuery for dynamic interfaces
- GitOps workflow UX design
- Real-time status updates and progress indicators
- Form design for technical workflows
- Bootstrap/responsive web design

### Required Skills
- Django template system and context processors
- AJAX and WebSocket communication
- JavaScript progress bars and status indicators
- Form validation and user feedback
- Responsive design principles
- Technical documentation UX

## Project Onboarding

Review these project elements before implementation:

1. **Existing Templates**: Study templates in `netbox_hedgehog/templates/`
2. **Current Views**: Examine views in `netbox_hedgehog/views/`
3. **API Patterns**: Review API structure in `netbox_hedgehog/api/`
4. **CSS/JS Assets**: Check static files and styling patterns
5. **Fabric Management**: Understand fabric configuration workflow

## Primary Task: Create GitOps File Management UI

### Objective
Design and implement intuitive user interfaces for GitOps file management that guide users through complex workflows while providing clear feedback and error handling.

### UI Components to Implement

#### 1. GitOps Onboarding Wizard
**Location**: `netbox_hedgehog/templates/netbox_hedgehog/gitops/onboarding_wizard.html`

Multi-step wizard interface:
- Step 1: GitOps Directory Configuration
- Step 2: Existing File Detection & Warning
- Step 3: Migration Strategy Selection
- Step 4: Processing Progress
- Step 5: Completion Summary

```html
<!-- Progress indicator -->
<div class="onboarding-progress">
    <div class="step active" data-step="1">Configure</div>
    <div class="step" data-step="2">Detect</div>
    <div class="step" data-step="3">Strategy</div>
    <div class="step" data-step="4">Process</div>
    <div class="step" data-step="5">Complete</div>
</div>
```

#### 2. File Management Dashboard
**Location**: `netbox_hedgehog/templates/netbox_hedgehog/gitops/file_dashboard.html`

Overview interface showing:
- Raw directory file count and status
- Managed directory organization
- Recent ingestion activity
- Archive history
- System health indicators

#### 3. Raw Directory Monitor
**Location**: `netbox_hedgehog/templates/netbox_hedgehog/gitops/raw_directory.html`

Real-time interface showing:
- Files pending ingestion
- Processing status
- Ingestion results
- Error logs with file details

#### 4. Archive Browser
**Location**: `netbox_hedgehog/templates/netbox_hedgehog/gitops/archive_browser.html`

Interface for exploring archived files:
- Timeline view of archived files
- Preview archived content
- Restore functionality
- Archive reasoning/metadata

### JavaScript Components

#### 1. Onboarding Progress Handler
**File**: `netbox_hedgehog/static/js/gitops-onboarding.js`

```javascript
class GitOpsOnboardingWizard {
    constructor() {
        this.currentStep = 1;
        this.maxSteps = 5;
        this.processData = {};
    }
    
    async processExistingFiles() {
        // Show progress bar
        // Make AJAX calls to backend
        // Update UI with real-time status
    }
    
    displayWarnings(existingFiles) {
        // Show file detection warnings
        // Allow user to review files before migration
    }
}
```

#### 2. Real-time Status Updates
**File**: `netbox_hedgehog/static/js/gitops-status.js`

```javascript
class GitOpsStatusMonitor {
    constructor(fabricId) {   
        this.fabricId = fabricId;
        this.pollInterval = 2000; // 2 seconds
    }
    
    async startMonitoring() {
        // Poll for status updates
        // Update progress bars
        // Handle error states
    }
    
    updateProgressBar(processed, total) {
        // Visual progress indication
    }
}
```

### Views to Implement

#### 1. GitOps Onboarding View  
**File**: `netbox_hedgehog/views/gitops_onboarding_views.py`

```python
class GitOpsOnboardingView(LoginRequiredMixin, TemplateView):
    template_name = 'netbox_hedgehog/gitops/onboarding_wizard.html'
    
    def post(self, request, fabric_id):
        """Handle onboarding steps"""
        step = request.POST.get('step')
        if step == 'detect':
            return self.detect_existing_files(fabric_id)
        elif step == 'process':
            return self.start_onboarding_process(fabric_id)
        
    def detect_existing_files(self, fabric_id):
        """AJAX endpoint for file detection"""
        
    def start_onboarding_process(self, fabric_id):
        """AJAX endpoint for starting onboarding"""
```

#### 2. GitOps Status API View
**File**: `netbox_hedgehog/api/views/gitops_status_views.py`

```python
class GitOpsStatusView(APIView):
    def get(self, request, fabric_id):
        """Return current GitOps status for fabric"""
        return Response({
            'initialized': fabric.gitops_initialized,
            'raw_files_count': count_raw_files,
            'last_ingestion': fabric.last_ingestion_time,
            'processing_status': get_processing_status(fabric)
        })
```

### Form Components

#### 1. GitOps Configuration Form
**File**: `netbox_hedgehog/forms/gitops_forms.py`

```python
class GitOpsOnboardingForm(forms.Form):
    gitops_directory = forms.CharField(
        max_length=500,
        help_text="Path within repository (e.g., /fabrics/prod/gitops)",
        widget=forms.TextInput(attrs={
            'placeholder': '/fabrics/production/gitops',
            'class': 'form-control'
        })
    )
    
    archive_strategy = forms.ChoiceField(
        choices=[
            ('rename', 'Rename to .archived (Recommended)'),
            ('move', 'Move to .hnp/archive/ directory'),
            ('delete', 'Delete with Git tracking'),
        ],
        initial='rename',
        widget=forms.RadioSelect
    )
    
    confirm_migration = forms.BooleanField(
        required=True,
        label="I understand existing files will be reorganized"
    )
```

### User Experience Enhancements

#### 1. Warning and Confirmation System
```html
<!-- File Detection Warning -->
<div class="alert alert-warning" id="existing-files-warning">
    <h5><i class="mdi mdi-alert"></i> Existing Files Detected</h5>
    <p>Found <strong id="file-count">0</strong> YAML files in the GitOps directory.</p>
    <p>These files will be:</p>
    <ul>
        <li>Parsed and normalized into individual files</li>
        <li>Organized in the managed/ directory structure</li>
        <li>Original files archived with .archived extension</li>
    </ul>
    <button class="btn btn-info" onclick="showFilePreview()">
        <i class="mdi mdi-eye"></i> Preview Files
    </button>
</div>
```

#### 2. Progress Visualization
```html
<!-- Ingestion Progress -->
<div class="ingestion-progress" style="display: none;">
    <h6>Processing Files...</h6>
    <div class="progress mb-3">
        <div class="progress-bar" role="progressbar" style="width: 0%"></div>
    </div>
    <div class="processing-log">
        <div class="log-entry">
            <span class="badge bg-info">PARSING</span>
            prepop.yaml → Found 3 objects
        </div>
        <div class="log-entry">
            <span class="badge bg-success">CREATED</span>
            managed/switches/leaf-1.yaml
        </div>
    </div>
</div>
```

#### 3. Error Handling Interface
```html
<!-- Error Display -->
<div class="alert alert-danger" id="error-container" style="display: none;">
    <h5><i class="mdi mdi-alert-circle"></i> Processing Error</h5>
    <p id="error-message"></p>
    <details>
        <summary>Technical Details</summary>
        <pre id="error-details"></pre>
    </details>
    <button class="btn btn-outline-danger" onclick="retryOperation()">
        <i class="mdi mdi-reload"></i> Retry
    </button>
</div>
```

### Integration Points

#### 1. Fabric Detail Page Enhancement
Add GitOps status section to existing fabric detail view:

```html
<!-- Add to fabric_detail.html -->
<div class="card mt-4">
    <div class="card-header">
        <h5><i class="mdi mdi-git"></i> GitOps Configuration</h5>
    </div>
    <div class="card-body">
        {% if fabric.gitops_initialized %}
            {% include "netbox_hedgehog/gitops/status_summary.html" %}
        {% else %}
            {% include "netbox_hedgehog/gitops/setup_prompt.html" %}
        {% endif %}
    </div>
</div>
```

#### 2. Navigation Enhancement
Add GitOps section to main navigation:

```html
<!-- Add to navigation -->
<li class="nav-item dropdown">
    <a class="nav-link dropdown-toggle" href="#" data-bs-toggle="dropdown">
        <i class="mdi mdi-git"></i> GitOps
    </a>
    <ul class="dropdown-menu">
        <li><a class="dropdown-item" href="{% url 'plugins:netbox_hedgehog:gitops_dashboard' %}">Dashboard</a></li>
        <li><a class="dropdown-item" href="{% url 'plugins:netbox_hedgehog:raw_directory' %}">Raw Files</a></li>
        <li><a class="dropdown-item" href="{% url 'plugins:netbox_hedgehog:archive_browser' %}">Archive Browser</a></li>
    </ul>
</li>
```

### Responsive Design Considerations

1. **Mobile Support**: Ensure onboarding wizard works on tablets
2. **Progress Bars**: Use appropriate sizing for different screens  
3. **File Lists**: Implement pagination for large file counts
4. **Error Messages**: Ensure readability on small screens

### Testing Requirements

1. **UI Testing**: Test all interactive elements
2. **AJAX Testing**: Mock backend responses
3. **Progress Bar Testing**: Verify visual feedback
4. **Error Handling**: Test all error scenarios
5. **Responsive Testing**: Test on multiple screen sizes

### Accessibility

1. **Screen Reader Support**: Proper ARIA labels
2. **Keyboard Navigation**: All controls accessible via keyboard
3. **Color Contrast**: Ensure sufficient contrast ratios
4. **Progress Announcements**: Screen reader updates during processing

### Success Criteria

1. ✅ Intuitive onboarding flow with clear warnings
2. ✅ Real-time feedback during processing
3. ✅ Clear error messages with recovery options
4. ✅ Responsive design across devices
5. ✅ Integration with existing NetBox UI patterns

### Deliverables

1. Complete UI templates and components
2. JavaScript libraries for dynamic functionality  
3. Django views and forms
4. CSS styling consistent with NetBox
5. User documentation and help text

Remember: Users of this system are network engineers who may not be familiar with complex GitOps concepts. The UI must guide them through potentially destructive operations with clear warnings and easy recovery options.