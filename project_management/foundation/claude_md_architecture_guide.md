# CLAUDE.md Architecture Implementation Guide

**Document Purpose**: Practical implementation guide for CLAUDE.md file architecture  
**Target**: Immediate deployment to solve HNP context management issues  
**Priority**: CRITICAL - Prevents agent context overflow and discovery cycles

---

## CLAUDE.md File Hierarchy for HNP

### Root Level: Project Overview
**Location**: `/hedgehog-netbox-plugin/CLAUDE.md`  
**Purpose**: Essential project context for all agents  
**Max Length**: 25 lines (strict limit for context efficiency)

```markdown
# Hedgehog NetBox Plugin (HNP) - Project Overview

**Mission**: Self-service Kubernetes CRD management through professional NetBox interface
**Status**: MVP COMPLETE - 12 CRD types operational across VPC API (5) and Wiring API (7)
**Tech Stack**: Django 4.2 + NetBox 4.3.3 plugin + Kubernetes + Bootstrap 5 + PostgreSQL

## Environment Architecture
- **NetBox**: Docker deployment with custom plugin integration
- **Kubernetes**: HCKC cluster with live CRD connectivity (49 CRDs imported)
- **GitOps**: ArgoCD integration for fabric deployment automation
- **Database**: PostgreSQL shared with NetBox core, complete schema

## Current Capabilities
- ✅ Full GUI framework with all templates and navigation
- ✅ Real-time Kubernetes connectivity and CRD import/sync
- ✅ Multi-fabric support with comprehensive status tracking
- ✅ Professional NetBox-integrated interface with Bootstrap 5
- ✅ All 12 CRD types with functional list and detail views

## Development Context
- **Branch**: feature/mvp2-database-foundation (current work)
- **Git Status**: Clean working directory, ready for new features
- **Testing**: Comprehensive test suite with fixtures and integration tests
- **Documentation**: Complete project management docs in /project_management/

## Import Additional Context
@project_management/CLAUDE.md
@netbox_hedgehog/CLAUDE.md
```

### Plugin Level: Core Functionality
**Location**: `/netbox_hedgehog/CLAUDE.md`  
**Purpose**: Plugin architecture and implementation details  
**Max Length**: 50 lines

```markdown
# NetBox Hedgehog Plugin - Core Implementation

**Architecture**: Standard NetBox plugin with models, views, API, templates, and utilities
**Database**: 12 CRD models + fabric management + git repository integration
**Integration**: Real Kubernetes connectivity with CRD import/sync capabilities

## Plugin Structure
- **Models**: CRD definitions, fabric management, git repositories, reconciliation tracking
- **Views**: List/detail views for all CRD types, sync operations, GitOps workflows  
- **API**: REST endpoints with serializers, filtering, and Kubernetes integration
- **Templates**: Bootstrap 5 responsive UI with progressive disclosure patterns
- **Utils**: Kubernetes client, GitOps integration, reconciliation services

## CRD Types Managed (12 Total)
**VPC API (5 types)**:
- VPC, VPCAttachment, VPCPeering, IPv4Namespace, VLANNamespace

**Wiring API (7 types)**:
- Switch, SwitchGroup, Connection, External, ExternalAttachment, ExternalPeering, Server

## Key Features
- **Real-time Sync**: Kubernetes watch patterns with reconciliation alerts
- **Multi-fabric Support**: Complete isolation and status tracking per fabric
- **GitOps Integration**: Repository sync, branch management, file operations
- **Progressive UI**: Complex data presentation with disclosure patterns
- **State Management**: Six-state workflow (Pending→Applied→Ready→Synced→Error→Unknown)

## Development Patterns
- **Testing**: Django TestCase with fixtures, integration tests for K8s connectivity
- **Performance**: Query optimization, prefetch_related, database indexing
- **Security**: RBAC integration, credential management, audit logging
- **Documentation**: Comprehensive docstrings, API docs, user guides

## Current Architecture Status
- ✅ All models operational with proper relationships and validation
- ✅ Complete view layer with list/detail/edit capabilities
- ✅ Full API implementation with filtering and serialization
- ✅ Responsive UI with NetBox integration and progressive disclosure
- ✅ Real Kubernetes integration with 49 CRDs successfully imported

## Import Specialized Context
@models/CLAUDE.md
@api/CLAUDE.md
@views/CLAUDE.md
@utils/CLAUDE.md
@templates/CLAUDE.md
```

