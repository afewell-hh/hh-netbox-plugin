# ADR-002: Repository-Fabric Authentication Separation

**Status**: 🔄 APPROVED FOR IMPLEMENTATION  
**Decision Date**: Identified during architecture analysis (July 29, 2025)  
**Context**: Authentication tightly coupled with fabric creation causing multi-fabric inefficiencies

## Decision Statement

Separate git repository authentication from fabric configuration to enable efficient multi-fabric management on shared repositories.

## Context and Problem Statement

### Current Architecture Issues
- **Coupled Authentication**: Git authentication occurs during fabric creation workflow
- **Repeated Authentication**: Each fabric creation requires separate authentication for same repository
- **Enterprise Limitation**: Cannot efficiently support multiple fabrics (Production, Staging) in single repository using different directories
- **User Experience**: Suboptimal experience requiring repeated authentication for shared repositories

### Use Case Requirements
```
Enterprise Scenario:
Repository: company-infrastructure-repo.git
├── gitops/hedgehog/production/     # Production fabric
├── gitops/hedgehog/staging/        # Staging fabric  
└── gitops/hedgehog/development/    # Development fabric

Current Problem:
- Each fabric requires separate authentication setup
- No reuse of repository credentials across fabrics
- Authentication management scattered across fabric configurations
```

### Current Implementation State
```python
# Current tightly-coupled approach:
class HedgehogFabric:
    # Authentication mixed with configuration
    git_repository_url: str
    git_credentials: dict  # Mixed with fabric data
    gitops_directory: str
    
    # Issues:
    # - Duplicate authentication for shared repositories
    # - No centralized credential management
    # - Difficult multi-fabric repository support
```

## Decision Rationale

### 1. Separation of Concerns
- **Authentication** (infrastructure concern) separate from **Configuration** (application logic)
- Clear responsibility boundaries between credential management and fabric setup
- Simplified debugging and maintenance through separated concerns

### 2. Multi-Fabric Enterprise Support
- Single repository authentication supports multiple fabric configurations
- Enterprise customers can efficiently manage complex repository structures
- Reduced authentication overhead for shared repositories

### 3. User Experience Enhancement
- Eliminates repeated authentication for shared repositories
- Streamlined fabric creation workflow with repository selection
- Post-creation git configuration editing capability

### 4. Operational Efficiency
- Centralized credential management and rotation
- Simplified repository health monitoring
- Reduced authentication-related support issues

## Proposed Architecture

### Separated Data Models
```python
# Centralized Repository Management
class GitRepository:
    id: str
    name: str                                    # "Company Infrastructure Repo"
    url: str                                     # Repository URL
    authentication_type: str                     # 'token', 'ssh_key', 'oauth'
    authentication_credentials: dict             # Encrypted storage
    connection_status: str                       # 'connected', 'failed', 'pending'
    last_validated: datetime                     # Health monitoring
    validation_error: str                        # Error details
    
    def test_connection(self):
        """Test repository connectivity with current credentials"""
        pass
    
    def refresh_credentials(self):
        """Refresh and validate authentication credentials"""
        pass

# Fabric Configuration Reference
class HedgehogFabric:
    git_repository: ForeignKey(GitRepository)    # Reference to authenticated repo
    gitops_directory: str                        # Directory path within repository
    
    # Example configurations:
    # fabric_prod = HedgehogFabric(
    #     git_repository=repo,
    #     gitops_directory="gitops/hedgehog/production/"
    # )
    # 
    # fabric_staging = HedgehogFabric(
    #     git_repository=repo,
    #     gitops_directory="gitops/hedgehog/staging/"
    # )
```

### Enhanced User Interfaces

#### Git Repository Management Interface
**Dedicated Management Page**: `/plugins/hedgehog/git-repositories/`

```html
<!-- Repository List Interface -->
<div class="repository-list">
    <div class="repository-header">
        <h2>Git Repositories</h2>
        <button class="btn btn-primary" onclick="addRepository()">Add Repository</button>
    </div>
    
    <div class="repository-cards">
        {% for repo in repositories %}
        <div class="repository-card">
            <div class="repo-header">
                <h4>{{ repo.name }}</h4>
                <span class="connection-status {{ repo.connection_status }}">
                    {{ repo.get_connection_status_display }}
                </span>
            </div>
            <div class="repo-details">
                <p><strong>URL:</strong> {{ repo.url }}</p>
                <p><strong>Authentication:</strong> {{ repo.get_authentication_type_display }}</p>
                <p><strong>Last Validated:</strong> {{ repo.last_validated|timesince }} ago</p>
                <p><strong>Used by:</strong> {{ repo.fabric_count }} fabric(s)</p>
            </div>
            <div class="repo-actions">
                <button onclick="testConnection({{ repo.id }})">Test Connection</button>
                <button onclick="editRepository({{ repo.id }})">Edit</button>
                <button onclick="deleteRepository({{ repo.id }})">Delete</button>
            </div>
        </div>
        {% endfor %}
    </div>
</div>
```

