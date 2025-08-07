# FGD Sync Issue - Problem Confirmation Report

**Date**: August 4, 2025  
**QAPM Agent**: Enhanced QAPM v2.5  
**Issue**: Raw Directory Ingestion Failure

## Problem Confirmed ✅

The Fabric GitOps Directory (FGD) synchronization system has a **confirmed failure in raw directory processing**. The investigation has identified the exact nature and scope of the issue.

## Evidence Summary

### ✅ Working Components
1. **Directory Structure Creation**: Properly creates HNP opinionated directory structure
   - `.hnp/` directory present
   - `managed/` directory with proper subdirectories (connections, vpcs, switches, etc.)
   - `raw/` directory created
   - `unmanaged/` directory created

2. **Fabric Configuration**: Properly configured with valid git repository connection
   - Fabric: "Test Fabric for GitOps Initialization" (ID: 31)
   - GitOps Directory: "gitops/hedgehog/fabric-1"
   - Git Repository: Connected and authenticated

### ❌ Failing Components
1. **Raw Directory Ingestion**: Files are not processed from raw/ directory
   - **Evidence**: 3 YAML files (639 lines total) sitting unprocessed in raw/
   - `prepop.yaml` (617 lines) - Contains SwitchGroup and other CRDs
   - `test-vpc.yaml` (11 lines) - Contains VPC configuration
   - `test-vpc-2.yaml` (11 lines) - Contains VPC configuration

2. **Database Record Creation**: No CRD records created in database
   - **Evidence**: Fabric cached_crd_count = 0
   - **Expected**: Should have multiple CRD records from processed files

## Detailed Investigation Results

### Current Repository State
**Repository**: https://github.com/afewell-hh/gitops-test-1  
**Directory Path**: gitops/hedgehog/fabric-1/

```
gitops/hedgehog/fabric-1/
├── .hnp/
├── README.md
├── managed/               ← Empty (files should be here)
│   ├── connections/
│   ├── vpcs/
│   ├── switches/
│   └── [other CRD subdirectories]
├── raw/                  ← FILES STUCK HERE (should be processed)
│   ├── prepop.yaml       ← 617 lines of CRD definitions
│   ├── test-vpc.yaml     ← 11 lines of VPC configuration  
│   └── test-vpc-2.yaml   ← 11 lines of VPC configuration
└── unmanaged/
```

### Expected vs Actual Behavior

| Component | Expected | Actual | Status |
|-----------|----------|---------|---------|
| Directory Creation | ✓ Create structure | ✓ Structure created | ✅ Working |
| Raw File Processing | ✓ Process files from raw/ | ❌ Files remain in raw/ | ❌ Failed |
| File Movement | ✓ Move to managed/ subdirs | ❌ No movement occurred | ❌ Failed |
| Database Records | ✓ Create CRD records | ❌ No records created | ❌ Failed |
| CRD Count Update | ✓ Update cached count | ❌ Remains at 0 | ❌ Failed |

### File Content Analysis
The files in raw/ contain valid Kubernetes CRDs:
- **SwitchGroup** resources in prepop.yaml 
- **VPC** configurations in test-vpc files
- **Valid YAML structure** confirmed
- **Total content**: 639 lines of configuration

## Root Cause Analysis Required

### Investigation Targets
1. **Raw Directory Processing Service**: Code responsible for scanning and processing raw/ directory
2. **File Ingestion Logic**: Code that moves files from raw/ to managed/ subdirectories  
3. **Database Record Creation**: Code that creates CRD records from processed files
4. **Synchronization Triggers**: When and how raw directory processing is triggered

### Code Locations to Investigate
Based on HNP architecture:
- `netbox_hedgehog/services/gitops_ingestion_service.py`
- `netbox_hedgehog/services/gitops_onboarding_service.py`
- `netbox_hedgehog/services/raw_directory_watcher.py`
- Related signal handlers and initialization code

## Impact Assessment

### User Impact
- **Broken Feature**: Users cannot add existing YAML files to raw/ directory for processing
- **Failed Initialization**: New fabrics don't properly ingest pre-existing files
- **Manual Workaround Required**: Users must manually create records through UI

### System Impact
- **Data Integrity**: GitOps directory out of sync with database
- **Workflow Disruption**: GitOps-first workflow partially broken
- **Configuration Drift**: Intended configuration not applied to fabric

## Next Steps

1. **Code Analysis**: Examine ingestion service implementations
2. **Logic Tracing**: Identify where raw directory processing should occur
3. **Gap Identification**: Find specific failure points in the code
4. **Fix Design**: Create comprehensive solution addressing all failure modes
5. **Evidence-Based Testing**: Implement validation to prevent future failures

## Resolution Criteria

The issue will be considered resolved when:
- ✅ Files placed in raw/ directory are automatically processed
- ✅ Valid CRD files are moved to appropriate managed/ subdirectories  
- ✅ Database records are created for processed CRDs
- ✅ Fabric cached_crd_count reflects actual processed files
- ✅ Both initial fabric creation and ongoing raw/ monitoring work correctly