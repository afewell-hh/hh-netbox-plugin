# Quick Reference Checklist - Claude Agent Instructions

**Purpose**: Immediate reference for creating and optimizing Claude agent instructions  
**Usage**: Copy-paste templates and validation checklists for rapid deployment

---

## Agent Instruction Creation Checklist

### ✅ Claude 4 Optimization Requirements
- [ ] **Extreme Specificity**: Instructions are detailed with explicit context and motivation
- [ ] **Role Definition**: Clear agent type (Orchestrator/Manager/Specialist) with authority level
- [ ] **Context Import**: CLAUDE.md files referenced with @import syntax
- [ ] **Extended Thinking**: Complex tasks include "use extended thinking" directive
- [ ] **Performance Modifiers**: Include phrases like "Go beyond the basics", "Include thoughtful details"
- [ ] **Examples Included**: 3-5 diverse examples showing expected output patterns

### ✅ Context Management Requirements  
- [ ] **Context Window Awareness**: Instructions include context monitoring directive
- [ ] **External Memory Integration**: MCP memory system referenced for persistence
- [ ] **Progressive Disclosure**: Information organized in Level 0/1/2 hierarchy
- [ ] **Import Strategy**: Specific CLAUDE.md files imported for domain context
- [ ] **Context Preservation**: "As established previously" patterns for efficiency

### ✅ Multi-Agent Coordination
- [ ] **Clear Hierarchy**: Orchestrator → Manager → Specialist chain defined
- [ ] **Task Boundaries**: Non-overlapping responsibilities clearly specified
- [ ] **Parallel Execution**: Direction to use Task tool for simultaneous operations  
- [ ] **Communication Protocol**: All coordination flows through orchestrator
- [ ] **Escalation Paths**: Clear protocols for handling blockers and conflicts

### ✅ Process Compliance Integration
- [ ] **Git Workflow**: Feature branch → test → PR → merge process required
- [ ] **Testing Requirements**: TDD with 80%+ coverage specified
- [ ] **Quality Gates**: All tests pass, documentation updated, performance validated
- [ ] **Documentation Standards**: API docs, user guides, code comments required
- [ ] **Review Process**: Code review and approval gates specified

### ✅ HNP-Specific Requirements
- [ ] **Environment Knowledge**: NetBox Docker, HCKC cluster, ArgoCD context included
- [ ] **Technical Stack**: Django 4.2, NetBox 4.3.3, Kubernetes, Bootstrap 5 specified
- [ ] **CRD Context**: 12 CRD types (VPC API + Wiring API) referenced
- [ ] **Integration Points**: Kubernetes connectivity, GitOps workflows included
- [ ] **Project Status**: MVP complete, current development phase specified

---

## Role-Specific Quick Templates

### Orchestrator Agent - Essential Elements
```markdown
**Agent Type**: Project Orchestrator (Claude Opus 4)
**Mission**: [Specific project coordination objective]
**Authority**: Full project coordination and resource allocation

**Immediate Context**:
@project_management/CLAUDE.md
@netbox_hedgehog/CLAUDE.md  
@project_management/environment/CLAUDE.md

**Core Workflow**:
1. Use extended thinking for complex task analysis
2. Spawn 3-5 specialized subagents with focused contexts
3. Monitor progress through regular checkpoints
4. Integrate results and validate system-wide quality

**Success Criteria**: [Specific measurable outcomes]
```

### Manager Agent - Essential Elements
```markdown
**Agent Type**: [Feature] Manager (Claude Sonnet 4)
**Feature Area**: [Specific domain - GitOps/UI/API/Backend]
**Authority**: Feature-level development with git privileges

**Team**: [3-4 specialist agents reporting]
**Context**: @netbox_hedgehog/[feature_area]/CLAUDE.md

**Key Responsibilities**:
- Feature implementation coordination
- Specialist agent task delegation  
- Cross-functional integration management
- Quality assurance and delivery accountability

**Process Requirements**: Feature branch → TDD → integration testing → PR → review
```

### Specialist Agent - Essential Elements
```markdown
**Agent Type**: [Domain] Specialist (Claude Sonnet 4)
**Technical Domain**: [Models/API/Frontend/Integration]
**Code Scope**: [Specific files and functions]

**Context**: @netbox_hedgehog/[domain]/CLAUDE.md

**Implementation Requirements**:
- TDD with 80%+ test coverage
- PEP 8 compliance with type hints
- Django/NetBox pattern adherence
- Comprehensive error handling

**Deliverables**: Code + tests + documentation + performance validation
```

---

## Context Management Quick Setup

### CLAUDE.md File Creation Order
1. **Root**: `/hedgehog-netbox-plugin/CLAUDE.md` (25 lines max)
2. **Plugin**: `/netbox_hedgehog/CLAUDE.md` (50 lines max)  
3. **Environment**: `/project_management/environment/CLAUDE.md` (60 lines max)
4. **Components**: Domain-specific files (40 lines max each)

### Essential Content Templates

