# Architecture Navigation Training - Level 1 (Mandatory)

**CRITICAL MISSION**: Ensure all agents can efficiently navigate centralized architectural documentation, eliminating the documentation discovery chaos that previously caused 255+ scattered documents.

## 🎯 Training Objectives

**PRIMARY COMPETENCY**: Navigate from `/architecture_specifications/CLAUDE.md` to any specific technical detail within 2 minutes.

**SECONDARY COMPETENCIES**:
- Locate architectural decisions (ADRs) relevant to assigned work
- Access current system architecture before making changes  
- Find GitOps specifications for coordination requirements
- Understand documentation structure and cross-reference system

## 📚 Core Navigation Skills

### Skill 1: Architecture Entry Point Mastery
**START LOCATION**: Always begin at `/architecture_specifications/CLAUDE.md`

**CRITICAL UNDERSTANDING**:
```markdown
architecture_specifications/CLAUDE.md serves as the master index for ALL architectural information.

NEVER start architectural research anywhere else.
NEVER create documentation outside this centralized structure.
```

**Navigation Pattern**:
1. **Read Master Context**: `/architecture_specifications/CLAUDE.md` provides high-level overview
2. **Follow Navigation Map**: Use the directory structure guide to locate specific areas
3. **Use Cross-References**: Follow @references to related specifications
4. **Verify Current Status**: Check implementation evidence and operational status

### Skill 2: Architectural Decision Lookup
**LOCATION**: `/architecture_specifications/01_architectural_decisions/`

**CRITICAL PROCESS**:
1. **Check Decision Log**: `/01_architectural_decisions/decision_log.md`
2. **Review Relevant ADRs**: Navigate to specific decision documents
3. **Understand Context**: Review rationale and implications
4. **Check Implementation Status**: Verify if decision is approved/implemented

**Example Navigation**:
```markdown
Task: Implement new GitOps repository integration
Navigation Path:
1. Start: /architecture_specifications/CLAUDE.md
2. Navigate: @01_architectural_decisions/decision_log.md
3. Find: ADR-003: Repository Separation Design
4. Review: @01_architectural_decisions/active_decisions/ADR-003-repository-separation.md
5. Understand: Multi-fabric authentication requirements
```

### Skill 3: Current System Architecture Access
**LOCATION**: `/architecture_specifications/00_current_architecture/`

**MANDATORY PRE-WORK PROCESS**:
Before making ANY technical changes:
1. **System Overview**: Read `/00_current_architecture/system_overview.md`
2. **Component Understanding**: Navigate to relevant component specifications
3. **Integration Points**: Review how your changes affect existing systems
4. **Operational Status**: Verify current system state and health

**Component Navigation Map**:
```markdown
Kubernetes Work → /00_current_architecture/component_architecture/kubernetes_integration.md
NetBox Plugin → /00_current_architecture/component_architecture/netbox_plugin_layer.md  
GitOps Changes → /00_current_architecture/component_architecture/gitops/gitops_overview.md
```

### Skill 4: GitOps Specification Access
**LOCATION**: `/architecture_specifications/00_current_architecture/component_architecture/gitops/`

**COORDINATION REQUIREMENTS**:
For any GitOps-related work:
1. **GitOps Overview**: Start with `gitops_overview.md`
2. **Directory Management**: Review `directory_management_specification.md`
3. **Drift Detection**: Understand `drift_detection_design.md`
4. **Repository Structure**: Access repository-specific requirements

## 🧭 Navigation Exercises

### Exercise 1: Architecture Context Discovery
**Scenario**: You need to understand the current NetBox plugin architecture.

**Required Navigation Path**:
1. Start: `/architecture_specifications/CLAUDE.md`
2. Navigate: Look for "NetBox Plugin Layer" reference
3. Follow: @00_current_architecture/component_architecture/netbox_plugin_layer.md
4. Understand: Django plugin architecture and integration patterns

**Success Criteria**: Complete navigation and summarize plugin architecture in <2 minutes.

### Exercise 2: Architectural Decision Research
**Scenario**: You need to implement repository authentication changes.

**Required Navigation Path**:
1. Start: `/architecture_specifications/CLAUDE.md`
2. Navigate: @01_architectural_decisions/decision_log.md
3. Search: Repository authentication decisions
4. Review: Relevant ADRs and their implications
5. Understand: Authentication design requirements

**Success Criteria**: Locate and understand relevant architectural decisions in <3 minutes.

