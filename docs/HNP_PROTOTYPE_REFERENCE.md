# HNP Prototype Reference Documentation

**Purpose**: Comprehensive reference for Hedgehog NetBox Plugin prototype  
**Status**: Prototype system - reference only for CNOC development  
**Branch**: experimental/main (preserved for reference)

## Overview

The Hedgehog NetBox Plugin (HNP) was the original Python/Django prototype system that demonstrated NetBox integration patterns and CRD management concepts. This prototype has been **superseded by CNOC** and is no longer under active development.

## HNP Architecture (Reference Only)

### Technical Stack
- **Backend**: Django 4.2, NetBox 4.3.3 plugin architecture  
- **Frontend**: Bootstrap 5 with progressive disclosure UI
- **Integration**: Kubernetes Python client, ArgoCD GitOps
- **Database**: PostgreSQL (shared with NetBox core)
- **Deployment**: Docker container with NetBox integration

### Core Components
- **12 CRD Types**: VPC API (7 types) + Wiring API (5 types)
- **GitOps Integration**: Repository synchronization with YAML parsing
- **Fabric Management**: HedgehogFabric model with sync operations
- **Web Interface**: NetBox-compatible UI with progressive disclosure

### Key Features Demonstrated
1. **CRD Management**: CRUD operations for 12 Kubernetes CRD types
2. **GitOps Workflow**: Git repository integration with drift detection
3. **Fabric Synchronization**: Bidirectional sync between NetBox, Git, and K8s
4. **User Interface**: Professional NetBox-style interface with Bootstrap 5

## Relationship to CNOC

### Purpose of HNP Prototype
- **Proof of Concept**: Validated NetBox integration patterns
- **Feature Discovery**: Identified essential CRD management requirements
- **UI/UX Validation**: Established user experience patterns
- **GitOps Patterns**: Demonstrated repository synchronization workflows

### CNOC Implementation Approach
HNP prototype insights inform CNOC development through:
- **Feature Parity Matrix**: CNOC implements equivalent functionality
- **Anti-Corruption Layers**: Clean separation from NetBox dependencies  
- **Domain Model Translation**: Go structs equivalent to Django models
- **API Patterns**: REST endpoints inspired by HNP operations

## Feature Mapping (HNP → CNOC)

### Core Feature Translation
| HNP Component | CNOC Equivalent | Implementation |
|---------------|-----------------|----------------|
| HedgehogFabric Django model | Fabric Go struct | Domain-driven design |
| 12 CRD Django models | Generic CRDResource struct | Type-agnostic approach |
| NetBox plugin views | CNOC REST API + Web UI | Independent implementation |
| GitOps Python integration | Go GitOps service | Cloud-native patterns |
| PostgreSQL (NetBox shared) | Independent PostgreSQL | Clean database separation |

### Architecture Evolution
```
HNP Prototype (Django/NetBox)    →    CNOC Production (Go/Cloud-Native)
├── Plugin architecture          →    ├── Standalone application
├── NetBox UI framework          →    ├── Independent web components  
├── Shared PostgreSQL            →    ├── Dedicated database
├── Python/Django stack          →    ├── Go/Kubernetes stack
└── Container deployment         →    └── Cloud-native deployment
```

## Documentation Assets

### Existing HNP Documentation
- **System Overview**: `/architecture_specifications/00_current_architecture/system_overview.md`
- **GitOps Architecture**: `/architecture_specifications/00_current_architecture/component_architecture/gitops/`
- **Architectural Decisions**: `/architecture_specifications/01_architectural_decisions/decision_log.md`
- **Feature Parity Roadmap**: `/cnoc/docs/CNOC_FEATURE_PARITY_ROADMAP.md`

### Development History
- **MVP Evidence**: `/archive/evidence/session_reports/` - Implementation evidence and validation
- **Implementation Plans**: `/archive/implementation_plans/` - Detailed development plans
- **Technical Decisions**: Complete ADR documentation with 9 decisions

## Usage Guidelines for Agents

### When to Reference HNP
- **Feature equivalence questions**: Understanding what functionality CNOC should implement
- **UI/UX patterns**: Reference for user experience design decisions
- **GitOps workflows**: Understanding repository synchronization patterns
- **Data model relationships**: Foreign key patterns and schema design

### When NOT to Reference HNP
- **Current development**: Focus on CNOC for all active development
- **Architecture decisions**: Use CNOC patterns, not HNP legacy patterns
- **Technology choices**: Go/Kubernetes patterns, not Django/NetBox patterns
- **Deployment procedures**: CNOC deployment, not NetBox plugin deployment

### Quick Reference Pointers
- **"What CRDs does CNOC need?"** → See HNP 12 CRD types for reference
- **"What should the UI look like?"** → Reference HNP progressive disclosure patterns
- **"How should GitOps work?"** → Study HNP repository synchronization design
- **"What API endpoints are needed?"** → Analyze HNP Django view patterns

## Conclusion

HNP serves as a valuable reference prototype that validated key concepts now implemented in CNOC. While HNP is no longer under active development, its documented patterns and feature definitions continue to inform CNOC development decisions through the comprehensive feature parity roadmap and architectural documentation.