### Component Level: Specialized Documentation
**Location**: `/netbox_hedgehog/models/CLAUDE.md`  
**Purpose**: Database schema and model implementation details  
**Max Length**: 40 lines

```markdown
# NetBox Hedgehog Models - Database Architecture

**Database Design**: PostgreSQL with Django ORM, shared with NetBox core
**Schema Status**: Complete with all 12 CRD types, relationships, and indexes
**Migration Status**: Current, no pending migrations

## Core Model Architecture
**Base Classes**: 
- NetBoxModel: Standard NetBox model with ID, timestamps, custom fields
- ChangeLoggedModel: Automatic change logging and history
- CustomValidationMixin: Domain-specific validation rules

## CRD Model Hierarchy
**VPC API Models**:
- VPC: Core VPC definition with CIDR and policy configuration
- VPCAttachment: Links VPCs to switches with VLAN management
- VPCPeering: Inter-VPC connectivity with routing configuration
- IPv4Namespace: IP address space management and allocation
- VLANNamespace: VLAN pool management and assignment

**Wiring API Models**:
- Switch: Physical switch definitions with port management
- SwitchGroup: Logical groupings for redundancy and policy
- Connection: Physical connections between network elements
- External: External system integration and peering
- ExternalAttachment: External connection management
- ExternalPeering: BGP and routing protocol configuration
- Server: Server connectivity and network interface management

## Management Models
- **Fabric**: Container for CRD collections with isolation and sync status
- **GitRepository**: Git integration with credential and branch management
- **HedgehogResource**: Generic foreign key for CRD change tracking
- **ReconciliationAlert**: Error tracking and resolution workflows

## Key Relationships
- Fabric → CRDs (One-to-Many): All CRDs belong to a specific fabric
- GitRepository → Fabric (Many-to-Many): Multi-repo support per fabric
- HedgehogResource → All CRDs (Generic FK): Universal change tracking
- CRDs → NetBox Objects (FK): Integration with devices, interfaces, IP addresses

## Performance Optimizations
- Database indexes on frequently queried fields (name, fabric, status)
- Prefetch patterns for related object loading
- Custom managers for common query patterns
- Caching for expensive operations (Kubernetes status, git operations)

## Validation Rules
- Kubernetes naming conventions (RFC 1123 compliance)
- CIDR validation for network definitions
- Port range validation for switch configurations
- Git URL and credential validation
```

### API Level: REST Endpoint Documentation
**Location**: `/netbox_hedgehog/api/CLAUDE.md`  
**Purpose**: API implementation patterns and endpoint details  
**Max Length**: 40 lines

```markdown
# NetBox Hedgehog API - REST Implementation

**Framework**: Django REST Framework with NetBox patterns
**Authentication**: Token-based with NetBox RBAC integration
**Documentation**: Auto-generated OpenAPI schema with comprehensive examples

## API Architecture
**ViewSets**: ModelViewSet inheritance with NetBox customizations
- Standard CRUD operations (GET, POST, PUT, PATCH, DELETE)
- Custom actions for Kubernetes operations (sync, reconcile, status)
- Filtering, searching, and ordering capabilities
- Pagination for large datasets

**Serializers**: 
- Model serializers with nested relationships
- Custom field serialization for complex data types
- Validation integration with model clean() methods
- Performance optimization with select_related/prefetch_related

## Endpoint Categories
**CRD Management Endpoints**: 
- `/api/plugins/netbox-hedgehog/vpcs/` - VPC API endpoints (5 types)
- `/api/plugins/netbox-hedgehog/wiring/` - Wiring API endpoints (7 types)
- Standard operations: list, create, retrieve, update, delete

**Fabric Management**:
- `/api/plugins/netbox-hedgehog/fabrics/` - Fabric CRUD operations
- `/api/plugins/netbox-hedgehog/fabrics/{id}/sync/` - Kubernetes synchronization
- `/api/plugins/netbox-hedgehog/fabrics/{id}/status/` - Real-time status

**GitOps Integration**:
- `/api/plugins/netbox-hedgehog/git-repositories/` - Repository management
- `/api/plugins/netbox-hedgehog/git-repositories/{id}/sync/` - Git synchronization
- `/api/plugins/netbox-hedgehog/git-repositories/{id}/validate/` - Connectivity testing

**Synchronization Operations**:
- `/api/plugins/netbox-hedgehog/sync/kubernetes/` - Cluster-wide sync
- `/api/plugins/netbox-hedgehog/sync/git/` - Repository sync operations
- `/api/plugins/netbox-hedgehog/reconciliation/alerts/` - Error management

## Custom Actions
- **sync_kubernetes**: Synchronize fabric configuration with K8s cluster
- **validate_git_connectivity**: Test git repository accessibility
- **reconcile_status**: Force reconciliation of CRD status
- **export_configuration**: Export fabric config for backup/migration

## Error Handling
- Standardized error responses with detail codes
- Kubernetes connectivity error management
- Git operation failure handling with retry logic
- Validation error formatting with field-specific messages

## Performance Features
- Query optimization with select_related/prefetch_related
- Caching for expensive Kubernetes operations
- Async task integration for long-running operations
- Rate limiting for resource-intensive endpoints
```