### Exercise 3: Change Impact Analysis
**Scenario**: You need to modify GitOps drift detection behavior.

**Required Navigation Path**:
1. Start: `/architecture_specifications/CLAUDE.md`
2. Navigate: @00_current_architecture/component_architecture/gitops/
3. Review: `drift_detection_design.md`
4. Cross-reference: Related system components
5. Identify: Potential impact points

**Success Criteria**: Complete impact analysis using centralized documentation in <5 minutes.

## ⚠️ Critical Navigation Rules

### Rule 1: NEVER Skip Architecture Review
**VIOLATION CONSEQUENCES**:
- Changes made without architectural context cause regressions
- Documentation scatter when agents create specs outside centralized structure
- Lost design decisions when architectural implications ignored

**COMPLIANCE REQUIREMENT**: Always review relevant architecture documentation before beginning technical work.

### Rule 2: ALWAYS Use Centralized Documentation
**FORBIDDEN PRACTICES**:
- Creating architectural documentation outside `/architecture_specifications/`
- Relying on scattered documentation or outdated specifications
- Making assumptions about system architecture without verification

**COMPLIANCE REQUIREMENT**: Use only centralized documentation and update it appropriately.

### Rule 3: Follow Cross-Reference System
**NAVIGATION PATTERN**:
- Use @references to navigate between related specifications
- Maintain awareness of cross-component implications
- Update cross-references when making architectural changes

**COMPLIANCE REQUIREMENT**: Follow established cross-reference patterns for navigation.

## 🔍 Validation Tests

### Test 1: Speed Navigation
**Challenge**: Navigate from CLAUDE.md to specific GitOps drift detection design in <90 seconds.
**Pass Criteria**: Successful navigation with understanding of drift detection patterns.
**Failure Action**: Repeat navigation exercises until automatic.

### Test 2: Architecture Context
**Challenge**: Explain current system architecture based on centralized documentation.
**Pass Criteria**: Accurate system description using only centralized specifications.
**Failure Action**: Review system overview and component architecture documentation.

### Test 3: Decision Awareness
**Challenge**: Identify architectural decisions relevant to assigned technical work.
**Pass Criteria**: Correct identification and understanding of relevant ADRs.
**Failure Action**: Practice decision log navigation and ADR review process.

## 📊 Mastery Evidence

### Navigation Competency Indicators
- **Sub-2-minute Navigation**: Reach any specification from CLAUDE.md entry point
- **Cross-Reference Fluency**: Follow @references seamlessly between specifications
- **Decision Awareness**: Identify relevant ADRs for assigned work automatically
- **System Context**: Understand current architecture before making changes

### Compliance Behavior Indicators
- **Centralized Documentation Usage**: Never creates scattered architectural documents
- **Architecture-First Approach**: Reviews specifications before beginning technical work
- **Cross-Component Awareness**: Considers architectural implications across system
- **Proper Navigation Patterns**: Uses established entry points and reference system

## 🚀 Advanced Navigation Skills

### Skill Enhancement: Multi-Component Navigation
For complex changes affecting multiple system components:
1. **System Map Creation**: Identify all affected components
2. **Cross-Reference Following**: Navigate between related specifications
3. **Impact Matrix Development**: Map changes across component boundaries
4. **Coordination Requirements**: Identify architectural coordination needs

### Skill Enhancement: Architecture Evolution Tracking
For understanding system evolution:
1. **Historical Context**: Review ADR timeline and implementation history
2. **Current State Verification**: Confirm current operational status
3. **Future Direction**: Understand planned architectural evolution
4. **Change Readiness**: Assess architecture readiness for planned changes

## ⚡ Quick Reference Guide

### Essential Navigation Commands
```markdown
Architecture Entry Point: /architecture_specifications/CLAUDE.md
System Overview: @00_current_architecture/system_overview.md
Decisions Log: @01_architectural_decisions/decision_log.md
GitOps Specs: @00_current_architecture/component_architecture/gitops/
```

### Common Navigation Patterns
```markdown
Feature Work: CLAUDE.md → Current Architecture → Component Specs → ADRs
Bug Fixing: CLAUDE.md → System Overview → Component Details → Implementation Evidence
Integration: CLAUDE.md → Multiple Components → Cross-References → Coordination Requirements
```

**ARCHITECTURE NAVIGATION TRAINING COMPLETE**: Agent can efficiently navigate centralized architectural documentation preventing reliance on scattered or outdated specifications.