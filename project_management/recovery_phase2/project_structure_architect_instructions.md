# Project Structure Architect Instructions

**Agent Role**: Project Structure Architect  
**Project Phase**: Recovery Phase 2 - Organizational Foundation  
**Priority**: CRITICAL - Infrastructure for all future project management  
**Duration**: 1 week focused design and implementation  
**Authority Level**: Directory structure creation and documentation organization

---

## Mission Statement

**Primary Objective**: Design and implement an intuitive, scalable project management directory structure that enables efficient navigation and organization for agent-based development teams working on complex, long-running software projects.

**Critical Context**: Based on Phase 1 research findings, create organizational infrastructure that incorporates CLAUDE.md architecture, external memory systems, and supports the orchestrator-worker agent patterns that have proven 90%+ more effective than single-agent approaches.

**Strategic Importance**: Your directory structure will be the foundation for all future project management, documentation, and agent coordination. It must be so intuitive that even untrained agents can navigate and understand the current project state.

---

## Research Foundation Integration

### Key Research Findings to Apply

**From Agent Instruction Best Practices Research**:
- **CLAUDE.md Architecture**: Implement external memory system structure
- **Hierarchical Agent Patterns**: Support orchestrator → manager → specialist workflows
- **Context Management**: Structure that minimizes agent memory usage
- **Process Compliance**: Built-in organization for git workflows and documentation

**Specific Patterns to Implement**:
- External memory file hierarchy (CLAUDE.md system)
- Role-based directory organization (orchestrator, manager, specialist levels)
- Progressive disclosure directory structure
- Automated navigation and discovery systems

### Environment Integration Requirements

**From CEO Requirements**:
- **NetBox Docker Environment**: Clear organization for development environment procedures
- **GitOps Test Infrastructure**: Structured approach to test repository management  
- **Kubernetes Clusters**: Organized documentation for HCKC and ArgoCD cluster operations
- **Manager Training**: Directory structure supporting manager agent creation and coordination

---

## Directory Structure Design Requirements

### 1. Project Management Master Structure

**Core Requirement**: Single directory containing ALL project management information that enables complete project state understanding without leaving the directory structure.

**Organizational Principles**:
- **Intuitive Navigation**: Logical hierarchy that guides users to information
- **Scalable Structure**: Supports years of ongoing development and multiple sub-projects
- **Role-Based Access**: Clear paths for different agent types (orchestrator, manager, specialist)
- **Historical Preservation**: Maintains project history without cluttering current state

### 2. Architecture and Specifications Structure  

**Core Requirement**: Separate but coordinated directory for all architectural decisions and technical specifications.

**Integration Points**:
- Clear relationship with project management directory
- Support for architectural governance and change management
- Historical architecture decision tracking
- Technology stack and dependency management

### 3. CLAUDE.md External Memory Implementation

**Research Finding Integration**: Implement external memory system that prevents agent context overflow and eliminates repeated environment discovery.

**Required Components**:
- Structured external memory files
- Environment setup and operational procedures
- Project context and background information
- Agent coordination and communication protocols

---

## Detailed Design Specifications

### Project Management Directory Structure

**Primary Location**: `/project_management/`

**Required Sub-Structure**:

```
project_management/
├── 00_current_state/           # Always current project status
│   ├── project_overview.md     # Executive summary of current state
│   ├── active_sprints.md       # Current sprint status and progress
│   ├── resource_allocation.md  # Current agent assignments and workload
│   └── immediate_priorities.md # Next actions and critical path items
│
├── 01_planning/                # Project planning and roadmaps
│   ├── strategic_roadmap.md    # Long-term project vision and goals
│   ├── sprint_planning/        # Sprint planning documents
│   ├── resource_planning.md    # Resource allocation and capacity planning
│   └── risk_management.md      # Risk assessment and mitigation plans
│
├── 02_execution/               # Active project execution tracking
│   ├── sprint_logs/            # Individual sprint execution logs
│   ├── task_tracking/          # Detailed task status and progress
│   ├── quality_assurance/      # QA processes and validation results
│   └── delivery_tracking.md    # Milestone and deliverable tracking
│
├── 03_coordination/            # Agent coordination and communication
│   ├── agent_assignments.md    # Current agent roles and responsibilities
│   ├── inter_agent_comm.md     # Communication logs and coordination
│   ├── escalation_tracking.md  # Issue escalation and resolution
│   └── manager_reports/        # Manager status reports and updates
│
├── 04_history/                 # Historical project information
│   ├── completed_sprints/      # Archive of completed sprint documentation
│   ├── lessons_learned.md      # Project lessons learned and improvements
│   ├── architectural_changes/  # Historical architecture decision log
│   └── team_evolution.md       # Changes in team structure and process
│
├── 05_recovery/                # Project recovery specific documentation
│   ├── phase1_research/        # Phase 1 research results and findings
│   ├── phase2_structure/       # Phase 2 structural improvements
│   ├── phase3_agile/           # Phase 3 agile implementation
│   └── recovery_outcomes.md    # Recovery results and effectiveness
│
└── 99_templates/               # Reusable templates and standards
    ├── sprint_planning_template.md
    ├── agent_instruction_template.md
    ├── status_report_template.md
    └── project_documentation_standards.md
```

