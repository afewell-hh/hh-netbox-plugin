# Architecture Specifications Context

**Purpose**: Technical architecture and design documentation for HNP
**Architecture Style**: NetBox plugin with Kubernetes integration

## Core Architecture
- Plugin Pattern: NetBox 4.3.3 compatible Django app
- Data Flow: K8s CRDs → Python Client → Django Models → NetBox UI
- State Management: Six-state workflow with conflict resolution
- Integration: Real-time sync with Kubernetes watch patterns

## Key Components
- Models: 12 CRD types (VPC API + Wiring API)
- Views: List/Detail with progressive disclosure
- API: REST endpoints for all CRD operations
- Sync: KubernetesSync class for cluster integration

## Design Principles
1. NetBox compatibility first
2. Kubernetes-native patterns
3. Progressive UI disclosure
4. GitOps-ready architecture

## References
@00_current_architecture/system_overview.md
@02_design_specifications/data_models/
@03_standards_governance/coding_standards.md