# Cloud NetOps Command (CNOC) Project Context

**Mission**: Enterprise-grade cloud networking operations infrastructure with bootable ISO deployment
**Status**: Production Development - Go-based CLI with Kubernetes architecture
**Branch**: modernization/k8s-foundation

## System Architecture Overview

**CNOC (Cloud NetOps Command)**: The new production system based on Go CLI, Kubernetes infrastructure, and domain-driven design patterns. This system replaces the original HNP prototype.

**HNP (Hedgehog NetBox Plugin)**: Original Python/Django prototype system preserved for reference on experimental/main branch.

## CNOC Technical Stack (Test-First Development Architecture)
- Core: Go-based cnocfab CLI utility with comprehensive test coverage
- Infrastructure: Kubernetes, GitOps, Terraform with test-driven infrastructure patterns
- Architecture: Domain-driven design, microservices with evidence-based validation
- Testing Strategy: Red-green-refactor enforcement, mutation testing, template validation
- Deployment: Bootable ISO with pre-configured components and validation frameworks
- Components: ArgoCD, Prometheus, Grafana, cert-manager with monitoring test suites

## HNP Prototype Stack (Reference Only)
- Backend: Django 4.2, NetBox 4.3.3 plugin architecture  
- Frontend: Bootstrap 5 with progressive disclosure UI
- Integration: Kubernetes Python client, ArgoCD GitOps
- Database: PostgreSQL (shared with NetBox core)

## Development Environment (Hive Queen Orchestration)

### Branch Strategy with Process Routing
- **CNOC Branch**: modernization/k8s-foundation (test-first development enforced)
- **HNP Reference**: experimental/main (prototype patterns preserved)
- **CLI Tool**: cnocfab (replacing hossfab) with comprehensive test suite
- **Infrastructure**: hossfab/, infrastructure/, hoss/ directories with TDD patterns

### Hive Queen Task Orchestration Rules
```yaml
Task_Type_Detection_and_Routing:
  # Implementation tasks (ANY code writing) - MANDATORY test-first
  Go_Development: 
    Pattern: "*.go|*/go.mod|*/go.sum"
    Process: testing-validation-engineer → implementation-specialist
    Hook: test_first_enforcement.sh (PreToolUse)
    
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