### Architecture and Specifications Directory

**Primary Location**: `/architecture_specifications/`

**Required Sub-Structure**:

```
architecture_specifications/
├── 00_current_architecture/    # Current system architecture
│   ├── system_overview.md      # High-level architecture overview
│   ├── component_architecture/ # Individual component specifications
│   ├── integration_patterns.md # Integration and interface specifications
│   └── technology_stack.md     # Current technology choices and versions
│
├── 01_architectural_decisions/ # Architecture decision records (ADRs)
│   ├── decision_log.md         # Chronological decision log with status
│   ├── active_decisions/       # Decisions currently being evaluated
│   ├── approved_decisions/     # Approved and implemented decisions
│   └── deprecated_decisions/   # Superseded or obsolete decisions
│
├── 02_design_specifications/   # Detailed design documents
│   ├── api_specifications/     # API design and interface specifications
│   ├── data_models/            # Database and data structure designs
│   ├── user_interface/         # UI/UX design specifications and patterns
│   └── integration_specs/      # External system integration specifications
│
├── 03_standards_governance/    # Architectural standards and governance
│   ├── coding_standards.md     # Development standards and conventions
│   ├── review_processes.md     # Architecture review and approval processes
│   ├── quality_standards.md    # Quality assurance and testing standards
│   └── change_management.md    # Architecture change management procedures
│
└── 04_reference/               # Reference materials and documentation
    ├── external_dependencies/  # Third-party component documentation
    ├── patterns_library/       # Reusable architectural patterns
    ├── best_practices.md       # Architectural best practices
    └── troubleshooting.md      # Common issues and resolution patterns
```

### CLAUDE.md External Memory Structure

**Primary Location**: `/CLAUDE.md` (root level for global access)

**Supporting Structure**: `/claude_memory/`

```
claude_memory/
├── environment/                # Development environment documentation
│   ├── netbox_docker_ops.md   # NetBox Docker operations and procedures
│   ├── kubernetes_clusters.md # HCKC and ArgoCD cluster information
│   ├── gitops_infrastructure.md # GitOps repository and workflow documentation
│   └── testing_environment.md # Testing procedures and validation
│
├── project_context/           # Project background and context
│   ├── project_history.md     # Project evolution and major milestones
│   ├── stakeholder_context.md # User requirements and business context
│   ├── technical_context.md   # Technical constraints and decisions
│   └── team_context.md        # Team structure and agent coordination
│
├── processes/                 # Standard operating procedures
│   ├── git_workflow.md        # Git commit and branch management
│   ├── documentation_standards.md # Documentation creation and maintenance
│   ├── quality_assurance.md   # Testing and validation procedures
│   └── agent_coordination.md  # Agent communication and coordination
│
└── quick_reference/           # Immediate access information
    ├── environment_checklist.md # Quick environment setup validation
    ├── common_commands.md      # Frequently used commands and procedures
    ├── troubleshooting_quick.md # Common issues and immediate solutions
    └── escalation_contacts.md  # When and how to escalate issues
```

---

## Implementation Requirements

### 1. Directory Creation and Organization

**Physical Structure Implementation**:
- Create all specified directories with proper permissions
- Implement consistent naming conventions throughout structure
- Create index files for major directory sections
- Establish cross-reference linking between related sections

**Navigation Enhancement**:
- Create README.md files for each major directory section
- Implement consistent navigation links and cross-references
- Create quick-access shortcuts for frequently needed information
- Establish search and discovery mechanisms

### 2. Template and Standard Creation

**Template Development**:
- Create reusable templates for each type of project document
- Develop standard formats for status reports and project tracking
- Establish consistent formatting and structure standards
- Create validation checklists for document quality

**Process Integration**:
- Integrate templates with established project processes
- Create workflow guides for using templates effectively
- Establish quality standards for template usage
- Create training materials for template implementation

### 3. Migration and Consolidation Planning

**Existing Content Assessment**:
- Inventory all current project management and documentation
- Identify content that should be preserved vs. deprecated
- Create migration plan for moving existing content to new structure
- Establish validation process for migrated content

**Content Organization Strategy**:
- Prioritize current vs. historical content organization
- Create clear separation between active and archived information
- Establish content lifecycle management procedures
- Create content validation and quality assurance processes

---

## Integration with Research Findings

### CLAUDE.md Architecture Implementation

**External Memory System**:
- Implement structured external memory files that agents can reference
- Create environment setup documentation that eliminates discovery cycles
- Establish project context files that provide immediate orientation
- Create process documentation that ensures compliance and quality

