# CNOC Feature Parity Roadmap

**Purpose**: Systematic implementation of HNP prototype features in CNOC  
**Target**: Cloud-native equivalent of NetBox Hedgehog Plugin functionality  
**Architecture**: MDD-aligned with Symphony-Level coordination  
**Date**: August 17, 2025

## 🎯 Executive Summary

CNOC (Cloud NetOps Command) will achieve feature parity with the HNP (Hedgehog NetBox Plugin) prototype while maintaining complete architectural independence. The system will provide the same GUI capabilities and CRD management features through a cloud-native, model-driven implementation.

## 📊 HNP Prototype Feature Analysis

### Core Features Identified
Based on analysis of `/netbox_hedgehog/urls.py` and model structures:

**1. Fabric Management**
- HedgehogFabric CRUD operations
- Connection status monitoring  
- Sync status tracking
- GitOps integration

**2. CRD Management (12 Types)**
**VPC API CRDs**:
- VPC (Virtual Private Cloud)
- External (External systems)
- ExternalAttachment (External system attachments)
- ExternalPeering (External peerings)
- IPv4Namespace (IPv4 namespace management)
- VPCAttachment (VPC attachments)
- VPCPeering (VPC peerings)

**Wiring API CRDs**:
- Connection (Network connections)
- Switch (Switch management)
- Server (Server management)
- SwitchGroup (Switch group management)
- VLANNamespace (VLAN namespace management)

**3. GitOps Operations**
- Git repository management
- GitOps directory synchronization
- YAML parsing and validation
- Drift detection

**4. User Interface Features**
- Overview dashboard with statistics
- List views with pagination (25 items)
- Detail views with progressive disclosure
- Edit forms with validation
- Connection testing
- Sync operations

## 🏗️ CNOC Implementation Architecture

### Domain-Driven Design Mapping

**CNOC Bounded Contexts**:
1. **Fabric Management Context** → HedgehogFabric equivalent
2. **CRD Management Context** → 12 CRD types equivalent
3. **GitOps Integration Context** → Git repository operations
4. **User Interface Context** → Web dashboard equivalent

### Anti-Corruption Layer Design
```
HNP Django Models → CNOC Go Structs
NetBox UI Framework → CNOC Web Components  
PostgreSQL (NetBox) → CNOC PostgreSQL (independent)
Kubernetes Python Client → CNOC Kubernetes Go Client
```

## 📋 Implementation Phases

### Phase 1: Domain Models and Data Layer (Week 1)
**Goal**: Establish CNOC domain models equivalent to HNP models

**Domain Models to Implement**:
```go
type Fabric struct {
    ID              string                 `json:"id" db:"id"`
    Name            string                 `json:"name" db:"name"`
    Description     string                 `json:"description" db:"description"`
    Status          FabricStatus          `json:"status" db:"status"`
    ConnectionStatus ConnectionStatus      `json:"connection_status" db:"connection_status"`
    SyncStatus      SyncStatus            `json:"sync_status" db:"sync_status"`
    KubernetesServer string               `json:"kubernetes_server" db:"kubernetes_server"`
    GitRepository   string                `json:"git_repository" db:"git_repository"`
    GitOpsDirectory string               `json:"gitops_directory" db:"gitops_directory"`
    Created         time.Time             `json:"created" db:"created"`
    LastModified    time.Time             `json:"last_modified" db:"last_modified"`
}

type CRDResource struct {
    ID          string                 `json:"id" db:"id"`
    FabricID    string                 `json:"fabric_id" db:"fabric_id"`
    Name        string                 `json:"name" db:"name"`
    Kind        string                 `json:"kind" db:"kind"`
    APIVersion  string                 `json:"api_version" db:"api_version"`
    Spec        map[string]interface{} `json:"spec" db:"spec"`
    Status      map[string]interface{} `json:"status" db:"status"`
    Created     time.Time             `json:"created" db:"created"`
    LastSynced  time.Time             `json:"last_synced" db:"last_synced"`
}
```

**Database Schema**:
- PostgreSQL tables mirroring HNP structure
- Foreign key relationships maintained
- Indexing for performance optimization

### Phase 2: API Layer Implementation (Week 2)
**Goal**: REST API endpoints equivalent to HNP Django views

