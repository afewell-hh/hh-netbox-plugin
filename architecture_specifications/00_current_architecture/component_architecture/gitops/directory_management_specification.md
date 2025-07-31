# GitOps Directory Management Specification

**Purpose**: Detailed specification for GitOps directory initialization and management  
**Status**: Design approved for implementation  
**Current Implementation**: Basic directory targeting operational

## Directory Management Overview

This specification defines how HNP manages GitOps directories within git repositories, enabling multi-fabric support while maintaining separation of concerns between authentication and configuration management.

## Core Directory Architecture

### Repository Structure Pattern
```
Standard GitOps Repository Layout:
company-infrastructure-repo/
├── gitops/
│   └── hedgehog/
│       ├── production-fabric/          # Production environment
│       │   ├── prepop.yaml            # Base configuration
│       │   ├── vpc-config.yaml        # VPC definitions
│       │   ├── connection-config.yaml # Connection specifications
│       │   └── switch-config.yaml     # Switch configurations
│       ├── staging-fabric/            # Staging environment
│       │   ├── staging-prepop.yaml
│       │   ├── staging-vpc.yaml
│       │   └── staging-connections.yaml
│       └── development-fabric/        # Development environment
│           ├── dev-config.yaml
│           └── dev-vpc.yaml
└── other-infrastructure/              # Non-HNP content
    ├── terraform/
    └── ansible/
```

### Current Operational Example
```
Operational Directory Structure:
github.com/afewell-hh/gitops-test-1/
└── gitops/hedgehog/fabric-1/
    ├── prepop.yaml        # ✅ Successfully processed
    ├── test-vpc.yaml      # ✅ Successfully processed  
    └── test-vpc-2.yaml    # ✅ Successfully processed
    
Processing Results:
- Files Processed: 3
- Resources Updated: 48
- CRD Records Created: 36
- Status: ✅ Fully operational
```

## Directory Path Management

### Path Specification Format
```python
# Directory path specification:
gitops_directory: str = "path/within/repository/"

# Examples:
gitops_directory = "gitops/hedgehog/fabric-1/"           # Current operational
gitops_directory = "gitops/hedgehog/production-fabric/" # Multi-fabric example
gitops_directory = "infrastructure/hedgehog/staging/"   # Alternative structure
gitops_directory = "k8s-configs/fabric-main/"          # Custom naming
```

### Path Validation Rules
1. **Format Validation**: Must be valid relative path within repository
2. **Uniqueness Enforcement**: No two fabrics can use identical directory paths
3. **Access Verification**: Directory must be accessible with repository credentials
4. **Content Validation**: Directory must contain valid YAML configuration files
5. **Conflict Prevention**: Path conflicts detected and prevented during configuration

### Directory Resolution Process
```python
# Directory resolution workflow:
def resolve_gitops_directory(fabric):
    1. Validate directory path format
    2. Check path uniqueness across fabrics
    3. Verify repository authentication
    4. Test directory accessibility
    5. Scan for YAML configuration files
    6. Validate file parsing capability
    7. Return resolution status and file count
```

## Directory Initialization

### Automatic Directory Creation
When a fabric references a non-existent directory path:

```python
# Directory initialization workflow:
def initialize_gitops_directory(git_repo, directory_path):
    """
    Initialize GitOps directory if it doesn't exist
    """
    1. Authenticate with repository
    2. Check if directory path exists
    3. If not exists:
       a. Create directory structure
       b. Add default configuration templates
       c. Commit initialization
    4. Validate directory access
    5. Return initialization status
    
# Default template files created:
templates = [
    "prepop.yaml",      # Base configuration template
    "vpc-config.yaml",  # VPC configuration template  
    "README.md"         # Directory documentation
]
```

### Manual Directory Management
For existing directories with content:

```python
# Directory validation workflow:
def validate_existing_directory(git_repo, directory_path):
    """
    Validate and prepare existing GitOps directory
    """
    1. Verify directory exists and is accessible
    2. Scan for YAML configuration files
    3. Validate YAML syntax and structure
    4. Check for required configuration elements
    5. Generate configuration summary
    6. Return validation report
```

## Multi-Fabric Directory Support

### Repository Sharing Architecture
```python
# Single repository supporting multiple fabrics:
class GitRepository:
    id: 6
    name: "Company Infrastructure Repository"
    url: "https://github.com/company/infrastructure-repo"
    
# Multiple fabrics referencing different directories:
fabric_production = HedgehogFabric(
    git_repository=git_repo,
    gitops_directory="gitops/hedgehog/production/"
)

fabric_staging = HedgehogFabric(
    git_repository=git_repo,
    gitops_directory="gitops/hedgehog/staging/"
)

fabric_development = HedgehogFabric(
    git_repository=git_repo,
    gitops_directory="gitops/hedgehog/development/"
)
```

### Directory Conflict Prevention
```python
# Conflict detection logic:
def validate_directory_uniqueness(new_fabric):
    """
    Prevent directory conflicts across fabrics
    """
    existing_paths = HedgehogFabric.objects.values_list(
        'gitops_directory', flat=True
    )
    
    if new_fabric.gitops_directory in existing_paths:
        raise ValidationError(
            f"Directory path '{new_fabric.gitops_directory}' "
            f"already in use by another fabric"
        )
    
    return True
```

