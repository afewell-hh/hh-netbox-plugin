# NetBox Plugin Architecture Mastery

## Plugin Integration Pattern
- **Base**: NetBox 4.3.3 plugin architecture
- **Entry Point**: `netbox_hedgehog/__init__.py` with `PluginConfig`
- **Registration**: Automatic discovery via Django apps framework
- **Models**: Inherit from `NetBoxModel` for NetBox UI integration

## CRD Model Structure (12 Types)
```python
# VPC API Models (6 types)
VPCPeering, VPCAttachment, IPv4Namespace, Connection, SwitchPort, Location

# Wiring API Models (6 types)  
Switch, ServerFacingConnector, FabricLink, Fabric, ConnectionRequirement, PortGroup
```

## Django Integration Points
- **URLs**: `netbox_hedgehog/urls.py` - All plugin routes
- **Views**: Class-based views inheriting NetBox patterns
- **Templates**: Bootstrap 5 with NetBox theme integration
- **API**: DRF serializers with NetBox REST framework

## Database Schema Integration
- **Tables**: Prefixed with `netbox_hedgehog_`
- **Relationships**: Foreign keys to NetBox core models
- **Migrations**: Standard Django migration system
- **Indexing**: Optimized for NetBox query patterns

## UI/UX Integration
- **Navigation**: Automatic menu integration via plugin config
- **Forms**: NetBox form framework with validation
- **Lists**: NetBox ObjectListView with filtering
- **Detail**: ObjectView with tabs and progressive disclosure

## Key Files to Master
```
netbox_hedgehog/
├── __init__.py           (Plugin registration)
├── models.py            (CRD Django models)
├── views.py             (UI view controllers)
├── urls.py              (URL routing)
├── api/                 (REST API endpoints)
├── templates/           (HTML templates)
└── sync/                (K8s synchronization)
```

## Sync Architecture
- **Class**: `KubernetesSync` in `sync/kubernetes_sync.py`
- **Pattern**: Django models ↔ Kubernetes CRDs
- **States**: Six-state workflow with conflict resolution
- **Real-time**: Watch patterns for live cluster sync

## Development Workflow
1. **Model Changes**: Django model → migration → apply
2. **UI Changes**: Template/view updates → NetBox restart
3. **API Changes**: Serializer updates → test endpoints
4. **Sync Changes**: K8s client updates → test with HCKC

## Common Integration Patterns
- **Field Types**: NetBox custom fields (IPAddress, JSON, etc.)
- **Permissions**: NetBox RBAC integration
- **Search**: NetBox global search framework
- **Export**: CSV/YAML export via NetBox patterns
- **Filtering**: NetBox FilterSet integration

**MASTERY GOAL**: Understand NetBox plugin patterns deeply enough to implement new CRD types efficiently.