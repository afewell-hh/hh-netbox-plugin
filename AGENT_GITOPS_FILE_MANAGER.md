# GitOps File Manager Implementation Agent

## Agent Profile

### Background & Expertise
You are a senior software engineer specializing in:
- GitOps workflows and patterns (ArgoCD, Flux)
- Python Django development
- YAML parsing and multi-document handling
- Git automation and file system operations
- Distributed systems and data synchronization

### Required Skills
- Deep understanding of Kubernetes CRD patterns
- Experience with bidirectional sync systems
- File system transaction safety
- Git operations via Python
- Django ORM and model design
- Error handling and rollback strategies

## Project Onboarding

Before beginning implementation, thoroughly review these project documents in order:

1. **Architecture Overview**: Read `ARCHITECTURE_REVIEW_AGENT_INSTRUCTIONS.md` to understand the overall system design
2. **GitOps Workflow**: Study `AGENT_INSTRUCTIONS_GITOPS_WORKFLOW.md` for current GitOps implementation
3. **Database Schema**: Review `netbox_hedgehog/models/base.py` for BaseCRD structure
4. **Current Sync Logic**: Analyze `netbox_hedgehog/utils/git_directory_sync.py` for existing sync patterns
5. **GitOps Edit Service**: Examine `netbox_hedgehog/services/gitops_edit_service.py` for current edit workflow

## Primary Task: Implement GitOps File Management System

### Objective
Implement a robust bidirectional GitOps file management system that:
1. Preserves user's ability to manually edit files
2. Maintains structured organization for HNP management
3. Prevents data loss from multi-document YAML files
4. Provides clear audit trails

### Architecture Requirements

#### Directory Structure
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

### Implementation Tasks

#### 1. Create GitOps Onboarding Service
**File**: `netbox_hedgehog/services/gitops_onboarding_service.py`

Implement:
- `GitOpsOnboardingService` class
- Directory structure initialization
- Existing file detection and migration
- Archive strategy (rename to .archived)
- Manifest generation

#### 2. Create File Ingestion Service  
**File**: `netbox_hedgehog/services/gitops_ingestion_service.py`

Implement:
- Multi-document YAML parsing
- File normalization (one object per file)
- Archive original files
- Update tracking manifests
- Error handling and rollback

#### 3. Update GitOpsEditService
**File**: `netbox_hedgehog/services/gitops_edit_service.py`

Fix the critical bug:
- Remove file overwriting behavior
- Implement single-file updates in managed/ directory
- Preserve multi-document files in raw/
- Add safety checks

#### 4. Create Raw Directory Watcher
**File**: `netbox_hedgehog/services/raw_directory_watcher.py`

Implement:
- Monitor raw/ directory for new files
- Automatic ingestion on file detection
- Scheduled or event-based processing
- Integration with Django signals

#### 5. Update Fabric Model
**File**: `netbox_hedgehog/models/fabric.py`

Add fields:
- `gitops_initialized` (BooleanField)
- `archive_strategy` (CharField with choices)
- `raw_directory_path` (CharField)
- `managed_directory_path` (CharField)

#### 6. Create Management Commands
**Files**: 
- `netbox_hedgehog/management/commands/init_gitops.py`
- `netbox_hedgehog/management/commands/ingest_raw_files.py`

#### 7. Add API Endpoints
**File**: `netbox_hedgehog/api/views/gitops_views.py`

Endpoints:
- POST `/api/plugins/hedgehog/fabrics/{id}/init-gitops/`
- POST `/api/plugins/hedgehog/fabrics/{id}/ingest-raw/`
- GET `/api/plugins/hedgehog/fabrics/{id}/gitops-status/`

### Critical Implementation Details

#### Multi-Document YAML Handling
```python
def parse_multi_document_yaml(file_path):
    """Safely parse multi-document YAML files"""
    documents = []
    with open(file_path, 'r') as f:
        for doc in yaml.safe_load_all(f):
            if doc:  # Skip empty documents
                documents.append(doc)
    return documents
```

#### Archive Safety
```python
def archive_file(file_path):
    """Archive file with rollback capability"""
    archived_path = f"{file_path}.archived"
    try:
        os.rename(file_path, archived_path)
        return archived_path
    except Exception as e:
        # Rollback logic
        if os.path.exists(archived_path):
            os.rename(archived_path, file_path)
        raise
```

#### Transaction Safety
- Use database transactions for multi-step operations
- Implement filesystem rollback for failed operations
- Log all operations for debugging

### Testing Requirements

1. **Unit Tests**:
   - Multi-document YAML parsing
   - Archive operations
   - Directory initialization
   - Manifest generation

2. **Integration Tests**:
   - Full onboarding flow
   - Ingestion with various file formats
   - Edit operations on managed files
   - Rollback scenarios

3. **Edge Cases**:
   - Empty YAML files
   - Invalid YAML syntax
   - Duplicate object names
   - Permission errors
   - Git operation failures

### Success Criteria

1. ✅ No data loss when editing multi-document YAMLs
2. ✅ Clear separation of user vs HNP managed files
3. ✅ Preserved Git history with archived files
4. ✅ Robust error handling and rollback
5. ✅ Performance: <1 second for single file ingestion
6. ✅ Complete audit trail in manifests

### Delivery Expectations

1. Clean, well-documented code following project patterns
2. Comprehensive error messages for debugging
3. Unit and integration tests
4. Migration guide for existing installations
5. API documentation

### Notes on Current Codebase Issues

**CRITICAL BUG**: The current `GitOpsEditService._update_cr_yaml_file()` method overwrites entire files, destroying other objects in multi-document YAMLs. This MUST be fixed before any GUI editing is used in production.

**Integration Points**:
- Work with existing `GitDirectorySync` for read operations
- Enhance `GitOpsEditService` for write operations
- Maintain compatibility with existing CR models

Remember: The goal is to make GitOps file management invisible to users while maintaining full control and safety for HNP operations.