## File Processing Specification

### YAML File Discovery
```python
# File discovery process:
def discover_configuration_files(directory_path):
    """
    Discover and categorize YAML files in GitOps directory
    """
    supported_extensions = ['.yaml', '.yml']
    configuration_files = []
    
    for file in directory_contents:
        if file.extension in supported_extensions:
            file_info = {
                'path': file.path,
                'name': file.name,
                'size': file.size,
                'modified': file.last_modified,
                'content_type': detect_content_type(file.content)
            }
            configuration_files.append(file_info)
    
    return configuration_files
```

### Content Processing Pipeline
```python
# File processing pipeline:
def process_configuration_files(files):
    """
    Process discovered YAML files into CRD records
    """
    processing_results = {
        'files_processed': 0,
        'resources_created': 0,
        'resources_updated': 0,
        'errors': []
    }
    
    for file in files:
        try:
            1. Parse YAML content
            2. Validate schema compliance
            3. Extract CRD specifications
            4. Create/update database records
            5. Update processing statistics
        except Exception as e:
            processing_results['errors'].append({
                'file': file.name,
                'error': str(e)
            })
    
    return processing_results
```

## Directory Health Monitoring

### Health Check Specification
```python
# Directory health monitoring:
def check_directory_health(fabric):
    """
    Comprehensive directory health assessment
    """
    health_report = {
        'directory_accessible': False,
        'authentication_valid': False,
        'files_discovered': 0,
        'files_parseable': 0,
        'last_check': datetime.now(),
        'issues': []
    }
    
    try:
        1. Test repository authentication
        2. Verify directory path accessibility
        3. Scan for configuration files
        4. Validate file parsing
        5. Check for configuration drift
        6. Generate health summary
    except Exception as e:
        health_report['issues'].append(str(e))
    
    return health_report
```

### Continuous Monitoring
- **Scheduled Health Checks**: Periodic validation of directory accessibility
- **Authentication Monitoring**: Continuous credential validation
- **File Change Detection**: Monitoring for configuration file modifications
- **Drift Detection**: Comparison between repository content and database records

## Directory Change Management

### Configuration Updates
```python
# Directory path updates:
def update_gitops_directory(fabric, new_directory_path):
    """
    Safely update fabric GitOps directory path
    """
    1. Validate new directory path
    2. Check path uniqueness
    3. Test directory accessibility
    4. Backup current configuration
    5. Update fabric configuration
    6. Validate sync functionality
    7. Rollback if validation fails
```

### Repository Migration
```python
# Repository changes:
def migrate_fabric_repository(fabric, new_git_repository):
    """
    Migrate fabric to different git repository
    """
    1. Validate new repository authentication
    2. Check directory path exists in new repository
    3. Compare configuration content
    4. Backup current state
    5. Update fabric repository reference
    6. Test synchronization
    7. Validate functionality
```

## Error Handling and Recovery

### Common Directory Issues
1. **Directory Not Found**: Automatic creation or user notification
2. **Access Denied**: Authentication validation and credential update prompts
3. **Invalid YAML**: File-specific error reporting with parsing details
4. **Configuration Conflicts**: Conflict resolution workflow
5. **Network Issues**: Retry logic with exponential backoff

### Recovery Procedures
```python
# Error recovery workflow:
def recover_from_directory_error(fabric, error_type):
    """
    Automated recovery from directory access issues
    """
    recovery_actions = {
        'directory_not_found': initialize_gitops_directory,
        'access_denied': prompt_credential_update,
        'invalid_yaml': report_parsing_errors,
        'network_timeout': retry_with_backoff,
        'authentication_failed': refresh_authentication
    }
    
    recovery_action = recovery_actions.get(error_type)
    if recovery_action:
        return recovery_action(fabric)
    else:
        return escalate_to_user(fabric, error_type)
```

## Implementation Status

### Current Capabilities
- **✅ Directory Targeting**: Successfully accessing specific directory paths
- **✅ File Processing**: YAML files parsed and processed into CRD records
- **✅ Authentication**: Encrypted credentials working with repository access
- **✅ Error Handling**: Basic error detection and reporting

### Enhancement Requirements
- **🔄 Directory Creation**: Automatic initialization of non-existent directories
- **🔄 Conflict Prevention**: Multi-fabric directory uniqueness enforcement
- **🔄 Health Monitoring**: Comprehensive directory health checks
- **🔄 Change Management**: Safe directory path updates and migrations

## Success Metrics

### Operational Metrics
- **Directory Access Rate**: 100% successful access to configured directories
- **File Processing Rate**: 100% of valid YAML files processed successfully
- **Conflict Prevention**: Zero directory conflicts across fabrics
- **Recovery Success**: Automated recovery from common directory issues

### User Experience Metrics
- **Configuration Time**: Reduced time for GitOps directory setup
- **Error Resolution**: Clear error messages with actionable guidance
- **Multi-Fabric Support**: Seamless management of multiple fabric directories
- **Change Management**: Safe and reliable directory configuration updates

## References
- [GitOps Architecture Overview](gitops_overview.md)
- [Drift Detection Design](drift_detection_design.md)
- [Kubernetes Integration](../kubernetes_integration.md)
- [ADR-002: Repository-Fabric Authentication Separation](../../../01_architectural_decisions/active_decisions/gitops_repository_separation.md)