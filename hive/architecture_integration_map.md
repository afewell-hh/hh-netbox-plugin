# NetBox Hedgehog Plugin - Complete Architecture Integration Map

## Executive Summary

The NetBox Hedgehog Plugin implements a sophisticated **GitOps-First Architecture** with dual-state management, service-oriented design, and comprehensive Kubernetes CRD integration. The architecture demonstrates enterprise-grade patterns including dependency injection, signal-driven automation, and clean separation of concerns.

## 1. NetBox Plugin Architecture Foundation

### 1.1 Django Plugin Integration

**Plugin Configuration (`netbox_hedgehog/__init__.py`)**
```python
class HedgehogPluginConfig(PluginConfig):
    name = 'netbox_hedgehog'
    verbose_name = 'Hedgehog Fabric Manager'
    base_url = 'hedgehog'
    version = '0.2.0'  # MVP2 GitOps features
```

**Key Integration Points:**
- **NetBox Core Integration**: Extends `NetBoxModel` for all CRDs
- **URL Namespace**: `/plugins/netbox_hedgehog/` routing
- **Navigation Integration**: Plugin menu with 5 major sections
- **Permission System**: Leverages NetBox RBAC

### 1.2 App Configuration (`apps.py`)
```python
class NetboxHedgehogConfig(AppConfig):
    def ready(self):
        # Load signals for GitOps automation
        from . import signals
```

**Initialization Pattern:**
- Minimal initialization to prevent circular imports
- Signal-based event handling for CRD lifecycle
- Graceful error handling with continued functionality

## 2. Domain Model Architecture

### 2.1 Base CRD Model (`models/base.py`)

**AbstractBaseModel Pattern:**
```python
class BaseCRD(NetBoxModel):
    fabric = models.ForeignKey('HedgehogFabric', on_delete=models.CASCADE)
    spec = models.JSONField()
    kubernetes_status = models.CharField(choices=KubernetesStatusChoices)
    
    class Meta:
        abstract = True
        unique_together = [['fabric', 'namespace', 'name']]
```

**Core Capabilities:**
- Kubernetes manifest generation (`to_kubernetes_manifest()`)
- YAML serialization (`to_yaml()`)
- DNS-1123 name validation
- GitOps integration hooks
- Status tracking with icons

### 2.2 Fabric Model (`models/fabric.py`)

**Multi-Tenant Architecture:**
```python
class HedgehogFabric(NetBoxModel):
    # Connection Management
    kubernetes_server = models.URLField()
    connection_status = models.CharField(choices=ConnectionStatusChoices)
    
    # GitOps Configuration
    git_repository_url = models.URLField()
    gitops_tool = models.CharField()  # ArgoCD, Flux, etc.
    
    # State Tracking
    sync_status = models.CharField(choices=SyncStatusChoices)
    drift_count = models.PositiveIntegerField()
```

**Integration Capabilities:**
- Multi-cluster support (each fabric = one K8s cluster)
- GitOps tool abstraction (ArgoCD, Flux, Manual)
- Real-time drift detection
- Connection health monitoring

### 2.3 CRD Type Hierarchy

**VPC API Models** (`models/vpc_api.py`):
- VPC, External, ExternalAttachment, ExternalPeering
- IPv4Namespace, VPCAttachment, VPCPeering

**Wiring API Models** (`models/wiring_api.py`):
- Connection, Server, Switch, SwitchGroup, VLANNamespace

**GitOps Models** (`models/gitops.py`):
- HedgehogResource (dual-state tracking)
- StateTransitionHistory (audit trail)
- ReconciliationAlert (monitoring)

## 3. Service Layer Architecture

### 3.1 Dependency Injection Container (`application/service_registry.py`)

**Enterprise Pattern Implementation:**
```python
class ServiceRegistry:
    def register_singleton(self, interface: Type[T], implementation: T)
    def register_factory(self, interface: Type[T], factory: Callable)
    def get(self, interface: Type[T]) -> T
    
@service(interface=GitSyncInterface)
class GitSyncService:
    pass
```

