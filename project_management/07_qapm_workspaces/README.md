# QAPM Workspaces: Organized Project Management

**Purpose**: Dedicated workspaces for QAPM projects to prevent file scattering and ensure systematic organization  
**Created**: July 30, 2025  
**Usage**: All QAPM projects must use this workspace structure

## Overview

This directory contains individual workspaces for each QAPM project. Each workspace follows a standardized template to ensure consistent organization and prevent the file scattering that previously resulted in 222+ scattered files.

## Workspace Structure Template

Each QAPM project gets a dedicated workspace with this structure:

```
[project_name]/
├── 00_project_overview/          # Project context and navigation
├── 01_problem_analysis/          # Problem scoping and investigation
├── 02_process_design/            # Systematic workflow documentation
├── 03_execution_artifacts/       # Agent coordination and progress tracking
├── 04_evidence_collection/       # Technical and validation evidence
├── 05_quality_validation/        # Independent testing and verification
├── 06_completion_documentation/  # Final solution and handoff docs
└── temp/                         # Gitignored temporary files
```

## Usage Requirements

### MANDATORY for All QAPMs

1. **Project Initiation**: Every QAPM project MUST begin with workspace creation
2. **File Organization**: All project artifacts MUST be stored in appropriate workspace directories
3. **Cleanup Responsibility**: Temporary files MUST be cleaned or archived upon completion
4. **Documentation**: Each workspace MUST include proper README files for navigation

### Creating a New Workspace

1. **Create Directory**: `mkdir [project_name]`
2. **Copy Template**: Use the template structure provided in FILE_MANAGEMENT_PROTOCOLS.md
3. **Initialize README**: Document project context and file organization plan
4. **Configure .gitignore**: Ensure temp/ directory is properly ignored

## File Placement Guidelines

### Use Workspace For:
- Project-specific documentation and reports
- Agent coordination artifacts
- Evidence collection from spawned agents
- Process design and workflow documentation
- Temporary working files (in temp/ directory)

### Do NOT Use Workspace For:
- Source code changes (use appropriate source directories)
- Test scripts (use /tests/ directory structure)
- Centralized documentation (use /project_management/ or /architecture_specifications/)
- Essential configuration files (use repository root with justification)

## Integration with QAPM Methodology

This workspace structure integrates directly with the QAPM systematic problem approach:

1. **Phase 1: Problem Systematization** → Use `01_problem_analysis/`
2. **Phase 2: Process Architecture Design** → Use `02_process_design/`
3. **Phase 3: Agent Orchestration** → Use `03_execution_artifacts/`
4. **Phase 4: Quality Validation** → Use `05_quality_validation/`

## Quality Requirements

### Workspace Compliance Audit
- [ ] Follows template directory structure
- [ ] Contains appropriate README files
- [ ] Has proper .gitignore configuration
- [ ] No files scattered outside designated directories
- [ ] Temporary files properly managed

### Project Completion Requirements
- [ ] All artifacts in proper workspace locations
- [ ] Documentation complete and well-organized
- [ ] Temporary files cleaned or archived
- [ ] Handoff documentation prepared
- [ ] Repository root remains clean

## Current Active Workspaces

*This section will be updated as QAPM projects are created*

## Support and Templates

- **Detailed Protocols**: See `../06_qapm_track/FILE_MANAGEMENT_PROTOCOLS.md`
- **Template Structure**: Available in protocols documentation
- **Training Materials**: Available in QAPM onboarding system
- **Audit Tools**: Automated scripts for organization validation

---

**Remember**: Organization is not overhead—it's a quality enabler that makes complex projects manageable and prevents the repository chaos that hinders development efficiency.