# GitOps Architecture Overview

**Purpose**: Comprehensive GitOps directory management design for HNP  
**Status**: Current implementation operational, enhanced design approved for implementation  
**Recovery Source**: Consolidated from scattered design documentation

## Executive Summary

This document consolidates the comprehensive GitOps architecture design for HNP that addresses fundamental issues in fabric/git synchronization and presents a sophisticated solution for multi-fabric GitOps directory management.

## Core Design Principles

### Separation of Concerns
The architecture elegantly separates git repository authentication from fabric configuration management, enabling efficient multi-fabric operations on shared repositories.

### Multi-Fabric Support
Architecture supports multiple fabrics using different directories within the same git repository:
```
Repository Structure Example:
├── gitops/
│   └── hedgehog/
│       ├── fabric-1/          # Production fabric
│       │   ├── prepop.yaml
│       │   ├── test-vpc.yaml
│       │   └── test-vpc-2.yaml
│       └── staging-fabric/    # Staging fabric
│           ├── staging-vpc.yaml
│           └── staging-config.yaml
```

### Directory Initialization Process
Sophisticated design for how HNP initializes and manages gitops directory structures with validation and conflict prevention.

## Repository Authentication Architecture

### Centralized Authentication Model
```python
class GitRepository:
    id: str
    name: str
    url: str
    authentication_type: str  # 'token', 'ssh_key', 'oauth'
    authentication_credentials: dict  # encrypted storage
    connection_status: str  # 'connected', 'failed', 'pending'
    last_validated: datetime
    validation_error: str
```

### Authentication Features
- **Component**: GitRepository management interface separate from fabric creation
- **Authentication Types**: Personal Access Tokens, SSH Keys, OAuth
- **Connection Testing**: Real-time connectivity validation
- **Health Monitoring**: Continuous authentication status tracking
- **Security**: Encrypted credential storage with no exposure

## Fabric Configuration Architecture

### Repository Reference Pattern
```python
class HedgehogFabric:
    git_repository: ForeignKey(GitRepository)  # reference to authenticated repo
    gitops_directory: str  # directory path within repository
    
    # Current operational example:
    # git_repository: GitRepository(id=6)
    # gitops_directory: "gitops/hedgehog/fabric-1/"
```

### Directory Management Features
- **Path Validation**: Uniqueness enforcement across fabrics
- **Directory Creation**: Capability to create paths if they don't exist
- **Conflict Prevention**: Multi-fabric conflict detection
- **Path Accessibility**: Verification of directory access rights

## Current Implementation Status

### Operational GitOps Integration
```
Current Working Example:
- Repository: github.com/afewell-hh/gitops-test-1
- Directory: gitops/hedgehog/fabric-1/
- Files Processed: prepop.yaml, test-vpc.yaml, test-vpc-2.yaml
- Records Synchronized: 36 CRD records
- Sync Status: ✅ Fully operational
```

### Authentication Status
```
GitRepository(id=6):
- name: "GitOps Test Repository 1"
- connection_status: "connected"
- last_validated: 2025-07-29 08:57:53+00:00
- encrypted_credentials: ✅ Configured and working
```

## Synchronization Workflow Architecture

### Current Sync Process
1. **User Trigger**: Sync initiated from fabric detail page
2. **Authentication**: Encrypted credentials retrieved securely
3. **Repository Access**: GitHub API access with encrypted auth
4. **Directory Targeting**: Access specific gitops_directory path
5. **YAML Processing**: Parse all YAML files in directory
6. **CRD Creation**: Database records created/updated from YAML
7. **Cache Update**: fabric.cached_crd_count updated
8. **Status Report**: Results returned to user interface

### Quality Gate Matrix
The design includes sophisticated quality assurance with phase-based implementation:

| Phase | Entry Criteria | Exit Criteria | Evidence Required |
|-------|---------------|---------------|-------------------|
| 1.1 | Project assignment | Pre-conditions pass | Test logs, DB queries |
| 2.1 | Phase 1 complete | FK relationship established | DB relationship verification |
| 3.1 | Phase 2 complete | Authentication working | Connection success evidence |
| 4.2 | Phase 4.1 complete | Sync creates records | Database record verification |

## Enhanced User Experience Design

### Unified Fabric Creation Workflow
The design consolidates the dual-pathway problem into a streamlined experience:
- **Single Entry Point**: Remove confusing "Add Fabric" vs "Add Git-First Fabric" options
- **Progressive Disclosure**: Step-by-step workflow with validation at each stage
- **Inline Repository Addition**: Add repositories without leaving fabric creation workflow

### Git Repository Management Interface
**Dedicated Management Page**: `/plugins/hedgehog/git-repositories/`
- List authenticated repositories with status indicators
- Add repository modal with authentication workflow  
- Edit repository credentials management
- Delete repository with dependency validation

