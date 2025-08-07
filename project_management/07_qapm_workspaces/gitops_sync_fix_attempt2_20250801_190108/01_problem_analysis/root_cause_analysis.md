# ROOT CAUSE ANALYSIS - GitOps Sync Failure

## 🚨 CRITICAL FINDING: Two Competing Sync Systems

### PROBLEM IDENTIFIED
The system has **TWO SEPARATE** GitOps sync mechanisms that operate on DIFFERENT directory structures:

### 1. Legacy Git Directory Sync System
**File**: `/netbox_hedgehog/utils/git_directory_sync.py`
**Triggered by**: `fabric.trigger_gitops_sync()` 
**Operates on**: Repository root with `gitops_directory` path
**Expected**: Processes YAML files directly from Git repository clone
**DOES NOT** use raw/managed directory structure

### 2. New GitOps Architecture System  
**File**: `/netbox_hedgehog/services/gitops_onboarding_service.py`
**Triggered by**: GitOps API endpoints (`/ingest-raw/`, `/init-gitops/`)
**Operates on**: raw/managed/unmanaged directory structure
**Expected**: Processes files from raw/ directory to managed/ subdirectories

## 🎯 ROOT CAUSE HYPOTHESIS

The 3 YAML files in GitHub raw/ directory are NOT being processed because:

### Issue #1: Wrong Sync System Being Used
- The GitHub repository has files in `/raw/` directory structure
- But `fabric.trigger_gitops_sync()` uses the LEGACY system
- Legacy system looks for files in repository root at `gitops_directory` path
- Legacy system IGNORES the new raw/managed structure

### Issue #2: GitOps Structure Not Initialized
- The new GitOps system requires initialization via `/init-gitops/` API
- If GitOps structure is not initialized, the fabric lacks:
  - `gitops_initialized = True` flag
  - `raw_directory_path` field
  - `managed_directory_path` field

### Issue #3: API Endpoint Mismatch
- Current sync uses: `/api/plugins/hedgehog/fabrics/{id}/gitops_sync/`  
- But for raw/ processing, should use: `/api/plugins/hedgehog/fabrics/{id}/ingest-raw/`

## 🔍 EVIDENCE REQUIRED

1. **Check fabric.gitops_initialized status**
2. **Test NEW GitOps ingestion API** (`/ingest-raw/`)
3. **Verify directory structure** in fabric configuration
4. **Trace actual sync path** being used

## 🎯 EXPECTED SOLUTION

1. Initialize GitOps structure if not done
2. Use correct API endpoint for raw/ directory processing
3. OR modify legacy sync to handle new directory structure