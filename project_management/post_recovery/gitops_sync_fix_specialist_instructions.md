# GitOps Sync Fix Specialist Instructions

**Agent Role**: GitOps Sync Fix Specialist (Technical Implementation)  
**Agent Type**: Claude Sonnet 4  
**Authority Level**: GitOps sync implementation and Git integration fixes  
**Project Phase**: Post-Recovery Enhancement - GitOps Sync Resolution  
**Duration**: 1 week focused GitOps sync implementation

---

## IMMEDIATE CONTEXT (Level 0 - Essential)

**Current Task**: Fix "Sync from Git" functionality to resolve "Not from Git" attribution issue  
**Success Criteria**: CRDs imported from GitOps show "From Git" attribution and Git sync operates without errors  
**Critical Issue**: HCKC sync works but Git sync fails, CRs show "Not from Git" despite being in GitOps directory

**Environment Status**:
- NetBox Docker: localhost:8000 (admin/admin) ✅
- HCKC Cluster: 127.0.0.1:6443 via ~/.kube/config ✅  
- GitOps Test Repo: https://github.com/afewell-hh/gitops-test-1.git ✅
- Test Directory: https://github.com/afewell-hh/gitops-test-1/tree/main/gitops/hedgehog/fabric-1 ✅
- Project Root: /home/ubuntu/cc/hedgehog-netbox-plugin/ ✅

**Recent Context**: 6-phase recovery just completed successfully, codebase is clean and organized, comprehensive testing framework is operational and ready for validation.

---

## EXPANDED CONTEXT (Level 1 - Reference)

**HNP Mission**: Self-service Kubernetes CRD management via NetBox interface with GitOps workflow integration  
**GitOps Integration**: Bi-directional sync between Git repository, NetBox, and Kubernetes cluster  
**Current Status**: MVP complete with 95% functionality, GitOps sync is the primary remaining gap

**Technical Stack**:
- Backend: Django 4.2 with NetBox 4.3.3 plugin architecture
- GitOps: Extensive codebase with 13 GitOps-related Python files
- Sync: Six-state resource model (Draft → Committed → Synced → Drifted → Orphaned → Pending)
- Testing: Comprehensive framework specifically designed to catch GitOps integration issues

**Known Working Systems** (PRESERVE):
- All 12 CRD pages 100% functional
- HCKC sync and CRD import functionality  
- Database operations and plugin integration
- UI rendering and user workflows
- Testing framework infrastructure

---

## GITOPS SYNC PROBLEM ANALYSIS

### Current Issue Symptoms

**Primary Problem**: "Sync from Git" button fails to properly attribute CRDs as "From Git"
- CRDs imported from GitOps directory show "Not from Git" status
- Git sync operations complete but with errors
- HCKC sync works correctly (validates cluster connectivity)
- GitOps directory contains valid CRDs but sync attribution fails

**Evidence from Previous Analysis**:
- **GitOps Repository**: https://github.com/afewell-hh/gitops-test-1/tree/main/gitops/hedgehog/fabric-1
- **Test Framework Target**: Specifically designed to catch this issue
- **Extensive Codebase**: 13 GitOps files present but sync logic needs validation
- **Six-State Model**: Implementation present but Git state transitions may be broken

### Expected Behavior vs. Actual

**Expected GitOps Workflow**:
1. User clicks "Sync from Git" button
2. HNP connects to configured GitOps repository  
3. Discovers CRDs in GitOps directory (fabric-1/)
4. Imports CRDs with proper "From Git" attribution
5. Updates NetBox with Git file paths and status
6. Shows sync success with resource counts

**Current Broken Behavior**:
1. User clicks "Sync from Git" button
2. Sync operation runs but encounters errors
3. CRDs may be imported but show "Not from Git"
4. Attribution to Git file paths fails
5. Sync status shows errors or incomplete state

---

## GITOPS SYNC IMPLEMENTATION FOCUS

### Phase 5 Testing Framework Integration

