# Agent Instruction File Management Templates

**Purpose**: Standardized templates for including file management requirements in all agent instructions  
**Version**: 1.0  
**Created**: July 30, 2025  
**Usage**: MANDATORY inclusion in all QAPM agent spawning instructions

## Overview

These templates ensure every spawned agent receives comprehensive file management requirements, preventing file scattering and maintaining repository organization. All QAPMs MUST use these templates when creating agent instructions.

## Universal File Management Section

**MANDATORY SECTION** (Include in every agent instruction):

```markdown
## FILE MANAGEMENT REQUIREMENTS

### WORKSPACE LOCATION
Primary workspace: /project_management/07_qapm_workspaces/[PROJECT_NAME]/

### ABSOLUTE PROHIBITIONS
- NEVER create files in repository root without explicit justification and QAPM approval
- NEVER scatter files outside designated workspace or appropriate centralized directories
- NEVER leave temporary files uncommitted to git without proper .gitignore
- NEVER create debug scripts outside designated temporary directories

### REQUIRED FILE LOCATIONS BY TYPE
- Investigation outputs → [workspace]/01_problem_analysis/
- Process documentation → [workspace]/02_process_design/
- Implementation evidence → [workspace]/04_evidence_collection/implementation_evidence/
- Test results → [workspace]/04_evidence_collection/test_results/
- Debug scripts → [workspace]/temp/debug_scripts/ (temporary - clean after use)
- Working files → [workspace]/temp/working_files/ (temporary - clean after use)
- Source code changes → Appropriate source code directories
- Test scripts → /tests/ directory structure (organized by test type)
- Documentation → Appropriate centralized directories (/project_management/ or /architecture_specifications/)

### CLEANUP REQUIREMENTS
Before marking your work complete, you MUST:
- [ ] Move all artifacts to proper workspace or centralized locations
- [ ] Clean temporary files or move to gitignored temp/ directory
- [ ] Run `git status` to verify no unintended files created
- [ ] Document all file locations in completion report
- [ ] Verify repository root contains only essential files

### VALIDATION REQUIREMENT
Your work will NOT be considered complete until file organization is verified and approved by QAPM.
Include file location documentation in your completion evidence.
```

## Agent Type-Specific Templates

### Problem Scoping Specialist Template

```markdown
## FILE MANAGEMENT REQUIREMENTS - PROBLEM SCOPING SPECIALIST

### PRIMARY OUTPUT LOCATIONS
- Problem scope documentation → [workspace]/01_problem_analysis/scoping_reports/
- Affected systems mapping → [workspace]/01_problem_analysis/affected_systems_map.md
- Root cause analysis → [workspace]/01_problem_analysis/root_cause_analysis/
- Investigation scripts → [workspace]/temp/debug_scripts/ (clean after use)

### EVIDENCE ORGANIZATION REQUIREMENTS
- Comprehensive problem map in designated workspace location
- All investigation artifacts properly documented and located
- No investigation materials left in repository root
- All temporary scripts cleaned or archived in workspace temp/

### SPECIFIC CLEANUP RESPONSIBILITIES
- Remove any debug scripts created during investigation
- Archive investigation materials in appropriate workspace directories
- Document investigation process and findings in designated locations
- Verify no scattered files remain from scoping activities

### HANDOFF REQUIREMENTS
Prepare organized handoff to implementation agents including:
- All findings properly documented in workspace structure
- Clear navigation guide to investigation results
- Clean repository status with no scattered artifacts
```

### Technical Implementation Specialist Template

```markdown
## FILE MANAGEMENT REQUIREMENTS - TECHNICAL IMPLEMENTATION SPECIALIST

### PRIMARY OUTPUT LOCATIONS
- Source code changes → Appropriate source code directories (NOT workspace)
- Implementation documentation → [workspace]/04_evidence_collection/implementation_evidence/
- Test scripts → /tests/ directory structure (organized by test type)
- Debug artifacts → [workspace]/temp/debug_scripts/ (clean after use)
- Configuration changes → Appropriate config directories with documentation

### EVIDENCE ORGANIZATION REQUIREMENTS
- Working implementation with source code in proper directories
- Implementation evidence documented in workspace
- Test coverage documented with test scripts in /tests/ structure
- No temporary files left uncommitted or scattered

### SPECIFIC CLEANUP RESPONSIBILITIES
- Ensure all source code changes are in appropriate directories
- Move implementation documentation to workspace evidence collection
- Organize test scripts in proper /tests/ subdirectories
- Clean debug scripts and temporary files created during development
- Document all changes and their locations

### INTEGRATION REQUIREMENTS
- Coordinate with other agents through workspace coordination logs
- Document integration points in workspace structure
- Provide clear documentation of changes for validation agents
- Maintain clean separation between source code and project documentation
```