#### Root CLAUDE.md Template (25 lines)
```markdown
# [Project Name] - Overview
**Mission**: [One sentence project purpose]
**Status**: [Current development phase and key achievements]  
**Stack**: [Primary technologies - Django, NetBox, Kubernetes, etc.]

## Environment
- [Development setup - Docker, cluster, database]
- [Integration points - external systems]

## Current State  
- ✅ [Key completed capabilities]
- ✅ [Major features operational]
- 🚧 [Current development focus]

## Context Imports
@project_management/CLAUDE.md
@[main_component]/CLAUDE.md
```

#### Component CLAUDE.md Template (40 lines)
```markdown
# [Component] - Implementation Details
**Purpose**: [Component responsibility and scope]
**Architecture**: [Technical architecture and patterns]

## Key Features
- [Primary capability 1 with technical details]
- [Primary capability 2 with technical details]
- [Primary capability 3 with technical details]

## Implementation Patterns
- [Code organization and conventions]
- [Data models and relationships]  
- [API design and validation]
- [Testing and quality assurance]

## Integration Points
- [External system connections]
- [Internal component dependencies]
- [Data flow and communication patterns]

## Development Context
- [File structure and organization]
- [Key configuration and settings]
- [Performance and scalability considerations]

## Import Specialized Context
@[subdomain1]/CLAUDE.md
@[subdomain2]/CLAUDE.md
```

---

## Common Instruction Patterns

### Extended Thinking Trigger Phrases
- "Think deeply about this implementation before beginning"
- "Use extended thinking to analyze the requirements and approach"
- "Consider all implications and edge cases before proceeding"
- "Develop a comprehensive strategy using extended thinking"

### Parallel Execution Directives
- "Use the Task tool to spawn multiple agents simultaneously"
- "Deploy [3-5] specialized agents with focused, non-overlapping responsibilities"
- "Execute these operations in parallel rather than sequentially"
- "Coordinate multiple agents through the orchestrator rather than direct communication"

### Quality Gate Integration
- "All existing tests must continue passing before proceeding"
- "New functionality requires comprehensive test coverage (80%+)"
- "Update documentation for all user-facing changes"
- "Validate performance impact and optimize if necessary"
- "Conduct security review and address any findings"

### Error Prevention Patterns
- "When uncertain about system behavior, request clarification rather than assuming"
- "Implement graceful fallbacks for edge cases and error conditions"
- "Use database transactions for multi-step operations to ensure consistency"
- "Validate preconditions before performing operations"
- "Escalate to human oversight for high-risk operations"

---

## Validation and Testing Quick Checks

### Agent Effectiveness Test
```markdown
**5-Minute Agent Test**:
1. Launch agent with new instructions
2. Give simple task related to project
3. Observe: Does agent ask for environment details? (FAIL if yes)
4. Observe: Does agent use correct technical patterns? (FAIL if no)
5. Observe: Does agent follow established processes? (FAIL if no)

**Success Criteria**: Agent starts work immediately with correct context
```

### Context Efficiency Check
```markdown
**Context Usage Validation**:
1. Monitor agent context consumption during task
2. Check for redundant information requests
3. Validate agent memory of previous context  
4. Confirm agent uses appropriate technical vocabulary
5. Verify agent follows project conventions without reminders

**Optimization Triggers**: 
- Agent asks for information available in CLAUDE.md files
- Agent repeats questions about environment or architecture
- Agent uses incorrect patterns or conventions
- Agent fails to follow established processes
```

### Multi-Agent Coordination Test
```markdown
**Coordination Effectiveness Check**:
1. Deploy orchestrator with complex task requiring multiple agents
2. Observe task decomposition and agent spawning strategy
3. Monitor inter-agent coordination and information flow
4. Validate integration of specialist agent outputs
5. Confirm quality gates are enforced before completion

**Red Flags**:
- Direct agent-to-agent communication
- Overlapping or conflicting agent assignments
- Poor integration of specialist outputs
- Quality gates bypassed or ignored
```

---

## Emergency Fixes and Optimizations

### Context Overflow Emergency Protocol
```markdown
**When Agent Hits Context Limits**:
1. Use `/compact` command immediately
2. Store essential decisions in external memory
3. Spawn fresh subagent with focused context
4. Transfer only critical information for continuity
5. Update CLAUDE.md files with lessons learned
```

### Agent Ineffectiveness Quick Fixes
```markdown
**When Agent Struggles**:
1. Add more specific examples to instructions
2. Include explicit motivation and context for requirements
3. Reduce cognitive load by breaking task into smaller pieces
4. Provide more detailed technical context about environment
5. Use extended thinking directive for complex analysis
```

### Process Compliance Enforcement
```markdown
**When Agent Skips Process Steps**:
1. Add explicit quality gates to instructions
2. Include specific testing requirements with examples
3. Mandate documentation updates with templates
4. Require status reporting at defined checkpoints
5. Add escalation protocols for process violations  
```

---

This quick reference provides immediate, actionable guidance for creating effective Claude agent instructions that solve HNP's specific challenges while following latest best practices.