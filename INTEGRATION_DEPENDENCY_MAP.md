# Hedgehog NetBox Plugin - Integration Dependency Map

**Generated:** 2025-08-11  
**Analysis Version:** v1.0.0  
**Purpose:** System Architecture Dependency Analysis with Failure Mode Assessment

## Executive Summary

The Hedgehog NetBox Plugin is a complex, multi-layered system with 47 distinct integration points across 8 major technology domains. The system exhibits a high degree of coupling between GitOps workflows, Kubernetes APIs, and async processing, creating potential cascading failure scenarios that require careful monitoring.

## 1. Core Technologies Stack

### 1.1 Django/NetBox Integration Points

**Framework Foundation:**
- NetBox v4.3-3.3.0 (Docker base)
- Django Plugin Architecture via `PluginConfig`
- NetBox Model inheritance (`NetBoxModel`)
- Authentication integration with NetBox RBAC

**Plugin Architecture:**
```python
# Core plugin configuration
class HedgehogPluginConfig(PluginConfig):
    name = 'netbox_hedgehog'
    base_url = 'hedgehog'
    version = '0.2.0'
```

**Critical Integration Points:**
- URL routing integration via `urlpatterns`
- Model registration in NetBox database
- Navigation menu integration
- Permission system integration
- Signal system for model changes

**Failure Modes:**
- Plugin initialization failures block entire NetBox startup
- Model migration conflicts can corrupt NetBox database
- URL routing conflicts can break NetBox navigation

### 1.2 Python Dependencies and Versions

**Core Dependencies (from setup.py & requirements.txt):**
```
# Infrastructure
kubernetes>=24.0.0          # K8s API client - CRITICAL
pyyaml>=6.0                # YAML processing
jsonschema>=4.0.0          # Schema validation
GitPython>=3.1.0           # Git operations

# Async Processing
channels>=4.0.0            # WebSocket support
channels-redis>=4.0.0      # Redis channel layer
redis>=4.0.0               # Redis client
celery>=5.3.0              # Task queue
django-redis>=5.3.0        # Django Redis integration

# Development/Testing
pytest>=7.0.0              # Testing framework
playwright>=1.40.0         # GUI testing
black>=22.0.0              # Code formatting
```

**Version Constraints Analysis:**
- Python 3.8-3.11 support range
- Kubernetes client version pinned to avoid API breakage
- All async components version-aligned for compatibility

**Dependency Risk Assessment:**
- **HIGH RISK:** Kubernetes client version compatibility
- **MEDIUM RISK:** Celery/Redis version alignment
- **LOW RISK:** Testing/development dependencies

### 1.3 Database Integration (PostgreSQL)

**Database Models (23 total models):**
```
Core Models:
├── HedgehogFabric (main orchestration)
├── GitRepository (GitOps integration)
├── HedgehogResource (CRD tracking)
└── ReconciliationAlert (error handling)

VPC API Models (6):
├── VPC, External, ExternalAttachment
├── ExternalPeering, IPv4Namespace
├── VPCAttachment, VPCPeering

Wiring API Models (5):
├── Connection, Server, Switch
├── SwitchGroup, VLANNamespace

State Management (3):
├── StateTransitionHistory
├── SyncOperation
└── BaseCRD (abstract base)
```

**Database Relationships:**
- Foreign Key: HedgehogFabric → GitRepository
- Generic Foreign Keys for flexible CRD relationships
- Index optimization for sync operations

**Migration History:** 23 migrations with critical constraint fixes
- Migration 0022: Fixed NOT NULL constraint violations
- Migration 0023: Added scheduler_enabled field

## 2. External Integrations

### 2.1 Kubernetes API Connections and CRD Management

**Kubernetes Client Architecture:**
```python
class KubernetesClient:
    """Multi-fabric isolation with explicit configuration"""
    def __init__(self, fabric: HedgehogFabric):
        self.fabric = fabric
        # Each fabric requires explicit K8s configuration
        # No fallback to default kubeconfig allowed
```

**CRD Management:**
- Custom Resource Definitions for Hedgehog resources
- Multi-namespace support per fabric
- Bearer token authentication
- CA certificate validation

**API Endpoints:**
- `/api/plugins/netbox-hedgehog/fabrics/{id}/test-connection/`
- `/api/plugins/netbox-hedgehog/fabrics/{id}/sync/`
- K8s Custom Objects API integration

**Connection Configuration:**
- kubernetes_server (URL)
- kubernetes_token (Bearer token)
- kubernetes_ca_cert (Certificate)
- kubernetes_namespace (default namespace)

