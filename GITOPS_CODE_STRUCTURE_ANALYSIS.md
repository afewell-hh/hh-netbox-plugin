# GitOps Implementation Code Structure Analysis

## Executive Summary

I have analyzed the GitOps implementation in the Hedgehog NetBox Plugin codebase. The system is well-structured with a clear separation of concerns for:

1. **GitOps Structure Initialization** - Setting up directory hierarchies
2. **File Ingestion** - Processing raw YAML files and normalizing them
3. **Sync & Reconciliation** - Coordinating between NetBox and Kubernetes
4. **Raw Directory Monitoring** - Automatic processing of newly added files

## Core GitOps Components Found

### 1. Main Sync Entry Points

**File: `netbox_hedgehog/views/fabric_views.py`**
- `FabricSyncView.post()` (lines 226-288) - Main sync trigger with GitOps integration
- `FabricOnboardingView.post()` (lines 312-362) - Fabric onboarding with GitOps setup
- Flow: `ensure_gitops_structure()` → `ingest_fabric_raw_files()` → `ReconciliationManager`

**File: `netbox_hedgehog/signals.py`**
- `ensure_gitops_structure()` (lines 104-147) - Validates/initializes GitOps structure
- `initialize_fabric_gitops()` (lines 14-50) - Called on new fabric creation
- `ingest_fabric_raw_files()` (lines 52-78) - Processes raw files before sync

### 2. GitOps Directory Structure Management

**File: `netbox_hedgehog/services/gitops_onboarding_service.py`**
- `GitOpsOnboardingService` class - Initializes complete directory structure
- Creates: `raw/`, `managed/`, `.hnp/` directories with proper subdirectories
- Handles migration of existing files from old structure

**Expected Directory Layout:**
```
fabrics/{fabric-name}/gitops/
├── raw/                        # User drops files here
├── managed/                    # HNP manages these
│   ├── connections/
│   ├── servers/
│   ├── switches/
│   ├── switchgroups/
│   ├── vlannamespaces/
│   ├── vpcs/
│   ├── externals/
│   ├── externalattachments/
│   ├── externalpeerings/
│   ├── ipv4namespaces/
│   ├── vpcattachments/
│   └── vpcpeerings/
└── .hnp/                      # HNP metadata
    ├── manifest.yaml
    └── archive-log.yaml
```

### 3. File Ingestion Pipeline

**File: `netbox_hedgehog/services/gitops_ingestion_service.py`**
- `GitOpsIngestionService` class (lines 22-555) - Core ingestion logic
- `process_raw_directory()` (lines 68-117) - Processes all files in raw/
- `process_single_file()` (lines 119-157) - Handles individual files
- Key Methods:
  - `_parse_multi_document_yaml()` - Safely parses multi-doc YAML files
  - `_normalize_document_to_file()` - Splits multi-doc into single files
  - `_archive_file()` - Archives processed files with `.archived` extension

**File: `netbox_hedgehog/management/commands/ingest_raw_files.py`**
- Django management command for manual/automated ingestion
- Supports: `--fabric`, `--all`, `--file`, `--watch` modes
- Can monitor directories continuously or run one-time batch processing

### 4. Raw Directory Monitoring

**File: `netbox_hedgehog/services/raw_directory_watcher.py`**
- `RawDirectoryWatcher` class (lines 22-442) - Monitors raw/ for new files
- Threading-based polling with configurable intervals
- Integrates with `GitOpsIngestionService` for automatic processing
- `RawDirectoryWatcherManager` for managing multiple fabric watchers

### 5. Path Resolution Logic

The system uses multiple fallback strategies for determining GitOps paths:

1. **New Architecture**: `fabric.raw_directory_path`, `fabric.managed_directory_path`
2. **Git Repository Integration**: `fabric.git_repository.local_path`
3. **Legacy Git Config**: `fabric.git_repository_url` → `/tmp/hedgehog-repos/`
4. **Default Fallback**: `/var/lib/hedgehog/fabrics/{fabric.name}/gitops`

## Key Integration Points

### Signal-Driven Initialization
- New fabrics automatically trigger GitOps structure creation via `post_save` signal
- CRD changes are tracked through Django signals for GitOps sync

### File Processing Flow
1. User drops YAML files in `raw/` directory
2. `RawDirectoryWatcher` detects new files (or manual trigger)
3. `GitOpsIngestionService` processes files:
   - Parses multi-document YAML
   - Validates Kubernetes structure
   - Normalizes to single-document files in `managed/`
   - Archives original files with `.archived` extension
   - Updates tracking metadata in `.hnp/`

### Sync Integration
- Fabric sync operations call `ensure_gitops_structure()` first
- Raw file ingestion runs before reconciliation
- Integration with existing `ReconciliationManager` for K8s sync

## Potential Issues to Debug

Based on the code analysis, potential debugging areas include:

1. **Path Resolution Conflicts**: Multiple fallback strategies could lead to inconsistent paths
2. **File Locking**: Multi-threaded access to raw directories during ingestion
3. **Error Handling**: Failed ingestion might leave files in inconsistent states
4. **GitOps Structure Validation**: `validate_gitops_structure()` logic needs verification
5. **Signal Race Conditions**: Multiple signals firing during fabric/CRD operations

## File Organization Quality

The code is well-organized with clear separation of concerns:
- ✅ Services properly separated (ingestion, onboarding, watching)
- ✅ Views handle HTTP interactions only
- ✅ Signals provide integration hooks
- ✅ Management commands enable CLI operations
- ✅ Comprehensive error handling and logging

## Debugging Recommendations

1. **Verify Directory Structure**: Check if `ensure_gitops_structure()` properly initializes all required directories
2. **Test File Ingestion**: Verify multi-document YAML splitting and archiving works correctly
3. **Path Resolution**: Confirm path resolution logic chooses correct directories consistently
4. **Raw Directory Monitoring**: Test if file watching properly detects and processes new files
5. **Integration Flow**: Verify the complete flow from file drop → ingestion → sync → reconciliation

The implementation appears comprehensive and well-architected for handling the GitOps workflow requirements.