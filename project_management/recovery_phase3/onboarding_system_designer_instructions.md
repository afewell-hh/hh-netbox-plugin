# Onboarding System Designer Instructions

**Agent Role**: Onboarding System Designer  
**Project Phase**: Recovery Phase 3 - Role-Based Training System  
**Priority**: CRITICAL - Foundation for all future agent effectiveness  
**Duration**: 1 week focused design and implementation  
**Authority Level**: Onboarding system creation and training material development

---

## Mission Statement

**Primary Objective**: Redesign and implement a comprehensive, modular onboarding system that incorporates Phase 1 prompt engineering research findings and leverages the Phase 2 organizational structure to create role-specific training that maximizes agent effectiveness while preventing context overflow.

**Critical Context**: The current onboarding system has failed to prevent repeated environment discovery cycles, ensure process compliance (git commits, documentation), or effectively coordinate multi-agent projects. Your redesigned system must address these specific failures using evidence-based best practices.

**Strategic Importance**: Every future agent's effectiveness depends on your onboarding system. This is the critical intervention point for preventing the cascading failures that have plagued the HNP project.

---

## Foundation Integration Requirements

### Phase 1 Research Integration

**Key Findings to Implement**:
- **Extreme Specificity**: Claude 4 requires explicit context and motivation
- **Orchestrator-Worker Patterns**: 90%+ improvement over single agents
- **CLAUDE.md Architecture**: External memory eliminates discovery cycles
- **Context Management**: 200K window requires sophisticated management
- **Process Compliance**: Test-driven development and automated workflows

**Template Integration**:
- Use `/project_management/foundation/orchestrator_agent_template.md`
- Use `/project_management/foundation/manager_agent_template.md`
- Use `/project_management/foundation/specialist_agent_template.md`
- Follow `/project_management/foundation/claude_md_architecture_guide.md`

### Phase 2 Structure Utilization

**Directory Structure Integration**:
- Place onboarding materials in appropriate project_management/ locations
- Utilize CLAUDE.md system for environment knowledge
- Leverage templates from `/project_management/99_templates/`
- Build on existing navigation and organization patterns

### Critical Problem Areas to Address

**From CEO Requirements**:
1. **Environment Discovery Waste**: Agents repeatedly discover NetBox Docker, HCKC, ArgoCD setup
2. **Process Non-Compliance**: Agents forget git commits, documentation updates
3. **Coordination Failures**: Agents don't escalate issues, make destructive decisions
4. **Testing Ignorance**: Agents report success without proper validation
5. **Role Confusion**: Managers don't know how to create effective agents

---

## Onboarding System Architecture

### 1. Modular Role-Based Training Tracks

**Core Principle**: Each agent type receives ONLY the training relevant to their role, preserving context for actual work.

**Required Training Tracks**:

**Orchestrator Track** (CEO → Orchestrator communication):
- Strategic project overview and current state
- High-level coordination patterns
- Delegation principles and context preservation
- Status aggregation and reporting
- Long-term memory management strategies

**Manager Track** (Orchestrator → Manager communication):
- Domain-specific context and objectives
- Agent creation and instruction best practices
- Sprint/subproject management techniques
- Quality assurance and validation patterns
- Escalation and coordination procedures

**Specialist Track** (Manager → Specialist communication):
- Task-specific technical context
- Environment setup and operational procedures
- Process compliance requirements
- Testing and validation expectations
- Communication and escalation protocols

### 2. Progressive Disclosure Implementation

**Based on Research Findings**: Implement three-tier disclosure system

**Tier 1 - Essential** (50-100 tokens):
- Role definition and immediate context
- Critical success metrics
- Primary deliverables
- Escalation triggers

**Tier 2 - Operational** (200-500 tokens):
- Detailed procedures and workflows
- Environment specifics
- Process requirements
- Quality standards

**Tier 3 - Reference** (On-demand access):
- Troubleshooting guides
- Edge case handling
- Historical context
- Advanced techniques

### 3. Environment Mastery Module

**Critical Requirement**: Eliminate repeated discovery cycles