**Failure Modes:**
- **CRITICAL:** Token expiration breaks all fabric operations
- **HIGH:** Certificate validation failures prevent connections
- **MEDIUM:** Network connectivity issues to K8s API

### 2.2 GitOps Workflows and GitHub Integration

**GitOps Architecture:**
```
GitOps Flow:
NetBox Changes → Git Repository → GitHub Sync → ArgoCD → Kubernetes
```

**GitHub Integration Services:**
- `GitHubSyncService` - Push changes to remote repositories
- `GitOpsIngestionService` - Process incoming changes
- `FileIngestionPipeline` - Handle YAML file processing

**Git Repository Management:**
- Bidirectional sync support
- Conflict resolution engine
- Drift detection
- File directory management

**API Endpoints:**
- `/api/plugins/netbox-hedgehog/fabrics/{id}/github-sync/`
- `/api/plugins/netbox-hedgehog/fabrics/{id}/gitops-status/`
- `/api/plugins/netbox-hedgehog/gitops/global-status/`

**Authentication:**
- Git credential management
- SSH key support
- Personal Access Token integration

### 2.3 Docker Containerization and Deployment

**Docker Configuration:**
```dockerfile
FROM netboxcommunity/netbox:v4.3-3.3.0
# Plugin installation via file copy
# User permission management (unit:root)
```

**Deployment Architecture:**
- NetBox container extension
- No standalone containerization
- Makefile-based development environment
- Docker Compose integration via `gitignore/netbox-docker`

**Service Dependencies:**
- PostgreSQL (database)
- Redis (caching/channels)
- Redis-Cache (additional cache layer)

### 2.4 Celery Task Queues and Async Processing

**Queue Architecture (Enhanced Phase 2 Scheduler):**
```python
SCHEDULER_QUEUE_CONFIG = {
    'scheduler_master': {'concurrency': 1, 'priority': 10},
    'sync_git': {'concurrency': 4, 'priority': 8},
    'sync_kubernetes': {'concurrency': 3, 'priority': 8},
    'sync_micro': {'concurrency': 8, 'priority': 9},
    'sync_orchestration': {'concurrency': 2, 'priority': 6}
}
```

**Periodic Tasks:**
- Master sync scheduler (60-second cycle)
- Fabric sync checker (5-minute intervals)
- Performance metrics collection
- Kubernetes health checks

**Task Routing:**
- Priority-based task distribution
- Queue-specific concurrency limits
- Soft/hard time limits per task type

**Performance Configuration:**
- Worker prefetch multiplier: 3
- Task acknowledgment on completion
- Result compression with gzip
- 30-minute result expiration

### 2.5 Redis Caching and Session Management

**Redis Usage:**
```python
# Multiple Redis databases
REDIS_DB_CACHE = 1      # General caching
REDIS_DB_CHANNELS = 2   # WebSocket channels
REDIS_DB_CELERY = 3     # Task queue
```

**Caching Strategy:**
- Fabric status (60 seconds)
- CRD schemas (1 hour)
- Git status (30 seconds)
- Drift analysis (2 minutes)

**Channel Layer:**
- WebSocket support for real-time updates
- Redis channel backend
- Connection management

## 3. Internal Architecture

### 3.1 Plugin Structure and NetBox Integration

**Directory Structure:**
```
netbox_hedgehog/
├── models/ (12 model files)
├── views/ (15 view modules)
├── api/ (REST API endpoints)
├── services/ (25+ business logic services)
├── tasks/ (Celery background tasks)
├── utils/ (20+ utility modules)
├── static/ (CSS/JS assets)
└── templates/ (40+ HTML templates)
```

**Service Layer Architecture:**
- Bidirectional sync orchestrator
- Configuration template engine
- Conflict resolution engine
- File management service
- GitHub sync service

### 3.2 Model Relationships and Data Flow

**Data Flow Patterns:**
```
User Input → Django Views → Services → Celery Tasks → External APIs
    ↓
Database Models ← Sync Operations ← Kubernetes/Git APIs
```

**Critical Relationships:**
- HedgehogFabric (1) → (N) HedgehogResources
- GitRepository (1) → (N) HedgehogFabrics
- SyncOperation tracking for all state changes

### 3.3 API Endpoints and Serialization

**REST API Structure:**
- 47 registered endpoints
- ViewSet-based architecture
- Custom serializers for each model
- Permission-based access control

**Key API Categories:**
- Fabric management (8 endpoints)
- GitOps operations (12 endpoints)
- CRD management (20+ endpoints)
- Health/monitoring (7 endpoints)

### 3.4 View/Template Structure

**Template Architecture:**
- Base template inheritance
- Component-based UI elements
- Progressive disclosure patterns
- Responsive design implementation

