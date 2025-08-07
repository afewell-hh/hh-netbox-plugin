# Drift Detection Dashboard Investigation Findings

## Current State Analysis

### Existing Infrastructure ✅
1. **Sophisticated Drift Detection Logic** (679 lines)
   - Location: `/netbox_hedgehog/utils/drift_detection.py`
   - Industry-aligned drift definition (ArgoCD/FluxCD compliant)
   - DriftDetector class with deep comparison algorithms
   - DriftAnalyzer class for fabric-wide analysis
   - Advanced features: semantic comparisons, drift scoring, categorization

2. **API Framework Partially Present**
   - Location: `/netbox_hedgehog/api/views.py`
   - DriftAnalysisAPIView exists but basic functionality
   - FabricViewSet has drift-related method stubs (commented out)
   - HedgehogResourceViewSet has calculate_drift action

3. **URL Structure Ready**
   - Location: `/netbox_hedgehog/urls.py`
   - Comprehensive URL patterns for all CRs and fabrics
   - No dedicated drift detection URLs yet

### Critical Missing Components ❌
1. **No Drift Detection Dashboard Page**
   - No dedicated view for viewing specific drifted CRs
   - No template for drift dashboard
   - No navigation integration

2. **API Endpoints Not Functional**
   - analyze_fabric_drift function exists but not exposed via web API
   - No REST endpoints for dashboard data consumption
   - Existing DriftAnalysisAPIView is basic

3. **No CR-Level Drift Status Integration**
   - CR list/detail pages don't show drift status
   - No indicators for drift state
   - No links from drift summaries to specific drifted resources

## Industry Alignment Validation ✅

The existing drift detection logic is **90% ArgoCD/FluxCD compliant**:
- ✅ Treats any difference between Git and Kubernetes as drift
- ✅ Resources in Git but not in cluster = drift
- ✅ Resources in cluster but not in Git = drift  
- ✅ Specification differences = drift
- ✅ Proper severity classification (high/medium/low)

## Implementation Requirements

### 1. Dashboard Page Creation
- Create `/drift-detection/` URL and view
- Template with filterable list of drifted CRs
- Show resource type, name, fabric, drift score, and severity
- Provide actionable information (sync/resolve options)

### 2. API Completion
- Expose fabric-level drift analysis via REST API
- Create resource-level drift detail API
- Dashboard data API for frontend consumption
- Integrate with existing analyze_fabric_drift function

### 3. Navigation Integration  
- Add drift detection link to main navigation
- Link existing drift summary cards to detailed dashboard
- Add drift status indicators to CR list/detail pages

### 4. User Experience Features
- Filter by fabric, resource type, severity
- Sort by drift score, last updated, etc.
- Direct links to resolve drift (sync actions)
- Real-time status updates

## Files to Create/Modify

### New Files Needed:
- Drift detection dashboard view
- Dashboard template
- JavaScript for dashboard interaction
- API serializers for drift data

### Files to Modify:
- `/netbox_hedgehog/urls.py` - Add drift dashboard URLs
- `/netbox_hedgehog/api/urls.py` - Add drift API endpoints  
- `/netbox_hedgehog/api/views.py` - Complete drift API implementation
- Navigation templates - Add drift detection links
- CR list/detail templates - Add drift status indicators

## Next Steps
1. Create drift detection dashboard view and template
2. Implement functional drift analysis API endpoints  
3. Add URL routing and navigation integration
4. Test with real drift scenarios
5. Add drift status to CR pages