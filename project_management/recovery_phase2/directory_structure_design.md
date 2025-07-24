# HNP Project Directory Structure Design
## Recovery Phase 2 - Organizational Foundation

**Designer**: Project Structure Architect  
**Date**: July 23, 2025  
**Status**: Design Complete - Ready for Implementation  
**Integration**: Based on Phase 1 Research Findings

---

## Executive Summary

This document presents the complete directory structure design for the Hedgehog NetBox Plugin (HNP) project, incorporating all findings from Phase 1 research including CLAUDE.md architecture, external memory systems, and orchestrator-worker patterns.

---

## Complete Directory Structure

### Root Level CLAUDE.md Architecture

```
/hedgehog-netbox-plugin/
├── CLAUDE.md                    # Global project context (20 lines max)
├── project_management/          # All project management documentation
├── architecture_specifications/ # Technical architecture and design docs
├── claude_memory/              # External memory system for agents
├── netbox_hedgehog/            # Core plugin implementation
└── [existing project files]
```

### Project Management Directory Structure

```
/project_management/
├── README.md                    # Navigation guide and directory purpose
├── CLAUDE.md                    # Project management context
│
├── 00_current_state/           # Always current project status
│   ├── README.md               # How to maintain current state
│   ├── project_overview.md     # Executive summary of current state
│   ├── active_sprints.md       # Current sprint status and progress
│   ├── resource_allocation.md  # Current agent assignments and workload
│   ├── immediate_priorities.md # Next actions and critical path items
│   └── health_indicators.md    # Project health metrics and alerts
│
├── 01_planning/                # Project planning and roadmaps
│   ├── README.md               # Planning process and templates
│   ├── strategic_roadmap.md    # Long-term project vision and goals
│   ├── sprint_planning/        # Sprint planning documents
│   │   ├── sprint_template.md  # Template for new sprints
│   │   └── active/            # Current sprint planning docs
│   ├── resource_planning.md    # Resource allocation and capacity
│   ├── risk_management.md      # Risk assessment and mitigation
│   └── milestone_schedule.md   # Major milestones and deadlines
│
├── 02_execution/               # Active project execution tracking
│   ├── README.md               # Execution tracking guidelines
│   ├── sprint_logs/            # Individual sprint execution logs
│   │   ├── current/           # Active sprint logs
│   │   └── archive/           # Historical sprint logs
│   ├── task_tracking/          # Detailed task status and progress
│   │   ├── active_tasks.md    # Currently active tasks
│   │   └── task_registry.md   # All tasks with status
│   ├── quality_assurance/      # QA processes and validation
│   │   ├── test_results/      # Test execution results
│   │   └── qa_checklists.md   # Quality validation checklists
│   └── delivery_tracking.md    # Milestone and deliverable tracking
│
├── 03_coordination/            # Agent coordination and communication
│   ├── README.md               # Coordination protocols
│   ├── agent_assignments.md    # Current agent roles and responsibilities
│   ├── inter_agent_comm.md     # Communication logs and coordination
│   ├── escalation_tracking.md  # Issue escalation and resolution
│   ├── manager_reports/        # Manager status reports and updates
│   │   ├── template.md        # Report template
│   │   └── current/           # Current period reports
│   └── orchestrator_logs.md    # Orchestrator decision tracking
│
├── 04_history/                 # Historical project information
│   ├── README.md               # Archive organization guide
│   ├── completed_sprints/      # Archive of completed sprint docs
│   ├── lessons_learned.md      # Project lessons and improvements
│   ├── architectural_changes/  # Historical architecture decisions
│   ├── team_evolution.md       # Changes in team and process
│   └── incident_reports/       # Post-mortems and resolutions
│
├── 05_recovery/                # Project recovery specific docs
│   ├── README.md               # Recovery process documentation
│   ├── phase1_research/        # Phase 1 research results
│   │   └── [existing files]   # Preserve existing research
│   ├── phase2_structure/       # Phase 2 structural improvements
│   │   ├── implementation_log.md
│   │   └── validation_results.md
│   ├── phase3_agile/           # Phase 3 agile implementation
│   │   └── planning/          # Agile transformation plans
│   └── recovery_outcomes.md    # Recovery results and effectiveness
│
└── 99_templates/               # Reusable templates and standards
    ├── README.md               # Template usage guide
    ├── sprint_planning_template.md
    ├── agent_instruction_template.md
    ├── status_report_template.md
    ├── task_definition_template.md
    ├── risk_assessment_template.md
    ├── retrospective_template.md
    └── project_documentation_standards.md
```