**Service Categories:**
- **State Management**: StateTransitionService
- **Git Operations**: GitSyncService, GitOpsIngestionService
- **Kubernetes**: KubernetesWatchService
- **Real-time**: EventService, WebSocketService
- **Directory Management**: DirectoryWatcherService

### 3.2 GitOps Service Architecture

**GitOps Onboarding Service** (`services/gitops_onboarding_service.py`):
- Fabric-to-Git repository linking
- Directory structure validation
- Initial YAML discovery and ingestion

**GitOps Ingestion Service** (`services/gitops_ingestion_service.py`):
- Multi-document YAML parsing
- CRD creation from Git sources
- Conflict resolution algorithms

**GitOps Edit Service** (`services/gitops_edit_service.py`):
- Bidirectional editing workflows
- YAML generation and validation
- Git commit automation

## 4. API Architecture

### 4.1 Django REST Framework Integration

**Router Configuration** (`api/urls.py`):
```python
router = NetBoxRouter()

# Core APIs
router.register('fabrics', views.FabricViewSet)
router.register('git-repos-api', views.GitRepositoryViewSet)

# GitOps APIs
router.register('gitops-fabrics', views.EnhancedFabricViewSet)
router.register('gitops-resources', views.HedgehogResourceViewSet)

# CRD APIs (VPC + Wiring)
router.register('vpcs', views.VPCViewSet)
router.register('connections', views.ConnectionViewSet)
```

**API Endpoint Categories:**
1. **CRUD APIs**: Standard NetBox model operations
2. **GitOps APIs**: Workflow and sync operations
3. **Health APIs**: Connection testing and monitoring
4. **Bidirectional Sync APIs**: Git ↔ NetBox synchronization

### 4.2 Custom API Endpoints

**GitOps Workflow APIs:**
- `/api/plugins/netbox_hedgehog/gitops/drift-analysis/`
- `/api/plugins/netbox_hedgehog/gitops/argocd/setup/`
- `/api/plugins/netbox_hedgehog/fabrics/{id}/init-gitops/`

**Sync Control APIs:**
- `/api/plugins/netbox_hedgehog/gitops-fabrics/{id}/hckc_sync/`
- `/api/plugins/netbox_hedgehog/gitops-fabrics/{id}/state-comparison/`

## 5. View Layer Architecture

### 5.1 URL Pattern Organization (`urls.py`)

**Hierarchical URL Structure:**
```
/plugins/netbox_hedgehog/
├── fabrics/                    # Fabric management
├── git-repositories/           # Git repo management  
├── vpcs/, connections/         # CRD management
├── gitops/*/edit/             # GitOps editing workflow
└── api/                       # REST API endpoints
```

**View Types:**
- **ListView**: Table-based CRD browsing with filtering
- **DetailView**: Individual CRD inspection with GitOps status
- **EditView**: Form-based CRD editing
- **GitOpsEditView**: YAML-based GitOps editing workflow

### 5.2 Template Architecture

**Template Hierarchy** (`templates/netbox_hedgehog/`):
```
netbox_hedgehog/
├── base.html                   # Plugin base template
├── overview.html               # Dashboard
├── fabric_*.html               # Fabric management templates
├── *_list.html, *_detail.html  # CRUD templates
├── gitops/                     # GitOps workflow templates
│   ├── onboarding_wizard.html
│   ├── vpc_edit.html
│   └── generic_cr_edit.html
└── components/                 # Reusable UI components
    ├── fabric_filter.html
    ├── six_state_indicators.html
    └── realtime_status_indicators.html
```

## 6. Static Asset Organization

### 6.1 CSS Architecture (`static/netbox_hedgehog/css/`)