### Test Validation Specialist Template

```markdown
## FILE MANAGEMENT REQUIREMENTS - TEST VALIDATION SPECIALIST

### PRIMARY OUTPUT LOCATIONS
- Test results → [workspace]/05_quality_validation/independent_validation/
- Test scripts → /tests/ directory (organized by test type - functional, integration, etc.)
- HTML captures → /tests/evidence/captures/
- Validation reports → [workspace]/05_quality_validation/
- Performance benchmarks → [workspace]/05_quality_validation/performance_benchmarks/

### EVIDENCE ORGANIZATION REQUIREMENTS
- Comprehensive test results in workspace validation directory
- Test artifacts properly organized in /tests/ structure
- No test files scattered in repository root
- Clean repository status after completion

### SPECIFIC CLEANUP RESPONSIBILITIES
- Organize all test scripts in appropriate /tests/ subdirectories
- Move test evidence to designated workspace locations
- Archive HTML captures in proper evidence directories
- Remove temporary test artifacts and debug materials
- Document test coverage and results in workspace structure

### VALIDATION COORDINATION
- Coordinate with implementation agents through workspace logs
- Provide clear validation evidence in organized workspace structure
- Document any issues found and their resolution status
- Prepare organized handoff materials for project completion
```

### Architecture Review Specialist Template

```markdown
## FILE MANAGEMENT REQUIREMENTS - ARCHITECTURE REVIEW SPECIALIST

### PRIMARY OUTPUT LOCATIONS
- Architecture decisions → /architecture_specifications/ (centralized system)
- Design documentation → [workspace]/02_process_design/ OR centralized system
- Review reports → [workspace]/05_quality_validation/
- Impact analysis → [workspace]/01_problem_analysis/
- Design artifacts → Appropriate centralized directories

### EVIDENCE ORGANIZATION REQUIREMENTS
- Architecture decisions properly documented in centralized system
- Design rationale and alternatives analysis in appropriate locations
- Impact assessments organized in workspace or centralized system
- No design documents scattered outside proper locations

### SPECIFIC CLEANUP RESPONSIBILITIES
- Ensure architecture decisions are in centralized /architecture_specifications/
- Move temporary design materials to appropriate permanent locations
- Clean any design artifacts created during review process
- Document review process and decisions in proper locations

### INTEGRATION WITH CENTRALIZED SYSTEMS
- Coordinate with centralized architecture documentation system
- Follow established patterns for architecture decision documentation
- Ensure design decisions are discoverable through centralized navigation
- Update centralized system indexes and navigation as appropriate
```

## Quick Reference Decision Tree Template

Include this decision tree in agent instructions for quick file placement decisions:

```markdown
## QUICK FILE PLACEMENT DECISION TREE

When creating any file, follow this decision process:

1. **Is this file temporary/working?**
   YES → [workspace]/temp/ (with appropriate subdirectory)
   NO → Continue to step 2

2. **Is this file source code?**
   YES → Appropriate source code directory (NOT workspace)
   NO → Continue to step 3

3. **Is this file a test script?**
   YES → /tests/ directory structure (organized by test type)
   NO → Continue to step 4

4. **Is this file project-specific documentation?**
   YES → Appropriate workspace directory
   NO → Continue to step 5

5. **Is this file centralized documentation?**
   YES → /project_management/ or /architecture_specifications/
   NO → ESCALATE TO QAPM - unclear file type

6. **EMERGENCY RULE**: When in doubt, use workspace temp/ and escalate to QAPM
```

## Standard Cleanup Validation Template

