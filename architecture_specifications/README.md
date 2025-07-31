# Architecture Specifications Directory

**Purpose**: Technical architecture documentation, design specifications, and architectural governance for the Hedgehog NetBox Plugin (HNP) project.

## Directory Structure

### 🏗️ 00_current_architecture/
**Current system architecture** - The implemented architecture
- `system_overview.md` - ✅ High-level architecture overview (MVP Complete - 12 CRD types operational)
- `component_architecture/` - ✅ Individual component specifications
  - `kubernetes_integration.md` - ✅ K8s cluster integration patterns
  - `netbox_plugin_layer.md` - ✅ NetBox 4.3.3 plugin architecture
  - `gitops/` - ✅ GitOps architecture and directory management
    - `gitops_overview.md` - ✅ Comprehensive GitOps design
    - `directory_management_specification.md` - ✅ Directory management patterns
    - `drift_detection_design.md` - ✅ First-class drift detection

### 📋 01_architectural_decisions/
**Architecture decision records (ADRs)** - Decision tracking
- `decision_log.md` - ✅ Comprehensive decision index (9 ADRs total)
- `active_decisions/` - ✅ Decisions currently being evaluated
  - `gitops_repository_separation.md` - ✅ ADR-002: Multi-fabric architecture design
- `approved_decisions/` - ✅ Approved and implemented decisions
  - `adr-001-gitops-first-architecture.md` - ✅ Single GitOps workflow
  - [8 additional implemented ADRs documented]
- `deprecated_decisions/` - Superseded or obsolete decisions (none currently)

### 📐 02_design_specifications/
**Detailed design documents** - Technical specifications
- `api_specifications/` - API design and interface specifications
- `data_models/` - Database and data structure designs
- `user_interface/` - UI/UX design specifications and patterns
- `integration_specs/` - External system integration specifications

### 📏 03_standards_governance/
**Architectural standards and governance** - Quality control
- `coding_standards.md` - Development standards and conventions
- `review_processes.md` - Architecture review and approval processes
- `quality_standards.md` - Quality assurance and testing standards
- `security_standards.md` - Security requirements and guidelines
- `change_management.md` - Architecture change management procedures

### 📚 04_reference/
**Reference materials and documentation** - Supporting resources
- `external_dependencies/` - Third-party component documentation
- `patterns_library/` - Reusable architectural patterns
- `best_practices.md` - Architectural best practices
- `troubleshooting.md` - Common issues and resolution patterns
- `glossary.md` - Technical terms and definitions

## Quick Start Guide

1. **Understanding current architecture?** Start with `00_current_architecture/system_overview.md`
2. **Making architectural changes?** Review `01_architectural_decisions/` and create an ADR
3. **Implementing features?** Check `02_design_specifications/` for detailed specs
4. **Code review?** Reference `03_standards_governance/coding_standards.md`

## Architecture Principles

1. **NetBox Plugin Compatibility** - All designs must maintain NetBox 4.3.3 compatibility
2. **Kubernetes Native** - Leverage Kubernetes patterns and best practices
3. **Progressive Disclosure** - UI complexity revealed gradually
4. **GitOps Ready** - Support declarative configuration management
5. **Extensibility** - Design for future CRD types and features

## Decision Process

1. **Proposal** - Create ADR in `active_decisions/`
2. **Review** - Technical review per `review_processes.md`
3. **Approval** - Move to `approved_decisions/` when accepted
4. **Implementation** - Update `00_current_architecture/` after implementation
5. **Deprecation** - Move outdated decisions to `deprecated_decisions/`

## Key Technologies

- **Backend**: Django 4.2, NetBox 4.3.3 Plugin Framework
- **Database**: PostgreSQL (shared with NetBox)
- **Frontend**: Bootstrap 5, HTMX for interactivity
- **Integration**: Kubernetes Python Client, ArgoCD
- **Deployment**: Docker, Kubernetes

## Maintenance

- **Weekly**: Review active decisions
- **Per Change**: Update current architecture docs
- **Monthly**: Archive completed decisions
- **Quarterly**: Review standards and governance