**Stylesheet Structure:**
- `hedgehog.css`: Main plugin styles with NetBox theme integration
- `progressive-disclosure.css`: Advanced UI patterns

**Design Patterns:**
- NetBox color scheme compliance
- Responsive layout patterns
- GitOps-specific status indicators
- Dark theme compatibility

### 6.2 JavaScript Architecture (`static/netbox_hedgehog/js/`)

**Frontend Modules:**
- `hedgehog.js`: Core plugin functionality
- `gitops-dashboard.js`: Real-time GitOps monitoring
- `websocket-client.js`: Live status updates
- `progressive-disclosure.js`: Advanced UI interactions
- `sync-handler.js`: GitOps sync operations

## 7. Integration Patterns

### 7.1 Signal-Driven Architecture (`signals.py`)

**Automatic GitOps Sync:**
```python
@receiver(post_save)
def on_crd_saved(sender, instance, created, **kwargs):
    # Auto-transition CRD to DRAFT state
    state_service.transition_resource_state(instance, 'draft')
```

**Event Types:**
- CRD creation → DRAFT state transition
- CRD modification → Drift detection
- CRD deletion → GitOps cleanup
- Fabric updates → Repository sync triggers

### 7.2 Middleware Integration (`middleware.py`)

**Performance Monitoring:**
```python
class PerformanceMonitoringMiddleware:
    def process_response(self, request, response):
        # Track response times, DB queries, cache hits
        # Provide optimization suggestions
        # Store metrics for dashboard
```

**Cache Optimization:**
```python
class CacheOptimizationMiddleware:
    CACHEABLE_VIEWS = {
        '/hedgehog/fabrics/': 3600,  # 1 hour
        '/hedgehog/fabric/': 1800,   # 30 minutes  
    }
```

## 8. GitOps Integration Architecture

### 8.1 Dual-State Management

**State Tracking Model:**
```python
class HedgehogResource(models.Model):
    # Desired state (from Git)
    desired_spec = models.JSONField()
    desired_commit = models.CharField()
    
    # Actual state (from Kubernetes/NetBox)
    actual_spec = models.JSONField()
    
    # Drift analysis
    drift_status = models.CharField()
    drift_score = models.FloatField()
```

**Six-State Workflow:**
1. **DRAFT**: Created in NetBox UI
2. **COMMITTED**: Pushed to Git repository
3. **SYNCED**: Applied to target system
4. **LIVE**: Running in Kubernetes
5. **DRIFTED**: Detected configuration drift
6. **CONFLICT**: Requires manual resolution

### 8.2 Bidirectional Sync Architecture

**Sync Service Components** (`services/bidirectional_sync/`):
- `BiDirectionalSyncOrchestrator`: Main coordination
- `GitOpsDirectoryManager`: File system operations
- `GithubSyncClient`: Git provider integration
- `FileIngestionPipeline`: YAML processing
- `HNPIntegration`: NetBox integration

## 9. Security Architecture

### 9.1 Authentication & Authorization

**Git Authentication** (`security/credential_manager.py`):
- Token-based Git access
- Encrypted credential storage
- User-scoped Git operations

**RBAC Integration** (`security/rbac.py`):
- NetBox permission inheritance
- GitOps-specific permissions
- Audit trail maintenance

### 9.2 Security Middleware

**Audit Logging** (`security/audit_logger.py`):
- All GitOps operations logged
- User action tracking
- Configuration change history

## 10. Performance Architecture

### 10.1 Caching Strategy

**Multi-Level Caching:**
```python
caching_config = {
    'fabric_status': 60,      # Fabric status cache
    'crd_schemas': 3600,      # CRD schema cache
    'git_status': 30,         # Git sync status
    'drift_analysis': 120,    # Drift detection results
}
```

### 10.2 Query Optimization

**Database Patterns:**
- Strategic indexes on frequently queried fields
- `select_related`/`prefetch_related` usage
- Query result caching
- Bulk operation optimizations