#### Enhanced Fabric Creation Workflow
```html
<!-- Fabric Creation with Repository Selection -->
<div class="fabric-creation-form">
    <div class="form-step" id="step-1">
        <h3>Step 1: Basic Information</h3>
        <input type="text" name="fabric_name" placeholder="Fabric Name" required>
        <textarea name="description" placeholder="Description"></textarea>
    </div>
    
    <div class="form-step" id="step-2">
        <h3>Step 2: Repository Configuration</h3>
        <div class="repository-selection">
            <label>Select Git Repository:</label>
            <select name="git_repository" required>
                <option value="">Choose existing repository...</option>
                {% for repo in available_repositories %}
                <option value="{{ repo.id }}">{{ repo.name }} ({{ repo.url }})</option>
                {% endfor %}
            </select>
            <button type="button" onclick="addNewRepository()">Add New Repository</button>
        </div>
        
        <div class="directory-configuration">
            <label>GitOps Directory Path:</label>
            <input type="text" name="gitops_directory" 
                   placeholder="gitops/hedgehog/fabric-name/" required>
            <button type="button" onclick="validateDirectory()">Validate Path</button>
        </div>
    </div>
    
    <div class="form-step" id="step-3">
        <h3>Step 3: Validation and Creation</h3>
        <div class="configuration-summary">
            <!-- Dynamic summary of selected configuration -->
        </div>
        <button type="submit">Create Fabric</button>
    </div>
</div>
```

### API Architecture Enhancement

#### New Repository Management Endpoints
```python
# Repository Management API
@api_view(['GET'])
def list_git_repositories(request):
    """List all authenticated git repositories"""
    repositories = GitRepository.objects.all()
    serializer = GitRepositorySerializer(repositories, many=True)
    return Response(serializer.data)

@api_view(['POST'])
def create_git_repository(request):
    """Add new git repository with authentication"""
    serializer = GitRepositorySerializer(data=request.data)
    if serializer.is_valid():
        repository = serializer.save()
        # Test connection immediately
        connection_result = repository.test_connection()
        return Response({
            'repository': GitRepositorySerializer(repository).data,
            'connection_test': connection_result
        })
    return Response(serializer.errors, status=400)

@api_view(['PUT'])
def update_git_repository(request, repository_id):
    """Update repository credentials and configuration"""
    repository = GitRepository.objects.get(id=repository_id)
    serializer = GitRepositorySerializer(repository, data=request.data, partial=True)
    if serializer.is_valid():
        repository = serializer.save()
        # Re-test connection after update
        connection_result = repository.test_connection()
        return Response({
            'repository': GitRepositorySerializer(repository).data,
            'connection_test': connection_result
        })
    return Response(serializer.errors, status=400)

@api_view(['POST'])
def test_repository_connection(request, repository_id):
    """Test repository connectivity"""
    repository = GitRepository.objects.get(id=repository_id)
    connection_result = repository.test_connection()
    return Response(connection_result)

@api_view(['DELETE'])
def delete_git_repository(request, repository_id):
    """Delete repository with dependency validation"""
    repository = GitRepository.objects.get(id=repository_id)
    
    # Check for dependent fabrics
    dependent_fabrics = HedgehogFabric.objects.filter(git_repository=repository)
    if dependent_fabrics.exists():
        return Response({
            'error': 'Cannot delete repository with dependent fabrics',
            'dependent_fabrics': [f.name for f in dependent_fabrics]
        }, status=400)
    
    repository.delete()
    return Response({'success': True})
```

## Implementation Plan

### Phase 1: Backend Model Separation (2-3 weeks)
1. **Create GitRepository Model**
   - Design model with authentication fields
   - Implement encrypted credential storage
   - Add connection testing methods
   