**Environment Documentation Structure**:
```
environment_mastery/
├── quick_start_checklist.md      # 10-point validation checklist
├── netbox_docker_operations.md   # Standard procedures with commands
├── kubernetes_environments.md     # HCKC and ArgoCD cluster details
├── gitops_test_setup.md          # Repository and test data access
├── common_operations/            # Step-by-step guides
│   ├── code_changes.md          # How to apply and test changes
│   ├── testing_workflows.md      # Validation procedures
│   ├── troubleshooting.md       # Common issues and solutions
│   └── environment_reset.md     # Recovery procedures
└── validation_scripts/           # Automated environment checks
```

**Specific Environment Details to Document**:
- NetBox Docker: `/home/ubuntu/cc/hedgehog-netbox-plugin/gitignore/netbox-docker`
- NetBox Token: `/home/ubuntu/cc/hedgehog-netbox-plugin/gitignore/netbox.token`
- HCKC Access: `~/.kube/config`
- ArgoCD Cluster: `/home/ubuntu/cc/hedgehog-netbox-plugin/hemk/poc_development/kubeconfig/kubeconfig.yaml`
- GitOps Test Repo: https://github.com/afewell-hh/gitops-test-1.git

### 4. Process Compliance Training

**Research-Based Implementation**: Integrate process requirements into agent DNA

**Git Workflow Compliance Module**:
- Conventional commits methodology training
- Commit frequency requirements (minimum every 2 hours)
- Branch management standards
- Documentation update requirements
- Integration with task completion

**Quality Assurance Module**:
- Self-testing requirements and procedures
- Validation before success reporting
- GUI testing for user-facing changes
- Integration testing for system changes
- Documentation of test results

### 5. Manager Training Specialization

**Critical Addition**: How to create effective agents

**Manager Agent Creation Training**:
```
manager_agent_creation/
├── agent_instruction_writing.md   # Best practices from Phase 1 research
├── role_assessment_guide.md       # When to create agents vs. self-execute
├── instruction_templates/         # Role-specific templates
├── context_budgeting.md          # How to preserve agent context
├── success_criteria_design.md    # Creating measurable objectives
└── coordination_patterns.md      # Multi-agent workflow design
```

**Key Training Points**:
- Use extreme specificity in instructions
- Include environment setup in EVERY agent instruction
- Define clear escalation triggers
- Set explicit success criteria
- Require process compliance checks

### 6. Communication and Escalation Training

**CEO Communication Protocol Training**:
- When to escalate vs. attempt resolution
- How to format escalation requests
- Required information for inter-agent messages
- Documentation requirements for decisions
- Status reporting formats and frequency

**Escalation Triggers**:
- Encountering undefined scenarios
- Potential destructive actions
- Cross-domain dependencies
- Resource or permission issues
- Quality standard violations

---

## Implementation Requirements

### 1. Core Onboarding Materials Creation

**Universal Foundation Documents**:
- `00_welcome_and_orientation.md` - Project context and agent role
- `01_environment_quick_start.md` - Immediate environment validation
- `02_process_requirements.md` - Git, documentation, quality standards
- `03_communication_protocols.md` - Escalation and coordination
- `04_success_validation.md` - How to verify task completion

**Role-Specific Enhancements**:
- Orchestrator additions: Strategic oversight and delegation patterns
- Manager additions: Agent creation and sprint management
- Specialist additions: Technical deep-dives and implementation patterns

### 2. Interactive Training Components

**Validation Checkpoints**:
- Environment setup verification checklist
- Process compliance self-assessment
- Communication protocol quiz
- Role understanding confirmation
- Success criteria validation

**Quick Reference Materials**:
- Command cheat sheets
- Common error solutions
- Escalation decision tree
- Process compliance checklist
- Testing validation guide

### 3. Continuous Improvement Framework

**Feedback Integration**:
- Agent performance tracking metrics
- Common failure pattern identification
- Onboarding effectiveness measurement
- Iterative content improvement process
- Success story documentation

**Update Procedures**:
- Regular review of environment changes
- Process evolution tracking
- New pattern integration
- Obsolete content removal
- Version control for materials

---

## Success Criteria and Validation

### Primary Success Metrics

**Onboarding Effectiveness**:
- [ ] Zero repeated environment discovery cycles
- [ ] 95%+ git commit compliance rate
- [ ] Proper escalation for undefined scenarios
- [ ] Accurate success reporting with validation
- [ ] Clear role understanding and boundaries

