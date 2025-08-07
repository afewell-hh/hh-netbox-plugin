# Content Categorization Matrix
**Analysis Date**: July 31, 2025  
**Purpose**: Detailed mapping of Universal vs Role-Specific content for neutral CLAUDE.md design

## Categorization Framework

### Classification Criteria

**UNIVERSAL Content**:
- Applies to all agent types regardless of role
- Enhances effectiveness without role confusion
- Provides factual project context and technical tools
- Contains no coordination or management instructions

**ROLE-SPECIFIC Content**:
- Designed for specific agent roles (primarily QAPM)
- Contains coordination, management, or oversight instructions
- Would create confusion or inappropriate behavior in sub-agents
- Requires specific authority levels or coordination responsibilities

## Detailed Content Matrix

| Line Range | Section | Category | Confidence | Rationale | Risk Level |
|------------|---------|----------|------------|-----------|------------|
| 1-7 | Project Header | UNIVERSAL | High | Basic project identification needed by all agents | None |
| 11-37 | Tech Stack | UNIVERSAL | High | Technical specifications required by all technical agents | None |
| 40-65 | Development Commands | UNIVERSAL | High | Factual commands usable by all technical agents | None |
| 66-77 | Production Operations | UNIVERSAL | Medium | Basic operational commands, may need role context | Low |
| 79-113 | Code Standards | UNIVERSAL | High | Technical standards apply to all code-generating agents | None |
| 116-121 | File Organization (Basic) | UNIVERSAL | High | Project structure understanding needed by all | None |
| 123-137 | Git Workflow (Basic) | UNIVERSAL | High | Standard development practices | None |
| 138-144 | Testing Requirements | UNIVERSAL | Medium | May be too comprehensive for some agent types | Low |
| 146-180 | Project Structure | UNIVERSAL | High | Architectural understanding needed by all | None |
| **182-210** | **QAPM Methodology** | **ROLE-SPECIFIC** | **High** | **Four-phase approach designed for QAPM coordination** | **High** |
| **212-248** | **Agent Orchestration** | **ROLE-SPECIFIC** | **High** | **Agent spawning and coordination framework** | **High** |
| **251-295** | **QAPM File Organization** | **ROLE-SPECIFIC** | **High** | **Workspace management for QAPM coordination** | **High** |
| **297-339** | **Evidence Framework** | **ROLE-SPECIFIC** | **Medium** | **Comprehensive validation system for coordination** | **Medium** |
| **341-405** | **Agent Success Framework** | **ROLE-SPECIFIC** | **High** | **Instructions for creating agent instructions** | **High** |
| **407-435** | **Quality Gates** | **ROLE-SPECIFIC** | **High** | **Multi-level coordination quality management** | **High** |
| **437-477** | **Foundation Standards** | **ROLE-SPECIFIC** | **Medium** | **Despite name, contains coordination and escalation** | **Medium** |
| 479-506 | HNP Context | UNIVERSAL | High | Project-specific technical context for all agents | None |
| **508-530** | **Performance Optimization** | **ROLE-SPECIFIC** | **Medium** | **Agent behavior and coordination optimization** | **Medium** |

## Universal Content Extraction (187 lines, ~35%)

### Section 1: Project Foundation (Lines 1-37)
```markdown
# NetBox Hedgehog Plugin Technical Context
**Project**: NetBox Hedgehog Plugin (HNP) - Self-service Kubernetes CRD management via NetBox  
**Status**: Production Ready - MVP Complete with 12 CRD types operational  
**Architecture**: NetBox 4.3.3 Django plugin with GitOps integration

## Tech Stack
- **NetBox**: 4.3.3 (Django-based network management)
- **Python**: 3.9+ with Django 4.2.x
- **Kubernetes**: Client integration for CRD management
[Full tech stack details...]
```

### Section 2: Development Tools (Lines 40-77)
```bash
# Environment setup
source venv/bin/activate
pip install -r requirements.txt

# Testing and validation
python -m pytest
python -m pytest --cov=netbox_hedgehog
[Full command reference...]
```

### Section 3: Code Standards (Lines 79-121)
```python
# Python Standards
- Import Style: Use explicit imports
- Function Naming: snake_case
- Class Naming: PascalCase
[Full standards reference...]
```

### Section 4: Project Structure (Lines 146-180, 479-506)
```
netbox_hedgehog/
├── models/           # Django model definitions
├── views/           # HTTP request handlers
└── templates/       # HTML templates
[Full structure + HNP context...]
```

## Role-Specific Content Analysis (343 lines, ~65%)

### High-Risk Role Confusion Content

#### Agent Orchestration Framework (Lines 212-248)
**Risk**: Technical specialists would attempt to spawn other agents
**Evidence**: "When determining which specialist agent to spawn"
**Impact**: Sub-agents exceeding intended scope

#### QAPM Methodology (Lines 182-210)
**Risk**: Technical agents implementing full four-phase methodology
**Evidence**: "Phase 1: Problem Systematization (25% effort)"
**Impact**: Massive process overhead for simple technical tasks

#### Agent Success Framework (Lines 341-405)
**Risk**: Sub-agents creating instructions for other agents
**Evidence**: "Every agent instruction must begin with"
**Impact**: Inappropriate authority assumption and coordination attempts

### Medium-Risk Areas

#### Evidence Framework (Lines 297-339)
**Risk**: Over-documentation instead of focused implementation
**Evidence**: "Five-Category Evidence System"
**Impact**: Technical agents spending excessive time on documentation

#### Quality Gates (Lines 407-435)
**Risk**: Implementing unnecessary validation layers
**Evidence**: "Three-Level Quality Validation System"
**Impact**: Simple tasks becoming complex coordination exercises

## Separation Strategy

### Universal Content Structure
1. **Project Foundation**: Essential technical context
2. **Development Tools**: Commands and workflow basics
3. **Code Standards**: Technical implementation guidelines
4. **Project Architecture**: Structure and integration points

### Role-Specific Relocation
1. **QAPM Methodology** → `/project_management/qapm_methodology/`
2. **Agent Orchestration** → `/project_management/agent_coordination/`
3. **Quality Systems** → `/project_management/quality_frameworks/`
4. **Performance Optimization** → `/project_management/optimization_guides/`

## Validation Criteria

### Universal Content Validation
- [ ] No coordination or management instructions
- [ ] No agent spawning or orchestration references
- [ ] No QAPM-specific methodology requirements
- [ ] Enhances all agent types equally
- [ ] Contains only factual project context and technical tools

### Role-Specific Content Validation
- [ ] Requires specific coordination authority
- [ ] Contains management or oversight instructions
- [ ] References other agent types or coordination
- [ ] Designed for specific methodological approaches
- [ ] Would confuse or misdirect technical specialists

## Implementation Recommendations

1. **Extract Universal Core**: Create neutral CLAUDE.md with universal content only
2. **Relocate Role-Specific**: Move QAPM content to appropriate methodology documentation
3. **Test Neutrality**: Validate with different agent types to ensure clarity
4. **Maintain Links**: Ensure QAPM agents can still access methodology documentation
5. **Version Control**: Implement gradual transition to prevent workflow disruption

This matrix provides the detailed foundation for implementing effective content separation.