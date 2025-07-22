# GitOps Workflow Agent Instructions

## Agent Role: GitOps Workflow Specialist
**Specialization**: GitOps Integration, State Management, CRUD Operations  
**Project**: Hedgehog NetBox Plugin (HNP) GitOps Workflow Implementation  
**Reporting To**: Lead Architect (Claude)  
**Priority Level**: CRITICAL - Core GitOps Functionality

## Mission Statement

Implement the **complete GitOps workflow** for HNP, enabling users to:
1. **Filter CR views by fabric** across all 12 CR types
2. **Sync actual state from HCKC cluster** and compare with desired state  
3. **Edit CRs through GUI** with automatic Git commit/push
4. **Visualize drift detection** between desired (Git) and actual (HCKC) state

## Foundation Available

### What Previous Agents Delivered
- ✅ **Clean Architecture** (Phase 1): Service-oriented design, zero circular dependencies
- ✅ **Real-Time Monitoring** (Phase 2): WebSocket infrastructure, Kubernetes watch APIs  
- ✅ **Performance Optimization** (Phase 3): Redis caching, background processing, optimized queries
- ✅ **Git Directory Sync**: Working Git → HNP database synchronization
- ✅ **HCKC Integration**: Service account authentication, 32 live CRDs accessible

### Current System Capabilities
- Git sync imports CRDs from repository to HNP database
- Real-time monitoring shows live cluster state
- All 12 CR types have functional list/detail pages
- WebSocket infrastructure for live updates
- Background processing with Celery ready

## Your Critical Objectives

### **1. Fabric-Filtered CR Views (Week 1)**
**Goal**: Users can view CRs filtered by specific fabric

**Implementation Requirements**:
```python
# URL patterns needed:
/plugins/hedgehog/vpcs/?fabric=11
/plugins/hedgehog/connections/?fabric=11
/plugins/hedgehog/switches/?fabric=11
# ... for all 12 CR types

# Filter bar component for each list page
class FabricFilterMixin:
    def get_queryset(self):
        queryset = super().get_queryset()
        fabric_id = self.request.GET.get('fabric')
        if fabric_id:
            queryset = queryset.filter(fabric_id=fabric_id)
        return queryset
```

**UI Components**:
- Filter dropdown on each CR list page
- "View All CRDs" button on fabric detail page
- Breadcrumb navigation showing active filters
- Clear filter functionality

### **2. HCKC Cluster State Sync (Week 1-2)**
**Goal**: Read actual state from HCKC cluster and compare with desired state

**Implementation Requirements**:
```python
# New service for cluster state sync
class HCKCStateService:
    def sync_actual_state_from_cluster(self, fabric: HedgehogFabric):
        """Read actual CRD state from HCKC cluster"""
        
    def compare_desired_vs_actual(self, fabric: HedgehogFabric):
        """Compare Git state with HCKC state"""
        
    def detect_drift(self, fabric: HedgehogFabric):
        """Identify resources that are out of sync"""
```

**New Fabric Detail Features**:
- "Sync from HCKC" button alongside "Sync from Git"  
- Drift detection dashboard showing:
  - Resources in sync ✅
  - Resources with drift ⚠️  
  - Resources missing from cluster ❌
  - Resources not in Git 🔄

### **3. CR Edit Functionality (Week 2-3)**
**Goal**: Edit CRs through GUI with automatic Git workflow

**Implementation Requirements**:
```python
# Edit views for all 12 CR types
class VPCEditView(UpdateView):
    def form_valid(self, form):
        # 1. Save to database
        response = super().form_valid(form)
        # 2. Update YAML file in Git repo
        # 3. Commit changes
        # 4. Push to remote
        # 5. Trigger real-time updates
        return response

# Git operations service
class GitOpsService:
    def update_cr_yaml(self, cr_instance, fabric):
        """Update YAML file for CR changes"""
        
    def commit_and_push_changes(self, fabric, commit_message):
        """Commit and push changes to Git repository"""
```

**Edit Form Features**:
- Edit buttons on all CR detail pages
- Form validation matching Kubernetes CRD schemas
- Real-time preview of YAML changes
- Commit message customization
- Automatic Git push after save

### **4. Desired vs Actual State Visualization (Week 3-4)**
**Goal**: Clear visualization of GitOps state across the fabric

**Implementation Requirements**:
```python
# State comparison service
class StateComparisonService:
    def generate_fabric_state_report(self, fabric):
        return {
            'total_resources': count,
            'in_sync': count,
            'drifted': count, 
            'missing_from_cluster': count,
            'missing_from_git': count,
            'drift_details': [...]
        }
```

**Dashboard Components**:
- Fabric-level sync status indicators
- CR-level drift detection
- Real-time sync progress
- Detailed drift reports with diff views
- One-click sync resolution actions

## Technical Architecture

### **GitOps Workflow Architecture**
```
User Edits CR → HNP Database → Update YAML → Git Commit/Push → GitOps Tool Deploys → HCKC Cluster
                    ↑                                                                      ↓
              Real-time Updates ←←←←← WebSocket ←←←←← Watch APIs ←←←←← Live State Changes
                    ↑                                                                      ↓  
              Drift Detection ←←←←←← State Comparison ←←←←← HCKC State Sync ←←←←←←←←←←←←←←←
```

### **Key Services to Implement**

