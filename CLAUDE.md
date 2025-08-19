# Cloud NetOps Command (CNOC) Project Context

**Mission**: Enterprise-grade cloud networking operations infrastructure with bootable ISO deployment
**Methodology**: FORGE (Formal Operations with Rigorous Guaranteed Engineering)
**Status**: Production Development - Go-based CLI with Kubernetes architecture
**Branch**: modernization/k8s-foundation

## System Architecture Overview

**CNOC (Cloud NetOps Command)**: The new production system based on Go CLI, Kubernetes infrastructure, and domain-driven design patterns. This system replaces the original HNP prototype.

**HNP (Hedgehog NetBox Plugin)**: Original Python/Django prototype system preserved for reference on experimental/main branch.

## CNOC Technical Stack (Production Architecture)
- Core: Go 1.24 backend with Gorilla Mux router and FORGE validation coverage
- Frontend: Bootstrap 5.3 with vanilla JavaScript and server-rendered Go HTML templates
- Infrastructure: Kubernetes (K3s), GitOps, PostgreSQL 15, Redis 7
- Architecture: Domain-driven design with monolithic deployment pattern and FORGE evidence validation
- Testing Strategy: FORGE Symphony movements - red-green-refactor, mutation testing, comprehensive validation
- Deployment: HOSS bootable ISO with pre-configured components or direct K3s deployment
- Components: ArgoCD, Prometheus, Grafana, cert-manager with FORGE monitoring suites

## Technology Architecture Decisions

### Current Production Stack (CNOC)
**Rationale**: Proven Go+Bootstrap stack provides excellent performance (<200ms API responses), maintainability, and operational simplicity. This pragmatic approach enables rapid delivery of HNP feature parity while maintaining enterprise-grade reliability.

### Future Technology Considerations (Deferred)
**Advanced Technologies**: WasmCloud agent orchestration and React/NextJS frontend modernization are preserved as future options for consideration only if specific requirements emerge that cannot be efficiently addressed by the current stack.

**Decision Context**: GitHub Issue #60 (WasmCloud/React modernization) is marked as "DEFERRED - Future Consideration Only" based on current production success with Go+Bootstrap architecture.

## HNP Prototype Stack (Reference Only)
- Backend: Django 4.2, NetBox 4.3.3 plugin architecture  
- Frontend: Bootstrap 5 with progressive disclosure UI
- Integration: Kubernetes Python client, ArgoCD GitOps
- Database: PostgreSQL (shared with NetBox core)

## Development Environment (FORGE Symphony Orchestration)

### Branch Strategy with FORGE Process Routing
- **CNOC Branch**: modernization/k8s-foundation (FORGE methodology enforced)
- **HNP Reference**: experimental/main (prototype patterns preserved)
- **CLI Tool**: cnocfab (replacing hossfab) with FORGE validation suite (production Go application)
- **Infrastructure**: hossfab/, infrastructure/, hoss/ directories with FORGE patterns

### FORGE Symphony Task Orchestration Rules
```yaml
FORGE_Task_Routing:
  # Implementation tasks (ANY code writing) - MANDATORY FORGE test-first
  Go_Development: 
    Pattern: "*.go|*/go.mod|*/go.sum"
    FORGE_Movement: testing-validation-engineer → implementation-specialist
    Hook: forge_test_enforcement.sh (PreToolUse)
    
  Infrastructure_Code:
    Pattern: "*terraform/*|*/kubernetes/*|*/manifests/*"
    Process: infrastructure-deployment-specialist + testing-validation-engineer
    Validation: end-to-end deployment testing required
    
  CLI_Development:
    Pattern: "*cnocfab*|*/cmd/*|*/cli/*"
    Process: testing-validation-engineer → implementation-specialist
    Requirements: command testing, integration testing, error path testing
    
  Domain_Modeling:
    Pattern: "*models*|*domain*|*types*"
    Process: model-driven-architect + testing-validation-engineer
    Validation: bounded context definition + test scenarios
```

### Agent Selection Logic for Project Types
```yaml
CNOC_Tasks: 
  - Go backend development → testing-validation-engineer + implementation-specialist
  - Infrastructure deployment → infrastructure-deployment-specialist + kubernetes-gitops-specialist
  - CLI development → testing-validation-engineer + implementation-specialist
  - Domain modeling → model-driven-architect + testing-validation-engineer

HNP_Reference_Tasks:
  - Django plugin patterns → netbox-integration-specialist + testing-validation-engineer  
  - API development → contract-first-api-designer + testing-validation-engineer
  - GitOps integration → kubernetes-gitops-specialist + testing-validation-engineer
```

## Quick Links
- Project Mgmt: @project_management/CLAUDE.md
- Architecture: @architecture_specifications/CLAUDE.md
- System Overview: @architecture_specifications/00_current_architecture/system_overview.md
- GitOps Architecture: @architecture_specifications/00_current_architecture/component_architecture/gitops/gitops_overview.md
- Architectural Decisions: @architecture_specifications/01_architectural_decisions/decision_log.md
- Environment: @claude_memory/environment/
- Current State: @project_management/00_current_state/
- Archive: @archive/README.md