**API Endpoints to Implement**:
```
# Fabric Management
GET    /api/fabrics              → Fabric list
POST   /api/fabrics              → Create fabric
GET    /api/fabrics/{id}         → Fabric detail
PUT    /api/fabrics/{id}         → Update fabric
DELETE /api/fabrics/{id}         → Delete fabric
POST   /api/fabrics/{id}/sync    → Trigger sync
POST   /api/fabrics/{id}/test    → Test connection

# CRD Management (12 types)
GET    /api/crds/{type}          → CRD list by type
POST   /api/crds/{type}          → Create CRD
GET    /api/crds/{type}/{id}     → CRD detail
PUT    /api/crds/{type}/{id}     → Update CRD
DELETE /api/crds/{type}/{id}     → Delete CRD

# GitOps Operations
GET    /api/gitops/repositories  → Git repository list
POST   /api/gitops/sync          → GitOps sync operation
GET    /api/gitops/status        → Sync status
```

### Phase 3: Web UI Implementation (Week 3)
**Goal**: Web dashboard equivalent to HNP NetBox interface

**GUI Components to Implement**:

**1. Overview Dashboard** (equivalent to HNP overview.html):
```html
<!-- Statistics Cards -->
<div class="statistics-grid">
    <div class="stat-card">Fabric Count: {fabric_count}</div>
    <div class="stat-card">CRD Count: {crd_count}</div>
    <div class="stat-card">Sync Status: {in_sync_count}/{total_count}</div>
    <div class="stat-card">Drift Detected: {drift_count}</div>
</div>

<!-- Recent Activity -->
<div class="recent-activity">
    <h3>Recent Fabrics</h3>
    <ul class="fabric-list">
        {#each recent_fabrics as fabric}
            <li><a href="/fabrics/{fabric.id}">{fabric.name}</a></li>
        {/each}
    </ul>
</div>
```

**2. Fabric Management Interface**:
- Fabric list view with pagination
- Fabric detail view with progressive disclosure
- Fabric create/edit forms
- Connection testing interface
- Sync operation controls

**3. CRD Management Interface**:
- CRD list views by type (12 types)
- CRD detail views with YAML display
- CRD create/edit forms
- Bulk operations interface

**4. GitOps Interface**:
- Git repository management
- Sync status monitoring
- Drift detection display
- YAML validation interface

### Phase 4: GitOps Integration (Week 4)
**Goal**: GitOps functionality equivalent to HNP git operations

**GitOps Features**:
```go
type GitOpsService struct {
    client       *github.Client
    repositories map[string]*GitRepository
    syncManager  *SyncManager
}

func (g *GitOpsService) SyncFromGit(fabricID string) error {
    // 1. Clone/pull repository
    // 2. Parse YAML files in gitops directory
    // 3. Create/update CRD records
    // 4. Update fabric sync status
    // 5. Detect configuration drift
}

func (g *GitOpsService) DetectDrift(fabricID string) (*DriftReport, error) {
    // Compare local CRDs with git repository
    // Generate drift detection report
    // Update fabric drift status
}
```

## 🎯 Feature Parity Matrix

