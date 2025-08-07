# Architecture Research Summary - GitOps Directory Feature

## Architecture Specifications Found

### Core GitOps Architecture
**Location**: `/architecture_specifications/00_current_architecture/component_architecture/gitops/`

**Key Documents Reviewed**:
1. `gitops_overview.md` - Comprehensive GitOps architecture design
2. `directory_management_specification.md` - Detailed directory management spec

## Expected System Behavior (Per Architecture)

### Directory Initialization Process
1. **When Fabric Added**: GitOps directory should undergo initialization with ingestion procedure
2. **Pre-existing Files**: YAML files with valid CRs should be ingested into HNP's opinionated directory structure  
3. **File Processing**: Support single or multiple valid CR objects per file
4. **File Recreation**: Create separate YAML file for each valid CR in proper structure
5. **Original File Cleanup**: Delete original files after successful ingestion
6. **Invalid File Handling**: Move non-valid CR files to "unmanaged" directory

### Opinionated Directory Structure
```
fabric-gitops-directory/
├── [HNP managed structure]/
│   ├── vpc/                 # VPC-related CRs
│   ├── connections/         # Connection CRs  
│   ├── switches/           # Switch CRs
│   └── ...                 # Other CR categories
├── raw/                    # Customer manual file drop location
└── unmanaged/             # Invalid/non-CR files
```

### Raw Directory Monitoring
- **Purpose**: Allow customers to place valid CR YAML files for import
- **Behavior**: Any file in raw/ should be ingested following same process
- **Invalid Handling**: Invalid files in raw/ moved to unmanaged/

### Pre-Sync Directory Validation
- **Trigger**: Before each synchronization event
- **Validation**: Ensure fabric's gitops directory compliant with required structure
- **Repair**: Attempt to safely repair structure by:
  - Moving invalid files to unmanaged/
  - Ingesting files if needed
  - Repairing subdirectory structure if needed

## Current Implementation Status

### What's Working ✅
- **Directory Structure Creation**: Gitops directory subdirectory structure is created correctly
- **Repository Authentication**: GitRepository system working with encrypted credentials
- **Basic Sync**: Existing YAML files can be processed when in correct structure

### What's NOT Working ❌
- **File Ingestion**: Pre-existing YAML files in directory root are NOT being ingested
- **Original File Cleanup**: Files remain in original location after fabric creation

### Status Unknown ❓
- **Raw Directory Monitoring**: Unknown if raw/ directory ingestion is working
- **Directory Structure Validation**: Unknown if pre-sync validation/repair is working  
- **Invalid File Management**: Unknown if invalid files are moved to unmanaged/

## Critical Missing Components Identified

### 1. Initialization Ingestion Process
**Problem**: When fabric is created, existing YAML files in gitops directory are not processed through ingestion workflow.

**Expected Workflow**:
```python
def initialize_fabric_gitops_directory(fabric):
    1. Scan gitops directory for existing YAML files
    2. For each YAML file:
       a. Parse and validate YAML content
       b. Extract valid CR objects  
       c. Create separate files in opinionated structure
       d. Delete original file after successful processing
    3. Move invalid files to unmanaged/
    4. Create required directory structure (raw/, unmanaged/, etc)
```

### 2. Raw Directory Monitoring
**Problem**: No evidence that raw/ directory is being monitored for new files.

**Expected Workflow**:
```python
def process_raw_directory(fabric):
    1. Check raw/ directory for new files
    2. Process valid CR files through ingestion
    3. Move invalid files to unmanaged/
    4. Clean raw/ directory after processing
```

### 3. Pre-Sync Structure Validation
**Problem**: No validation/repair process before sync events.

**Expected Workflow**:
```python
def validate_directory_structure_before_sync(fabric):
    1. Verify required directories exist (raw/, unmanaged/, etc)
    2. Check for files in wrong locations
    3. Process any files needing ingestion
    4. Move invalid files to unmanaged/
    5. Repair directory structure if broken
```

## Evidence from Test Environment

### Current State in Test Environment
- **Test Fabric**: Configured in HNP with prestaged YAML files
- **Directory Structure**: Created correctly ✅
- **File Ingestion**: FAILED ❌ - Files still in gitops directory root unchanged
- **Files Present**: Valid CR YAML files sitting unprocessed in directory root

### Expected vs Actual
**Expected**: Files should be processed, recreated in opinionated structure, originals deleted
**Actual**: Files remain exactly as they were before fabric creation

## Next Steps for Implementation Analysis

1. **Examine Current Sync Code**: Analyze existing synchronization implementation
2. **Identify Missing Ingestion Logic**: Find where initialization ingestion should be but isn't
3. **Check Raw Directory Handling**: Verify if raw directory monitoring exists
4. **Validate Structure Repair**: Check if pre-sync validation exists
5. **Test Environment Verification**: Validate current state in test environment

## Key Files to Investigate

Based on architecture and HNP structure:
- `netbox_hedgehog/sync/` - Synchronization logic
- `netbox_hedgehog/models.py` - HedgehogFabric model methods
- `netbox_hedgehog/views/` - Fabric creation views
- Fabric detail page and sync triggers

## Success Criteria for Fix

1. **Initialization Ingestion**: Pre-existing files processed during fabric creation
2. **Opinionated Structure**: Files recreated in proper directory structure  
3. **File Cleanup**: Original files deleted after successful ingestion
4. **Raw Directory**: Files placed in raw/ are processed automatically
5. **Structure Validation**: Pre-sync validation repairs directory structure
6. **Invalid File Handling**: Invalid files moved to unmanaged/ directory
7. **Test Environment Proof**: User can see working ingestion in HNP test environment