### Architecture Specifications Directory

```
/architecture_specifications/
├── README.md                   # Architecture documentation guide
├── CLAUDE.md                   # Architecture context for agents
│
├── 00_current_architecture/    # Current system architecture
│   ├── README.md               # Current state overview
│   ├── system_overview.md      # High-level architecture
│   ├── component_architecture/ # Individual components
│   │   ├── netbox_plugin.md   # Plugin architecture
│   │   ├── kubernetes_integration.md
│   │   ├── gitops_workflow.md
│   │   └── ui_framework.md
│   ├── integration_patterns.md # Integration specifications
│   ├── technology_stack.md     # Current tech choices
│   └── deployment_architecture.md
│
├── 01_architectural_decisions/ # Architecture decision records
│   ├── README.md               # ADR process and template
│   ├── decision_log.md         # Chronological decision log
│   ├── active_decisions/       # Decisions being evaluated
│   ├── approved_decisions/     # Implemented decisions
│   │   └── adr_template.md    # ADR template
│   └── deprecated_decisions/   # Superseded decisions
│
├── 02_design_specifications/   # Detailed design documents
│   ├── README.md               # Design doc guidelines
│   ├── api_specifications/     # API design and interfaces
│   │   ├── rest_api.md        # REST API specs
│   │   └── internal_api.md    # Internal interfaces
│   ├── data_models/            # Database and data structures
│   │   ├── crd_models.md      # CRD data models
│   │   └── state_management.md
│   ├── user_interface/         # UI/UX specifications
│   │   └── progressive_disclosure.md
│   └── integration_specs/      # External integrations
│       ├── kubernetes_api.md
│       └── argpcd_integration.md
│
├── 03_standards_governance/    # Standards and governance
│   ├── README.md               # Governance overview
│   ├── coding_standards.md     # Development standards
│   ├── review_processes.md     # Architecture review process
│   ├── quality_standards.md    # Quality assurance standards
│   ├── security_standards.md   # Security requirements
│   └── change_management.md    # Change procedures
│
└── 04_reference/               # Reference materials
    ├── README.md               # Reference guide
    ├── external_dependencies/  # Third-party docs
    ├── patterns_library/       # Reusable patterns
    ├── best_practices.md       # Best practices
    ├── troubleshooting.md      # Common issues
    └── glossary.md            # Technical terms
```

### CLAUDE.md External Memory Structure

```
/claude_memory/
├── README.md                   # Memory system usage guide
├── CLAUDE.md                   # Meta-context about memory system
│
├── environment/                # Development environment docs
│   ├── README.md               # Environment overview
│   ├── netbox_docker_ops.md   # NetBox Docker operations
│   ├── kubernetes_clusters.md  # HCKC and ArgoCD info
│   ├── gitops_infrastructure.md # GitOps repository docs
│   ├── testing_environment.md  # Testing procedures
│   └── local_development.md   # Local dev setup
│
├── project_context/           # Project background and context
│   ├── README.md              # Context overview
│   ├── project_history.md     # Evolution and milestones
│   ├── stakeholder_context.md # Requirements and business
│   ├── technical_context.md   # Technical constraints
│   ├── team_context.md        # Team structure
│   └── domain_knowledge.md    # Hedgehog/NetBox specifics
│
├── processes/                 # Standard operating procedures
│   ├── README.md              # Process overview
│   ├── git_workflow.md        # Git procedures
│   ├── documentation_standards.md
│   ├── quality_assurance.md   # Testing procedures
│   ├── agent_coordination.md  # Agent communication
│   ├── deployment_process.md  # Release procedures
│   └── incident_response.md   # Issue handling
│
└── quick_reference/           # Immediate access info
    ├── README.md              # Quick ref guide
    ├── environment_checklist.md
    ├── common_commands.md     # Frequently used commands
    ├── troubleshooting_quick.md
    ├── escalation_contacts.md
    └── critical_paths.md      # Key file locations
```