## 11. Extension Points

### 11.1 Service Registry Pattern

**New Service Integration:**
```python
@service(MyServiceInterface)
class MyCustomService:
    def custom_operation(self):
        pass

# Automatic registration and dependency injection
```

### 11.2 GitOps Tool Abstraction

**Multi-Tool Support:**
- ArgoCD integration (primary)
- Flux integration (planned)
- Manual Git operations (fallback)
- Custom tool plugins (extensible)

## 12. Deployment Integration

### 12.1 NetBox Plugin Installation

**Package Configuration** (`setup.py`, `pyproject.toml`):
- Standard NetBox plugin packaging
- Dependency management (Kubernetes, GitPython, etc.)
- Static asset inclusion
- Database migration support

### 12.2 Configuration Management

**Environment Variables** (`.env` support):
- Database connections
- Git provider settings
- Kubernetes cluster access
- Feature toggles

## Architectural Decision Records (ADRs)

### ADR-001: GitOps-First Architecture
- **Decision**: All configuration changes flow through Git
- **Rationale**: Ensures auditability, version control, and disaster recovery
- **Status**: Implemented

### ADR-002: Dual-State Management
- **Decision**: Track both desired (Git) and actual (K8s) state
- **Rationale**: Enables drift detection and conflict resolution
- **Status**: Implemented

### ADR-003: Service-Oriented Architecture
- **Decision**: Use dependency injection for service management
- **Rationale**: Enables testability, extensibility, and clean architecture
- **Status**: Implemented

## Technology Evaluation Matrix

| Component | Technology | Rationale | Status |
|-----------|------------|-----------|---------|
| Web Framework | Django | NetBox compatibility | ✅ Implemented |
| API Framework | Django REST Framework | NetBox standard | ✅ Implemented |
| Database | PostgreSQL | NetBox requirement | ✅ Implemented |
| Cache | Redis | Performance optimization | ✅ Implemented |
| Git Integration | GitPython | Python-native Git ops | ✅ Implemented |
| K8s Integration | kubernetes-python | Official K8s client | ✅ Implemented |
| WebSockets | Django Channels | Real-time updates | ✅ Implemented |
| Task Queue | Celery | Background processing | 📋 Planned |

## Quality Attributes Assessment

### Scalability
- **Multi-tenant**: ✅ Fabric-based isolation
- **Horizontal scaling**: ✅ Stateless service design
- **Database performance**: ✅ Strategic indexing

### Reliability
- **Error handling**: ✅ Graceful degradation
- **State consistency**: ✅ ACID transactions
- **Monitoring**: ✅ Built-in health checks

### Security
- **Authentication**: ✅ NetBox RBAC integration
- **Authorization**: ✅ Permission inheritance
- **Audit trails**: ✅ Comprehensive logging

### Maintainability
- **Clean architecture**: ✅ Service separation
- **Testability**: ✅ Dependency injection
- **Documentation**: ✅ Comprehensive docs

## Future Extension Opportunities

1. **Multi-Cloud Support**: Extend beyond single Kubernetes clusters
2. **Policy Engine**: Implement configuration validation policies  
3. **Metrics Integration**: Add Prometheus/Grafana monitoring
4. **AI/ML Integration**: Intelligent drift analysis and remediation
5. **Mobile Support**: Progressive Web App capabilities

## Conclusion

The NetBox Hedgehog Plugin demonstrates enterprise-grade architecture with:

- **Clean separation of concerns** through service-oriented design
- **Robust GitOps integration** with dual-state management
- **Comprehensive NetBox integration** leveraging all platform capabilities
- **Performance optimization** through multi-level caching and query optimization
- **Security-first approach** with comprehensive audit trails
- **Extensible design** enabling future enhancements

The architecture successfully bridges the gap between NetBox's DCIM capabilities and Kubernetes GitOps workflows, providing a unified management plane for network infrastructure as code.