**Leverage Existing Test Suite**: The testing framework specialist created specific tests for this issue:

```python
def test_fabric_onboarding_gitops_attribution():
    # Create fabric with GitOps repository
    fabric = create_test_fabric()
    
    # Connect to GitOps repository with existing CRDs
    connect_fabric_to_gitops(fabric, TEST_GITOPS_REPO)
    
    # Trigger Git sync
    sync_result = fabric.sync_from_git()
    assert sync_result['success'] == True
    
    # Verify CRDs imported with proper attribution
    crds = get_fabric_crds(fabric)
    for crd in crds:
        assert crd.git_file_path is not None  # Should have Git path
        assert crd.get_git_file_status() == "From Git"  # Should show Git attribution
```

**Use Testing Framework**: Run these specific tests to validate your fixes work correctly.

### GitOps Codebase Investigation

**Files to Examine and Fix**:
```
Primary GitOps Implementation:
- netbox_hedgehog/services/gitops_ingestion_service.py (core ingestion logic)
- netbox_hedgehog/utils/gitops_integration.py (integration utilities)  
- netbox_hedgehog/views/gitops_onboarding_views.py (UI sync triggers)
- netbox_hedgehog/models/gitops.py (state management models)

Git Integration:
- netbox_hedgehog/application/services/git_sync_service.py (sync service core)
- netbox_hedgehog/tasks/git_sync_tasks.py (async sync operations)
- netbox_hedgehog/utils/git_directory_sync.py (directory operations)

State Management:
- netbox_hedgehog/models/fabric.py (fabric Git sync methods)
- netbox_hedgehog/models/reconciliation.py (six-state resource model)
```

### Specific Implementation Tasks

**Task 1: Git Repository Connection Validation**
- Verify GitOps repository authentication works
- Test connection to https://github.com/afewell-hh/gitops-test-1.git
- Validate directory discovery in `/gitops/hedgehog/fabric-1/`
- Ensure YAML file parsing works correctly

**Task 2: CRD Import Attribution Fix**
- Fix CRD import to properly set git_file_path
- Ensure get_git_file_status() returns "From Git"
- Validate Git metadata preserved during import
- Test with real GitOps repository CRDs

**Task 3: Sync Operation Error Resolution**
- Debug sync operation error handling
- Fix any authentication or connection issues
- Resolve YAML parsing or validation problems
- Ensure proper state transitions in six-state model

**Task 4: UI Integration Validation**
- Test "Sync from Git" button functionality
- Verify sync status display accuracy
- Validate error message clarity and helpfulness
- Ensure sync results show correct resource counts

---

## IMPLEMENTATION APPROACH

### 1. Investigation and Diagnosis Phase (Days 1-2)

**Environment Validation**:
- Test GitOps repository access from HNP environment
- Validate NetBox fabric configuration for GitOps
- Verify existing CRDs in test repository are accessible
- Run Phase 5 test suite to confirm current failure patterns

**Code Analysis**:
- Trace "Sync from Git" button to underlying implementation
- Identify exact point where attribution fails
- Map Git sync service flow and identify breakpoints
- Document current behavior vs. expected behavior

**Error Analysis**:
- Capture and analyze Git sync error logs
- Identify authentication, connection, or parsing issues
- Test individual components (repo access, YAML parsing, CRD creation)
- Create reproduction case for reliable testing

### 2. Core Sync Implementation Fix (Days 3-4)

**Git Repository Integration**:
```python
# Fix GitOps repository connection and authentication
def connect_to_gitops_repository(fabric):
    """Establish authenticated connection to GitOps repository"""
    # Implement actual Git repository authentication
    # Handle SSH keys, tokens, or other auth methods
    # Validate repository access and directory structure
    # Return connection status and repository client

def discover_gitops_crds(fabric, repository):
    """Discover CRDs in GitOps directory structure"""  
    # Navigate to fabric-specific GitOps directory
    # Parse YAML files and validate CRD structure
    # Extract metadata including file paths for attribution
    # Return list of CRDs with Git attribution data
```

