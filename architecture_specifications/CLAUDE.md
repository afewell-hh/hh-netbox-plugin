# Architecture Specifications Context

**Purpose**: Technical architecture and design documentation for CNOC system  
**Architecture Style**: Go-based CLI with Kubernetes infrastructure and domain-driven design  
**Status**: Production Development - CNOC system architecture based on HOSS foundations

## System Scope

**CNOC Architecture**: This documents the new Cloud NetOps Command system architecture
**HNP Reference**: Original prototype architecture preserved for reference and transition planning

## Core Architecture (✅ Documented)
- **Plugin Pattern**: NetBox 4.3.3 compatible Django app
- **Data Flow**: GitOps repository → YAML parsing → Django models → NetBox UI
- **GitOps Integration**: Multi-fabric directory management with drift detection
- **Authentication**: Encrypted credential storage with repository separation design

## Current System Status
- **Operational**: 12 CRD types with 36 synchronized records
- **GitOps**: github.com/afewell-hh/gitops-test-1.git operational
- **Testing**: 10/10 tests passing with evidence-based validation
- **Security**: Comprehensive authentication with encrypted credentials

## Key Architecture Documentation

### System Architecture
- **System Overview**: Comprehensive current architecture status
- **Kubernetes Integration**: K8s cluster integration patterns and GitOps processing
- **NetBox Plugin Layer**: Django plugin architecture with authentication integration
- **GitOps Architecture**: Multi-fabric directory management and drift detection design

### Architectural Decisions
- **Decision Log**: 9 ADRs total (8 implemented, 1 approved for implementation)
- **GitOps-First**: Single workflow architecture (implemented)
- **Repository Separation**: Multi-fabric authentication design (approved)
- **Quality Framework**: Test-driven development with evidence-based validation

### Component Architecture
- **Models**: HedgehogFabric, GitRepository with proper foreign key relationships
- **Views**: List/Detail with progressive disclosure and drift detection UI
- **API**: REST endpoints with encrypted credential management
- **Templates**: Bootstrap 5 with NetBox-consistent styling

## Design Principles (Validated)
1. **NetBox Compatibility First**: ✅ NetBox 4.3.3 integration operational
2. **Kubernetes-Native Patterns**: ✅ GitOps workflow with YAML processing
3. **Progressive UI Disclosure**: ✅ Professional interface with drift detection prominence
4. **GitOps-Ready Architecture**: ✅ Repository-based configuration management

## Navigation Map
```
architecture_specifications/
├── 00_current_architecture/          # ✅ Current system documentation
│   ├── system_overview.md            # ✅ MVP complete status
│   └── component_architecture/       # ✅ Detailed component specs
│       ├── kubernetes_integration.md # ✅ K8s integration patterns
│       ├── netbox_plugin_layer.md   # ✅ Plugin architecture
│       └── gitops/                  # ✅ GitOps architecture
│           ├── gitops_overview.md   # ✅ Comprehensive GitOps design
│           ├── directory_management_specification.md
│           └── drift_detection_design.md
├── 01_architectural_decisions/       # ✅ Complete ADR documentation
│   ├── decision_log.md              # ✅ 9 ADRs indexed
│   ├── active_decisions/            # ✅ Repository separation design
│   └── approved_decisions/          # ✅ Implemented decisions
└── README.md                        # ✅ Architecture navigation guide
```

## Implementation Evidence
- **All Components Operational**: System architecture fully documented with current operational status
- **Quality Assurance**: Evidence-based validation with comprehensive test coverage
- **Zero Information Loss**: All scattered architectural information consolidated
- **Clear Navigation**: Professional documentation structure with cross-references

## References
- **System Overview**: @00_current_architecture/system_overview.md
- **GitOps Architecture**: @00_current_architecture/component_architecture/gitops/gitops_overview.md
- **Architectural Decisions**: @01_architectural_decisions/decision_log.md
- **Archive**: @../archive/README.md - Consolidated scattered documentation