### CLAUDE.md Content Structure

#### Root CLAUDE.md (20 lines max)
```markdown
# Hedgehog NetBox Plugin (HNP) Project Context

**Mission**: Self-service Kubernetes CRD management via NetBox interface
**Status**: MVP Complete - 12 CRD types operational
**Branch**: feature/mvp2-database-foundation

## Technical Stack
- Backend: Django 4.2, NetBox 4.3.3 plugin
- Frontend: Bootstrap 5 with progressive disclosure
- Integration: Kubernetes Python client, ArgoCD GitOps
- Database: PostgreSQL (shared with NetBox)

## Environment
- NetBox Docker: Custom plugin integration
- HCKC Cluster: Local Kubernetes management
- GitOps: github.com/afewell-hh/gitops-test-1.git

## Quick Links
- Project Mgmt: @project_management/CLAUDE.md
- Architecture: @architecture_specifications/CLAUDE.md
- Environment: @claude_memory/environment/
- Current State: @project_management/00_current_state/
```

#### Project Management CLAUDE.md
```markdown
# Project Management Context

**Purpose**: Centralized project coordination and tracking
**Structure**: Progressive disclosure from current state to history

## Navigation
- 00_current_state/: Live project status
- 01_planning/: Roadmaps and sprint planning  
- 02_execution/: Active work tracking
- 03_coordination/: Agent coordination
- 04_history/: Completed work archive
- 05_recovery/: Recovery phase documentation
- 99_templates/: Reusable templates

## Key Processes
- Sprint Planning: 2-week cycles
- Agent Coordination: Orchestrator-worker pattern
- Quality Gates: Test-driven development
- Documentation: Maintained with code changes

## Import
@00_current_state/project_overview.md
@01_planning/strategic_roadmap.md
```

---

## Implementation Priorities

### Phase 1: Core Structure (Days 1-2)
1. Create all directory structures
2. Implement CLAUDE.md files at key locations
3. Create README.md navigation files
4. Set up claude_memory infrastructure

### Phase 2: Content Migration (Days 3-4)
1. Migrate existing project_management content
2. Preserve valuable documentation
3. Archive outdated materials
4. Update all cross-references

### Phase 3: Template Creation (Days 5-6)
1. Develop all templates in 99_templates
2. Create process documentation
3. Implement quality checklists
4. Establish maintenance procedures

### Phase 4: Validation (Day 7)
1. Test agent navigation scenarios
2. Validate information accessibility
3. Confirm no critical content lost
4. Prepare handoff documentation

---

## Success Metrics

- [ ] Untrained agent can find current project state in <30 seconds
- [ ] All project information accessible within directory structure
- [ ] Environment setup eliminates repeated discovery cycles
- [ ] Historical information preserved but clearly separated
- [ ] CLAUDE.md architecture properly implemented
- [ ] Templates support consistent documentation
- [ ] Navigation is intuitive without external guidance

---

## Integration Points

### NetBox Docker Environment
- Location: `/gitignore/netbox-docker/`
- Documentation: `/claude_memory/environment/netbox_docker_ops.md`

### HCKC Kubernetes Cluster
- Kubeconfig: `~/.kube/config`
- Documentation: `/claude_memory/environment/kubernetes_clusters.md`

### GitOps Test Repository
- URL: `https://github.com/afewell-hh/gitops-test-1.git`
- Documentation: `/claude_memory/environment/gitops_infrastructure.md`

---

## Maintenance Guidelines

1. **Current State Updates**: Daily updates to 00_current_state
2. **Sprint Documentation**: Updated at sprint boundaries
3. **CLAUDE.md Files**: Reviewed weekly for accuracy
4. **Template Evolution**: Updated based on usage feedback
5. **Archive Management**: Monthly review of historical content

This structure provides the intuitive, scalable foundation needed for effective agent-based development on the HNP project.