### Environment Level: Operational Knowledge
**Location**: `/project_management/environment/CLAUDE.md`  
**Purpose**: Complete environment setup to prevent discovery cycles  
**Max Length**: 60 lines

```markdown
# HNP Development Environment - Complete Operational Context

**Purpose**: Eliminate repeated environment discovery cycles for all agents
**Status**: Fully operational development environment with all integrations working

## NetBox Docker Environment
**Version**: NetBox 4.3.3 running in Docker with custom plugin integration
**Configuration**: 
- Docker Compose setup with PostgreSQL, Redis, and Nginx
- Custom plugin mounting via volume: `/opt/netbox/netbox/plugins/netbox_hedgehog`
- Database: PostgreSQL 13 with shared connection pool
- Cache: Redis for session management and task queuing
- Web Server: Nginx reverse proxy with static file serving

**Access**:
- NetBox Interface: http://localhost:8000 (admin/admin)
- Database: localhost:5432 (netbox/password)
- Admin Interface: Full superuser access for development and testing

## HCKC Kubernetes Cluster
**Type**: Local development cluster with Hedgehog CRD support
**Status**: Operational with 49 CRDs successfully imported and monitored
**Configuration**:
- Kubernetes API: Direct connectivity from NetBox plugin
- CRD Types: All 12 HNP-managed types plus Hedgehog infrastructure CRDs
- Namespaces: Multi-tenant with fabric isolation
- RBAC: Service account with cluster-level CRD management permissions

**Connectivity**:
- Kubeconfig: Embedded in plugin configuration
- Authentication: Service account token with appropriate RBAC
- Network: Direct cluster network access from Docker environment
- Monitoring: Real-time watch integration for CRD status changes

## ArgoCD GitOps Integration
**Purpose**: Application deployment and GitOps workflow automation
**Status**: Integrated with repository monitoring and sync capabilities
**Configuration**:
- ArgoCD Server: Accessible from NetBox environment
- Repository Integration: Multi-repo support with credential management
- Application Sync: Automated deployment from git repositories
- Status Monitoring: Real-time application health and sync status

## Development Tools and Workflows
**Git Integration**:
- Repository Sync: Automated monitoring and synchronization
- Branch Management: Feature branch workflows with merge tracking
- Credential Management: Secure token and SSH key storage
- Multi-repo Support: Fabric-specific repository organization

**Database Management**:
- Django Migrations: All current, no pending changes
- Fixtures: Comprehensive test data for all CRD types
- Performance: Optimized queries with proper indexing
- Backup: Automated backup and restore procedures

**Testing Infrastructure**:
- Test Database: Isolated PostgreSQL instance for testing
- Kubernetes Testing: Mock cluster integration for unit tests
- Integration Tests: Full stack testing with real Kubernetes connectivity
- Performance Testing: Load testing for large fabric configurations

## File System Organization
**Plugin Structure**: Standard NetBox plugin layout with HNP extensions
- `/netbox_hedgehog/` - Main plugin code
- `/netbox_hedgehog/models/` - CRD model definitions
- `/netbox_hedgehog/api/` - REST API implementation
- `/netbox_hedgehog/views/` - Web interface views
- `/netbox_hedgehog/templates/` - UI templates and components
- `/netbox_hedgehog/static/` - CSS, JavaScript, and assets
- `/netbox_hedgehog/utils/` - Kubernetes and GitOps utilities
- `/tests/` - Comprehensive test suite with fixtures

**Configuration Files**:
- `pyproject.toml` - Python package configuration and dependencies
- `setup.py` - Plugin installation and metadata
- `requirements.txt` - Python dependencies for development
- Docker configuration files for development environment

## Common Operations
**Plugin Development**:
- Code changes automatically reload in development mode
- Database migrations applied automatically during development
- Static files served directly without collection
- Debug logging enabled for all plugin operations

**Testing Procedures**:
- `python manage.py test netbox_hedgehog` - Run plugin test suite
- `python manage.py validate_git_repositories` - Test git connectivity
- `python manage.py sync_fabric <fabric_name>` - Manual fabric sync
- Performance testing with realistic data loads

**Troubleshooting**:
- Kubernetes connectivity: Check service account and RBAC permissions
- Database issues: Verify PostgreSQL connection and migration status
- Git operations: Validate credentials and repository accessibility
- UI problems: Check template inheritance and static file serving
```