```markdown
## COMPLETION CLEANUP VALIDATION

Before reporting completion, verify ALL of the following:

### File Organization Checklist
- [ ] All outputs in designated workspace or appropriate directories
- [ ] No files created in repository root without justification
- [ ] Temporary files cleaned or moved to gitignored directories
- [ ] Debug scripts removed or properly archived
- [ ] Working files cleaned from inappropriate locations

### Git Status Verification
- [ ] Run `git status` and verify only intended changes
- [ ] No untracked files outside appropriate locations
- [ ] No temporary files committed to git
- [ ] Repository root clean (essential files only)

### Documentation Requirements
- [ ] File locations documented in completion report
- [ ] Navigation guide provided for created artifacts
- [ ] Integration points documented for other agents
- [ ] Cleanup process documented for future reference

### Handoff Preparation
- [ ] All materials organized for easy discovery
- [ ] Clear documentation of what was created and where
- [ ] Proper integration with workspace structure
- [ ] No organizational barriers for subsequent agents
```

## Training Integration Template

```markdown
## FILE MANAGEMENT TRAINING REQUIREMENTS

As part of your agent responsibilities, you are required to:

### Repository Navigation Competency
- Understand centralized documentation systems structure
- Know purpose and scope of each major directory
- Use QAPM workspace architecture effectively
- Navigate between project-specific and centralized materials

### File Placement Competency
- Use file placement decision tree systematically
- Recognize when to escalate unclear placement decisions
- Understand temporary vs. permanent file management
- Coordinate with other agents through proper file organization

### Quality Integration Competency
- Include file organization in all deliverables
- Validate organization before claiming completion
- Document file management for subsequent agents
- Maintain clean repository status throughout work

### Escalation Protocols
- Escalate to QAPM when file placement unclear
- Request workspace setup if not provided
- Report organization violations observed
- Coordinate with other agents on file sharing
```

## Agent Coordination File Sharing Template

```markdown
## AGENT COORDINATION THROUGH FILE ORGANIZATION

### Sharing Files Between Agents
- Use workspace coordination_logs/ for agent-to-agent communication
- Document handoff materials in appropriate workspace directories
- Provide navigation guides for materials created for other agents
- Follow workspace structure for discoverable collaboration

### Multi-Agent Project Organization
- Coordinate file creation to avoid conflicts
- Use workspace structure as coordination framework
- Document integration points and shared materials
- Maintain clean separation of agent responsibilities

### Integration Requirements
- Follow workspace template for consistent organization
- Document agent coordination in workspace logs
- Provide clear handoff materials in designated locations
- Maintain workspace integrity throughout multi-agent workflows
```

## Validation and Audit Template

```markdown
## FILE ORGANIZATION AUDIT REQUIREMENTS

### Self-Audit Before Completion
1. **Inventory All Created Files**: List every file created during work
2. **Verify Proper Placement**: Confirm each file is in correct location
3. **Clean Temporary Materials**: Remove or archive temporary files
4. **Document Organization**: Provide navigation guide to created materials

### QAPM Validation Preparation
1. **Organized Evidence**: All deliverables in proper workspace locations
2. **Clean Repository**: No scattered files or temporary materials
3. **Navigation Documentation**: Clear guide to finding all work products
4. **Integration Documentation**: How materials integrate with other agent work

### Quality Standards Compliance
1. **Workspace Compliance**: Follow template structure exactly
2. **Centralized System Integration**: Proper use of centralized directories
3. **Cleanup Completion**: No temporary files or debug materials remaining
4. **Documentation Standards**: Clear, discoverable, well-organized materials
```

## Implementation Notes for QAPMs

### Using These Templates

1. **Copy Appropriate Sections**: Use universal section plus agent-specific template
2. **Customize for Project**: Replace [workspace] and [PROJECT_NAME] with actual values
3. **Add Project Context**: Include specific file organization requirements for the project
4. **Integrate with Mission**: Make file management integral to agent success

### Template Maintenance

1. **Update Based on Experience**: Refine templates based on agent performance
2. **Add New Agent Types**: Create templates for new specialist types as needed
3. **Integration with Training**: Keep templates aligned with QAPM training materials
4. **Quality Improvement**: Enhance templates based on organization effectiveness

### Enforcement Requirements

1. **Mandatory Inclusion**: NEVER spawn agent without file management requirements
2. **Completion Validation**: Verify file organization before accepting agent work
3. **Continuous Monitoring**: Check agent compliance throughout work execution
4. **Documentation Updates**: Keep templates current with organizational improvements

---

**Remember**: These templates are not optional overhead—they are essential quality requirements that prevent repository chaos and enable effective collaboration. Use them consistently for predictable, organized project execution.