2. **Update HedgehogFabric Model**
   - Add ForeignKey to GitRepository
   - Remove direct authentication fields
   - Maintain backward compatibility during transition
   
3. **Data Migration Strategy**
   - Migrate existing fabric git configurations to separated model
   - Preserve authentication credentials during transition
   - Validate migration success

### Phase 2: API Development (1-2 weeks)
1. **Repository Management Endpoints**
   - CRUD operations for git repositories
   - Connection testing API
   - Repository health monitoring
   
2. **Enhanced Fabric Endpoints**
   - Updated fabric creation with repository selection
   - Fabric editing with repository changes
   - Validation endpoints for directory paths

### Phase 3: Frontend Implementation (2-3 weeks)
1. **Git Repository Management Interface**
   - Repository list and detail views
   - Add/edit repository modals
   - Connection status monitoring
   
2. **Enhanced Fabric Creation Workflow**
   - Multi-step creation process
   - Repository selection and validation
   - Inline repository addition

### Phase 4: Integration and Testing (1-2 weeks)
1. **End-to-End Testing**
   - Multi-fabric repository scenarios
   - Authentication and sync workflows
   - Error handling and recovery
   
2. **Migration Testing**
   - Data migration validation
   - Backward compatibility verification
   - Performance impact assessment

### Phase 5: Deployment and Migration (1 week)
1. **Production Migration**
   - Staged migration process
   - Rollback procedures
   - User communication and training

## Risk Mitigation

### Authentication Security Risks
- **Credential Migration**: Secure transfer of existing credentials to new model
- **Connection Testing**: Validate credentials without exposure
- **Error Handling**: Secure failure modes without credential leakage

### User Experience Risks
- **Migration Complexity**: Gradual migration with user guidance
- **Workflow Changes**: Clear documentation and training materials
- **Rollback Capability**: Ability to revert if issues arise

### Technical Implementation Risks
- **Data Integrity**: Comprehensive testing of model relationships
- **Performance Impact**: Optimization of new query patterns
- **Container Synchronization**: Validation of file sync during development

## Success Criteria

### Technical Success Metrics
- **Multi-Fabric Support**: Single repository supports multiple fabrics successfully
- **Authentication Efficiency**: No repeated authentication for shared repositories
- **Connection Health**: Continuous monitoring of repository connectivity
- **Migration Success**: All existing configurations preserved and functional

### User Experience Success Metrics
- **Workflow Simplification**: Reduced steps for fabric creation with shared repositories
- **Repository Management**: Centralized interface for credential management
- **Configuration Flexibility**: Post-creation editing of git repository assignments

### Performance Success Metrics
- **Query Optimization**: No performance degradation from model separation
- **Connection Testing**: Repository health checks complete within 10 seconds
- **Sync Performance**: No impact on existing GitOps synchronization speed

## Implementation Status

### Current State
- **Architecture Designed**: ✅ Complete separation architecture documented
- **Quality Gates Defined**: ✅ Phase-based implementation with validation
- **User Experience Mapped**: ✅ Enhanced workflows designed
- **API Specifications**: ✅ Endpoint definitions completed

### Next Steps
1. **Backend Implementation**: Begin GitRepository model creation
2. **Migration Planning**: Develop detailed data migration procedures
3. **Testing Framework**: Enhance test suite for multi-fabric scenarios
4. **Documentation**: Create user guides for new workflow

## Consequences

### Positive Consequences
- **Enterprise Readiness**: Supports complex multi-fabric enterprise use cases
- **Operational Efficiency**: Centralized credential management and monitoring
- **User Experience**: Streamlined workflows with reduced authentication overhead
- **Architecture Cleanliness**: Clear separation of concerns and responsibilities

### Negative Consequences
- **Implementation Complexity**: Significant development effort required
- **Migration Risk**: Potential disruption during transition period
- **Learning Curve**: Users must adapt to new workflow patterns

### Risk Mitigation Actions
- **Comprehensive Testing**: Extensive validation before production deployment
- **Gradual Migration**: Phased rollout with rollback capabilities
- **User Training**: Documentation and support during transition

## References
- [GitOps Architecture Overview](../../00_current_architecture/component_architecture/gitops/gitops_overview.md)
- [Current System Architecture](../../00_current_architecture/system_overview.md)
- [Directory Management Specification](../../00_current_architecture/component_architecture/gitops/directory_management_specification.md)
- [Implementation Timeline and Resources](../../../project_management/01_planning/strategic_roadmap.md)