**CRD Import with Attribution**:
```python
def import_crd_from_git(fabric, crd_data, git_file_path):
    """Import CRD with proper Git attribution"""
    # Create or update CRD in NetBox
    # Set git_file_path to actual repository file path
    # Set git_status to "From Git" explicitly
    # Update fabric sync status and resource counts
    # Return import result with attribution validation
```

**Sync Operation Core Logic**:
```python
def sync_fabric_from_git(fabric):
    """Complete Git sync operation with proper error handling"""
    try:
        # Connect to GitOps repository
        repository = connect_to_gitops_repository(fabric)
        
        # Discover CRDs in GitOps directory
        git_crds = discover_gitops_crds(fabric, repository)
        
        # Import each CRD with attribution
        results = []
        for crd_data in git_crds:
            result = import_crd_from_git(fabric, crd_data, crd_data['git_file_path'])
            results.append(result)
        
        # Update fabric sync status
        fabric.last_git_sync = timezone.now()
        fabric.git_sync_status = 'success'
        fabric.save()
        
        return {
            'success': True,
            'imported_count': len([r for r in results if r['success']]),
            'results': results
        }
    except Exception as e:
        # Proper error handling and logging
        logger.error(f"Git sync failed: {e}")
        fabric.git_sync_status = 'failed'
        fabric.git_sync_error = str(e)
        fabric.save()
        return {'success': False, 'error': str(e)}
```

### 3. Testing and Validation (Days 5-6)

**Use Phase 5 Testing Framework**:
- Run existing GitOps attribution tests
- Validate "From Git" status appears correctly
- Test with real GitOps repository data
- Verify sync operation success metrics

**Integration Testing**:
- Test complete workflow: repository setup → sync → validation
- Verify UI shows correct sync status and resource counts
- Test error handling with invalid repositories or credentials
- Validate performance with larger GitOps directories

**End-to-End Validation**:
- Test with actual GitOps test repository
- Verify CRDs show proper attribution in UI
- Test sync operation multiple times for consistency
- Validate state management through six-state model

### 4. UI and User Experience Polish (Day 7)

**Sync Button Enhancement**:
- Ensure button provides clear feedback during operation
- Show progress indicator for longer sync operations
- Display helpful error messages for common issues
- Update sync status display with accurate information

**Status Display Improvements**:
- Show "From Git" attribution clearly in CRD lists
- Display Git file paths in CRD detail views
- Update fabric status to reflect Git sync state
- Provide clear sync operation results and metrics

---

## SUCCESS VALIDATION

### Before Implementation (Pre-work validation):
- [ ] Phase 5 testing framework runs and shows current failure patterns
- [ ] GitOps test repository accessible from HNP environment
- [ ] Current sync operation behavior documented and reproducible
- [ ] Code analysis completed with specific failure points identified
- [ ] Integration strategy planned with rollback procedures

### During Implementation (Continuous validation):
- [ ] Each component fixed independently with unit tests
- [ ] Integration testing performed after each major change
- [ ] Phase 5 test suite runs progressively show improvements
- [ ] Git repository operations work correctly in isolation
- [ ] CRD attribution logic verified with test data

### Before Delivery (Completion validation):
- [ ] All Phase 5 GitOps tests pass without modification
- [ ] "Sync from Git" button works correctly with test repository
- [ ] CRDs show "From Git" attribution in UI consistently
- [ ] Sync operation completes without errors for test data
- [ ] End-to-end workflow validated from GitOps repo to NetBox display

---

## TECHNICAL IMPLEMENTATION DETAILS

### GitOps Repository Structure

**Test Repository**: https://github.com/afewell-hh/gitops-test-1.git  
**CRD Directory**: `/gitops/hedgehog/fabric-1/`  
**Expected Files**: YAML files containing Hedgehog CRDs for testing