**Template Count:** 40+ templates with hierarchical organization

### 3.5 Signal Handlers and Event Processing

**Django Signals:**
- Model save/delete signal handlers
- Template engine signal connections
- Real-time update propagation

**Event Processing:**
- Async event handling via Celery
- State transition tracking
- Reconciliation alerts

## 4. Network Dependencies

### 4.1 API Endpoints and Ports Used

**NetBox Integration:**
- Port 8000 (HTTP) - NetBox web interface
- Plugin URL: `/plugins/hedgehog/`

**External Service Ports:**
- Kubernetes API (typically 6443/443)
- Git repositories (22/443/80)
- Redis (6379)
- PostgreSQL (5432)

### 4.2 Authentication Mechanisms

**Multi-layer Authentication:**
1. NetBox session authentication
2. Kubernetes bearer tokens
3. Git repository credentials
4. Redis authentication (configured)

### 4.3 SSL/TLS Requirements

**Certificate Management:**
- Kubernetes CA certificate validation
- Git repository SSL verification
- Optional NetBox HTTPS

### 4.4 Service Discovery Patterns

**Static Configuration:**
- Explicit service endpoints
- No dynamic service discovery
- Configuration via environment variables

## 5. Development/Deployment Pipeline

### 5.1 Docker Build Processes

**Build Strategy:**
- NetBox base image extension
- Plugin file copying
- Permission management

### 5.2 CI/CD Integration Points

**Testing Framework:**
- Playwright for GUI testing
- pytest for unit testing
- Manual validation scripts

### 5.3 Testing Frameworks and Dependencies

**Test Categories:**
- Unit tests (pytest)
- Integration tests (K8s mocks)
- GUI tests (Playwright)
- Performance tests (custom)

### 5.4 Monitoring and Logging Systems

**Logging Architecture:**
- Django logging framework
- Celery task logging
- Performance monitoring
- Audit trail logging

## 6. Critical Failure Modes and Risk Assessment

### 6.1 High-Risk Failure Scenarios

#### **CRITICAL: Kubernetes API Token Expiration**
- **Impact:** Complete fabric disconnection
- **Cascade Effect:** All sync operations fail
- **Mitigation:** Token rotation monitoring

#### **CRITICAL: Database Migration Failures**
- **Impact:** Plugin initialization blocked
- **Cascade Effect:** NetBox startup failure
- **Mitigation:** Migration rollback procedures

#### **HIGH: Redis Service Failure**
- **Impact:** Task queue and caching unavailable
- **Cascade Effect:** Async operations blocked
- **Mitigation:** Redis clustering/failover

#### **HIGH: Git Repository Authentication**
- **Impact:** GitOps workflows broken
- **Cascade Effect:** No configuration deployment
- **Mitigation:** Multiple auth method support

### 6.2 Medium-Risk Integration Points

- Network connectivity to external services
- Celery worker health and capacity
- Template rendering performance
- WebSocket connection stability

### 6.3 Monitoring and Alerting Requirements

**Essential Monitoring:**
- Kubernetes connection health
- Git repository accessibility
- Celery queue lengths
- Database query performance
- Redis memory usage

**Alert Thresholds:**
- Sync failure rate > 10%
- Task queue length > 100
- Response time > 5 seconds
- Memory usage > 80%

## 7. Recommendations

### 7.1 Immediate Actions

1. **Implement health check endpoints** for all external integrations
2. **Add circuit breaker patterns** for Kubernetes API calls
3. **Create monitoring dashboards** for critical metrics
4. **Establish backup procedures** for Git repositories

### 7.2 Architecture Improvements

1. **Decouple critical paths** to prevent cascading failures
2. **Implement graceful degradation** for non-critical features
3. **Add retry mechanisms** with exponential backoff
4. **Create integration test suites** for all external dependencies

### 7.3 Security Enhancements

1. **Rotate credentials regularly** for all external services
2. **Implement audit logging** for all configuration changes
3. **Add rate limiting** for API endpoints
4. **Encrypt sensitive data** in transit and at rest

## 8. Integration Points Summary

**Total Integration Points:** 47  
**External Dependencies:** 8  
**Internal Services:** 25+  
**API Endpoints:** 47  
**Database Models:** 23  
**Background Tasks:** 15+  

**Complexity Score:** HIGH (multi-service, async, external API dependent)  
**Reliability Score:** MEDIUM (multiple failure modes, but comprehensive error handling)  
**Maintainability Score:** HIGH (well-structured, documented, modular)  

---

*This analysis provides a comprehensive view of all system integrations and dependencies. Regular updates are recommended as the system evolves.*