---

## Implementation Strategy

### Phase 1: Immediate Deployment (Day 1)
1. **Create Root CLAUDE.md**: Essential project context for all agents
2. **Deploy Plugin CLAUDE.md**: Core functionality reference
3. **Add Environment CLAUDE.md**: Eliminate discovery cycles
4. **Test Context Loading**: Verify agents receive complete context

### Phase 2: Component Specialization (Day 2-3)
1. **Models CLAUDE.md**: Database schema and relationships
2. **API CLAUDE.md**: REST endpoint patterns and validation
3. **Views CLAUDE.md**: UI implementation and template patterns
4. **Utils CLAUDE.md**: Kubernetes and GitOps integration patterns

### Phase 3: Optimization and Maintenance (Ongoing)
1. **Monitor Context Usage**: Track agent context consumption patterns
2. **Optimize Content**: Remove redundant information, focus on essentials
3. **Update Regularly**: Keep context current with project evolution
4. **Agent Feedback**: Adjust based on agent effectiveness metrics

---

## Context Management Best Practices

### Content Guidelines
1. **Be Extremely Concise**: Every line must provide essential value
2. **Focus on Actionable Information**: What agents need to do their job
3. **Avoid Redundancy**: Don't repeat information available elsewhere
4. **Update Frequently**: Keep context current with project evolution
5. **Import Strategically**: Use @imports to load additional context only when needed

### File Organization Principles
1. **Hierarchical Structure**: General → specific context flow
2. **Logical Grouping**: Related functionality in same context files
3. **Clear Boundaries**: Distinct responsibilities for each file
4. **Import Relationships**: Clear dependency chains without circular references

### Performance Optimization
1. **Strict Length Limits**: Enforce maximum line counts per file
2. **Essential Information Only**: Remove nice-to-have information
3. **Strategic Imports**: Load additional context only when needed
4. **Regular Cleanup**: Remove outdated or redundant information

---

## Validation and Testing

### Context Effectiveness Testing
```markdown
**Agent Context Test Protocol**:
1. Launch agent in clean environment
2. Verify agent understands project context without additional questions
3. Test agent ability to navigate codebase structure
4. Validate agent knowledge of environment setup and constraints
5. Confirm agent follows established patterns and conventions

**Success Criteria**:
- Agent starts work immediately without environment discovery
- Agent uses correct technical patterns and conventions
- Agent understands project structure and relationships
- Agent follows established development workflows
- Agent escalates appropriately when encountering unknowns
```

### Maintenance Procedures
```markdown
**Weekly Context Review**:
- Check for outdated information and update accordingly
- Verify import chains are working correctly
- Monitor agent effectiveness metrics and adjust content
- Update project status and current development focus
- Validate environment information remains accurate

**Monthly Architecture Review**:
- Assess context file organization effectiveness
- Identify opportunities for consolidation or separation
- Update context hierarchy based on usage patterns
- Review and optimize import relationships
- Plan context evolution for upcoming project phases
```

---

## Integration with External Memory Systems

### MCP Integration Strategy
```markdown
**Memory Complement Strategy**:
- CLAUDE.md files provide immediate, essential context
- MCP memory stores conversational history and learned patterns
- External memory maintains long-term project knowledge
- Integration creates seamless context experience for agents

**Implementation Pattern**:
- CLAUDE.md: Static, essential, immediately available
- MCP Memory: Dynamic, conversational, persistent across sessions
- External Storage: Historical, searchable, comprehensive project knowledge
```

This CLAUDE.md architecture will immediately solve HNP's context management crisis while providing a scalable foundation for complex multi-agent workflows.