# QAPM Workspace Template

**Purpose**: Template workspace structure for new QAPM projects  
**Usage**: Copy this structure when creating new QAPM workspaces  
**Reference**: See FILE_MANAGEMENT_PROTOCOLS.md for complete guidance

## How to Use This Template

1. **Copy Structure**: Copy this entire directory and rename to your project name
2. **Customize README**: Update this README with your project-specific information
3. **Configure .gitignore**: Ensure temp/ directory is properly ignored
4. **Document Organization Plan**: Specify where different artifact types will be stored

## Project Information Template

**Project Name**: [Your project name here]  
**QAPM Lead**: [Your name]  
**Start Date**: [Project start date]  
**Problem Statement**: [Brief description of the problem being solved]  
**Success Criteria**: [Measurable completion criteria]

## Directory Purpose Guide

### 00_project_overview/
- `README.md` - Project context and navigation guide
- `problem_statement.md` - Initial problem definition and scope
- `success_criteria.md` - Measurable completion criteria
- `stakeholder_analysis.md` - Affected systems and users

### 01_problem_analysis/
- `scoping_reports/` - Problem Scoping Specialist outputs
- `root_cause_analysis/` - Investigation findings and analysis
- `affected_systems_map.md` - System impact documentation
- `constraint_analysis.md` - Technical and process limitations

### 02_process_design/
- `workflow_design.md` - Systematic process documentation
- `agent_coordination_plan.md` - Multi-agent coordination strategy
- `validation_framework.md` - Evidence requirements design
- `quality_gates.md` - Checkpoint and validation requirements

### 03_execution_artifacts/
- `agent_instructions/` - Spawned agent instruction sets
- `coordination_logs/` - Agent handoff documentation
- `progress_tracking/` - Milestone and status updates
- `communication_logs/` - Agent coordination communications

### 04_evidence_collection/
- `implementation_evidence/` - Technical completion proof
- `test_results/` - Validation and testing evidence
- `user_workflow_validation/` - UX and user testing proof
- `integration_testing/` - System integration evidence

### 05_quality_validation/
- `independent_validation/` - Test Validation Specialist results
- `regression_testing/` - Regression prevention evidence
- `performance_benchmarks/` - Performance impact validation
- `security_validation/` - Security impact assessment

### 06_completion_documentation/
- `solution_summary.md` - Final solution documentation
- `lessons_learned.md` - Process improvement insights
- `handoff_documentation.md` - Transition to maintenance
- `archive_plan.md` - Long-term storage and access plan

### temp/ (gitignored)
- `debug_scripts/` - Investigation scripts
- `working_files/` - Session temporary files
- `scratch/` - Ad-hoc temporary content
**NOTE**: This directory should be added to .gitignore

## File Organization Plan

Document your specific plan for organizing files in this workspace:

### Agent Outputs
- Problem Scoping Specialist → `01_problem_analysis/scoping_reports/`
- Technical Specialists → `04_evidence_collection/implementation_evidence/`
- Test Validation Specialist → `05_quality_validation/independent_validation/`

### Evidence Collection
- Implementation proof → `04_evidence_collection/implementation_evidence/`
- Test results → `04_evidence_collection/test_results/`
- User workflow validation → `04_evidence_collection/user_workflow_validation/`

### Temporary Files
- Debug scripts → `temp/debug_scripts/`
- Working files → `temp/working_files/`
- Session artifacts → `temp/scratch/`

## Quality Checklist

Use this checklist to ensure workspace organization compliance:

### Setup Phase
- [ ] Workspace follows template structure
- [ ] Project-specific README created
- [ ] .gitignore configured for temp/ directory
- [ ] File organization plan documented

### During Execution
- [ ] Agent outputs going to designated directories
- [ ] Temporary files contained in temp/ directory
- [ ] No files being created outside workspace
- [ ] Progress tracking updated regularly

### Completion Phase
- [ ] All evidence properly organized
- [ ] Temporary files cleaned or archived
- [ ] Documentation complete and accessible
- [ ] Handoff materials prepared
- [ ] Repository root remains clean

## References

- **Complete Protocols**: `../06_qapm_track/FILE_MANAGEMENT_PROTOCOLS.md`
- **QAPM Methodology**: `../06_qapm_track/QAPM_MASTERY.md`
- **Agent Coordination**: `../06_qapm_track/agent_orchestration/`
- **Quality Standards**: `../06_qapm_track/quality_assurance/`

---

**Remember**: This workspace structure is designed to prevent file scattering and ensure systematic organization. Use it consistently for predictable, manageable project execution.