# Kubernetes Integration Architecture

**Purpose**: Document HNP's integration patterns with Kubernetes clusters  
**Status**: Operational with K3s cluster at 127.0.0.1:6443  
**Integration Method**: GitOps-first with YAML parsing

## Integration Overview

HNP integrates with Kubernetes through a GitOps-first approach, processing YAML files from git repositories and creating corresponding database records for CRD management through the NetBox interface.

## Core Integration Components

### GitOps Repository Processing
```
Repository Access Pattern:
HNP → GitRepository(encrypted_auth) → GitHub API → 
Clone Repository → Access gitops/hedgehog/fabric-1/ → 
Parse YAML files → Create CRD Records
```

### File Processing Architecture
```
Repository Files Currently Processed:
├── prepop.yaml        # Base configuration  
├── test-vpc.yaml      # VPC definitions
└── test-vpc-2.yaml    # Additional VPC configuration

Processing Results (Current State):
├── Resources Created: 0
├── Resources Updated: 48
├── Files Processed: 3
└── Total CRD Records: 36
```

## CRD Type Support

### Currently Operational CRD Types
- **VPCs**: 2 records synchronized from YAML definitions
- **Connections**: 26 records synchronized from connection configurations
- **Switches**: 8 records synchronized from switch definitions
- **Total**: 12 CRD types with 36 total records operational

### Data Model Integration
```python
# CRD Models Successfully Synchronized:
class VPC(models.Model):
    # VPC CRD representations with NetBox integration

class Connection(models.Model):
    # Connection CRD representations with fabric linking

class Switch(models.Model):
    # Switch CRD representations with operational data
```

## Synchronization Workflow

### GitOps Synchronization Process
1. **User Trigger**: Sync initiated from fabric detail page
2. **Authentication**: Encrypted credentials retrieved for repository access
3. **Repository Clone**: Secure git repository access with directory targeting
4. **YAML Processing**: Parse files in gitops_directory path
5. **CRD Creation**: Database records created/updated from YAML content
6. **Cache Update**: fabric.cached_crd_count updated to reflect changes
7. **Status Report**: Sync results returned to user interface

### Real-Time Sync Results
```
Current Operational Sync:
- Repository: github.com/afewell-hh/gitops-test-1
- Directory: gitops/hedgehog/fabric-1/
- Files Processed: 3 YAML files
- Records Updated: 48 resource updates
- Total CRDs: 36 records synchronized
- Sync Status: Successfully completed
```

## Environment Integration

### Cluster Configuration
- **HCKC Cluster**: K3s at 127.0.0.1:6443
- **Access Method**: GitOps repository-based (no direct cluster API access)
- **Configuration Source**: YAML files in git repository structure

### Authentication Architecture
```python
class GitRepository:
    encrypted_credentials: dict  # Secure credential storage
    connection_status: str       # 'connected', 'failed', 'pending'
    last_validated: datetime     # Connection health tracking
```

## Integration Patterns

### Repository Access Pattern
```python
# Successful Authentication Flow
git_repo = GitRepository.objects.get(id=6)
# Uses encrypted_credentials for GitHub access
# connection_status: "connected"
# last_validated: 2025-07-29 08:57:53+00:00
```

### Directory Management
- **Targeted Access**: Specific directory paths within repositories
- **Current Path**: `gitops/hedgehog/fabric-1/`
- **Multi-Fabric Ready**: Architecture supports multiple directory paths

## Performance and Monitoring

### Sync Performance Metrics
- **Processing Speed**: 48 resource updates processed successfully
- **File Parsing**: 3 YAML files processed without errors
- **Database Operations**: 36 CRD records created/updated
- **Error Rate**: 0% - all operations successful

### Health Monitoring
- **Connection Health**: Continuous validation of git repository connectivity
- **Sync Status Tracking**: Success/failure tracking with detailed reporting
- **Resource Counts**: Real-time CRD count caching for performance

## Integration Strengths

### Proven Capabilities
- **Authentication**: Encrypted credential storage with successful connectivity
- **File Processing**: Reliable YAML parsing and CRD creation
- **Error Handling**: Graceful handling of authentication and processing issues
- **Performance**: Efficient processing of repository content

### Operational Reliability
- **Consistent Results**: Repeatable sync operations with predictable outcomes
- **Status Tracking**: Comprehensive monitoring of integration health
- **Security**: No credential exposure in logs or error messages

## Future Integration Enhancements

### Planned Improvements (from ADR-002)
1. **Multi-Fabric Support**: Enhanced directory management for multiple fabrics
2. **Repository Separation**: Centralized git repository management interface
3. **Enhanced Monitoring**: More sophisticated drift detection capabilities
4. **API Expansion**: Direct Kubernetes API integration alongside GitOps

## References
- [GitOps Architecture Overview](gitops/gitops_overview.md)
- [NetBox Plugin Layer](netbox_plugin_layer.md)
- [System Overview](../system_overview.md)
- [ADR-002: Repository-Fabric Authentication Separation](../../01_architectural_decisions/approved_decisions/adr-002-repository-fabric-separation.md)