#### **1. FabricFilterService**
```python
class FabricFilterService:
    def get_filtered_queryset(self, model_class, fabric_id):
        """Return filtered queryset for CR type by fabric"""
        
    def get_fabric_cr_counts(self, fabric):
        """Return counts of each CR type for fabric"""
```

#### **2. HCKCStateService** 
```python
class HCKCStateService:
    def read_cluster_state(self, fabric):
        """Read actual state from HCKC cluster"""
        
    def compare_states(self, fabric):
        """Compare Git vs HCKC state"""
        
    def generate_drift_report(self, fabric):
        """Generate detailed drift analysis"""
```

#### **3. GitOpsEditService**
```python
class GitOpsEditService:
    def update_and_commit_cr(self, cr_instance, form_data):
        """Edit CR and update Git repository"""
        
    def validate_yaml_schema(self, yaml_content, cr_type):
        """Validate YAML against Kubernetes schemas"""
```

#### **4. StateVisualizationService**
```python
class StateVisualizationService:
    def generate_fabric_dashboard_data(self, fabric):
        """Generate data for fabric state dashboard"""
        
    def create_drift_visualization(self, drift_data):
        """Create visual diff for drifted resources"""
```

## Implementation Phases

### **Phase 1: Fabric Filtering (Days 1-3)**
- [ ] Add fabric filter parameter to all 12 CR list views
- [ ] Create FabricFilterMixin for reusable filtering logic
- [ ] Add filter UI components to templates
- [ ] Add "View All CRDs" button to fabric detail page
- [ ] Test filtering functionality with live data

### **Phase 2: HCKC State Sync (Days 4-7)**
- [ ] Implement HCKCStateService to read cluster state
- [ ] Add "Sync from HCKC" button to fabric detail page
- [ ] Create state comparison logic (Git vs HCKC)
- [ ] Implement basic drift detection
- [ ] Add real-time updates for sync operations

### **Phase 3: CR Edit Workflow (Days 8-12)**
- [ ] Create edit views and forms for all 12 CR types
- [ ] Implement GitOpsEditService for YAML updates
- [ ] Add Git commit/push functionality
- [ ] Create edit buttons on all CR detail pages
- [ ] Test complete edit → commit → push → deploy workflow

### **Phase 4: State Visualization (Days 13-16)**
- [ ] Create fabric state dashboard
- [ ] Implement drift visualization with diff views
- [ ] Add sync status indicators throughout UI
- [ ] Create actionable sync resolution tools
- [ ] Polish user experience with real-time updates

## Integration Points

### **With Existing Systems**
- **Git Directory Sync**: Extend to support bidirectional sync
- **Real-Time Monitoring**: Add state comparison events
- **Performance Layer**: Cache state comparisons and drift data
- **Service Registry**: Register new GitOps services

### **With Live Infrastructure**
- **HCKC Cluster**: Read actual state via service account
- **Git Repository**: Commit/push CR changes
- **GitOps Tool**: Trigger deployments via Git updates
- **WebSocket**: Deliver real-time state updates

## Success Criteria

### **Fabric Filtering Success**
- [ ] All 12 CR list pages support `?fabric=X` parameter
- [ ] Filter UI components work across all pages
- [ ] "View All CRDs" button navigates with proper filters
- [ ] Performance remains <500ms with filters applied

### **HCKC Sync Success** 
- [ ] Can read actual state from live HCKC cluster
- [ ] Drift detection identifies out-of-sync resources
- [ ] Real-time updates show sync progress
- [ ] State comparison visualizations are clear and actionable

### **Edit Workflow Success**
- [ ] All 12 CR types have functional edit forms
- [ ] Edits automatically update Git repository
- [ ] Git commits trigger GitOps deployments
- [ ] Real-time monitoring shows deployment progress

### **State Visualization Success**
- [ ] Fabric dashboard clearly shows sync status
- [ ] Drift reports provide actionable information
- [ ] Users can easily resolve sync conflicts
- [ ] Real-time updates keep visualizations current

## Quality Requirements

### **User Experience Standards**
- **Intuitive Navigation**: Clear paths between fabric and CR views
- **Real-time Feedback**: Immediate visual feedback for all operations
- **Error Handling**: Clear error messages and recovery paths
- **Performance**: All operations complete within 3 seconds

### **Technical Standards**
- **Clean Architecture**: Follow established service patterns
- **Test Coverage**: 80%+ coverage for new functionality
- **Documentation**: Complete API documentation
- **Security**: Secure Git operations and credential handling

## Emergency Protocols

### **Critical Issues**
**Immediate escalation required for**:
- Git repository corruption or access issues
- HCKC cluster connectivity problems
- Data loss during edit operations
- Performance degradation below acceptable levels

### **Rollback Plan**
- **Git Operations**: All changes tracked with detailed commit messages
- **Database Changes**: Migrations reversible
- **UI Changes**: Feature flags for quick disable
- **Service Changes**: Clean interfaces allow component rollback

---

## Final Notes

**This is the heart of the GitOps workflow** - the features that make HNP a complete infrastructure management platform rather than just a configuration viewer. 

Your work directly enables:
- **Operational Efficiency**: Users can manage infrastructure entirely through HNP
- **GitOps Best Practices**: Complete Git-based workflow with automated deployments  
- **State Visibility**: Clear understanding of desired vs actual state
- **Conflict Resolution**: Tools to resolve drift and sync issues

The clean architecture and real-time infrastructure from previous phases provide the perfect foundation for this critical GitOps functionality.

**Success here transforms HNP into a complete GitOps management platform!**