## Drift Detection Integration

### Enhanced UI Integration
Comprehensive drift detection design with prominent placement:

#### Drift Spotlight Section
- **Placement**: Second major section on fabric detail page
- **Dynamic Styling**: 
  - `in-sync`: Green gradient background
  - `critical`: Red gradient background  
  - `warning`: Orange gradient background

#### Summary Cards Architecture
```html
<div class="drift-summary-cards">
    <div class="drift-summary-card">Resources with Drift: {{ count }}/{{ total }}</div>
    <div class="drift-summary-card">Last Check: {{ time_ago }}</div>
    <div class="drift-summary-card">Severity: {{ severity_level }}</div>
    <div class="drift-summary-card">Status: {{ drift_status }}</div>
</div>
```

#### Quick Action Buttons
- **Analyze Drift**: Detailed drift analysis modal
- **Sync from Git**: Configuration synchronization
- **Check for Drift**: Manual drift detection trigger
- **Configure Detection**: Settings for drift parameters

### Drift Detection Logic
```python
# Status Classification:
drift_summary = {
    'status': fabric.drift_status,       # 'in_sync', 'drift_detected', 'critical'
    'count': fabric.drift_count,         # Number of resources with drift
    'last_check': fabric.last_git_sync,  # Timestamp of last check
    'total_resources': total_crd_count,  # Total CRD count for comparison
    'severity': calculate_severity(drift_count)  # 'critical' (>5), 'important' (1-5)
}
```

## Technical Implementation Architecture

### Data Model Separation
```python
# Enhanced centralized authentication:
class GitRepository:
    # Handles authentication and connection management
    # Supports multiple fabrics per repository
    
# Updated fabric model:
class HedgehogFabric:
    git_repository: ForeignKey(GitRepository)
    gitops_directory: str
    # Removes direct authentication fields
    # Enables multi-fabric repository sharing
```

### API Architecture Expansion
**New Endpoints for Repository Management**:
- `GET /api/git-repositories/` - List authenticated repositories
- `POST /api/git-repositories/` - Add repository with authentication
- `PUT /api/git-repositories/{id}/` - Update credentials
- `POST /api/git-repositories/{id}/test-connection/` - Validate connectivity

### Migration Strategy
- **Data Preservation**: Migrate existing fabric git configurations to separated model
- **Authentication Migration**: Preserve credentials during transition
- **Backward Compatibility**: Maintain compatibility during migration period

## Implementation Timeline

### Phase-Based Development Plan
- **Phase 1: Architecture and Design** (1 week)
- **Phase 2: Backend Implementation** (2-3 weeks)  
- **Phase 3: Frontend Implementation** (2-3 weeks)
- **Phase 4: Integration and Testing** (1-2 weeks)
- **Phase 5: Deployment and Migration** (1 week)

**Total Timeline**: 7-10 weeks  
**Resources**: 2-3 full-stack developers, 1 QA engineer, UX consultation

## Risk Mitigation Strategies

### Agent False Completion Prevention
- **Independent Validation**: Required at each quality gate
- **Evidence Collection**: Mandatory before gate approval  
- **Cross-Validation**: Agent claims validated against actual functionality
- **Test-First Development**: Enforcement of TDD methodology

### Configuration Safety
- **Transaction-Based Changes**: Validation before commitment
- **Foreign Key Constraints**: Violation prevention mechanisms
- **Cache Invalidation**: After configuration changes
- **Container Restart Testing**: Persistence verification

## Success Criteria

### Technical Success Metrics
- All 10 mandatory tests pass
- Fabric correctly linked to GitRepository
- GitOps directory path properly configured
- Repository authentication working with encrypted credentials
- Sync creates CRD records (VPC, Connection, Switch)
- GUI displays functionality accurately

### User Experience Success
- Single repository authentication supports multiple fabrics
- No repeated authentication for shared repositories
- Streamlined fabric creation workflow
- Post-creation git configuration editing capability

## Architecture Evolution

This GitOps architecture design transforms HNP from a single-fabric, tightly-coupled system into an enterprise-ready GitOps platform capable of:

1. **Authentication/Configuration Separation**: Complete separation enabling efficient multi-fabric management
2. **Repository Directory Management**: Sophisticated directory initialization and management
3. **User Experience Enhancement**: Streamlined workflows with progressive disclosure
4. **Quality Assurance**: Comprehensive validation framework preventing false completions
5. **Technical Debt Resolution**: Clean architecture with proper separation of concerns

## References
- [Directory Management Specification](directory_management_specification.md)
- [Drift Detection Design](drift_detection_design.md)
- [System Overview](../../system_overview.md)
- [ADR-002: Repository-Fabric Authentication Separation](../../../01_architectural_decisions/active_decisions/gitops_repository_separation.md)