| HNP Feature | CNOC Equivalent | Implementation Status | Notes |
|-------------|-----------------|----------------------|-------|
| **Fabric Management** | | | |
| HedgehogFabric model | Fabric struct + DB | Phase 1 | Go struct with PostgreSQL |
| Fabric CRUD operations | Fabric API endpoints | Phase 2 | REST API equivalent |
| Connection testing | /api/fabrics/{id}/test | Phase 2 | K8s connectivity check |
| Sync operations | /api/fabrics/{id}/sync | Phase 4 | GitOps sync equivalent |
| **CRD Management** | | | |
| 12 CRD types | CRDResource generic model | Phase 1 | Generic struct for all types |
| CRD list views | /api/crds/{type} | Phase 2 | Paginated API endpoints |
| CRD detail views | /api/crds/{type}/{id} | Phase 2 | Individual CRD access |
| CRD editing | PUT /api/crds/{type}/{id} | Phase 2 | Update operations |
| **GitOps Operations** | | | |
| Git repository model | GitRepository struct | Phase 1 | Repository configuration |
| GitOps sync | GitOps service | Phase 4 | YAML parsing + sync |
| Drift detection | Drift service | Phase 4 | Configuration comparison |
| **User Interface** | | | |
| Overview dashboard | / (root) | Phase 3 | Statistics + navigation |
| Fabric management UI | /fabrics/* | Phase 3 | Full CRUD interface |
| CRD management UI | /crds/* | Phase 3 | 12 type interfaces |
| GitOps management UI | /gitops/* | Phase 3 | Repository + sync UI |

## 🔧 Technical Implementation Details

### Go Application Structure
```
cnoc/
├── cmd/cnoc-api/           # Main application
├── internal/
│   ├── domain/             # Domain models
│   │   ├── fabric/
│   │   ├── crd/
│   │   └── gitops/
│   ├── api/                # REST API handlers
│   │   ├── fabric/
│   │   ├── crd/
│   │   └── gitops/
│   ├── services/           # Business logic
│   │   ├── fabric/
│   │   ├── crd/
│   │   └── gitops/
│   └── infrastructure/     # External integrations
│       ├── database/
│       ├── kubernetes/
│       └── git/
├── web/                    # Web UI components
│   ├── static/
│   ├── templates/
│   └── components/
└── docs/                   # Documentation
```

### Database Schema Design
```sql
-- Fabric management
CREATE TABLE fabrics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100) UNIQUE NOT NULL,
    description TEXT,
    status VARCHAR(20) NOT NULL DEFAULT 'planned',
    connection_status VARCHAR(20) NOT NULL DEFAULT 'unknown',
    sync_status VARCHAR(20) NOT NULL DEFAULT 'never_synced',
    kubernetes_server TEXT,
    git_repository TEXT,
    gitops_directory TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- CRD resources
CREATE TABLE crd_resources (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    fabric_id UUID REFERENCES fabrics(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    kind VARCHAR(100) NOT NULL,
    api_version VARCHAR(100) NOT NULL,
    spec JSONB,
    status JSONB,
    created_at TIMESTAMP DEFAULT NOW(),
    last_synced_at TIMESTAMP
);

-- Git repositories
CREATE TABLE git_repositories (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    url TEXT NOT NULL,
    credentials_encrypted TEXT,
    connection_status VARCHAR(20) DEFAULT 'unknown',
    last_validated_at TIMESTAMP
);
```

## 🚀 Next Immediate Steps

### Step 1: Domain Model Implementation (Starting Now)
1. Create Go domain models for Fabric and CRDResource
2. Implement PostgreSQL schema and migrations
3. Add basic database operations (CRUD)
4. Validate domain model design with MDD principles

### Step 2: API Foundation
1. Implement REST API router and middleware
2. Add Fabric management endpoints
3. Implement basic CRD operations
4. Add input validation and error handling

### Step 3: GUI Foundation
1. Extend existing CNOC dashboard with fabric management
2. Add fabric list and detail views
3. Implement CRD browsing interface
4. Add navigation between views

**Next Visible Change**: Extended CNOC dashboard with fabric management interface (approximately 2-3 days)

## 🎯 Success Criteria

**Feature Parity Achieved When**:
1. All 12 CRD types can be managed through CNOC GUI
2. Fabric operations equivalent to HNP functionality
3. GitOps sync operations working with git repositories
4. Drift detection equivalent to HNP capabilities
5. User experience matches HNP prototype quality

**Quality Gates**:
- MDD compliance validated at each phase
- Symphony-Level coordination maintained
- Anti-corruption layers prevent domain leakage
- Declarative deployment patterns preserved
- Evidence-based validation at each milestone

## 📋 Architectural Principles Maintained

Throughout implementation, strict adherence to:
1. **Domain-Driven Design**: Clear bounded contexts
2. **Anti-Corruption Layers**: Clean interface separation
3. **Symphony-Level Coordination**: Orchestrated component interaction
4. **Declarative Patterns**: Configuration-driven behavior
5. **Evidence-Based Validation**: Test-driven development

This roadmap ensures CNOC achieves complete feature parity with the HNP prototype while maintaining superior architectural quality through MDD-aligned development practices.