**File Attribution Requirements**:
- Each imported CRD must have git_file_path set to full repository path
- CRD.get_git_file_status() must return "From Git" 
- Git metadata (commit SHA, last modified) should be preserved
- Sync operation must track which files were processed

### Integration with Existing Systems

**Preserve Working Functionality**:
- HCKC sync operations (currently working)
- All 12 CRD page functionality
- Database operations and migrations
- NetBox plugin integration patterns

**Use Existing Infrastructure**:
- Six-state resource model for state management
- Phase 5 testing framework for validation
- Clean codebase from Phase 6 cleanup
- Established GitOps service architecture

### Error Handling and Logging

**Comprehensive Error Handling**:
- Repository authentication failures
- Network connectivity issues
- YAML parsing errors
- CRD validation failures
- Database operation exceptions

**Logging Requirements**:
- Debug-level logging for sync operation steps
- Error logging with full context for failures
- Info logging for successful operations with metrics
- User-friendly error messages in UI

---

## ESCALATION PROTOCOLS

### Specialist-Level Resolution:
- GitOps sync implementation and debugging
- Git repository integration challenges  
- CRD attribution logic fixes
- Testing framework integration
- Performance optimization for sync operations

### Manager Escalation Required:
- Architecture changes affecting other HNP components
- Requirements clarification for GitOps workflow
- Integration issues with NetBox core functionality
- Timeline concerns for delivery commitments
- Resource constraints requiring additional support

### Immediate Escalation Triggers:
- Any changes that break existing HCKC sync functionality
- Database schema modifications required
- NetBox plugin compatibility issues discovered  
- Security concerns with Git repository authentication
- Test framework modifications needed for validation

---

## PROJECT INTEGRATION NOTES

### Post-Recovery Enhancement Context

**Clean Foundation**: Leverage the recently completed 6-phase recovery:
- Organized codebase from Phase 6 cleanup
- Comprehensive testing framework from Phase 5
- Clear architecture documentation and project structure
- Established agent coordination patterns

**Quality Standards**: Maintain the high standards established during recovery:
- Evidence-based changes with validation testing
- Preservation of working functionality
- Comprehensive documentation of changes
- Integration with established project patterns

### Future Development Foundation

**This Fix Enables**:
- Complete GitOps workflow for HNP users
- Bi-directional sync between Git, NetBox, and Kubernetes
- Full self-service CRD management with version control
- Foundation for advanced GitOps features (PRs, branching, etc.)

**Sustainable Implementation**:
- Clean, maintainable code that fits HNP architecture
- Comprehensive test coverage for regression prevention
- Clear documentation for future enhancements
- Error handling that provides actionable user feedback

---

## EXPECTED OUTCOMES

### Immediate Impact
- "Sync from Git" button works correctly with test repository
- CRDs show proper "From Git" attribution in NetBox UI
- Git sync operations complete without errors
- Users can see their GitOps repository CRDs in NetBox

### User Workflow Completion
**Before Fix**:
1. User has CRDs in GitOps repository
2. User adds fabric to HNP and clicks "Sync from Git"  
3. ❌ Sync fails or shows "Not from Git" status
4. ❌ User cannot see proper Git attribution

**After Fix**:
1. User has CRDs in GitOps repository
2. User adds fabric to HNP and clicks "Sync from Git"
3. ✅ Sync completes successfully with proper attribution
4. ✅ CRDs show "From Git" status with file paths
5. ✅ Complete GitOps workflow operational

### Project Completion Impact
- HNP reaches 100% MVP completion with full GitOps integration
- Users have complete self-service CRD management capabilities
- Foundation established for advanced GitOps features
- Project ready for production deployment and scaling

---

**SPECIALIST READY**: Begin GitOps sync implementation with focus on proper Git attribution and comprehensive testing validation using the clean codebase and testing framework from the completed 6-phase recovery.

**SUCCESS METRIC**: Phase 5 GitOps attribution tests pass consistently, "Sync from Git" shows CRDs with "From Git" status, complete end-to-end GitOps workflow operational.