**Context Management Optimization**:
- Structure information to minimize agent context usage
- Create progressive disclosure navigation patterns
- Implement quick reference materials for immediate access
- Establish clear escalation and communication pathways

### Multi-Agent Coordination Support

**Hierarchical Structure Support**:
- Create clear organizational structure for orchestrator → manager → specialist workflows
- Implement coordination and communication documentation structure
- Establish clear role definitions and responsibility boundaries
- Create status reporting and progress tracking mechanisms

**Agent Instruction Integration**:
- Structure supports the agent instruction templates from Phase 1 research
- Create clear pathways for agent onboarding and training
- Establish process compliance monitoring and validation
- Implement quality assurance and continuous improvement processes

---

## Success Criteria and Validation

### Primary Success Metrics

**Navigation and Usability**:
- [ ] Untrained agent can navigate structure and understand current project state
- [ ] All project management information accessible within directory structure
- [ ] Clear pathways exist for all agent roles (orchestrator, manager, specialist)
- [ ] Historical information preserved but clearly separated from current state

**Integration and Efficiency**:
- [ ] Structure supports CLAUDE.md external memory system implementation
- [ ] Environment setup documentation eliminates repeated discovery cycles
- [ ] Templates and standards enable consistent project documentation
- [ ] Migration plan preserves valuable existing content while eliminating confusion

**Scalability and Maintenance**:
- [ ] Structure supports years of ongoing development and multiple sub-projects
- [ ] Clear processes exist for maintaining and updating directory organization
- [ ] Content lifecycle management prevents information decay and obsolescence
- [ ] Quality standards ensure ongoing directory structure effectiveness

### Integration Validation

**Research Findings Application**:
- [ ] CLAUDE.md architecture properly implemented for external memory
- [ ] Directory structure supports orchestrator-worker agent patterns
- [ ] Context management optimization built into organizational structure
- [ ] Process compliance frameworks integrated throughout structure

**HNP Project Specific Requirements**:
- [ ] Environment setup documentation addresses NetBox Docker, HCKC, and ArgoCD clusters
- [ ] GitOps workflow integration properly documented and organized
- [ ] Agent coordination and communication pathways clearly established
- [ ] Quality assurance and testing framework support integrated

---

## Communication and Coordination Requirements

### Status Reporting

**Daily Progress Updates**: Directory creation progress and implementation status
**Integration Coordination**: Coordination with Onboarding System Designer for Phase 2 completion
**Quality Validation**: Template and standard validation with project requirements

### CEO Communication Protocol

**Approval Required For**:
- Final directory structure before implementation
- Migration strategy for existing project content
- Template and standard specifications
- Integration approach with existing agent onboarding materials

**Progress Reporting Requirements**:
- Daily implementation status with completion percentage
- Issue identification and resolution planning
- Quality validation results and effectiveness assessment
- Readiness confirmation for Phase 3 Agile Implementation planning

---

## Implementation Timeline

### Week Structure

**Days 1-2: Structure Design and Validation**
- Complete directory structure design based on research findings
- Create navigation and organization standards
- Validate structure against HNP project requirements
- Obtain CEO approval for implementation approach

**Days 3-4: Physical Implementation**
- Create all directory structures with proper organization
- Implement README files and navigation enhancement
- Create templates and standards for project documentation
- Establish migration planning for existing content

**Days 5-6: Content Organization and Migration**
- Assess existing project management and documentation content
- Implement migration strategy for valuable existing content
- Organize current state information in new structure
- Validate navigation and usability with test scenarios

**Day 7: Validation and Handoff**
- Complete final validation of directory structure effectiveness
- Create handoff documentation for Onboarding System Designer
- Establish ongoing maintenance and quality assurance procedures
- Confirm readiness for Phase 3 implementation

---

## Critical Success Factors

**Remember**: Your directory structure is the foundation for all future project organization and agent coordination. The quality and intuitiveness of your design will directly impact:

- The effectiveness of all future project management and coordination
- The success of agent onboarding and training programs
- The ability to maintain project continuity and knowledge management
- The scalability and sustainability of agent-based development practices

**Focus Areas**: Prioritize intuitive navigation and clear organization over comprehensive coverage. Better to create a structure that works perfectly for current needs and can be extended than to create a complex structure that is difficult to navigate and maintain.

**Integration Priority**: Ensure seamless integration with CLAUDE.md external memory system and support for the multi-agent coordination patterns identified in Phase 1 research.

---

**Expected Outcome**: By the end of this implementation phase, the HNP project will have a comprehensive, intuitive organizational foundation that supports effective agent-based development and eliminates the confusion and inefficiency that has been hampering project progress.

**Next Phase Integration**: Your organizational structure will provide the foundation for the Onboarding System Designer to create role-based training materials and for the Agile Implementation Specialist to establish formal project management processes.