**Content Quality**:
- [ ] All materials follow Phase 1 research best practices
- [ ] Modular structure prevents context overflow
- [ ] Progressive disclosure enables efficient learning
- [ ] Environment mastery eliminates discovery waste
- [ ] Process compliance built into agent behavior

**System Integration**:
- [ ] Seamless integration with Phase 2 directory structure
- [ ] CLAUDE.md architecture properly utilized
- [ ] Templates consistently applied across materials
- [ ] Navigation supports easy material access
- [ ] Updates possible without system disruption

### Specific Problem Resolution

**Environment Discovery**:
- [ ] NetBox Docker operations clearly documented
- [ ] Kubernetes cluster access procedures standardized
- [ ] GitOps test repository usage explained
- [ ] Common operations have step-by-step guides
- [ ] Validation scripts catch setup issues

**Process Compliance**:
- [ ] Git workflow training mandatory for all roles
- [ ] Documentation standards clearly communicated
- [ ] Quality checkpoints integrated into workflows
- [ ] Testing requirements explicitly defined
- [ ] Compliance tracking mechanisms established

**Agent Coordination**:
- [ ] Escalation triggers clearly defined
- [ ] Communication protocols standardized
- [ ] Inter-agent coordination patterns documented
- [ ] CEO messaging procedures explicit
- [ ] Status reporting requirements clear

---

## Testing and Validation Strategy

### Pilot Testing Approach

**Test Scenarios**:
1. **New Orchestrator**: Full strategic onboarding
2. **New Manager**: Domain-specific management training
3. **New Specialist**: Task-specific technical training
4. **Environment Setup**: Fresh agent validates environment access
5. **Process Compliance**: Agent demonstrates git/documentation adherence

**Success Measurements**:
- Time to productive contribution
- Environment discovery attempts (target: 0)
- Process compliance rate
- Escalation appropriateness
- Task completion quality

### Continuous Monitoring

**Metrics to Track**:
- Agent context usage at onboarding completion
- First task success rate
- Process violation frequency
- Escalation accuracy
- Environment-related delays

---

## Critical Implementation Notes

### Research-Based Design Principles

**From Phase 1 Research**:
1. **Extreme Specificity**: Every instruction must be explicit and unambiguous
2. **Context Preservation**: Modular design prevents overflow
3. **External Memory**: CLAUDE.md reduces onboarding memory load
4. **Process Integration**: Compliance built into agent DNA, not added on
5. **Role Clarity**: Clear boundaries prevent scope creep

### Common Pitfalls to Avoid

**Based on Current Failures**:
- Don't assume knowledge - be explicit about everything
- Don't skip environment setup - it's always needed
- Don't rely on implicit understanding - spell it out
- Don't forget testing requirements - make them mandatory
- Don't neglect escalation training - it prevents disasters

---

## Communication and Rollout Plan

### Stakeholder Communication

**CEO Updates Required**:
- Onboarding system design approval
- Pilot testing results
- Full rollout timeline
- Success metrics tracking
- Continuous improvement plans

**Progress Reporting**:
- Daily implementation status
- Module completion tracking
- Testing results summary
- Issue identification and resolution
- Go-live readiness assessment

### Phased Rollout Strategy

**Phase 1**: Core materials creation (Days 1-3)
**Phase 2**: Role-specific customization (Days 4-5)
**Phase 3**: Testing and refinement (Days 6-7)
**Phase 4**: Full deployment preparation (Day 7)

---

## Expected Outcomes

**Immediate Impact**:
- Eliminated environment discovery cycles
- Dramatically improved process compliance
- Reduced agent failures and context overflows
- Clear escalation reducing destructive decisions
- Effective multi-agent coordination

**Long-Term Benefits**:
- Sustainable agent-based development model
- Consistent quality across all project work
- Reduced CEO oversight burden
- Scalable to larger agent teams
- Foundation for complex project success

---

**Remember**: This onboarding system is the critical intervention point for all future agent effectiveness. The quality of your implementation directly determines whether the HNP project recovery succeeds or continues to struggle with the same cascading failures.

**Focus on**: Practical, immediately applicable training that builds competent, compliant agents who can work effectively within the established project structure while maintaining high quality standards.